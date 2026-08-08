from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
from PIL import Image
import requests

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.services.exam_prep_mistral_fidelity_benchmark import (
    FidelityBatchReview,
    chunks,
    find_target_regions,
    normalize_review_batch,
    padded_pixel_box,
    parse_fidelity_targets,
    summarize_verifier_consensus,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import analyze_ocr_document


_PILOT_MODELS = (
    "gpt-5.4-mini",
    "gemini-3-flash-preview",
)

_PILOT_TARGETS = (
    "question:65",
    "question:94",
    "question:120",
    "solution:50",
    "solution:57",
    "solution:133",
)

_DEFAULT_AVALAI_BASE_URL = "https://api.avalai.ir/v1"


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_")[:96] or "model"


def _base_url() -> str:
    value = (os.getenv("AVALAI_BASE_URL") or _DEFAULT_AVALAI_BASE_URL).strip().rstrip("/")
    if not re.search(r"/v\d+$", value):
        value += "/v1"
    return value


def _selected_pages(manifest: Mapping[str, Any]) -> list[int]:
    values = manifest.get("selectedOriginalPages")
    if isinstance(values, list):
        try:
            return [int(value) for value in values]
        except (TypeError, ValueError):
            return []
    try:
        count = int(manifest.get("pageCount") or 0)
    except (TypeError, ValueError):
        count = 0
    return list(range(1, count + 1)) if count > 0 else []


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


def _preflight(*, models: tuple[str, ...], api_key: str, timeout: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        try:
            response = requests.get(
                f"{_base_url()}/models/{model}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=min(30.0, timeout),
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


def _system_prompt() -> str:
    return (
        "You are an OCR fidelity auditor for Persian high-school exam material. "
        "The IMAGE is the only source of truth. Do not solve the problem and do not infer "
        "what the author intended. Compare the OCR candidate only with the visibly printed "
        "TARGET item. A crop may contain a little neighboring material; ignore text belonging "
        "to another printed question number. Check Persian text, digits, decimal marks, signs, "
        "units, option labels, equations and LaTeX semantics, chemical formulae, omissions, "
        "hallucinations, reading order, diagrams, tables, and whether a source visual is needed. "
        "Whitespace or equivalent Markdown alone is not an error. A changed digit, operator, "
        "exponent, variable, chemical symbol, answer option, or meaningful omission is major "
        "or critical. Return ONLY one valid JSON object and no Markdown fences."
    )


def _json_contract() -> str:
    return (
        "The JSON object must have exactly this top-level shape: "
        "{\"items\":[{\"item_id\":\"q-001\",\"verdict\":\"exact|minor_error|major_error|unreadable\","
        "\"candidate_usable_without_repair\":true,\"source_visual_required\":false,\"errors\":[{"
        "\"category\":\"persian_text|number|formula|option_label|omission|hallucination|visual_dependency|table_or_diagram|reading_order|other\","
        "\"severity\":\"minor|major|critical\",\"candidate_fragment\":\"short fragment\","
        "\"source_reading\":\"short visible correction\",\"note\":\"short reason\"}]}]}. "
        "Return exactly one items entry for every requested item_id and no extra item_id."
    )


def _batch_messages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    content: list[Any] = [
        {
            "type": "text",
            "text": (
                _json_contract()
                + " Audit every target below. Use verdict=exact only when all semantically "
                "meaningful visible text/formulas for that TARGET are preserved. For an error, "
                "quote only the shortest fragment necessary to identify it."
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


def _provider_content(root: Mapping[str, Any]) -> str:
    choices = root.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        raise ValueError("Provider response has no first choice object.")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Provider response first choice has no message object.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Provider response message content is empty or non-text.")
    return content.strip()


def _review_batch_once(
    *,
    model: str,
    items: list[dict[str, Any]],
    api_key: str,
    timeout: float,
    raw_path: Path,
    safe_meta_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected_ids = [str(item["itemId"]) for item in items]
    payload = {
        "model": model,
        "messages": _batch_messages(items),
        "response_format": {"type": "json_object"},
    }
    safe_meta_path.write_text(
        json.dumps(
            {
                "privateDiagnosticBundle": True,
                "model": model,
                "itemIds": expected_ids,
                "responseFormat": "json_object",
                "automaticRetry": False,
                "automaticRepair": False,
                "imageCount": len(items),
                "endpoint": f"{_base_url()}/chat/completions",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    started = time.monotonic()
    try:
        response = requests.post(
            f"{_base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"provider_transport:{type(exc).__name__}") from exc
    latency_ms = round((time.monotonic() - started) * 1000, 2)
    raw_path.write_bytes(response.content)
    if not response.ok:
        raise RuntimeError(f"provider_http_{response.status_code}")
    try:
        root = response.json()
    except ValueError as exc:
        raise RuntimeError("provider_non_json_root") from exc
    if not isinstance(root, Mapping):
        raise RuntimeError("provider_root_not_object")
    try:
        content = _provider_content(root)
        obj = json.loads(content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("provider_content_not_json_object") from exc
    try:
        review = FidelityBatchReview.model_validate(obj)
        normalized = normalize_review_batch(review, expected_item_ids=expected_ids)
    except Exception as exc:
        raise RuntimeError(f"provider_json_contract_invalid:{type(exc).__name__}") from exc
    usage = root.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    meta = {
        "model": model,
        "itemIds": expected_ids,
        "latencyMs": latency_ms,
        "responseId": str(root.get("id") or ""),
        "inputTokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        "outputTokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        "totalTokens": int(usage.get("total_tokens") or 0),
    }
    return normalized, meta


class Command(BaseCommand):
    help = (
        "Run the low-cost six-region OCR fidelity calibration using two strong economical "
        "multimodal models. Uses direct JSON-object calls with no retry or repair."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--batch-size", type=int, default=3)
        parser.add_argument("--timeout-seconds", type=float, default=600.0)
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Live verifier pilot requires --allow-private-transmission.")
        api_key = (os.getenv("AVALAI_API_KEY") or "").strip()
        if not api_key:
            raise CommandError("AVALAI_API_KEY is required in this PowerShell session.")
        batch_size = int(options.get("batch_size") or 0)
        if not 1 <= batch_size <= 3:
            raise CommandError("Pilot --batch-size must be between 1 and 3.")
        timeout = max(30.0, float(options.get("timeout_seconds") or 600.0))

        bundle = Path(options["bundle"]).expanduser().resolve()
        if not bundle.is_file():
            raise CommandError("--bundle must point to an existing successful ZIP.")
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("Output directory must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(
            "Economical fidelity pilot v2: "
            f"models={','.join(_PILOT_MODELS)}, targets={len(_PILOT_TARGETS)}, "
            f"batch_size={batch_size}, retry=0, repair=0"
        )

        preflight = _preflight(models=_PILOT_MODELS, api_key=api_key, timeout=timeout)
        (output_dir / "model-preflight.safe.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if any(not row.get("accessible") for row in preflight):
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
                "One or more pilot models are inaccessible; no source crop was sent. "
                f"bundle={archive_path}"
            )

        manifest, root, archive = _load_success_bundle(bundle)
        try:
            mapping = _selected_pages(manifest)
            analysis = analyze_ocr_document(root, original_page_numbers=mapping)
            targets = parse_fidelity_targets(",".join(_PILOT_TARGETS))
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
                [{key: value for key, value in item.items() if key != "cropBytes"} for item in private_items],
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
        call_meta: list[dict[str, Any]] = []
        current_model = ""
        current_batch_ids: list[str] = []
        try:
            for model in _PILOT_MODELS:
                current_model = model
                model_reviews: list[dict[str, Any]] = []
                batch_count = 0
                for batch_number, batch in enumerate(chunks(private_items, batch_size), start=1):
                    batch_items = list(batch)
                    current_batch_ids = [str(item["itemId"]) for item in batch_items]
                    prefix = f"verifier.{_safe_filename(model)}.batch-{batch_number:02d}"
                    normalized, meta = _review_batch_once(
                        model=model,
                        items=batch_items,
                        api_key=api_key,
                        timeout=timeout,
                        raw_path=output_dir / f"{prefix}.provider.private.json",
                        safe_meta_path=output_dir / f"{prefix}.request.safe.json",
                    )
                    model_reviews.extend(normalized)
                    batch_count += 1
                    call_meta.append({"batchNumber": batch_number, **meta})
                    (output_dir / f"verifier.{_safe_filename(model)}.partial.private.json").write_text(
                        json.dumps(model_reviews, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
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
                        "completedProviderCalls": len(call_meta),
                        "automaticRetry": False,
                        "automaticRepair": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(
                f"Fidelity verifier pilot failed; partial bundle={archive_path}"
            ) from exc

        consensus = summarize_verifier_consensus(
            targets=public_items,
            reviews_by_model=reviews_by_model,
        )
        (output_dir / "consensus.json").write_text(
            json.dumps(consensus, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "provider-calls.safe.json").write_text(
            json.dumps(call_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        run_manifest = {
            "schemaVersion": 2,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "sourceBundle": bundle.name,
            "models": list(_PILOT_MODELS),
            "modelPreflight": preflight,
            "itemCount": len(private_items),
            "batchSize": batch_size,
            "batchCounts": batch_counts,
            "providerCallCount": len(call_meta),
            "providerRetryPerCall": 0,
            "structuredRepairBudgetPerBatch": 0,
            "directJsonObjectMode": True,
            "autoRepairCandidateText": False,
            "consensusFile": "consensus.json",
            "acceptance": {
                "allTargetsResolvedLocally": len(private_items) == len(_PILOT_TARGETS),
                "allModelsCompleted": len(reviews_by_model) == len(_PILOT_MODELS),
                "exactExpectedProviderCalls": len(call_meta) == len(_PILOT_MODELS) * len(list(chunks(private_items, batch_size))),
            },
        }
        run_manifest["acceptance"]["passed"] = all(run_manifest["acceptance"].values())
        (output_dir / "manifest.json").write_text(
            json.dumps(run_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "README.txt").write_text(
            "PRIVATE LOW-COST OCR FIDELITY PILOT V2\n"
            "Direct JSON-object verifier calls; no automatic retry or repair.\n"
            "Source crops, OCR candidate text, and provider responses are private.\n"
            "No production record is modified and no verifier output auto-repairs OCR.\n",
            encoding="utf-8",
        )
        archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Mistral OCR fidelity pilot v2 completed: "
                f"items={len(private_items)}, calls={len(call_meta)}, "
                f"critical={consensus['consensusCriticalCount']}, "
                f"disagreements={consensus['verifierDisagreementCount']}, "
                f"bundle={archive_path}"
            )
        )
