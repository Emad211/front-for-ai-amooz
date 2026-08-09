"""Source-only Gemini page-batch transcription for Stage 4.

All suspicious crops from one physical PDF page are sent in one provider request.
Each crop remains an independent source image and is explicitly labeled with its
target id; the previous Mistral candidate is never sent.

The transport uses AvalAI's native Gemini generateContent endpoint so Gemini's
native JSON response schema can be enforced.  There is no automatic retry or
paid repair pass.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
import re
from typing import Any, Literal, Mapping, Sequence

import requests
from pydantic import BaseModel, Field

from .exam_prep_mistral_risk_engine import RegionRiskDecision
from .exam_prep_utils import clean_exam_markdown


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
    uncertain_fragments: list[str] = Field(default_factory=list, max_length=12)


class BatchResponse(BaseModel):
    items: list[BatchItem] = Field(min_length=1, max_length=12)


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
                        "uncertain_fragments",
                    ],
                },
            }
        },
        "required": ["items"],
    }


def _system_prompt() -> str:
    return (
        "You are a source-faithful transcription engine for Persian high-school exam material. "
        "Every image in this request is an exact crop from ONE physical source page and has an "
        "explicit TARGET_ID immediately before it. The images are the only source of truth. A "
        "previous OCR candidate exists but is intentionally hidden. Never solve, infer, normalize "
        "from subject knowledge, or guess unreadable glyphs. Return one result for every requested "
        "TARGET_ID and no extra targets. For kind=question, copy the visible question text and the "
        "four visible answer choices into question_text_markdown/options; if choices depend on a "
        "diagram, keep their visible labels/text and set source_visual_required=true. For "
        "kind=solution, copy the printed correct option label when visible and the worked solution "
        "into teacher_solution_markdown. Preserve digits, decimal marks, signs, units, Latin letters "
        "and equations faithfully with Markdown/LaTeX. Do not include author names or book/page "
        "citations unless they are part of the mathematical/scientific solution itself. If a glyph "
        "or requested target is genuinely unreadable or absent, set transcription_uncertain=true "
        "and list only short uncertain fragments. A visual flag never authorizes removing an "
        "existing source visual."
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
        raise ValueError("Gemini batch response has no candidate.")
    content = candidates[0].get("content")
    if not isinstance(content, Mapping):
        raise ValueError("Gemini batch response has no candidate content.")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise ValueError("Gemini batch response has no content parts.")
    values = [str(part.get("text") or "") for part in parts if isinstance(part, Mapping)]
    text = "".join(values).strip()
    if not text:
        raise ValueError("Gemini batch response contains no text.")
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

    def safe_dict(self) -> dict[str, Any]:
        return {
            "pageNumber": self.page_number,
            "model": self.model,
            "targetCount": len(self.items),
            "targetIds": [item.target_id for item in self.items],
            "requestId": self.request_id,
            **self.usage,
            "estimatedCostUnit": float(self.estimated_cost.get("unit") or 0),
            "estimatedCostIrt": float(self.estimated_cost.get("irt") or 0),
        }


def transcribe_page_batch(
    *,
    page_number: int,
    targets: Sequence[tuple[RegionRiskDecision, bytes]],
    model: str | None = None,
) -> PageBatchResult:
    """Make exactly one Gemini request for all suspicious crops on one page."""

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
                f"Physical source page {page_number}. Return exactly {len(targets)} items, "
                "one for each TARGET_ID below. Keep target ids exactly as supplied."
            )
        }
    ]
    for decision, payload in targets:
        parts.append({"text": _target_instruction(decision)})
        parts.append(_image_part(payload))

    maximum = max(5000, min(12000, 2500 + 1400 * len(targets)))
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
        raise ValueError("Gemini page-batch provider root is not JSON.") from exc
    if not isinstance(root, Mapping):
        raise ValueError("Gemini page-batch provider root is not an object.")
    try:
        parsed = BatchResponse.model_validate(json.loads(_response_text(root)))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Gemini page-batch structured response is invalid.") from exc

    expected = {item.target_id: item for item in decisions}
    returned: dict[str, BatchItem] = {}
    for item in parsed.items:
        if item.target_id in returned:
            raise ValueError("Gemini page-batch returned a duplicate target id.")
        decision = expected.get(item.target_id)
        if decision is None:
            raise ValueError("Gemini page-batch returned an unexpected target id.")
        if item.kind != decision.kind or item.question_number != decision.question_number:
            raise ValueError("Gemini page-batch target identity mismatch.")
        returned[item.target_id] = item
    if set(returned) != set(expected):
        raise ValueError("Gemini page-batch did not return every requested target.")

    ordered = tuple(returned[item.target_id] for item in decisions)
    return PageBatchResult(
        page_number=page_number,
        model=selected_model,
        items=ordered,
        request_id=request_id,
        usage=_usage(root),
        estimated_cost=_estimated_cost(root),
    )


__all__ = [
    "BatchItem",
    "BatchOption",
    "PageBatchResult",
    "transcribe_page_batch",
]
