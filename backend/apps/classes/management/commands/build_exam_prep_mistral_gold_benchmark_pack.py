from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import shutil
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
from PIL import Image

from apps.classes.services.exam_prep_mistral_fidelity_benchmark import (
    find_target_regions,
    padded_pixel_box,
)
from apps.classes.services.exam_prep_mistral_gold_benchmark import (
    boundary_recovery_questions,
    gold_targets,
    validate_gold_target_spec,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import analyze_ocr_document


def _load_success_bundle(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any], ZipFile]:
    try:
        archive = ZipFile(path)
    except (OSError, BadZipFile) as exc:
        raise CommandError("--bundle must point to a readable successful full-document ZIP.") from exc
    names = set(archive.namelist())
    if "failure.json" in names:
        archive.close()
        raise CommandError("--bundle is a failure bundle.")
    try:
        manifest = json.loads(archive.read("manifest.json"))
        root = json.loads(archive.read("response.raw.json"))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        archive.close()
        raise CommandError("Successful bundle is missing manifest.json or response.raw.json.") from exc
    if not isinstance(manifest, Mapping) or not isinstance(root, Mapping):
        archive.close()
        raise CommandError("Bundle manifest/response roots must be JSON objects.")
    return manifest, root, archive


def _original_pages(manifest: Mapping[str, Any]) -> list[int]:
    raw = manifest.get("selectedOriginalPages")
    if isinstance(raw, list):
        try:
            return [int(value) for value in raw]
        except (TypeError, ValueError):
            return []
    try:
        page_count = int(manifest.get("pageCount") or 0)
    except (TypeError, ValueError):
        page_count = 0
    return list(range(1, page_count + 1)) if page_count else []


def _gold_region_targets():
    """Return the frozen offline gold targets without the paid-probe 40-item cap.

    ``parse_fidelity_targets`` intentionally caps live fidelity probes at 40 to
    bound paid provider work. This builder makes zero provider calls and owns a
    separately validated 48-region frozen spec, so applying that paid-run cap here
    would couple unrelated safety policies and break the offline pack.
    """

    validate_gold_target_spec()
    return gold_targets()


def _annotation_row(*, item: Mapping[str, Any], stratum: str, crop_file: str) -> dict[str, Any]:
    return {
        "itemId": str(item["itemId"]),
        "kind": str(item["kind"]),
        "questionNumber": int(item["questionNumber"]),
        "physicalPageNumber": int(item["physicalPageNumber"]),
        "stratum": stratum,
        "sourceCropFile": crop_file,
        "gold": {
            "transcriptionMarkdown": "",
            "criticalNumbers": [],
            "criticalFormulae": [],
            "answerLabel": None,
            "sourceVisualRequired": None,
            "visualType": "unlabeled",
            "sourceReadable": True,
            "notes": "",
        },
    }


