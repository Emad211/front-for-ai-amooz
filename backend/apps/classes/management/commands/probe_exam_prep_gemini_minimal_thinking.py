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
    numeric_signature,
    text_similarity,
)
from apps.commons.json_utils import extract_json_object


_MODEL = "gemini-3-flash-preview"
_TARGETS = ("q-094", "s-133")
_DEFAULT_BASE_URL = "https://api.avalai.ir/v1"


def _base_url() -> str:
    value = (os.getenv("AVALAI_BASE_URL") or _DEFAULT_BASE_URL).strip().rstrip("/")
    if not re.search(r"/v\d+$", value):
        value += "/v1"
    return value


def _minimal_extra_body() -> dict[str, Any]:
    # AvalAI documents provider-specific parameters through extra_body, while
    # Google documents Gemini 3 thinkingLevel under generationConfig.thinkingConfig.
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
        "of truth. Transcribe; do not solve, explain, normalize, or correct from subject knowledge. "
        "Preserve all visible Persian text, digits, signs, option labels, units, Latin letters, and "
        "equations. Use Markdown and LaTeX for linear text/formulas. If a diagram, graph, circuit, "
        "chemical structure, table, or spatial construction carries information that should remain "
        "an image, do NOT invent a textual reconstruction of that visual; set source_visual_required "
        "to true and choose the closest visual_type. Still transcribe visible labels/captions and "
        "surrounding prose. Ignore a thin neighboring strip introduced by crop padding. If a visible "
        "fragment cannot be read confidently, preserve the best literal reading, set "
        "transcription_uncertain=true, and list only short uncertain fragments. Return ONLY one valid "
        "JSON object, with no Markdown fence and no surrounding prose."
    )


def _contract(*, item_id: str, target_meta: Mapping[str, Any]) -> str:
    return (
        "Return JSON with exactly these top-level keys: "
        '{"transcription_markdown":"full faithful target transcription",'
        '"source_visual_required":true,'
        '"visual_type":"none|diagram|graph|chemical_structure|table|spatial_layout|other",'
        '"transcription_uncertain":false,'
        '"uncertain_fragments":[]}. '
        "JSON string escaping must be valid, including LaTeX backslashes. "
        f"TARGET item_id={item_id} kind={target_meta.get('kind')} "
        f"question_number={target_meta.get('questionNumber')} "
        f"physical_page={target_meta.get('physicalPageNumber')}."
    )


def _messages(*, item_id: str, target_meta: Mapping[str, Any], crop_bytes: bytes) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _contract(item_id=item_id, target_meta=target_meta)},
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
    usage = root.get("usage")
    if not isinstance(usage, Mapping):
        return 0
    details = usage.get("completion_tokens_details")
    if not isinstance(details, Mapping):
        return 0
    try:
        return int(details.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _response_meta(root: Mapping[str, Any], *, status_code: int, latency_ms: float) -> dict[str, Any]:
    usage = root.get("usage") if isinstance(root, Mapping) else None
    usage = usage if isinstance(usage, Mapping) else {}
    estimated = root.get("estimated_cost") if isinstance(root, Mapping) else None
    estimated = estimated if isinstance(estimated, Mapping) else {}
    return {
        "statusCode": int(status_code),
        "latencyMs": latency_ms,
        "responseId": str(root.get("id") or "") if isinstance(root, Mapping) else "",
        "resolvedModel": str(root.get("model") or "") if isinstance(root, Mapping) else "",
        "promptTokens": int(usage.get("prompt_tokens") or 0),
        "completionTokens": int(usage.get("completion_tokens") or 0),
        "reasoningTokens": _reasoning_tokens(root),
        "totalTokens": int(usage.get("total_tokens") or 0),
        "estimatedUnit": float(estimated.get("unit") or 0),
        "estimatedIrt": float(estimated.get("irt") or 0),
        "exchangeRate": float(estimated.get("exchange_rate") or 0),
    }


def _load_direct_bundle(path: Path) -> tuple[dict[str, Any], dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]], ZipFile]:
    try:
        archive = ZipFile(path)
    except (OSError, BadZipFile) as exc:
        raise CommandError("--direct-bundle must be a readable successful ZIP.") from exc
    names = set(archive.namelist())
    if "failure.json" in names:
        archive.close()
        raise CommandError("--direct-bundle is a failure bundle.")
    try:
        manifest = json.loads(archive.read("manifest.json"))
        targets = json.loads(archive.read("targets.json"))
        baseline_rows = json.loads(archive.read(f"transcriber.{_MODEL}.private.json"))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        archive.close()
        raise CommandError("Direct bundle is missing required successful calibration files.") from exc
    if not isinstance(manifest, Mapping) or not manifest.get("acceptance", {}).get("passed"):
        archive.close()
        raise CommandError("Direct bundle acceptance did not pass.")
    target_map = {
        str(row.get("itemId")): row
        for row in targets
        if isinstance(row, Mapping) and row.get("itemId")
    }
    baseline_map = {
        str(row.get("itemId")): row
        for row in baseline_rows
        if isinstance(row, Mapping) and row.get("itemId")
    }
    missing = [item_id for item_id in _TARGETS if item_id not in target_map or item_id not in baseline_map or f"{item_id}.png" not in names]
    if missing:
        archive.close()
        raise CommandError(f"Direct bundle is missing calibration targets: {missing}")
    return dict(manifest), target_map, baseline_map, archive


