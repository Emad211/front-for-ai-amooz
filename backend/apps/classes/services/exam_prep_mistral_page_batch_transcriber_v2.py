"""Restored production-shaped Gemini page-batch transport for Stage 4.

The first live 12R replay proved the native AvalAI/Gemini ``responseSchema``
contract on the exact same source crops. A later transport-hardening experiment
changed that request contract and made valid provider items fail before field
safety. This module keeps the proven request shape and adds one non-negotiable
source-provenance invariant: provider output has no authority unless Gemini says
an IMAGE modality was actually processed for the request.

Provider omissions of request-known transport metadata are backfilled locally;
source content (stem/options/answer/solution) is never inferred here. Missing
content remains empty and is blocked later by Stage-4 field safety.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from . import exam_prep_mistral_page_batch_transcriber as base
from .exam_prep_mistral_risk_engine import RegionRiskDecision


BatchItem = base.BatchItem
BatchOption = base.BatchOption
BatchUncertainSpan = base.BatchUncertainSpan
PageBatchEnvelopeError = base.PageBatchEnvelopeError
PageBatchResult = base.PageBatchResult


def _normalize_items_envelope(raw: Any, *, target_count: int) -> Mapping[str, Any]:
    """Normalize only lossless wrapper variations; never reconstruct content."""

    if isinstance(raw, Mapping) and isinstance(raw.get("items"), list):
        return raw
    if isinstance(raw, list):
        return {"items": raw}
    if (
        target_count == 1
        and isinstance(raw, Mapping)
        and (
            str(raw.get("target_id") or "").strip()
            or str(raw.get("kind") or "").strip()
            or raw.get("question_number") is not None
        )
    ):
        return {"items": [raw]}
    if isinstance(raw, Mapping):
        keys = ",".join(sorted(str(key)[:60] for key in raw.keys())[:20])
        raise PageBatchEnvelopeError(
            f"invalid_items_envelope:object_keys={keys or '<empty>'}"
        )
    raise PageBatchEnvelopeError(
        f"invalid_items_envelope:root_type={type(raw).__name__}"
    )


def _safe_item_identity(raw_item: Any) -> str:
    """Describe only structural identity metadata; never source text/content."""

    if not isinstance(raw_item, Mapping):
        return f"type={type(raw_item).__name__}"
    keys = ",".join(sorted(str(key)[:40] for key in raw_item.keys())[:20])
    target = str(raw_item.get("target_id") or "")[:80]
    kind = str(raw_item.get("kind") or "")[:20]
    number = str(raw_item.get("question_number") or "")[:20]
    return (
        f"keys={keys or '<empty>'};target_id={target or '<empty>'};"
        f"kind={kind or '<empty>'};question_number={number or '<empty>'}"
    )


def _placeholder_present(raw: Mapping[str, Any]) -> bool:
    values = [
        raw.get("question_text_markdown"),
        raw.get("teacher_solution_markdown"),
        raw.get("correct_option_label"),
    ]
    for option in raw.get("options") or []:
        if isinstance(option, Mapping):
            values.append(option.get("text_markdown"))
    return any("[?]" in str(value or "") for value in values)


def _backfill_request_metadata(
    raw_item: Mapping[str, Any],
    *,
    decision: RegionRiskDecision,
) -> dict[str, Any]:
    """Fill only metadata already known from the request or explicit uncertainty."""

    normalized = dict(raw_item)
    normalized.setdefault("target_id", decision.target_id)
    normalized.setdefault("kind", decision.kind)
    normalized.setdefault("question_number", decision.question_number)
    normalized.setdefault("source_visual_required", False)
    normalized.setdefault("visual_type", "none")
    normalized.setdefault("uncertain_spans", [])
    normalized.setdefault("uncertain_fragments", [])
    if "transcription_uncertain" not in normalized:
        normalized["transcription_uncertain"] = bool(
            normalized.get("uncertain_spans")
            or normalized.get("uncertain_fragments")
            or _placeholder_present(normalized)
        )
    return normalized


def _validate_items_with_identity_fallback(
    raw: Mapping[str, Any],
    *,
    decisions: Sequence[RegionRiskDecision],
) -> tuple[tuple[BatchItem, ...], tuple[str, ...], tuple[str, ...]]:
    """Validate content, recovering only request-known transport metadata."""

    raw_items = raw.get("items")
    if not isinstance(raw_items, list):
        raise PageBatchEnvelopeError("invalid_items_envelope")

    expected = {item.target_id: item for item in decisions}
    returned: dict[str, BatchItem] = {}
    invalid: set[str] = set()
    rejection_notes: list[str] = []

    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, Mapping):
            rejection_notes.append(f"i{index}:{_safe_item_identity(raw_item)}")
            continue

        raw_target_id = str(raw_item.get("target_id") or "").strip()
        decision = expected.get(raw_target_id)
        if decision is None:
            kind = str(raw_item.get("kind") or "").strip()
            try:
                number = int(raw_item.get("question_number") or 0)
            except (TypeError, ValueError):
                number = 0
            matches = [
                item
                for item in decisions
                if item.kind == kind
                and int(item.question_number) == number
                and item.target_id not in returned
            ]
            if len(matches) != 1:
                rejection_notes.append(
                    f"i{index}:identity_unmatched:{_safe_item_identity(raw_item)};"
                    f"matches={len(matches)}"
                )
                continue
            decision = matches[0]

        if decision.target_id in returned:
            rejection_notes.append(f"i{index}:duplicate_identity:{decision.target_id}")
            continue

        normalized = _backfill_request_metadata(raw_item, decision=decision)
        normalized["target_id"] = decision.target_id
        try:
            item = BatchItem.model_validate(normalized)
        except ValidationError as exc:
            invalid.add(decision.target_id)
            errors = []
            for error in exc.errors():
                loc = ".".join(str(part) for part in (error.get("loc") or ()))
                errors.append(f"{loc or '?'}:{error.get('type') or 'validation'}")
            rejection_notes.append(
                f"i{index}:pydantic:{decision.target_id}:"
                f"{','.join(errors)[:320] or 'validation'}"
            )
            continue

        if item.kind != decision.kind or item.question_number != decision.question_number:
            invalid.add(decision.target_id)
            rejection_notes.append(
                f"i{index}:identity_conflict:{decision.target_id}:"
                f"kind={item.kind}:number={item.question_number}"
            )
            continue
        returned[decision.target_id] = item

    ordered = tuple(
        returned[item.target_id] for item in decisions if item.target_id in returned
    )
    missing = tuple(
        item.target_id
        for item in decisions
        if item.target_id not in returned and item.target_id not in invalid
    )
    invalid_ids = tuple(item.target_id for item in decisions if item.target_id in invalid)
    if decisions and not ordered:
        notes = "|".join(rejection_notes[:3]) or "no_raw_items"
        raise PageBatchEnvelopeError(
            f"no_usable_requested_items:rawCount={len(raw_items)}:{notes}"
        )
    return ordered, missing, invalid_ids


def _generation_config(maximum: int) -> dict[str, Any]:
    """Keep the structured-output contract proven by the successful live run."""

    return {
        "thinkingConfig": {"thinkingLevel": "minimal"},
        "maxOutputTokens": maximum,
        "responseMimeType": "application/json",
        "responseSchema": base._response_schema(),
    }


def _image_part_high(payload: bytes) -> dict[str, Any]:
    """Send every exact crop as an explicit high-resolution Gemini 3 media part."""

    return {
        "inlineData": {
            "mimeType": "image/png",
            "data": base64.b64encode(payload).decode("ascii"),
        },
        "mediaResolution": {"level": "media_resolution_high"},
    }


def _usage_with_modalities(root: Mapping[str, Any]) -> dict[str, int]:
    """Return normal usage plus processed input-modality token counts."""

    usage = dict(base._usage(root))
    metadata = root.get("usageMetadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    raw_details = metadata.get("promptTokensDetails")
    if raw_details is None:
        raw_details = metadata.get("prompt_tokens_details")
    details = raw_details if isinstance(raw_details, list) else []
    image_tokens = text_tokens = document_tokens = 0
    for raw in details:
        if not isinstance(raw, Mapping):
            continue
        modality = str(raw.get("modality") or "").strip().upper()
        try:
            count = int(raw.get("tokenCount") or raw.get("token_count") or 0)
        except (TypeError, ValueError):
            count = 0
        if modality.endswith("IMAGE"):
            image_tokens += max(0, count)
        elif modality.endswith("TEXT"):
            text_tokens += max(0, count)
        elif modality.endswith("DOCUMENT"):
            document_tokens += max(0, count)
    usage["promptModalityDetailsPresent"] = 1 if details else 0
    usage["imageInputTokens"] = image_tokens
    usage["textInputTokens"] = text_tokens
    usage["documentInputTokens"] = document_tokens
    return usage


def _require_image_provenance(
    root: Mapping[str, Any],
    *,
    request_id: str,
    finish_reason: str,
) -> dict[str, int]:
    """Fail closed unless the provider proves that IMAGE input was processed."""

    usage = _usage_with_modalities(root)
    if int(usage.get("imageInputTokens") or 0) > 0:
        return usage
    reason = (
        "image_modality_unproven:no_prompt_modality_details"
        if not int(usage.get("promptModalityDetailsPresent") or 0)
        else "image_modality_unproven:image_tokens_zero"
    )
    raise PageBatchEnvelopeError(
        reason,
        usage=usage,
        estimated_cost=base._estimated_cost(root),
        request_id=request_id,
        finish_reason=finish_reason,
    )


def transcribe_page_batch(
    *,
    page_number: int,
    targets: Sequence[tuple[RegionRiskDecision, bytes]],
    model: str | None = None,
) -> PageBatchResult:
    if page_number < 1 or not targets:
        raise ValueError("A positive page and at least one batch target are required.")
    decisions = [item[0] for item in targets]
    if any(item.page_number != page_number for item in decisions):
        raise ValueError("All batch targets must belong to the same physical page.")
    if len({item.target_id for item in decisions}) != len(decisions):
        raise ValueError("Batch target ids must be unique.")
    if any(not payload for _decision, payload in targets):
        raise ValueError("Every batch target requires a non-empty PNG crop.")

    selected_model = str(model or base._model()).strip()
    parts: list[dict[str, Any]] = [
        {
            "text": (
                f"Physical source page {page_number}. Return one independent item for each "
                f"of these {len(targets)} TARGET_ID values. Keep ids exactly as supplied."
            )
        }
    ]
    for decision, payload in targets:
        parts.append({"text": base._target_instruction(decision)})
        parts.append(_image_part_high(payload))

    maximum = max(3200, min(9000, 1600 + 1050 * len(targets)))
    body = {
        "systemInstruction": {"parts": [{"text": base._system_prompt()}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": _generation_config(maximum),
    }
    response = base.requests.post(
        f"{base._base_url()}/v1beta/models/{selected_model}:generateContent",
        headers={
            "x-goog-api-key": base._api_key(),
            "Authorization": f"Bearer {base._api_key()}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=base._timeout(),
    )
    request_id = str(response.headers.get("x-request-id") or "").strip()
    if response.status_code != 200:
        raise RuntimeError(f"gemini_page_batch_http_{response.status_code}")
    try:
        root = response.json()
    except ValueError as exc:
        raise PageBatchEnvelopeError("provider_root_not_json", request_id=request_id) from exc
    if not isinstance(root, Mapping):
        raise PageBatchEnvelopeError("provider_root_not_object", request_id=request_id)

    finish_reason = base._finish_reason(root)
    usage = _require_image_provenance(
        root,
        request_id=request_id,
        finish_reason=finish_reason,
    )
    try:
        response_text = base._response_text(root)
    except PageBatchEnvelopeError as exc:
        raise PageBatchEnvelopeError(
            exc.reason_code,
            usage=usage,
            estimated_cost=base._estimated_cost(root),
            request_id=request_id,
            finish_reason=finish_reason,
        ) from exc

    digest = hashlib.sha256(response_text.encode("utf-8", errors="replace")).hexdigest()
    prefix = response_text[:2000]
    try:
        decoded = base._decode_structured_text(response_text)
    except json.JSONDecodeError as exc:
        raise PageBatchEnvelopeError(
            "structured_json_invalid",
            usage=usage,
            estimated_cost=base._estimated_cost(root),
            request_id=request_id,
            finish_reason=finish_reason,
            response_text_sha256=digest,
            response_text_prefix=prefix,
        ) from exc

    try:
        normalized = _normalize_items_envelope(decoded, target_count=len(decisions))
        items, missing, invalid = _validate_items_with_identity_fallback(
            normalized, decisions=decisions
        )
    except PageBatchEnvelopeError as exc:
        raise PageBatchEnvelopeError(
            exc.reason_code,
            usage=usage,
            estimated_cost=base._estimated_cost(root),
            request_id=request_id,
            finish_reason=finish_reason,
            response_text_sha256=digest,
            response_text_prefix=prefix,
        ) from exc

    return PageBatchResult(
        page_number=page_number,
        model=selected_model,
        items=items,
        request_id=request_id,
        usage=usage,
        estimated_cost=base._estimated_cost(root),
        requested_target_ids=tuple(item.target_id for item in decisions),
        missing_target_ids=missing,
        invalid_target_ids=invalid,
    )


__all__ = [
    "BatchItem",
    "BatchOption",
    "BatchUncertainSpan",
    "PageBatchEnvelopeError",
    "PageBatchResult",
    "_backfill_request_metadata",
    "_generation_config",
    "_image_part_high",
    "_normalize_items_envelope",
    "_require_image_provenance",
    "_safe_item_identity",
    "_usage_with_modalities",
    "_validate_items_with_identity_fallback",
    "transcribe_page_batch",
]
