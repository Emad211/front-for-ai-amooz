"""Source-only Gemini page-batch transcription for Stage 4.

All suspicious crops from one physical PDF page are sent in one provider request.
Each crop remains an independent source image and is explicitly labeled with its
target id; the previous Mistral candidate is never sent.

The transport uses AvalAI's native Gemini generateContent endpoint so Gemini's
native JSON response schema can be enforced. There is no automatic same-batch
retry or paid JSON repair pass. Item validation is deliberately partial: one bad
item can never discard valid sibling items from the same provider response.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
import re
from typing import Any, Literal, Mapping, Sequence

import requests
from pydantic import BaseModel, Field, ValidationError

from .exam_prep_mistral_risk_engine import RegionRiskDecision


DEFAULT_MODEL = "gemini-3-flash-preview"
_VISUAL_TYPES = (
    "none",
    "diagram",
    "graph",
    "chemical_structure",
    "table",
    "spatial_layout",
    "other",
)
_UNCERTAIN_FIELDS = (
    "question_text_markdown",
    "option_1",
    "option_2",
    "option_3",
    "option_4",
    "correct_option_label",
    "teacher_solution_markdown",
)
_UNCERTAIN_REASONS = (
    "unreadable_glyph",
    "cropped",
    "absent",
    "ambiguous_layout",
    "other",
)


def _model() -> str:
    return (os.getenv("EXAM_PREP_STAGE4_PRIMARY_MODEL") or DEFAULT_MODEL).strip()


def _timeout() -> float:
    try:
        value = float(os.getenv("EXAM_PREP_STAGE4_TIMEOUT_SECONDS", "240"))
    except (TypeError, ValueError):
        value = 240.0
    return max(30.0, min(600.0, value))


def _base_url() -> str:
    value = (os.getenv("AVALAI_BASE_URL") or "https://api.avalai.ir/v1").strip().rstrip("/")
    value = re.sub(r"/v\d+(?:beta)?$", "", value)
    return value or "https://api.avalai.ir"


def _api_key() -> str:
    value = (os.getenv("AVALAI_API_KEY") or "").strip()
    if not value:
        raise RuntimeError("AVALAI_API_KEY is required for Stage-4 page batching.")
    return value


class BatchOption(BaseModel):
    label: str = Field(max_length=8)
    text_markdown: str = Field(max_length=4000)


class BatchUncertainSpan(BaseModel):
    field: Literal[
        "question_text_markdown",
        "option_1",
        "option_2",
        "option_3",
        "option_4",
        "correct_option_label",
        "teacher_solution_markdown",
    ]
    fragment: str = Field(default="", max_length=240)
    reason: Literal[
        "unreadable_glyph",
        "cropped",
        "absent",
        "ambiguous_layout",
        "other",
    ]


class BatchItem(BaseModel):
    target_id: str = Field(max_length=80)
    kind: Literal["question", "solution"]
    question_number: int = Field(gt=0)
    question_text_markdown: str = Field(default="", max_length=20000)
    options: list[BatchOption] = Field(default_factory=list, max_length=6)
    correct_option_label: str = Field(default="", max_length=8)
    teacher_solution_markdown: str = Field(default="", max_length=30000)
    source_visual_required: bool
    visual_type: Literal[
        "none",
        "diagram",
        "graph",
        "chemical_structure",
        "table",
        "spatial_layout",
        "other",
    ]
    transcription_uncertain: bool
    uncertain_spans: list[BatchUncertainSpan] = Field(default_factory=list, max_length=16)
    # Kept for checkpoint compatibility with the first page-batch schema.
    uncertain_fragments: list[str] = Field(default_factory=list, max_length=12)


class PageBatchEnvelopeError(ValueError):
    """The provider response cannot be safely decomposed into independent items."""

    def __init__(
        self,
        reason_code: str,
        *,
        usage: Mapping[str, int] | None = None,
        estimated_cost: Mapping[str, float] | None = None,
        request_id: str = "",
    ):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.usage = dict(usage or {})
        self.estimated_cost = dict(estimated_cost or {})
        self.request_id = str(request_id or "")


def _response_schema() -> dict[str, Any]:
    """Gemini-compatible JSON Schema with one uniform item shape."""

    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target_id": {"type": "string"},
                        "kind": {"type": "string", "enum": ["question", "solution"]},
                        "question_number": {"type": "integer"},
                        "question_text_markdown": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "text_markdown": {"type": "string"},
                                },
                                "required": ["label", "text_markdown"],
                            },
                        },
                        "correct_option_label": {"type": "string"},
                        "teacher_solution_markdown": {"type": "string"},
                        "source_visual_required": {"type": "boolean"},
                        "visual_type": {"type": "string", "enum": list(_VISUAL_TYPES)},
                        "transcription_uncertain": {"type": "boolean"},
                        "uncertain_spans": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field": {"type": "string", "enum": list(_UNCERTAIN_FIELDS)},
                                    "fragment": {"type": "string"},
                                    "reason": {"type": "string", "enum": list(_UNCERTAIN_REASONS)},
                                },
                                "required": ["field", "fragment", "reason"],
                            },
                        },
                        "uncertain_fragments": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "target_id",
                        "kind",
                        "question_number",
                        "question_text_markdown",
                        "options",
                        "correct_option_label",
                        "teacher_solution_markdown",
                        "source_visual_required",
                        "visual_type",
                        "transcription_uncertain",
                        "uncertain_spans",
                        "uncertain_fragments",
                    ],
                },
            }
        },
        "required": ["items"],
    }


def _system_prompt() -> str:
    return (
        "You are a literal source transcription engine for Persian high-school exam material. "
        "Every image is an exact crop from ONE physical source page and has an explicit TARGET_ID "
        "immediately before it. The image pixels are the only authority. A previous OCR candidate "
        "exists but is intentionally hidden. NEVER solve the problem, complete a sentence from "
        "subject knowledge, infer a chemical species, infer a number, or repair an unreadable glyph. "
        "If even one requested glyph is unreadable, copy only what is visibly supported, place [?] "
        "at that exact spot, set transcription_uncertain=true, and add an uncertain_spans entry for "
        "the affected canonical field. Do not silently turn a square/tofu glyph into a plausible word. "
        "Return at most one item per requested TARGET_ID and no extra targets. For kind=question, copy "
        "the visible question text and four visible answer choices into question_text_markdown/options. "
        "For kind=solution, copy the printed correct-option label when visible and the worked solution "
        "into teacher_solution_markdown. Preserve digits, decimal marks, signs, units, Latin letters "
        "and equations faithfully with Markdown/LaTeX. Do not include author names, solver names, "
        "book/page citations, URLs, or invented Markdown image links. A visual flag never authorizes "
        "removing an existing source visual."
    )


def _target_instruction(decision: RegionRiskDecision) -> str:
    return (
        f"TARGET_ID={decision.target_id}; kind={decision.kind}; "
        f"question_number={decision.question_number}; physical_page={decision.page_number}. "
        "The next image belongs only to this target."
    )


def _image_part(payload: bytes) -> dict[str, Any]:
    return {
        "inlineData": {
            "mimeType": "image/png",
            "data": base64.b64encode(payload).decode("ascii"),
        }
    }


def _response_text(root: Mapping[str, Any]) -> str:
    candidates = root.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], Mapping):
        raise PageBatchEnvelopeError("no_candidate")
    content = candidates[0].get("content")
    if not isinstance(content, Mapping):
        raise PageBatchEnvelopeError("no_candidate_content")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise PageBatchEnvelopeError("no_content_parts")
    values = [str(part.get("text") or "") for part in parts if isinstance(part, Mapping)]
    text = "".join(values).strip()
    if not text:
        raise PageBatchEnvelopeError("empty_content")
    return text


def _usage(root: Mapping[str, Any]) -> dict[str, int]:
    value = root.get("usageMetadata")
    value = value if isinstance(value, Mapping) else {}
    return {
        "inputTokens": int(value.get("promptTokenCount") or 0),
        "outputTokens": int(value.get("candidatesTokenCount") or 0),
        "reasoningTokens": int(value.get("thoughtsTokenCount") or 0),
        "totalTokens": int(value.get("totalTokenCount") or 0),
    }


def _estimated_cost(root: Mapping[str, Any]) -> dict[str, float]:
    value = root.get("estimated_cost")
    value = value if isinstance(value, Mapping) else {}
    out: dict[str, float] = {}
    for source, target in (("unit", "unit"), ("irt", "irt")):
        try:
            out[target] = float(value.get(source) or 0)
        except (TypeError, ValueError):
            out[target] = 0.0
    return out


@dataclass(frozen=True, slots=True)
class PageBatchResult:
    page_number: int
    model: str
    items: tuple[BatchItem, ...]
    request_id: str
    usage: dict[str, int]
    estimated_cost: dict[str, float]
    requested_target_ids: tuple[str, ...] = ()
    missing_target_ids: tuple[str, ...] = ()
    invalid_target_ids: tuple[str, ...] = ()

    def safe_dict(self) -> dict[str, Any]:
        requested = self.requested_target_ids or tuple(item.target_id for item in self.items)
        return {
            "pageNumber": self.page_number,
            "model": self.model,
            "targetCount": len(requested),
            "returnedTargetCount": len(self.items),
            "targetIds": list(requested),
            "missingTargetIds": list(self.missing_target_ids),
            "invalidTargetIds": list(self.invalid_target_ids),
            "partial": bool(self.missing_target_ids or self.invalid_target_ids),
            "requestId": self.request_id,
            **self.usage,
            "estimatedCostUnit": float(self.estimated_cost.get("unit") or 0),
            "estimatedCostIrt": float(self.estimated_cost.get("irt") or 0),
        }


def _validate_items(
    raw: Any,
    *,
    decisions: Sequence[RegionRiskDecision],
) -> tuple[tuple[BatchItem, ...], tuple[str, ...], tuple[str, ...]]:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("items"), list):
        raise PageBatchEnvelopeError("invalid_items_envelope")
    expected = {item.target_id: item for item in decisions}
    returned: dict[str, BatchItem] = {}
    invalid: set[str] = set()
    for raw_item in raw.get("items") or []:
        if not isinstance(raw_item, Mapping):
            continue
        target_id = str(raw_item.get("target_id") or "").strip()
        decision = expected.get(target_id)
        if not target_id or decision is None or target_id in returned:
            # Unexpected/duplicate content cannot poison valid expected siblings.
            continue
        try:
            item = BatchItem.model_validate(raw_item)
        except ValidationError:
            invalid.add(target_id)
            continue
        if item.kind != decision.kind or item.question_number != decision.question_number:
            invalid.add(target_id)
            continue
        returned[target_id] = item
    ordered = tuple(returned[item.target_id] for item in decisions if item.target_id in returned)
    missing = tuple(
        item.target_id
        for item in decisions
        if item.target_id not in returned and item.target_id not in invalid
    )
    invalid_ids = tuple(item.target_id for item in decisions if item.target_id in invalid)
    return ordered, missing, invalid_ids


def transcribe_page_batch(
    *,
    page_number: int,
    targets: Sequence[tuple[RegionRiskDecision, bytes]],
    model: str | None = None,
) -> PageBatchResult:
    """Make exactly one Gemini request and preserve every independently valid item."""

    if page_number < 1 or not targets:
        raise ValueError("A positive page and at least one batch target are required.")
    decisions = [item[0] for item in targets]
    if any(item.page_number != page_number for item in decisions):
        raise ValueError("All batch targets must belong to the same physical page.")
    if len({item.target_id for item in decisions}) != len(decisions):
        raise ValueError("Batch target ids must be unique.")
    if any(not payload for _decision, payload in targets):
        raise ValueError("Every batch target requires a non-empty PNG crop.")

    selected_model = str(model or _model()).strip()
    parts: list[dict[str, Any]] = [
        {
            "text": (
                f"Physical source page {page_number}. Return one independent item for each "
                f"of these {len(targets)} TARGET_ID values. Keep ids exactly as supplied."
            )
        }
    ]
    for decision, payload in targets:
        parts.append({"text": _target_instruction(decision)})
        parts.append(_image_part(payload))

    # Field-level output is materially shorter than free transcription. Keeping
    # this bounded also constrains the maximum cost of a malformed verbose reply.
    maximum = max(3200, min(9000, 1600 + 1050 * len(targets)))
    body = {
        "systemInstruction": {"parts": [{"text": _system_prompt()}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "thinkingConfig": {"thinkingLevel": "minimal"},
            "maxOutputTokens": maximum,
            "responseMimeType": "application/json",
            "responseSchema": _response_schema(),
        },
    }
    response = requests.post(
        f"{_base_url()}/v1beta/models/{selected_model}:generateContent",
        headers={
            "x-goog-api-key": _api_key(),
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=_timeout(),
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
    try:
        decoded = json.loads(_response_text(root))
    except PageBatchEnvelopeError as exc:
        raise PageBatchEnvelopeError(
            exc.reason_code,
            usage=_usage(root),
            estimated_cost=_estimated_cost(root),
            request_id=request_id,
        ) from exc
    except json.JSONDecodeError as exc:
        raise PageBatchEnvelopeError(
            "structured_json_invalid",
            usage=_usage(root),
            estimated_cost=_estimated_cost(root),
            request_id=request_id,
        ) from exc
    items, missing, invalid = _validate_items(decoded, decisions=decisions)

    return PageBatchResult(
        page_number=page_number,
        model=selected_model,
        items=items,
        request_id=request_id,
        usage=_usage(root),
        estimated_cost=_estimated_cost(root),
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
    "transcribe_page_batch",
]
