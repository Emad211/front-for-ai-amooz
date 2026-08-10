"""Gemini native page-batch transport with strict request-specific identity.

This module is deliberately transport-only. It preserves the source-only prompt,
Pydantic item contract, cost accounting and fail-closed validation from the
original transcriber while hardening provider-compatibility edges:

* lossless envelope variations are normalized;
* target identity is constrained by the request-specific JSON schema, with one
  deterministic fallback from exact ``(kind, question_number)`` when the model
  changes or omits ``target_id``;
* an HTTP-200 response that yields zero usable requested items is never cached as
  success. It becomes a diagnostic envelope failure containing only safe identity
  metadata, never source text.

No semantic JSON repair is performed. Unknown wrappers and ambiguous identities
remain errors/missing evidence rather than guessed content.
"""
from __future__ import annotations

from copy import deepcopy
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
    """Normalize only lossless provider envelope variations."""

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
        reason = f"invalid_items_envelope:object_keys={keys or '<empty>'}"
    else:
        reason = f"invalid_items_envelope:root_type={type(raw).__name__}"
    raise PageBatchEnvelopeError(reason)


def _response_schema_for(decisions: Sequence[RegionRiskDecision]) -> dict[str, Any]:
    """Bind structured output to this exact request without encoding source text."""

    schema = deepcopy(base._response_schema())
    items_schema = schema["properties"]["items"]
    item_schema = items_schema["items"]
    target_ids = [item.target_id for item in decisions]
    kinds = sorted({item.kind for item in decisions})
    numbers = sorted({int(item.question_number) for item in decisions})

    items_schema["minItems"] = len(decisions)
    items_schema["maxItems"] = len(decisions)
    item_schema["properties"]["target_id"]["enum"] = target_ids
    item_schema["properties"]["target_id"]["description"] = (
        "Copy exactly one TARGET_ID from the request; never invent or rewrite it."
    )
    item_schema["properties"]["kind"]["enum"] = kinds
    item_schema["properties"]["question_number"]["enum"] = numbers
    return schema


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


def _validate_items_with_identity_fallback(
    raw: Mapping[str, Any],
    *,
    decisions: Sequence[RegionRiskDecision],
) -> tuple[tuple[BatchItem, ...], tuple[str, ...], tuple[str, ...]]:
    """Validate content strictly, recovering only a unique transport identity."""

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
        normalized = dict(raw_item)
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
                    f"i{index}:identity_unmatched:{_safe_item_identity(raw_item)};matches={len(matches)}"
                )
                continue
            decision = matches[0]
            normalized["target_id"] = decision.target_id

        if decision.target_id in returned:
            rejection_notes.append(f"i{index}:duplicate_identity:{decision.target_id}")
            continue
        try:
            item = BatchItem.model_validate(normalized)
        except ValidationError as exc:
            invalid.add(decision.target_id)
            error_types = ",".join(
                sorted({str(error.get("type") or "validation") for error in exc.errors()})
            )[:240]
            rejection_notes.append(
                f"i{index}:pydantic:{decision.target_id}:{error_types or 'validation'}"
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
                f"Physical source page {page_number}. Return EXACTLY one item for each "
                f"of these {len(targets)} TARGET_ID values. Copy TARGET_ID, kind, and "
                f"question_number exactly from the instruction preceding each image."
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
            "responseJsonSchema": _response_schema_for(decisions),
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
        items, missing, invalid = _validate_items_with_identity_fallback(
            normalized, decisions=decisions
        )
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
    "_response_schema_for",
    "_safe_item_identity",
    "_validate_items_with_identity_fallback",
    "transcribe_page_batch",
]
