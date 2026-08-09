from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader

from apps.classes.services import exam_prep_mistral_stage2_core as stage2
from apps.classes.services.exam_prep_mistral_ocr_transport import OCR4DocumentResult
from apps.classes.services.exam_prep_mistral_production import (
    analyze_mistral_document_evidence,
)
from apps.classes.services.exam_prep_mistral_visual_reconcile import (
    VisualPipelineConfig,
    reconcile_mistral_source_visuals,
)
from apps.classes.services.exam_prep_page_records import assemble_page_extractions
from apps.classes.services.exam_prep_page_source import attach_source_regions
from apps.classes.services.exam_prep_question_verifier import rebuild_assembly_quality


class _DiagnosticStore:
    """Mirror private storage names into a portable local diagnostic directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.files: dict[str, str] = {}

    def save(self, name: str, payload: bytes) -> str:
        # Storage keys are POSIX identities even when the replay runs on Windows.
        parts = [part for part in str(name).replace("\\", "/").split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            raise ValueError("Unsafe diagnostic visual storage name.")
        safe = Path(*parts)
        if safe.is_absolute():
            raise ValueError("Unsafe diagnostic visual storage name.")
        target = self.root / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(payload)
        self.files[name] = target.relative_to(self.root).as_posix()
        return name


def _load_bundle_root(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise CommandError("--bundle must point to an existing ZIP bundle.")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            raw_name = next(
                (
                    name
                    for name in names
                    if Path(name).name == "response.raw.json"
                ),
                None,
            )
            if raw_name is None:
                raise CommandError(
                    "Bundle has no merged response.raw.json. Use the successful "
                    "full/chunked OCR bundle, not a failure bundle."
                )
            root = json.loads(archive.read(raw_name))
            manifest_name = next(
                (
                    name
                    for name in names
                    if Path(name).name == "manifest.json"
                ),
                None,
            )
            manifest = (
                json.loads(archive.read(manifest_name))
                if manifest_name is not None
                else {}
            )
    except CommandError:
        raise
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CommandError("The OCR bundle is not a valid successful diagnostic ZIP.") from exc
    if not isinstance(root, dict) or not isinstance(root.get("pages"), list):
        raise CommandError("response.raw.json has no valid pages array.")
    return root, manifest if isinstance(manifest, dict) else {}


def _physical_pages(root: Mapping[str, Any], *, page_count: int) -> tuple[dict[str, Any], ...]:
    output: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw in root.get("pages") or []:
        if not isinstance(raw, Mapping):
            continue
        try:
            index = int(raw.get("index"))
        except (TypeError, ValueError):
            continue
        physical = index + 1
        if not 1 <= physical <= page_count or physical in seen:
            continue
        page = dict(raw)
        page["index"] = physical - 1
        page["sourcePhysicalPage"] = physical
        output.append(page)
        seen.add(physical)
    expected = set(range(1, page_count + 1))
    if seen != expected:
        raise CommandError(
            "OCR bundle does not exactly cover the PDF pages "
            f"(missing={sorted(expected-seen)}, extra={sorted(seen-expected)})."
        )
    output.sort(key=lambda page: int(page["sourcePhysicalPage"]))
    return tuple(output)


def _diagnostic_result(
    *,
    pdf_data: bytes,
    root: Mapping[str, Any],
    page_count: int,
) -> OCR4DocumentResult:
    pages = _physical_pages(root, page_count=page_count)
    model = str(root.get("model") or "mistral-ocr-4-0")
    return OCR4DocumentResult(
        source_sha256=hashlib.sha256(pdf_data).hexdigest(),
        page_count=page_count,
        pages=pages,
        chunks=(),
        resolved_models=(model,) if model else (),
        request_ids=(),
        provider_call_count=0,
        retry_count=0,
        checkpoint_reuse_count=0,
        estimated_cost_unit=Decimal("0"),
        estimated_cost_irt=Decimal("0"),
        latency_ms=0.0,
    )


def _question_visual_summary(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    output: list[dict[str, Any]] = []
    for question in questions or []:
        if not isinstance(question, Mapping):
            continue
        visuals = [
            item
            for item in (question.get("visuals") or [])
            if isinstance(item, Mapping)
            and str(item.get("id") or "").startswith("inline-mistral-v1-")
        ]
        if not visuals:
            continue
        try:
            number = int(question.get("source_question_number") or 0)
        except (TypeError, ValueError):
            number = 0
        output.append(
            {
                "questionNumber": number,
                "sourcePages": list(question.get("source_pages") or []),
                "issues": list(question.get("issues") or []),
                "visualSourceContract": question.get("visualSourceContract"),
                "visuals": [
                    {
                        "id": item.get("id"),
                        "role": item.get("role"),
                        "optionLabel": item.get("optionLabel"),
                        "sourcePage": item.get("sourcePage"),
                        "sourceBBox": item.get("sourceBBox"),
                        "storagePath": item.get("storagePath"),
                        "visualMode": item.get("visualMode"),
                        "sourceKinds": item.get("sourceKinds"),
                        "componentIds": item.get("componentIds"),
                        "groupedOptionLabels": item.get("groupedOptionLabels"),
                        "reviewOnly": item.get("reviewOnly"),
                        "sanity": item.get("sanity"),
                    }
                    for item in visuals
                ],
            }
        )
    return output


class Command(BaseCommand):
    help = (
        "Replay the source-precise Stage-3 visual pipeline locally against an "
        "existing successful Mistral OCR bundle. Makes zero provider calls."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--title", default="Stage 3 visual replay")
        parser.add_argument("--detection-dpi", type=int, default=150)
        parser.add_argument("--crop-dpi", type=int, default=260)

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"]).expanduser().resolve()
        bundle_path = Path(options["bundle"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to an existing PDF file.")
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("--output-dir must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            pdf_data = pdf_path.read_bytes()
            page_count = len(PdfReader(str(pdf_path)).pages)
        except Exception as exc:
            raise CommandError("The supplied PDF cannot be opened.") from exc
        root, manifest = _load_bundle_root(bundle_path)
        bundle_page_count = int(
            manifest.get("originalPdfPageCount")
            or manifest.get("pageCount")
            or len(root.get("pages") or [])
            or 0
        )
        if bundle_page_count and bundle_page_count != page_count:
            raise CommandError(
                f"PDF/bundle page count mismatch ({page_count} != {bundle_page_count})."
            )

        result = _diagnostic_result(
            pdf_data=pdf_data,
            root=root,
            page_count=page_count,
        )
        replay_root = dict(root)
        replay_root["pages"] = [dict(page) for page in result.pages]
        evidence = analyze_mistral_document_evidence(
            replay_root,
            original_page_numbers=list(range(1, page_count + 1)),
        )

        page_extractions = stage2._build_page_extractions(
            result=result,
            evidence=evidence,
            recovered_targets={},
        )
        assembled = assemble_page_extractions(
            page_extractions,
            title=str(options["title"] or "Stage 3 visual replay"),
        )
        assembled = attach_source_regions(assembled, pages=page_extractions)
        assembled = rebuild_assembly_quality(assembled)

        store_root = output_dir / "stored"
        store = _DiagnosticStore(store_root)
        config = VisualPipelineConfig(
            detection_dpi=max(96, min(240, int(options["detection_dpi"]))),
            crop_dpi=max(150, min(450, int(options["crop_dpi"]))),
        )
        updated, stats, audit = reconcile_mistral_source_visuals(
            assembled,
            pdf_data=pdf_data,
            ocr_pages=result.pages,
            layout=evidence.layout,
            source_sha256=result.source_sha256,
            store=store,
            config=config,
        )

        projection_path = output_dir / "projection.stage3.json"
        audit_path = output_dir / "visual.audit.json"
        summary_path = output_dir / "visual.questions.json"
        mapping_path = output_dir / "stored-files.json"
        projection_path.write_text(
            json.dumps(updated.projection, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary_path.write_text(
            json.dumps(
                _question_visual_summary(updated.projection),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        mapping_path.write_text(
            json.dumps(store.files, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 2,
                    "privateDiagnosticBundle": True,
                    "productionPipelineChanged": False,
                    "providerRequests": 0,
                    "sourcePdfSha256": result.source_sha256,
                    "pageCount": page_count,
                    "inputBundle": bundle_path.name,
                    "stats": stats,
                    "visualQuestionCount": len(_question_visual_summary(updated.projection)),
                    "files": {
                        "projection": projection_path.name,
                        "audit": audit_path.name,
                        "questions": summary_path.name,
                        "storedMapping": mapping_path.name,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        archive = shutil.make_archive(
            str(output_dir),
            "zip",
            root_dir=output_dir,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Stage 3 visual replay completed: "
                f"providerRequests=0, pages={page_count}, "
                f"assets={int(stats.get('assetsAttached', 0))}, "
                f"reviewOnly={int(stats.get('reviewOnlyAssets', 0))}, "
                f"unresolved={int(stats.get('unresolvedRegions', 0))}, "
                f"bundle={archive}"
            )
        )
