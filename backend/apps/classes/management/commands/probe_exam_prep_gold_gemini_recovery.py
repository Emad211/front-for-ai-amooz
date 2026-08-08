from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
import requests

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.services.exam_prep_mistral_direct_transcription import (
    DirectTranscription,
    normalize_direct_transcription,
)
from apps.classes.services.exam_prep_mistral_gold_baseline import (
    GOLD_BASELINE_PASS_IDS,
    GOLD_GEMINI_RECOVERY_IDS,
    GOLD_LOCAL_VISUAL_REPAIR_IDS,
    validate_gold_baseline_partition,
)
from apps.commons.json_utils import extract_json_object


_MODEL = "gemini-3-flash-preview"
_DEFAULT_BASE_URL = "https://api.avalai.ir/v1"
_USER_LOOKUP_URL = "https://api.avalai.ir/user/v1/transactions/lookup"


def _base_url() -> str:
    value = (os.getenv("AVALAI_BASE_URL") or _DEFAULT_BASE_URL).strip().rstrip("/")
    if not re.search(r"/v\d+$", value):
        value += "/v1"
    return value


def _minimal_extra_body() -> dict[str, Any]:
    # AvalAI provider-specific parameters are passed through extra_body. This exact
    # shape was already accepted by AvalAI in the two-item minimal-thinking probe.
    return {
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": "minimal",
            }
        }
    }


def _system_prompt() -> str:
    return (
        "You are a source-faithful transcription engine for Persian high-school exam material. "
        "There is exactly ONE target and exactly ONE source image. The IMAGE is the only source "
        "of truth. The previous OCR candidate is intentionally hidden from you. Transcribe; do "
        "not solve, explain, normalize, or repair from subject knowledge. Preserve visible Persian "
        "text, digits, decimal marks, signs, units, option labels, Latin letters, and equations. "
        "Use Markdown and LaTeX for linear text/formulas. If a diagram, graph, circuit, chemical "
        "structure, table, or spatial construction carries information that should remain an image, "
        "do not invent a textual replacement; set source_visual_required=true and choose the closest "
        "visual_type. Still transcribe readable labels/captions and surrounding prose. Some source "
        "solution crops contain square/tofu glyphs caused by the original PDF/font. Do NOT guess or "
        "reconstruct those unreadable source glyphs from context; set transcription_uncertain=true "
        "and include only short uncertain fragments. Ignore a thin neighboring strip introduced by "
        "crop padding. Return ONLY one valid JSON object with no Markdown fence or surrounding prose."
    )


def _json_contract(*, item_id: str, meta: Mapping[str, Any]) -> str:
    return (
        "Return JSON with exactly these top-level keys: "
        '{"transcription_markdown":"full faithful readable target transcription",'
        '"source_visual_required":true,'
        '"visual_type":"none|diagram|graph|chemical_structure|table|spatial_layout|other",'
        '"transcription_uncertain":false,'
        '"uncertain_fragments":[]}. '
        "JSON string escaping must be valid, including LaTeX backslashes. "
        f"TARGET item_id={item_id} kind={meta.get('kind')} "
        f"question_number={meta.get('questionNumber')} physical_page={meta.get('physicalPageNumber')}."
    )


def _messages(*, item_id: str, meta: Mapping[str, Any], crop_bytes: bytes) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _json_contract(item_id=item_id, meta=meta)},
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


def _parse_transcript(content: str) -> dict[str, Any]:
    obj = extract_json_object(content)
    parsed = DirectTranscription.model_validate(obj)
    return normalize_direct_transcription(parsed)


