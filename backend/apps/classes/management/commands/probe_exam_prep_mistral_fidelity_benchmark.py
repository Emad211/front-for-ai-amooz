from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
from PIL import Image
import requests

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.services.exam_prep_mistral_fidelity_benchmark import (
    FidelityBatchReview,
    chunks,
    default_fidelity_target_tokens,
    find_target_regions,
    normalize_review_batch,
    padded_pixel_box,
    parse_fidelity_targets,
    summarize_verifier_consensus,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import analyze_ocr_document
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured


_DEFAULT_MODELS = ("gpt-5.5", "gemini-3.1-pro-preview")
_DEFAULT_AVALAI_BASE_URL = "https://api.avalai.ir/v1"


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_")[:96] or "model"


def _load_success_bundle(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any], ZipFile]:
    try:
        archive = ZipFile(path)
    except (OSError, BadZipFile) as exc:
        raise CommandError("--bundle must be a readable successful diagnostic ZIP.") from exc
    names = set(archive.namelist())
    if "failure.json" in names:
        archive.close()
        raise CommandError("--bundle is a failure bundle, not a successful full-document bundle.")
    try:
        manifest = json.loads(archive.read("manifest.json"))
        root = json.loads(archive.read("response.raw.json"))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        archive.close()
        raise CommandError("Successful bundle is missing valid manifest/response JSON.") from exc
    if not isinstance(manifest, Mapping) or not isinstance(root, Mapping):
        archive.close()
        raise CommandError("Successful bundle manifest/response roots must be objects.")
    return manifest, root, archive


def _selected_pages(manifest: Mapping[str, Any]) -> list[int]:
    values = manifest.get("selectedOriginalPages")
    if not isinstance(values, list):
        try:
            count = int(manifest.get("pageCount") or 0)
        except (TypeError, ValueError):
            count = 0
        return list(range(1, count + 1)) if count > 0 else []
    try:
        return [int(value) for value in values]
    except (TypeError, ValueError):
        return []


def _models(raw: str) -> tuple[str, ...]:
    values: list[str] = []
    for part in str(raw or "").split(","):
        model = part.strip().removeprefix("models/")
        if model and model not in values:
            values.append(model)
    if len(values) < 2:
        raise CommandError("Fidelity benchmark requires at least two distinct verifier models.")
    if len(values) > 3:
        raise CommandError("Fidelity benchmark is capped at three verifier models.")
    return tuple(values)


def _system_prompt() -> str:
    return (
        "You are an OCR fidelity auditor for Persian high-school exam material. "
        "The IMAGE is the source of truth. Do NOT solve the question and do NOT infer "
        "what the author probably intended. Compare the supplied OCR candidate against "
        "only what is visibly present for the TARGET item. The crop can contain a small "
        "amount of the neighboring question/solution because of safety padding; ignore "
        "neighboring material that belongs to another printed question number and do not "
        "penalize the candidate for excluding it. Check Persian words, digits, decimal "
        "marks, signs, units, option labels, equations/LaTeX semantics, chemical formulae, "
        "omissions, hallucinated text, reading order, and whether a diagram/table must "
        "remain a source visual. Harmless whitespace or equivalent Markdown formatting is "
        "not an error. A changed digit, operator, exponent, variable, chemical symbol, "
        "answer option, or omitted meaningful clause is major or critical. Return one "
        "review for every requested item_id."
    )


def _batch_messages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    content: list[Any] = [
        {
            "type": "text",
            "text": (
                "Audit each target below. For errors, quote only the shortest fragment "
                "needed to identify the discrepancy. Do not reproduce the entire source "
                "unless necessary. Use verdict=exact only when the candidate preserves "
                "all semantically meaningful visible text/formulas for the target item."
            ),
        }
    ]
    for item in items:
        content.append(
            {
                "type": "text",
                "text": (
                    f"\nITEM {item['itemId']}\n"
                    f"TARGET kind={item['kind']} question_number={item['questionNumber']} "
                    f"physical_page={item['physicalPageNumber']}\n"
                    "OCR_CANDIDATE_BEGIN\n"
                    f"{item['candidateText']}\n"
                    "OCR_CANDIDATE_END\n"
                    "SOURCE_IMAGE_FOLLOWS"
                ),
            }
        )
        content.append(part_from_bytes(data=item["cropBytes"], mime_type="image/png"))
    return [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": content},
    ]


