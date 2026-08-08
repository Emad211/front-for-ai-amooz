from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
from PIL import Image
from pydantic import BaseModel, Field
import requests

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.management.commands.probe_exam_prep_mistral_fidelity_pilot import (
    _base_url,
    _preflight,
    _safe_filename,
    _selected_pages,
)
from apps.classes.services.exam_prep_mistral_fidelity_benchmark import (
    FidelityError,
    find_target_regions,
    padded_pixel_box,
    parse_fidelity_targets,
    summarize_verifier_consensus,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import analyze_ocr_document
from apps.commons.json_utils import extract_json_object


_CALIBRATION_MODELS = ("gpt-5.4-mini", "gemini-3-flash-preview")
_CALIBRATION_TARGETS = (
    "question:65",
    "question:94",
    "solution:57",
    "solution:133",
)


class SingleFidelityReview(BaseModel):
    verdict: str = Field(pattern=r"^(exact|minor_error|major_error|unreadable)$")
    candidate_usable_without_repair: bool
    source_visual_required: bool
    errors: list[FidelityError] = Field(default_factory=list, max_length=24)


def _artifact(prefix: Path, suffix: str) -> Path:
    """Append suffix without treating dots in model names/item ids as file suffixes."""
    return Path(f"{prefix}{suffix}")


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


def _system_prompt() -> str:
    return (
        "You are an OCR fidelity auditor for Persian high-school exam material. "
        "The IMAGE is the only source of truth. There is exactly ONE target item and exactly "
        "ONE source image in this request. Do not solve the problem and do not infer what the "
        "author probably intended. Compare the OCR candidate only with visibly printed content "
        "for the TARGET. Ignore a thin neighboring strip introduced by crop padding. Check "
        "Persian text, digits, decimal marks, signs, units, answer labels, equations/LaTeX, "
        "chemical formulae, omissions, hallucinations, reading order, diagrams, tables, and "
        "whether a source visual must be preserved. Equivalent whitespace/Markdown alone is "
        "not an error. A changed digit, operator, exponent, variable, chemical symbol, answer "
        "option, or meaningful omission is major or critical. Return ONLY one valid JSON object."
    )


def _json_contract() -> str:
    return (
        "Return JSON with exactly these top-level keys and NO item_id: "
        "{\"verdict\":\"exact|minor_error|major_error|unreadable\","
        "\"candidate_usable_without_repair\":true,"
        "\"source_visual_required\":false,"
        "\"errors\":[{"
        "\"category\":\"persian_text|number|formula|option_label|omission|hallucination|visual_dependency|table_or_diagram|reading_order|other\","
        "\"severity\":\"minor|major|critical\","
        "\"candidate_fragment\":\"short fragment\","
        "\"source_reading\":\"short visible correction\","
        "\"note\":\"short reason\"}]}"
    )


def _messages(item: Mapping[str, Any], crop_bytes: bytes) -> list[dict[str, Any]]:
    prompt = (
        _json_contract()
        + f"\nTARGET kind={item['kind']} question_number={item['questionNumber']} "
        f"physical_page={item['physicalPageNumber']}\n"
        "OCR_CANDIDATE_BEGIN\n"
        f"{item['candidateText']}\n"
        "OCR_CANDIDATE_END\nSOURCE_IMAGE_FOLLOWS"
    )
    return [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                part_from_bytes(data=crop_bytes, mime_type="image/png"),
            ],
        },
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


def _parse_single_review(content: str, *, item_id: str) -> dict[str, Any]:
    # Deterministic local extraction tolerates harmless trailing provider junk without a
    # paid repair call. Semantic validation remains strict.
    obj = extract_json_object(content)
    review = SingleFidelityReview.model_validate(obj)
    return {
        "itemId": item_id,
        "verdict": str(review.verdict),
        "candidateUsableWithoutRepair": bool(review.candidate_usable_without_repair),
        "sourceVisualRequired": bool(review.source_visual_required),
        "errors": [
            {
                "category": str(error.category),
                "severity": str(error.severity),
                "candidateFragment": error.candidate_fragment,
                "sourceReading": error.source_reading,
                "note": error.note,
            }
            for error in review.errors
        ],
    }