def _reasoning_tokens(root: Mapping[str, Any]) -> int:
    usage = root.get("usage") if isinstance(root, Mapping) else None
    usage = usage if isinstance(usage, Mapping) else {}
    details = usage.get("completion_tokens_details")
    if not isinstance(details, Mapping):
        return 0
    try:
        return int(details.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _response_meta(
    root: Mapping[str, Any],
    *,
    status_code: int,
    latency_ms: float,
    request_id: str,
) -> dict[str, Any]:
    usage = root.get("usage") if isinstance(root, Mapping) else None
    usage = usage if isinstance(usage, Mapping) else {}
    estimated = root.get("estimated_cost") if isinstance(root, Mapping) else None
    estimated = estimated if isinstance(estimated, Mapping) else {}
    return {
        "statusCode": int(status_code),
        "latencyMs": latency_ms,
        "xRequestId": request_id,
        "responseId": str(root.get("id") or "") if isinstance(root, Mapping) else "",
        "resolvedModel": str(root.get("model") or "") if isinstance(root, Mapping) else "",
        "promptTokens": int(usage.get("prompt_tokens") or 0),
        "completionTokens": int(usage.get("completion_tokens") or 0),
        "reasoningTokens": _reasoning_tokens(root),
        "totalTokens": int(usage.get("total_tokens") or 0),
        "estimatedUnit": float(estimated.get("unit") or 0),
        "estimatedIrt": float(estimated.get("irt") or 0),
    }


def _load_source_pack(path: Path) -> tuple[dict[str, Any], dict[str, Mapping[str, Any]], ZipFile]:
    try:
        archive = ZipFile(path)
    except (OSError, BadZipFile) as exc:
        raise CommandError("--source-pack must be a readable blinded gold source ZIP.") from exc
    names = set(archive.namelist())
    try:
        manifest = json.loads(archive.read("manifest.safe.json"))
        items = json.loads(archive.read("items.safe.json"))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        archive.close()
        raise CommandError("Gold source pack is missing valid manifest/items JSON.") from exc
    if not isinstance(manifest, Mapping):
        archive.close()
        raise CommandError("Gold source manifest must be an object.")
    blinding = manifest.get("blinding") if isinstance(manifest.get("blinding"), Mapping) else {}
    if int(manifest.get("providerRequestCount") or -1) != 0 or not blinding.get("sourcePackExcludesMistralCandidateText"):
        archive.close()
        raise CommandError("Source pack does not satisfy the blinded zero-provider contract.")
    item_map = {
        str(row.get("itemId")): row
        for row in items
        if isinstance(row, Mapping) and row.get("itemId")
    }
    missing = [
        item_id
        for item_id in GOLD_GEMINI_RECOVERY_IDS
        if item_id not in item_map or f"source/{item_id}.png" not in names
    ]
    if missing:
        archive.close()
        raise CommandError(f"Gold source pack is missing recovery items: {missing}")
    return dict(manifest), item_map, archive


def _exact_cost_summary(root: Any) -> dict[str, Any]:
    if not isinstance(root, Mapping):
        return {"found": 0, "totalUnit": 0.0, "totalPaidIrt": 0.0}
    transactions = root.get("transactions")
    transactions = transactions if isinstance(transactions, list) else []
    total_unit = 0.0
    total_irt = 0.0
    for tx in transactions:
        if not isinstance(tx, Mapping):
            continue
        cost = tx.get("cost")
        if not isinstance(cost, Mapping):
            continue
        try:
            total_unit += float(cost.get("unit") or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_irt += float(cost.get("paid_irt") or 0)
        except (TypeError, ValueError):
            pass
    summary = root.get("summary") if isinstance(root.get("summary"), Mapping) else {}
    try:
        found = int(summary.get("found") or len(transactions))
    except (TypeError, ValueError):
        found = len(transactions)
    return {
        "found": found,
        "totalUnit": round(total_unit, 8),
        "totalPaidIrt": round(total_irt, 2),
    }


class Command(BaseCommand):
    help = (
        "Test-3 gold recovery: independently transcribe the 40 frozen Mistral OCR4 failures "
        "with Gemini 3 Flash thinking=minimal. One image per call, no retry, no paid repair."
    )

    def add_arguments(self, parser):
        parser.add_argument("--source-pack", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--timeout-seconds", type=float, default=300.0)
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--exact-cost-wait-seconds", type=float, default=30.0)
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        validate_gold_baseline_partition()
        if not options.get("allow_private_transmission"):
            raise CommandError("Live gold recovery requires --allow-private-transmission.")
        api_key = (os.getenv("AVALAI_API_KEY") or "").strip()
        if not api_key:
            raise CommandError("AVALAI_API_KEY is required in this PowerShell session.")
        source_pack = Path(options["source_pack"]).expanduser().resolve()
        if not source_pack.is_file():
            raise CommandError("--source-pack must point to the blinded gold source ZIP.")
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        resume = bool(options.get("resume"))
        if output_dir.exists() and any(output_dir.iterdir()) and not resume:
            raise CommandError("Output directory is non-empty; use --resume only for this exact run.")
        output_dir.mkdir(parents=True, exist_ok=True)
        timeout = max(30.0, float(options.get("timeout_seconds") or 300.0))
        cost_wait = min(30.0, max(0.0, float(options.get("exact_cost_wait_seconds") or 30.0)))

        config = {
            "schemaVersion": 1,
            "model": _MODEL,
            "thinkingLevel": "minimal",
            "sourcePackName": source_pack.name,
            "recoveryItemIds": list(GOLD_GEMINI_RECOVERY_IDS),
            "localVisualRepairItemIds": list(GOLD_LOCAL_VISUAL_REPAIR_IDS),
            "baselinePassItemIds": list(GOLD_BASELINE_PASS_IDS),
            "candidateMistralShown": False,
            "oneSourceImagePerProviderCall": True,
            "automaticRetry": False,
            "automaticPaidRepair": False,
        }
        config_path = output_dir / "recovery-config.safe.json"
        if resume:
            try:
                prior = json.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise CommandError("Resume directory has no valid recovery config.") from exc
            if prior != config:
                raise CommandError("Resume directory config does not match this recovery run.")
        else:
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            preflight_response = requests.get(
                f"{_base_url()}/models/{_MODEL}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=min(timeout, 30.0),
            )
        except requests.RequestException as exc:
            raise CommandError("Gemini preflight transport failed; no source crop was sent.") from exc
        preflight = {
            "model": _MODEL,
            "statusCode": preflight_response.status_code,
            "accessible": bool(preflight_response.ok),
        }
        (output_dir / "model-preflight.safe.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not preflight_response.ok:
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(f"Gemini model is inaccessible; no source crop was sent. bundle={archive_path}")

        _manifest, item_map, source_archive = _load_source_pack(source_pack)
        rows: list[dict[str, Any]] = []
        call_meta: list[dict[str, Any]] = []
        current_item_id = ""
        try:
            for item_id in GOLD_GEMINI_RECOVERY_IDS:
                current_item_id = item_id
                transcript_path = output_dir / f"{item_id}.transcript.private.json"
                meta_path = output_dir / f"{item_id}.response.safe.json"
                if resume and transcript_path.is_file() and meta_path.is_file():
                    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    rows.append(transcript)
                    call_meta.append(meta)
                    continue

                meta_source = item_map[item_id]
                crop_bytes = source_archive.read(f"source/{item_id}.png")
                (output_dir / f"{item_id}.png").write_bytes(crop_bytes)
                payload = {
                    "model": _MODEL,
                    "messages": _messages(item_id=item_id, meta=meta_source, crop_bytes=crop_bytes),
                    "response_format": {"type": "json_object"},
                    "extra_body": _minimal_extra_body(),
                }
                (output_dir / f"{item_id}.request.safe.json").write_text(
                    json.dumps(
                        {
                            "model": _MODEL,
                            "itemId": item_id,
                            "imageCount": 1,
                            "thinkingLevel": "minimal",
                            "candidateMistralShown": False,
                            "automaticRetry": False,
                            "automaticPaidRepair": False,
                            "endpoint": f"{_base_url()}/chat/completions",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                started = time.monotonic()
                try:
                    provider = requests.post(
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
                (output_dir / f"{item_id}.provider.private.json").write_bytes(provider.content)
                request_id = str(provider.headers.get("x-request-id") or "").strip()
                try:
                    root = provider.json()
                except ValueError as exc:
                    raise RuntimeError("provider_non_json_root") from exc
                if not isinstance(root, Mapping):
                    raise RuntimeError("provider_root_not_object")
                meta = {
                    "model": _MODEL,
                    "itemId": item_id,
                    **_response_meta(
                        root,
                        status_code=provider.status_code,
                        latency_ms=latency_ms,
                        request_id=request_id,
                    ),
                }
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                if not provider.ok:
                    raise RuntimeError(f"provider_http_{provider.status_code}")
                if not request_id:
                    raise RuntimeError("provider_missing_x_request_id")
                try:
                    normalized = _parse_transcript(_provider_content(root))
                except Exception as exc:
                    raise RuntimeError(f"provider_transcription_invalid:{type(exc).__name__}") from exc
                transcript = {"itemId": item_id, **normalized}
                transcript_path.write_text(
                    json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                rows.append(transcript)
                call_meta.append(meta)
        except Exception as exc:
            (output_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "privateDiagnosticBundle": True,
                        "stage": "gold_gemini_recovery",
                        "errorType": type(exc).__name__,
                        "error": str(exc)[:700],
                        "failedItemId": current_item_id,
                        "completedOrResumedItems": len(rows),
                        "automaticRetry": False,
                        "automaticPaidRepair": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(f"Gold Gemini recovery failed; partial bundle={archive_path}") from exc
        finally:
            source_archive.close()

        request_ids = [str(row.get("xRequestId") or "") for row in call_meta if str(row.get("xRequestId") or "")]
        exact_cost_result: Any = None
        exact_cost_error = ""
        if len(request_ids) == len(GOLD_GEMINI_RECOVERY_IDS):
            if cost_wait:
                time.sleep(cost_wait)
            try:
                exact_response = requests.post(
                    _USER_LOOKUP_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"transaction_ids": request_ids},
                    timeout=60,
                )
                (output_dir / "exact-cost-lookup.private.json").write_bytes(exact_response.content)
                if exact_response.ok:
                    exact_cost_result = exact_response.json()
                else:
                    exact_cost_error = f"user_api_http_{exact_response.status_code}"
            except Exception as exc:
                exact_cost_error = type(exc).__name__
        else:
            exact_cost_error = "missing_request_ids"

        exact_summary = _exact_cost_summary(exact_cost_result)
        estimated_unit = round(sum(float(row.get("estimatedUnit") or 0) for row in call_meta), 8)
        estimated_irt = round(sum(float(row.get("estimatedIrt") or 0) for row in call_meta), 2)
        reasoning_tokens = sum(int(row.get("reasoningTokens") or 0) for row in call_meta)
        (output_dir / "transcripts.private.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "provider-calls.safe.json").write_text(
            json.dumps(call_meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest = {
            "schemaVersion": 1,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "model": _MODEL,
            "thinkingLevel": "minimal",
            "itemCount": len(GOLD_GEMINI_RECOVERY_IDS),
            "providerCallCount": len(call_meta),
            "providerRetryPerCall": 0,
            "paidRepairBudgetPerCall": 0,
            "candidateMistralShown": False,
            "oneSourceImagePerProviderCall": True,
            "reasoningTokens": reasoning_tokens,
            "estimatedTotalUnit": estimated_unit,
            "estimatedTotalIrt": estimated_irt,
            "exactCostLookupError": exact_cost_error,
            "exactCostFound": exact_summary["found"],
            "exactTotalUnit": exact_summary["totalUnit"],
            "exactTotalPaidIrt": exact_summary["totalPaidIrt"],
            "localVisualOnlyRepairItemIds": list(GOLD_LOCAL_VISUAL_REPAIR_IDS),
            "baselinePassItemIds": list(GOLD_BASELINE_PASS_IDS),
            "acceptance": {
                "exactExpectedProviderCalls": len(call_meta) == len(GOLD_GEMINI_RECOVERY_IDS),
                "allTranscriptsAccepted": len(rows) == len(GOLD_GEMINI_RECOVERY_IDS),
                "allRequestIdsCaptured": len(request_ids) == len(GOLD_GEMINI_RECOVERY_IDS),
            },
        }
        manifest["acceptance"]["passed"] = all(manifest["acceptance"].values())
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Gold Gemini recovery completed: "
                f"calls={len(call_meta)}, reasoning={reasoning_tokens}, "
                f"exactCostFound={exact_summary['found']}/{len(request_ids)}, "
                f"exactPaidIrt={exact_summary['totalPaidIrt']}, bundle={archive_path}"
            )
        )
