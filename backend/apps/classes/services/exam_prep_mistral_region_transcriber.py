"""One-region/one-image source transcription for Stage 4.

The previous Mistral candidate is intentionally never included in provider
messages.  Every invocation makes exactly one OpenAI-compatible AvalAI request,
with SDK retries forced to zero and no structured-output repair pass.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Literal, Mapping

from apps.chatbot.services.llm_client import (
    _get_gapgpt_client,
    _strip_model_prefix,
    part_from_bytes,
)
from apps.classes.services.exam_prep_mistral_direct_transcription import (
    DirectTranscription,
    normalize_direct_transcription,
)
from apps.commons.json_utils import extract_json_object
from apps.commons.models import LLMUsageLog
from apps.commons.token_tracker import LLMTimer, track_llm_error, track_llm_usage


DEFAULT_PRIMARY_MODEL = "gemini-3-flash-preview"
DEFAULT_SECONDARY_MODEL = "gpt-5.4-mini"


def primary_model() -> str:
    return _strip_model_prefix(
        (os.getenv("EXAM_PREP_STAGE4_PRIMARY_MODEL") or DEFAULT_PRIMARY_MODEL).strip()
    )


def secondary_model() -> str:
    return _strip_model_prefix(
        (os.getenv("EXAM_PREP_STAGE4_SECONDARY_MODEL") or DEFAULT_SECONDARY_MODEL).strip()
    )


def _timeout() -> float:
    try:
        value = float(os.getenv("EXAM_PREP_STAGE4_TIMEOUT_SECONDS", "240"))
    except (TypeError, ValueError):
        value = 240.0
    return max(30.0, min(600.0, value))


def _max_tokens() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_MAX_OUTPUT_TOKENS", "6000"))
    except (TypeError, ValueError):
        value = 6000
    return max(1000, min(12000, value))


def _minimal_extra_body() -> dict[str, Any]:
    """Exact AvalAI Gemini minimal-thinking shape proven by the prior probe."""

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
        "There is exactly ONE target region and exactly ONE source image. The IMAGE is the only "
        "source of truth. A previous OCR candidate exists but is intentionally hidden from you. "
        "Transcribe only what is visibly present; do not solve, explain, normalize from subject "
        "knowledge, or guess unreadable glyphs. Preserve Persian text, digits, decimal marks, "
        "signs, units, option labels, Latin letters, and equations. Use Markdown/LaTeX for linear "
        "text and formulas. If a graph, circuit, chemical structure, table, diagram, or other "
        "spatial visual carries information, set source_visual_required=true instead of inventing "
        "a textual replacement. If any source glyph is genuinely unreadable, set "
        "transcription_uncertain=true and list only short uncertain fragments. Ignore only thin "
        "neighboring strips caused by bounded crop padding. Return ONLY one valid JSON object."
    )


def _user_contract(*, kind: str, question_number: int, page_number: int) -> str:
    return (
        "Return exactly these top-level JSON keys: "
        '{"transcription_markdown":"faithful visible transcription",'
        '"source_visual_required":true,'
        '"visual_type":"none|diagram|graph|chemical_structure|table|spatial_layout|other",'
        '"transcription_uncertain":false,'
        '"uncertain_fragments":[]}. '
        "Do not add confidence scores. Do not infer missing content. "
        f"TARGET kind={kind} question_number={question_number} physical_page={page_number}."
    )


@dataclass(frozen=True, slots=True)
class RegionTranscriptionResult:
    kind: Literal["question", "solution"]
    question_number: int
    page_number: int
    model: str
    transcript: dict[str, Any]
    response_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    reasoning_tokens: int

    def safe_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "questionNumber": self.question_number,
            "pageNumber": self.page_number,
            "model": self.model,
            "responseId": self.response_id,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "totalTokens": self.total_tokens,
            "reasoningTokens": self.reasoning_tokens,
            "sourceVisualRequired": bool(self.transcript.get("sourceVisualRequired")),
            "visualType": str(self.transcript.get("visualType") or "none"),
            "transcriptionUncertain": bool(self.transcript.get("transcriptionUncertain")),
        }


def _usage(response: Any) -> tuple[int, int, int, int]:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
    details = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = int(getattr(details, "reasoning_tokens", 0) or 0)
    return input_tokens, output_tokens, total_tokens, reasoning_tokens


def transcribe_source_region(
    *,
    image: bytes,
    kind: Literal["question", "solution"],
    question_number: int,
    page_number: int,
    model: str,
    thinking_minimal: bool,
) -> RegionTranscriptionResult:
    """Make exactly one source-only provider call and validate its JSON."""

    if not image:
        raise ValueError("A non-empty source region image is required.")
    clean_model = _strip_model_prefix(str(model or "").strip())
    if not clean_model:
        raise ValueError("A Stage-4 model is required.")
    if kind not in {"question", "solution"}:
        raise ValueError("kind must be question or solution")
    if question_number < 1 or page_number < 1:
        raise ValueError("positive question/page numbers are required")

    messages = [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": _user_contract(
                        kind=kind,
                        question_number=question_number,
                        page_number=page_number,
                    ),
                },
                part_from_bytes(data=image, mime_type="image/png"),
            ],
        },
    ]
    create_kwargs: dict[str, Any] = {
        "model": clean_model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "max_tokens": _max_tokens(),
        "timeout": _timeout(),
    }
    if thinking_minimal:
        create_kwargs["extra_body"] = _minimal_extra_body()

    timer = LLMTimer().start()
    context = {
        "stage": "exam_prep_stage4_region_transcription",
        "kind": kind,
        "question_number": question_number,
        "page_number": page_number,
        "image_count": 1,
        "candidate_mistral_shown": False,
        "provider_attempts": 1,
        "thinking_minimal": bool(thinking_minimal),
    }
    try:
        # Force SDK retries off for this call even when a broader environment
        # enables them elsewhere in the application.
        client = _get_gapgpt_client().with_options(max_retries=0)
        response = client.chat.completions.create(**create_kwargs)
        choice = response.choices[0]
        content = str(choice.message.content or "").strip()
        if not content:
            raise ValueError("Stage-4 provider returned empty content.")
        parsed = DirectTranscription.model_validate(extract_json_object(content))
        normalized = normalize_direct_transcription(parsed)
        track_llm_usage(
            resp=response,
            feature=LLMUsageLog.Feature.PDF_EXTRACTION,
            provider="avalai",
            model_name=clean_model,
            detail="exam-prep stage4 source-only region transcription",
            context=context,
            duration_ms=timer.elapsed_ms,
        )
        input_tokens, output_tokens, total_tokens, reasoning_tokens = _usage(response)
        return RegionTranscriptionResult(
            kind=kind,
            question_number=question_number,
            page_number=page_number,
            model=clean_model,
            transcript=normalized,
            response_id=str(getattr(response, "id", "") or ""),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            reasoning_tokens=reasoning_tokens,
        )
    except Exception as exc:
        track_llm_error(
            feature=LLMUsageLog.Feature.PDF_EXTRACTION,
            provider="avalai",
            model_name=clean_model,
            error_message=str(exc),
            detail="exam-prep stage4 source-only region transcription",
            context=context,
            duration_ms=timer.elapsed_ms,
        )
        raise


__all__ = [
    "DEFAULT_PRIMARY_MODEL",
    "DEFAULT_SECONDARY_MODEL",
    "RegionTranscriptionResult",
    "primary_model",
    "secondary_model",
    "transcribe_source_region",
]