class Command(BaseCommand):
    help = (
        "Re-transcribe Q94 and S133 with Gemini 3 Flash thinkingLevel=minimal and compare "
        "against the already-paid default-thinking direct-transcription bundle."
    )

    def add_arguments(self, parser):
        parser.add_argument("--direct-bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--timeout-seconds", type=float, default=300.0)
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Live minimal-thinking calibration requires --allow-private-transmission.")
        api_key = (os.getenv("AVALAI_API_KEY") or "").strip()
        if not api_key:
            raise CommandError("AVALAI_API_KEY is required in this PowerShell session.")
        direct_bundle = Path(options["direct_bundle"]).expanduser().resolve()
        if not direct_bundle.is_file():
            raise CommandError("--direct-bundle must point to an existing ZIP.")
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("Output directory must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)
        timeout = max(30.0, float(options.get("timeout_seconds") or 300.0))

        try:
            response = requests.get(
                f"{_base_url()}/models/{_MODEL}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=min(timeout, 30.0),
            )
        except requests.RequestException as exc:
            raise CommandError("Gemini minimal-thinking preflight transport failed.") from exc
        preflight = {"model": _MODEL, "statusCode": response.status_code, "accessible": bool(response.ok)}
        (output_dir / "model-preflight.safe.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not response.ok:
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(f"Gemini model is not accessible; no source crop was sent. bundle={archive_path}")

        direct_manifest, target_map, baseline_map, direct_archive = _load_direct_bundle(direct_bundle)
        minimal_rows: list[dict[str, Any]] = []
        call_meta: list[dict[str, Any]] = []
        comparisons: list[dict[str, Any]] = []
        try:
            for item_id in _TARGETS:
                target = target_map[item_id]
                crop_bytes = direct_archive.read(f"{item_id}.png")
                (output_dir / f"{item_id}.png").write_bytes(crop_bytes)
                payload = {
                    "model": _MODEL,
                    "messages": _messages(item_id=item_id, target_meta=target, crop_bytes=crop_bytes),
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
                try:
                    root = provider.json()
                except ValueError as exc:
                    raise RuntimeError("provider_non_json_root") from exc
                if not isinstance(root, Mapping):
                    raise RuntimeError("provider_root_not_object")
                meta = {"itemId": item_id, **_response_meta(root, status_code=provider.status_code, latency_ms=latency_ms)}
                (output_dir / f"{item_id}.response.safe.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                if not provider.ok:
                    raise RuntimeError(f"provider_http_{provider.status_code}")
                transcript = _parse_transcript(_provider_content(root))
                row = {"itemId": item_id, **transcript}
                minimal_rows.append(row)
                call_meta.append(meta)
                baseline = baseline_map[item_id]
                comparisons.append(
                    {
                        "itemId": item_id,
                        "textSimilarityToDefaultThinking": text_similarity(
                            str(baseline.get("transcriptionMarkdown") or ""),
                            str(row.get("transcriptionMarkdown") or ""),
                        ),
                        "numericSignatureMatchesDefaultThinking": numeric_signature(
                            str(baseline.get("transcriptionMarkdown") or "")
                        ) == numeric_signature(str(row.get("transcriptionMarkdown") or "")),
                        "visualRequiredMatchesDefaultThinking": bool(baseline.get("sourceVisualRequired")) == bool(row.get("sourceVisualRequired")),
                        "visualTypeMatchesDefaultThinking": str(baseline.get("visualType") or "none") == str(row.get("visualType") or "none"),
                        "minimalUncertain": bool(row.get("transcriptionUncertain")),
                    }
                )
                (output_dir / f"{item_id}.minimal.transcript.private.json").write_text(
                    json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        except Exception as exc:
            (output_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "privateDiagnosticBundle": True,
                        "stage": "minimal_thinking",
                        "errorType": type(exc).__name__,
                        "error": str(exc)[:500],
                        "completedProviderCalls": len(call_meta),
                        "automaticRetry": False,
                        "automaticPaidRepair": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(f"Gemini minimal-thinking calibration failed; partial bundle={archive_path}") from exc
        finally:
            direct_archive.close()

        prior_calls = []
        try:
            with ZipFile(direct_bundle) as archive:
                prior_calls = json.loads(archive.read("provider-calls.safe.json"))
        except Exception:
            prior_calls = []
        prior_selected = [
            row for row in prior_calls
            if isinstance(row, Mapping) and row.get("model") == _MODEL and row.get("itemId") in _TARGETS
        ]
        default_unit = sum(float(row.get("estimatedUnit") or 0) for row in prior_selected)
        default_irt = sum(float(row.get("estimatedIrt") or 0) for row in prior_selected)
        default_reasoning = sum(int(row.get("reasoningTokens") or 0) for row in prior_selected)
        # Older direct bundle metadata did not persist reasoningTokens, so recover it from raw provider files if needed.
        if default_reasoning == 0:
            try:
                with ZipFile(direct_bundle) as archive:
                    for item_id in _TARGETS:
                        root = json.loads(archive.read(f"transcriber.{_MODEL}.{item_id}.provider.private.json"))
                        default_reasoning += _reasoning_tokens(root if isinstance(root, Mapping) else {})
            except Exception:
                pass

        minimal_unit = sum(float(row.get("estimatedUnit") or 0) for row in call_meta)
        minimal_irt = sum(float(row.get("estimatedIrt") or 0) for row in call_meta)
        minimal_reasoning = sum(int(row.get("reasoningTokens") or 0) for row in call_meta)
        comparison = {
            "schemaVersion": 1,
            "contentFree": True,
            "model": _MODEL,
            "targets": list(_TARGETS),
            "defaultThinking": {
                "estimatedUnit": round(default_unit, 8),
                "estimatedIrt": round(default_irt, 2),
                "reasoningTokens": default_reasoning,
            },
            "minimalThinking": {
                "estimatedUnit": round(minimal_unit, 8),
                "estimatedIrt": round(minimal_irt, 2),
                "reasoningTokens": minimal_reasoning,
            },
            "costRatioMinimalToDefault": round(minimal_unit / default_unit, 6) if default_unit else None,
            "reasoningRatioMinimalToDefault": round(minimal_reasoning / default_reasoning, 6) if default_reasoning else None,
            "items": comparisons,
        }
        (output_dir / "comparison.safe.json").write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "minimal-transcripts.private.json").write_text(
            json.dumps(minimal_rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest = {
            "schemaVersion": 1,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "sourceDirectBundle": direct_bundle.name,
            "model": _MODEL,
            "thinkingLevel": "minimal",
            "itemCount": len(_TARGETS),
            "providerCallCount": len(call_meta),
            "providerRetryPerCall": 0,
            "paidRepairBudgetPerCall": 0,
            "estimatedTotalUnit": round(minimal_unit, 8),
            "estimatedTotalIrt": round(minimal_irt, 2),
            "reasoningTokens": minimal_reasoning,
            "acceptance": {
                "exactExpectedProviderCalls": len(call_meta) == len(_TARGETS),
                "allTranscriptsAccepted": len(minimal_rows) == len(_TARGETS),
                "passed": len(call_meta) == len(_TARGETS) and len(minimal_rows) == len(_TARGETS),
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Gemini minimal-thinking calibration completed: "
                f"calls={len(call_meta)}, reasoning={minimal_reasoning}, "
                f"costRatio={comparison['costRatioMinimalToDefault']}, bundle={archive_path}"
            )
        )