def _model_preflight(*, models: tuple[str, ...], api_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        try:
            response = requests.get(
                f"https://api.avalai.ir/v1/models/{model}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            rows.append(
                {
                    "model": model,
                    "statusCode": response.status_code,
                    "accessible": bool(response.ok),
                }
            )
        except requests.RequestException as exc:
            rows.append(
                {
                    "model": model,
                    "statusCode": None,
                    "accessible": False,
                    "transportError": type(exc).__name__,
                }
            )
    return rows


class Command(BaseCommand):
    help = (
        "Benchmark Mistral OCR transcription fidelity on difficult source regions using "
        "two independent multimodal verifiers. Diagnostic only; no production writes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument(
            "--targets",
            default=",".join(default_fidelity_target_tokens()),
            help="Comma-separated question:N / solution:N targets.",
        )
        parser.add_argument(
            "--models",
            default=",".join(_DEFAULT_MODELS),
            help="Comma-separated independent vision-capable verifier models.",
        )
        parser.add_argument("--batch-size", type=int, default=3)
        parser.add_argument("--timeout-seconds", type=float, default=600.0)
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Live verifier benchmark requires --allow-private-transmission.")
        api_key = (os.getenv("AVALAI_API_KEY") or "").strip()
        if not api_key:
            raise CommandError("AVALAI_API_KEY is required in this PowerShell session.")
        if not (os.getenv("AVALAI_BASE_URL") or "").strip():
            os.environ["AVALAI_BASE_URL"] = _DEFAULT_AVALAI_BASE_URL

        bundle = Path(options["bundle"]).expanduser().resolve()
        if not bundle.is_file():
            raise CommandError("--bundle must point to an existing successful ZIP.")
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("Output directory must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            targets = parse_fidelity_targets(options.get("targets"))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        models = _models(options.get("models"))
        batch_size = int(options.get("batch_size") or 0)
        if not 1 <= batch_size <= 5:
            raise CommandError("--batch-size must be between 1 and 5.")
        timeout = max(30.0, float(options.get("timeout_seconds") or 600.0))

        preflight = _model_preflight(models=models, api_key=api_key)
        (output_dir / "model-preflight.safe.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        inaccessible = [row for row in preflight if not row.get("accessible")]
        if inaccessible:
            (output_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "privateDiagnosticBundle": True,
                        "productionPipelineChanged": False,
                        "stage": "model_preflight",
                        "models": preflight,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(
                "One or more verifier models are not accessible; no source crop was sent. "
                f"bundle={archive_path}"
            )

        manifest, root, archive = _load_success_bundle(bundle)
        try:
            mapping = _selected_pages(manifest)
            analysis = analyze_ocr_document(root, original_page_numbers=mapping)
            try:
                selected = find_target_regions(analysis, targets)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc

            private_items: list[dict[str, Any]] = []
            public_items: list[dict[str, Any]] = []
            for item in selected:
                page_number = int(item["physicalPageNumber"])
                page_name = f"page-{page_number:03d}.original.png"
                try:
                    page_bytes = archive.read(page_name)
                except KeyError as exc:
                    raise CommandError(f"Bundle is missing {page_name}.") from exc
                from io import BytesIO

                with Image.open(BytesIO(page_bytes)) as source:
                    image = source.convert("RGB")
                try:
                    box = padded_pixel_box(
                        item["bbox"],
                        width=image.width,
                        height=image.height,
                    )
                    crop = image.crop(box)
                    try:
                        crop_path = output_dir / f"{item['itemId']}.png"
                        crop.save(crop_path, format="PNG", optimize=True)
                        crop_bytes = crop_path.read_bytes()
                    finally:
                        crop.close()
                finally:
                    image.close()

                if len(crop_bytes) > 10 * 1024 * 1024:
                    raise CommandError(f"Crop {item['itemId']} exceeds 10 MiB.")
                private_items.append({**item, "cropBytes": crop_bytes})
                public_items.append(
                    {
                        "itemId": item["itemId"],
                        "kind": item["kind"],
                        "questionNumber": item["questionNumber"],
                        "physicalPageNumber": page_number,
                        "bbox": item["bbox"],
                        "regionIssues": item["regionIssues"],
                        "cropFile": f"{item['itemId']}.png",
                        "cropBytes": len(crop_bytes),
                    }
                )
        finally:
            archive.close()

        (output_dir / "candidates.private.json").write_text(
            json.dumps(
                [
                    {
                        key: value
                        for key, value in item.items()
                        if key != "cropBytes"
                    }
                    for item in private_items
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (output_dir / "targets.json").write_text(
            json.dumps(public_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        reviews_by_model: dict[str, list[dict[str, Any]]] = {}
        batch_counts: dict[str, int] = {}
        current_model = ""
        current_batch_ids: list[str] = []
        try:
            for model in models:
                current_model = model
                model_reviews: list[dict[str, Any]] = []
                batch_count = 0
                for batch in chunks(private_items, batch_size):
                    batch_list = list(batch)
                    expected_ids = [str(item["itemId"]) for item in batch_list]
                    current_batch_ids = expected_ids
                    review = generate_structured(
                        schema=FidelityBatchReview,
                        messages=_batch_messages(batch_list),
                        model=model,
                        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
                        timeout=timeout,
                        max_repair=1,
                        json_object_mode=True,
                        strict_json_schema=False,
                        sensitive=True,
                        detail="exam_prep_mistral_fidelity_benchmark",
                        tracking_context={
                            "diagnostic": "mistral_fidelity",
                            "batch_items": len(batch_list),
                        },
                        provider_attempts=1,
                    )
                    try:
                        normalized = normalize_review_batch(
                            review,
                            expected_item_ids=expected_ids,
                        )
                    except ValueError as exc:
                        raise CommandError(f"Verifier {model} returned invalid item mapping: {exc}") from exc
                    model_reviews.extend(normalized)
                    batch_count += 1
                    current_batch_ids = []
                reviews_by_model[model] = model_reviews
                batch_counts[model] = batch_count
                (output_dir / f"verifier.{_safe_filename(model)}.private.json").write_text(
                    json.dumps(model_reviews, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except Exception as exc:
            (output_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "privateDiagnosticBundle": True,
                        "productionPipelineChanged": False,
                        "stage": "verifier",
                        "errorType": type(exc).__name__,
                        "error": str(exc)[:800],
                        "failedModel": current_model,
                        "failedBatchItemIds": current_batch_ids,
                        "modelsCompleted": list(reviews_by_model),
                        "batchCounts": batch_counts,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(
                f"Fidelity verifier benchmark failed; partial bundle={archive_path}"
            ) from exc

        consensus = summarize_verifier_consensus(
            targets=public_items,
            reviews_by_model=reviews_by_model,
        )
        (output_dir / "consensus.json").write_text(
            json.dumps(consensus, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        run_manifest = {
            "schemaVersion": 1,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "sourceBundle": bundle.name,
            "models": list(models),
            "modelPreflight": preflight,
            "llmBaseUrl": (os.getenv("AVALAI_BASE_URL") or "").strip(),
            "itemCount": len(private_items),
            "batchSize": batch_size,
            "batchCounts": batch_counts,
            "providerRetryPerCall": 0,
            "structuredRepairBudgetPerBatch": 1,
            "autoRepairCandidateText": False,
            "consensusFile": "consensus.json",
            "acceptance": {
                "allTargetsResolvedLocally": len(private_items) == len(targets),
                "allModelsCompleted": len(reviews_by_model) == len(models),
                "twoIndependentModels": len(models) >= 2,
            },
        }
        run_manifest["acceptance"]["passed"] = all(run_manifest["acceptance"].values())
        (output_dir / "manifest.json").write_text(
            json.dumps(run_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "README.txt").write_text(
            "PRIVATE OCR FIDELITY BENCHMARK\n"
            "Source crops, OCR candidate text, and verifier details are private.\n"
            "No production record is modified and no verifier output auto-repairs OCR.\n"
            "consensus.json is content-free and safe for architecture analysis.\n",
            encoding="utf-8",
        )
        archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Mistral OCR fidelity benchmark completed: "
                f"items={len(private_items)}, models={len(models)}, "
                f"critical={consensus['consensusCriticalCount']}, "
                f"disagreements={consensus['verifierDisagreementCount']}, "
                f"bundle={archive_path}"
            )
        )
