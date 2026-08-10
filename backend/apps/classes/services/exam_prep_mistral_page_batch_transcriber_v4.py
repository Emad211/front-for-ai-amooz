"""AvalAI OpenAI-compatible Stage-4 Gemini page-batch transport.

The native AvalAI ``v1beta:generateContent`` bridge has shown intermittent
text-only behavior for requests that contained valid inline image parts. This
transport moves only the provider boundary to AvalAI's advertised
``/v1/chat/completions`` endpoint while preserving the Stage-4 source-only prompt,
item contract, deterministic validation, and fail-closed provenance policy.

No semantic repair is performed here. A response has no authority unless AvalAI
reports non-zero image prompt tokens in the OpenAI-compatible usage block.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_page_batch_transcriber_v2 as v2
from .exam_prep_mistral_risk_engine import RegionRiskDecision


base = v2.base
BatchItem = v2.BatchItem
BatchOption = v2.BatchOption
BatchUncertainSpan = v2.BatchUncertainSpan
PageBatchEnvelopeError = v2.PageBatchEnvelopeError
PageBatchResult = v2.PageBatchResult


def _image_url_part(payload: bytes) -> dict[str, Any]:
    return {
        "type": "image_url",
        "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(payload).decode("ascii"),
            "detail": "high",
        },
    }


def _usage(root: Mapping[str, Any]) -> dict[str, int]:
    raw = root.get("usage")
    raw = raw if isinstance(raw, Mapping) else {}
    prompt_details = raw.get("prompt_tokens_details")
    prompt_details = prompt_details if isinstance(prompt_details, Mapping) else {}
    completion_details = raw.get("completion_tokens_details")
    completion_details = completion_details if isinstance(completion_details, Mapping) else {}

    def integer(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    return {
        "inputTokens": integer(raw.get("prompt_tokens")),
        "outputTokens": integer(raw.get("completion_tokens")),
        "reasoningTokens": integer(completion_details.get("reasoning_tokens")),
        "totalTokens": integer(raw.get("total_tokens")),
        "promptModalityDetailsPresent": 1 if prompt_details else 0,
        "imageInputTokens": integer(prompt_details.get("image_tokens")),
        "textInputTokens": integer(prompt_details.get("text_tokens")),
        "documentInputTokens": 0,
    }


def _estimated_cost(root: Mapping[str, Any]) -> dict[str, float]:
    value = root.get("estimated_cost")
    value = value if isinstance(value, Mapping) else {}
    output: dict[str, float] = {}
    for key in ("unit", "irt"):
        try:
            output[key] = float(value.get(key) or 0)
        except (TypeError, ValueError):
            output[key] = 0.0
    return output


def _finish_reason(root: Mapping[str, Any]) -> str:
    choices = root.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return ""
    return str(choices[0].get("finish_reason") or "").strip()


def _response_text(root: Mapping[str, Any]) -> str:
    choices = root.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        raise PageBatchEnvelopeError("no_candidate")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise PageBatchEnvelopeError("no_candidate_content")
    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        values: list[str] = []
        for part in content:
            if not isinstance(part, Mapping):
                continue
            if str(part.get("type") or "") == "text" or "text" in part:
                values.append(str(part.get("text") or ""))
        text = "".join(values).strip()
    else:
        text = ""
    if not text:
        raise PageBatchEnvelopeError("empty_content")
    return text


def _require_image_provenance(
    root: Mapping[str, Any],
    *,
    request_id: str,
    finish_reason: str,
) -> dict[str, int]:
    usage = _usage(root)
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
        estimated_cost=_estimated_cost(root),
        request_id=request_id,
        finish_reason=finish_reason,
    )


def _request_body(
    *,
    page_number: int,
    targets: Sequence[tuple[RegionRiskDecision, bytes]],
    model: str,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"Physical source page {page_number}. Return one independent item for each "
                f"of these {len(targets)} TARGET_ID values. Keep ids exactly as supplied."
            ),
        }
    ]
    for decision, payload in targets:
        content.append({"type": "text", "text": base._target_instruction(decision)})
        content.append(_image_url_part(payload))

    maximum = max(3200, min(9000, 1600 + 1050 * len(targets)))
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": base._system_prompt()},
            {"role": "user", "content": content},
        ],
        "max_tokens": maximum,
        # JSON mode is intentionally simpler than provider-specific native schema
        # translation; the same Pydantic/identity validators remain authoritative.
        "response_format": {"type": "json_object"},
    }


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
    body = _request_body(page_number=page_number, targets=targets, model=selected_model)
    response = base.requests.post(
        f"{base._base_url()}/v1/chat/completions",
        headers={
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

    finish_reason = _finish_reason(root)
    usage = _require_image_provenance(
        root,
        request_id=request_id,
        finish_reason=finish_reason,
    )
    try:
        response_text = _response_text(root)
    except PageBatchEnvelopeError as exc:
        raise PageBatchEnvelopeError(
            exc.reason_code,
            usage=usage,
            estimated_cost=_estimated_cost(root),
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
            estimated_cost=_estimated_cost(root),
            request_id=request_id,
            finish_reason=finish_reason,
            response_text_sha256=digest,
            response_text_prefix=prefix,
        ) from exc

    try:
        normalized = v2._normalize_items_envelope(decoded, target_count=len(decisions))
        items, missing, invalid = v2._validate_items_with_identity_fallback(
            normalized,
            decisions=decisions,
        )
    except PageBatchEnvelopeError as exc:
        raise PageBatchEnvelopeError(
            exc.reason_code,
            usage=usage,
            estimated_cost=_estimated_cost(root),
            request_id=request_id,
            finish_reason=finish_reason,
            response_text_sha256=digest,
            response_text_prefix=prefix,
        ) from exc

    return PageBatchResult(
        page_number=page_number,
        model=str(root.get("model") or selected_model),
        items=items,
        request_id=request_id,
        usage=usage,
        estimated_cost=_estimated_cost(root),
        requested_target_ids=tuple(item.target_id for item in decisions),
        missing_target_ids=missing,
        invalid_target_ids=invalid,
    )


def install_stage4_transport_policy() -> None:
    from . import exam_prep_mistral_stage4_page_batch as page_batch

    if page_batch.transcribe_page_batch is not transcribe_page_batch:
        page_batch.transcribe_page_batch = transcribe_page_batch


__all__ = [
    "BatchItem",
    "BatchOption",
    "BatchUncertainSpan",
    "PageBatchEnvelopeError",
    "PageBatchResult",
    "_request_body",
    "_usage",
    "install_stage4_transport_policy",
    "transcribe_page_batch",
]