class Command(BaseCommand):
    help = (
        "Build a zero-cost blinded 48-region gold benchmark pack from a successful full-document "
        "Mistral diagnostic bundle. No provider request is made."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)

    def handle(self, *args, **options):
        targets = _gold_region_targets()
        bundle_path = Path(options["bundle"]).expanduser().resolve()
        if not bundle_path.is_file():
            raise CommandError("--bundle must point to an existing successful full-document ZIP.")
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("Output directory must be absent or empty.")
        source_dir = output_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)

        manifest, root, archive = _load_success_bundle(bundle_path)
        try:
            analysis = analyze_ocr_document(root, original_page_numbers=_original_pages(manifest))
            try:
                selected = find_target_regions(analysis, targets)
            except ValueError as exc:
                raise CommandError(f"Gold target resolution failed: {exc}") from exc
            if len(selected) != 48:
                raise CommandError(f"Expected 48 resolved gold regions; got {len(selected)}.")

            stratum_by_id = {target.item_id: target.stratum for target in targets}
            annotations: list[dict[str, Any]] = []
            candidates: list[dict[str, Any]] = []
            public_items: list[dict[str, Any]] = []
            for item in selected:
                item_id = str(item["itemId"])
                page_number = int(item["physicalPageNumber"])
                page_name = f"page-{page_number:03d}.original.png"
                try:
                    page_bytes = archive.read(page_name)
                except KeyError as exc:
                    raise CommandError(f"Bundle is missing {page_name}.") from exc
                with Image.open(BytesIO(page_bytes)) as source:
                    image = source.convert("RGB")
                try:
                    box = padded_pixel_box(
                        item["bbox"], width=image.width, height=image.height, padding_ratio=0.012
                    )
                    crop = image.crop(box)
                    try:
                        crop_file = f"source/{item_id}.png"
                        crop_path = output_dir / crop_file
                        crop.save(crop_path, format="PNG", optimize=True)
                        crop_bytes = crop_path.stat().st_size
                    finally:
                        crop.close()
                finally:
                    image.close()

                annotations.append(
                    _annotation_row(
                        item=item,
                        stratum=stratum_by_id[item_id],
                        crop_file=crop_file,
                    )
                )
                candidates.append(
                    {
                        "itemId": item_id,
                        "kind": item["kind"],
                        "questionNumber": int(item["questionNumber"]),
                        "physicalPageNumber": page_number,
                        "mistralCandidateText": str(item.get("candidateText") or ""),
                        "mistralRegionIssues": list(item.get("regionIssues") or []),
                    }
                )
                public_items.append(
                    {
                        "itemId": item_id,
                        "kind": item["kind"],
                        "questionNumber": int(item["questionNumber"]),
                        "physicalPageNumber": page_number,
                        "stratum": stratum_by_id[item_id],
                        "cropBytes": crop_bytes,
                    }
                )
        finally:
            archive.close()

        annotation_path = output_dir / "gold-annotations.template.private.json"
        annotation_path.write_text(
            json.dumps(annotations, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        candidate_path = output_dir / "mistral-candidates.private.json"
        candidate_path.write_text(
            json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "items.safe.json").write_text(
            json.dumps(public_items, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest_out = {
            "schemaVersion": 1,
            "contentFree": True,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "providerRequestCount": 0,
            "sourceBundleName": bundle_path.name,
            "regionCount": len(public_items),
            "questionRegionCount": sum(row["kind"] == "question" for row in public_items),
            "solutionRegionCount": sum(row["kind"] == "solution" for row in public_items),
            "boundaryRecoveryQuestionNumbers": list(boundary_recovery_questions()),
            "annotationStatus": "empty_template",
            "blinding": {
                "sourcePackExcludesMistralCandidateText": True,
                "candidatePackContainsNoSourceImages": True,
            },
        }
        (output_dir / "manifest.safe.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "README.txt").write_text(
            "AI-AMOOZ OCR GOLD BENCHMARK PACK\n"
            "providerRequestCount=0\n"
            "Annotate source crops BEFORE opening mistral-candidates.private.json.\n"
            "The 48 regions are frozen and mix ordinary plus adversarial material.\n"
            "For source-font corruption such as solution 57, set sourceReadable=false if the crop "
            "itself is not legible and do not invent ground truth.\n",
            encoding="utf-8",
        )

        # Build two archives so annotation can remain genuinely blind.
        source_stage = output_dir / "_source_pack"
        source_stage.mkdir(exist_ok=True)
        shutil.copytree(source_dir, source_stage / "source")
        shutil.copy2(annotation_path, source_stage / annotation_path.name)
        shutil.copy2(output_dir / "items.safe.json", source_stage / "items.safe.json")
        shutil.copy2(output_dir / "manifest.safe.json", source_stage / "manifest.safe.json")
        shutil.copy2(output_dir / "README.txt", source_stage / "README.txt")
        source_zip = shutil.make_archive(
            str(output_dir) + ".source", "zip", root_dir=source_stage
        )
        candidate_stage = output_dir / "_candidate_pack"
        candidate_stage.mkdir(exist_ok=True)
        shutil.copy2(candidate_path, candidate_stage / candidate_path.name)
        shutil.copy2(output_dir / "manifest.safe.json", candidate_stage / "manifest.safe.json")
        candidate_zip = shutil.make_archive(
            str(output_dir) + ".candidates", "zip", root_dir=candidate_stage
        )
        shutil.rmtree(source_stage)
        shutil.rmtree(candidate_stage)

        self.stdout.write(
            self.style.SUCCESS(
                "Gold benchmark pack built: providerRequests=0, regions=48, "
                f"sourcePack={source_zip}, candidatePack={candidate_zip}"
            )
        )