def _response_meta(root: Mapping[str, Any], *, status_code: int, latency_ms: float) -> dict[str, Any]:
    usage = root.get("usage") if isinstance(root, Mapping) else None
    usage = usage if isinstance(usage, Mapping) else {}
    estimated = root.get("estimated_cost") if isinstance(root, Mapping) else None
    estimated = estimated if isinstance(estimated, Mapping) else {}
    return {
        "statusCode": status_code,
        "latencyMs": latency_ms,
        "responseId": str(root.get("id") or "") if isinstance(root, Mapping) else "",
        "resolvedModel": str(root.get("model") or "") if isinstance(root, Mapping) else "",
        "promptTokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        "completionTokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        "totalTokens": int(usage.get("total_tokens") or 0),
        "estimatedUnit": float(estimated.get("unit") or 0),
        "estimatedIrt": float(estimated.get("irt") or 0),
        "exchangeRate": float(estimated.get("exchange_rate") or 0),
    }


def _review_once(
    *,
    model: str,
    item: Mapping[str, Any],
    crop_bytes: bytes,
    api_key: str,
    timeout: float,
    prefix: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    item_id = str(item["itemId"])
    _artifact(prefix, ".request.safe.json").write_text(
        json.dumps(
            {
                "privateDiagnosticBundle": True,
                "model": model,
                "itemId": item_id,
                "imageCount": 1,
                "responseFormat": "json_object",
                "automaticRetry": False,
                "automaticRepair": False,
                "echoedItemIdRequired": False,
                "endpoint": f"{_base_url()}/chat/completions",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    payload = {
        "model": model,
        "messages": _messages(item, crop_bytes),
        "response_format": {"type": "json_object"},
    }
    started = time.monotonic()
    try:
        response = requests.post(
            f"{_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"provider_transport:{type(exc).__name__}") from exc
    latency_ms = round((time.monotonic() - started) * 1000, 2)
    _artifact(prefix, ".provider.private.json").write_bytes(response.content)

    root: Mapping[str, Any] = {}
    try:
        decoded = response.json()
        if isinstance(decoded, Mapping):
            root = decoded
    except ValueError:
        root = {}
    meta = _response_meta(root, status_code=response.status_code, latency_ms=latency_ms)
    _artifact(prefix, ".response.safe.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not response.ok:
        raise RuntimeError(f"provider_http_{response.status_code}")
    if not root:
        raise RuntimeError("provider_non_json_root")
    try:
        review = _parse_single_review(_provider_content(root), item_id=item_id)
    except Exception as exc:
        raise RuntimeError(f"provider_review_invalid:{type(exc).__name__}") from exc
    return review, meta


def _config(bundle: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "sourceBundleName": bundle.name,
        "sourceBundleBytes": bundle.stat().st_size,
        "models": list(_CALIBRATION_MODELS),
        "targets": list(_CALIBRATION_TARGETS),
        "oneSourceImagePerProviderCall": True,
        "automaticRetry": False,
        "automaticRepair": False,
    }


class Command(BaseCommand):
    help = (
        "Run four single-item OCR fidelity checks through two economical multimodal models. "
        "No retry, no paid repair, and no echoed item id."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--timeout-seconds", type=float, default=600.0)
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Live calibration requires --allow-private-transmission.")
        api_key = (os.getenv("AVALAI_API_KEY") or "").strip()
        if not api_key:
            raise CommandError("AVALAI_API_KEY is required in this PowerShell session.")
        timeout = max(30.0, float(options.get("timeout_seconds") or 600.0))
        bundle = Path(options["bundle"]).expanduser().resolve()
        if not bundle.is_file():
            raise CommandError("--bundle must point to an existing successful ZIP.")
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        resume = bool(options.get("resume"))
        config = _config(bundle)

        if output_dir.exists() and any(output_dir.iterdir()):
            if not resume:
                raise CommandError("Output directory is non-empty; use --resume only for this exact run.")
            try:
                previous = json.loads((output_dir / "calibration-config.safe.json").read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise CommandError("Resume directory has no valid calibration config.") from exc
            if previous != config:
                raise CommandError("Resume directory config does not match this run.")
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "calibration-config.safe.json").write_text(
                json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        preflight = _preflight(models=_CALIBRATION_MODELS, api_key=api_key, timeout=timeout)
        (output_dir / "model-preflight.safe.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if any(not row.get("accessible") for row in preflight):
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(
                "One or more calibration models are inaccessible; no source crop was sent. "
                f"bundle={archive_path}"
            )

        manifest, root, archive = _load_success_bundle(bundle)
        try:
            analysis = analyze_ocr_document(root, original_page_numbers=_selected_pages(manifest))
            targets = parse_fidelity_targets(",".join(_CALIBRATION_TARGETS))
            selected = find_target_regions(analysis, targets)
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
                    box = padded_pixel_box(item["bbox"], width=image.width, height=image.height)
                    crop = image.crop(box)
                    try:
                        crop_path = output_dir / f"{item['itemId']}.png"
                        crop.save(crop_path, format="PNG", optimize=True)
                        crop_bytes = crop_path.read_bytes()
                    finally:
                        crop.close()
                finally:
                    image.close()
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

        (output_dir / "targets.json").write_text(
            json.dumps(public_items, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "candidates.private.json").write_text(
            json.dumps(
                [{k: v for k, v in item.items() if k != "cropBytes"} for item in private_items],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        reviews_by_model: dict[str, list[dict[str, Any]]] = {model: [] for model in _CALIBRATION_MODELS}
        calls_path = output_dir / "provider-calls.safe.json"
        call_meta: list[dict[str, Any]] = []
        if resume and calls_path.is_file():
            try:
                previous_calls = json.loads(calls_path.read_text(encoding="utf-8"))
                if isinstance(previous_calls, list):
                    call_meta = previous_calls
            except (OSError, ValueError, json.JSONDecodeError):
                call_meta = []

        current_model = ""
        current_item = ""
        try:
            for model in _CALIBRATION_MODELS:
                safe_model = _safe_filename(model)
                for item in private_items:
                    current_model = model
                    current_item = str(item["itemId"])
                    review_path = output_dir / f"verifier.{safe_model}.{current_item}.review.private.json"
                    if resume and review_path.is_file():
                        loaded = json.loads(review_path.read_text(encoding="utf-8"))
                        if not isinstance(loaded, Mapping) or loaded.get("itemId") != current_item:
                            raise RuntimeError("resume_review_invalid")
                        reviews_by_model[model].append(dict(loaded))
                        continue
                    prefix = output_dir / f"verifier.{safe_model}.{current_item}"
                    review, meta = _review_once(
                        model=model,
                        item=item,
                        crop_bytes=item["cropBytes"],
                        api_key=api_key,
                        timeout=timeout,
                        prefix=prefix,
                    )
                    call_meta.append({"model": model, "itemId": current_item, **meta})
                    calls_path.write_text(
                        json.dumps(call_meta, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    review_path.write_text(
                        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    reviews_by_model[model].append(review)
        except Exception as exc:
            provider_files = list(output_dir.glob("verifier.*.*.provider.private.json"))
            (output_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "privateDiagnosticBundle": True,
                        "productionPipelineChanged": False,
                        "stage": "single_item_verifier",
                        "errorType": type(exc).__name__,
                        "error": str(exc)[:800],
                        "failedModel": current_model,
                        "failedItemId": current_item,
                        "providerResponseFileCount": len(provider_files),
                        "acceptedReviewCount": sum(len(rows) for rows in reviews_by_model.values()),
                        "automaticRetry": False,
                        "automaticRepair": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(f"Single-item fidelity calibration failed; partial bundle={archive_path}") from exc

        consensus = summarize_verifier_consensus(targets=public_items, reviews_by_model=reviews_by_model)
        (output_dir / "consensus.json").write_text(
            json.dumps(consensus, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        provider_files = list(output_dir.glob("verifier.*.*.provider.private.json"))
        manifest_out = {
            "schemaVersion": 1,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "models": list(_CALIBRATION_MODELS),
            "itemCount": len(private_items),
            "providerResponseFileCount": len(provider_files),
            "acceptedReviewCount": sum(len(rows) for rows in reviews_by_model.values()),
            "expectedProviderCalls": len(_CALIBRATION_MODELS) * len(private_items),
            "oneSourceImagePerProviderCall": True,
            "providerRetryPerCall": 0,
            "structuredRepairBudgetPerCall": 0,
            "echoedItemIdRequired": False,
            "estimatedTotalUnit": round(sum(float(row.get("estimatedUnit") or 0) for row in call_meta), 10),
            "estimatedTotalIrt": round(sum(float(row.get("estimatedIrt") or 0) for row in call_meta), 2),
            "acceptance": {
                "allTargetsResolvedLocally": len(private_items) == len(_CALIBRATION_TARGETS),
                "allReviewsAccepted": sum(len(rows) for rows in reviews_by_model.values()) == len(_CALIBRATION_MODELS) * len(private_items),
                "exactExpectedProviderResponses": len(provider_files) == len(_CALIBRATION_MODELS) * len(private_items),
            },
        }
        manifest_out["acceptance"]["passed"] = all(manifest_out["acceptance"].values())
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Single-item fidelity calibration completed: "
                f"items={len(private_items)}, calls={len(provider_files)}, "
                f"critical={consensus['consensusCriticalCount']}, "
                f"disagreements={consensus['verifierDisagreementCount']}, "
                f"estimated_irt={manifest_out['estimatedTotalIrt']}, bundle={archive_path}"
            )
        )
