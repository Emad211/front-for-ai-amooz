"""Gemini native page-batch transport with current JSON-schema semantics.

This module is deliberately transport-only. It preserves the source-only prompt,
Pydantic item contract, cost accounting and fail-closed validation from the
original transcriber while addressing one observed provider compatibility issue:
AvalAI/Gemini returned syntactically valid JSON for every batch but the decoded
root no longer matched the old ``{"items": [...]}`` envelope.

No semantic JSON repair is performed. Only three lossless envelope shapes are
accepted: the canonical object, a bare list of items, or a single item object when
exactly one target was requested.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_page_batch_transcriber as base
from .exam_prep_mistral_risk_engine import RegionRiskDecision


BatchItem = base.BatchItem
BatchOption = base.BatchOption
BatchUncertainSpan = base.BatchUncertainSpan
PageBatchEnvelopeError = base.PageBatchEnvelopeError
PageBatchResult = base.PageBatchResult


def _normalize_items_envelope(raw: Any, *, target_count: int) -> Mapping[str, Any]:
    """Normalize only lossless provider envelope variations.

    The content of an item is never modified here. Unknown wrappers remain an
    error so provider drift cannot silently change persisted exam content.
    """

    if isinstance(raw, Mapping) and isinstance(raw.get("items"), list):
        return raw
    if isinstance(raw, list):
        return {"items": raw}
    if (
        target_count == 1
        and isinstance(raw, Mapping)
        and str(raw.get("target_id") or "").strip()
    ):
        return {"items": [raw]}

    if isinstance(raw, Mapping):
        keys = ",".join(sorted(str(key)[:60] for key in raw.keys())[:20])
        reason = f"invalid_items_envelope:object_keys={keys or '<empty>'}"
    else:
        reason = f"invalid_items_envelope:root_type={type(raw).__name__}"
    raise PageBatchEnvelopeError(reason)


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
                f"Physical source page {page_number}. Return EXACTLY one JSON object "
                f"whose top-level key is items, containing one independent item for "
                f"each of these {len(targets)} TARGET_ID values. Keep ids exactly as supplied."
            )
        }
    ]
    for decision, payload in targets:
        parts.append({"text": base._target_instruction(decision)})
        parts.append(base._image_part(payload))

    maximum = max(3200, min(9000, 1600 + 1050 * len(targets)))
    body = {
        "systemInstruction": {"parts": [{"text": base._system_prompt()}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "thinkingConfig": {"thinkingLevel": "minimal"},
            "maxOutputTokens": maximum,
            "responseMimeType": "application/json",
            # Current Gemini REST accepts JSON Schema through responseJsonSchema.
            # The old responseSchema field is deprecated and has shown provider
            # drift through AvalAI despite HTTP 200 responses.
            "responseJsonSchema": base._response_schema(),
        },
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
    try:
        response_text = base._response_text(root)
    except PageBatchEnvelopeError as exc:
        raise PageBatchEnvelopeError(
            exc.reason_code,
            usage=base._usage(root),
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
            usage=base._usage(root),
            estimated_cost=base._estimated_cost(root),
            request_id=request_id,
            finish_reason=finish_reason,
            response_text_sha256=digest,
            response_text_prefix=prefix,
        ) from exc

    try:
        normalized = _normalize_items_envelope(decoded, target_count=len(decisions))
        items, missing, invalid = base._validate_items(normalized, decisions=decisions)
    except PageBatchEnvelopeError as exc:
        raise PageBatchEnvelopeError(
            exc.reason_code,
            usage=base._usage(root),
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
        usage=base._usage(root),
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
    "_normalize_items_envelope",
    "transcribe_page_batch",
]
