"""Cost-bounded page extractor routed by deterministic local layout signals."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import logging
import os
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.chatbot.services.llm_client import part_from_bytes
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import StructuredOutputError, generate_structured

from .exam_prep_page_extractor import (
    ExtractedPageNumberMismatch,
    RenderedExamPage,
    _sanitize_answer_only_records,
    _validate_page,
    select_exam_prep_page_model,
)
from .exam_prep_page_layout import PageLayoutDecision, classify_exam_page
from .exam_prep_page_quality import reconcile_page_extraction
from .exam_prep_page_regions import merge_page_region_extractions, split_vertical_columns
from .exam_prep_page_source import (
    SourcePageExtraction,
    SourcePageRecord,
    ensure_source_extraction,
    remap_extraction_bboxes,
)
from .exam_prep_text_quality import context_head, context_tail, native_text_for_model
from .exam_prep_utils import clean_exam_markdown


logger = logging.getLogger("apps.classes.exam_prep")
_RUNTIME_STATS: ContextVar[dict[int, list[dict[str, Any]]]] = ContextVar(
    "exam_prep_page_runtime_stats",
    default={},
)


class LoosePageRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scope_key: Any = "default"
    question_number: Any = None
    record_type: Any = ""
    question_text_markdown: Any = ""
    options: Any = Field(default_factory=list)
    correct_option_label: Any = None
    correct_option_text_markdown: Any = ""
    teacher_solution_markdown: Any = ""
    final_answer_markdown: Any = ""
    continues_from_previous_page: Any = False
    continues_on_next_page: Any = False
    confidence: Any = 0.0
    issues: Any = Field(default_factory=list)
    source_bbox: Any = None


class LooseSourcePageExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page_number: Any
    records: list[LoosePageRecord] = Field(default_factory=list)


@dataclass(slots=True)
class _CallBudget:
    provider_calls: int = 0
    retry_calls: int = 0
    column_calls: int = 0
    quarantined_records: int = 0


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _positive_float_env(name: str, default: float) -> float:
    try:
        return max(1.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _record_runtime(page_number: int, payload: dict[str, Any]) -> None:
    current = {key: list(value) for key, value in _RUNTIME_STATS.get().items()}
    current.setdefault(page_number, []).append(payload)
    _RUNTIME_STATS.set(current)


def consume_page_runtime_stats(page_number: int) -> list[dict[str, Any]]:
    current = {key: list(value) for key, value in _RUNTIME_STATS.get().items()}
    values = current.pop(page_number, [])
    _RUNTIME_STATS.set(current)
    return values


def _tracking_context(page_number: int, region: str) -> dict[str, int | str]:
    return {
        "stage": "page_extraction",
        "page_number": page_number,
        "region": region,
        "layout_routed": 1,
    }


def _text_instruction(page: RenderedExamPage, *, native_text: str, region: str) -> str:
    native = native_text_for_model(native_text, max_chars=30_000)
    previous = context_tail(page.previous_native_text)
    following = context_head(page.next_native_text)
    evidence = (
        "NATIVE_TEXT_EVIDENCE_BEGIN\n"
        f"{native}\n"
        "NATIVE_TEXT_EVIDENCE_END\n"
        if native
        else "No trustworthy native text is available.\n"
    )
    return (
        f"PAGE_NUMBER: {page.page_number}\n"
        f"REGION: {region}\n"
        "Extract only numbered question/answer records visibly supported by this page.\n"
        "A cover, instruction, separator, or blank region must return records=[].\n"
        "Never invent question numbers. Invalid non-record decorations must be omitted.\n"
        f"{evidence}"
        "PREVIOUS_PAGE_CONTEXT_BEGIN\n"
        f"{previous}\n"
        "PREVIOUS_PAGE_CONTEXT_END\n"
        "NEXT_PAGE_CONTEXT_BEGIN\n"
        f"{following}\n"
        "NEXT_PAGE_CONTEXT_END\n"
        "Neighbor context is only for continuation detection."
    )


def _coerce_page_number(value: Any) -> int:
    text = str(value or "").translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    digits = "".join(char for char in text if char.isdigit())
    return int(digits) if digits else 0


def _substantive_loose_record(record: LoosePageRecord) -> bool:
    return bool(
        clean_exam_markdown(record.question_text_markdown or "")
        or clean_exam_markdown(record.teacher_solution_markdown or "")
        or clean_exam_markdown(record.final_answer_markdown or "")
        or record.options
    )


def _normalize_loose_result(
    raw: LooseSourcePageExtraction,
    *,
    expected_page_number: int,
    budget: _CallBudget,
) -> SourcePageExtraction:
    page_number = _coerce_page_number(raw.page_number)
    if page_number != expected_page_number:
        raise ExtractedPageNumberMismatch(
            f"Expected page {expected_page_number}, received {page_number or raw.page_number}."
        )
    records: list[SourcePageRecord] = []
    for loose in raw.records:
        payload = loose.model_dump()
        try:
            records.append(SourcePageRecord.model_validate(payload))
        except (TypeError, ValueError):
            if _substantive_loose_record(loose):
                budget.quarantined_records += 1
                logger.warning(
                    "exam_prep.page.record_quarantined pageNumber=%s rawQuestionNumber=%r",
                    expected_page_number,
                    loose.question_number,
                )
    result = SourcePageExtraction(page_number=expected_page_number, records=records)
    return ensure_source_extraction(
        reconcile_page_extraction(
            _sanitize_answer_only_records(result),
            native_text="",
        )
    )


def _generate_once(
    *,
    page: RenderedExamPage,
    model: str,
    region: str,
    native_text: str,
    image_parts: list[dict[str, Any]],
    budget: _CallBudget,
) -> SourcePageExtraction:
    budget.provider_calls += 1
    raw = generate_structured(
        schema=LooseSourcePageExtraction,
        messages=[
            {
                "role": "system",
                "content": PROMPTS["exam_prep_page_extraction"]["default"],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _text_instruction(
                            page,
                            native_text=native_text,
                            region=region,
                        ),
                    },
                    *image_parts,
                ],
            },
        ],
        model=model,
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        timeout=_positive_float_env("EXAM_PREP_PAGE_TIMEOUT_SECONDS", 180.0),
        temperature=0,
        max_repair=0,
        strict_json_schema=True,
        sensitive=True,
        max_output_tokens=_positive_int_env(
            "EXAM_PREP_PAGE_MAX_OUTPUT_TOKENS",
            12_000,
        ),
        detail="exam_prep_page_layout_routed_extraction",
        tracking_context=_tracking_context(page.page_number, region),
        provider_attempts=1,
    )
    return _normalize_loose_result(
        raw,
        expected_page_number=page.page_number,
        budget=budget,
    )


def _extract_single(
    page: RenderedExamPage,
    *,
    mime_type: str,
    model: str,
    budget: _CallBudget,
) -> SourcePageExtraction:
    return _generate_once(
        page=page,
        model=model,
        region="full_page",
        native_text=page.native_text,
        image_parts=[part_from_bytes(data=page.image, mime_type=mime_type)],
        budget=budget,
    )


def _extract_uncertain(
    page: RenderedExamPage,
    *,
    mime_type: str,
    model: str,
    budget: _CallBudget,
) -> SourcePageExtraction:
    right, left = split_vertical_columns(
        page.image,
        right_native_text=page.right_column_native_text,
        left_native_text=page.left_column_native_text,
    )
    instruction = {
        "type": "text",
        "text": (
            "LAYOUT_IS_UNCERTAIN. The first image is the complete page and controls "
            "reading order. The next images are right and left close-ups only for "
            "legibility. Extract every record once; never duplicate content seen in "
            "more than one image. Return bounding boxes in full-page coordinates."
        ),
    }
    return _generate_once(
        page=page,
        model=model,
        region="uncertain_full_plus_columns",
        native_text=page.native_text,
        image_parts=[
            instruction,
            part_from_bytes(data=page.image, mime_type=mime_type),
            {"type": "text", "text": "RIGHT_COLUMN_CLOSEUP"},
            part_from_bytes(data=right.image, mime_type="image/png"),
            {"type": "text", "text": "LEFT_COLUMN_CLOSEUP"},
            part_from_bytes(data=left.image, mime_type="image/png"),
        ],
        budget=budget,
    )


def _extract_double(
    page: RenderedExamPage,
    *,
    model: str,
    budget: _CallBudget,
) -> SourcePageExtraction:
    crops = split_vertical_columns(
        page.image,
        right_native_text=page.right_column_native_text,
        left_native_text=page.left_column_native_text,
    )
    results: list[SourcePageExtraction] = []
    first_error: Exception | None = None
    for crop in crops:
        budget.column_calls += 1
        region_page = RenderedExamPage(
            page_number=page.page_number,
            image=crop.image,
            mime_type="image/png",
            native_text=crop.native_text,
            previous_native_text=(
                page.previous_native_text if crop.region == "right_column" else ""
            ),
            next_native_text=(
                page.next_native_text if crop.region == "left_column" else ""
            ),
        )
        for attempt in range(2):
            try:
                result = _generate_once(
                    page=region_page,
                    model=model,
                    region=crop.region,
                    native_text=crop.native_text,
                    image_parts=[
                        part_from_bytes(data=crop.image, mime_type="image/png")
                    ],
                    budget=budget,
                )
                results.append(
                    remap_extraction_bboxes(
                        result,
                        region_x0=crop.page_x0,
                        region_x1=crop.page_x1,
                    )
                )
                break
            except (StructuredOutputError, ExtractedPageNumberMismatch) as exc:
                first_error = first_error or exc
                if attempt == 0:
                    budget.retry_calls += 1
                    continue
                logger.warning(
                    "exam_prep.page.column_failed pageNumber=%s region=%s "
                    "errorCode=%s",
                    page.page_number,
                    crop.region,
                    getattr(exc, "error_kind", type(exc).__name__),
                )
    if not results:
        if first_error is not None:
            raise first_error
        raise StructuredOutputError(
            "Both column extractions failed.",
            error_kind="column_extraction_failed",
        )
    empty = SourcePageExtraction(page_number=page.page_number, records=[])
    return merge_page_region_extractions(empty, results)


def extract_exam_prep_page(
    page: RenderedExamPage,
    *,
    model: str | None = None,
    scope_hint: str = "default",
    continuation_hint: int | None = None,
) -> SourcePageExtraction:
    """Extract one page using the locally selected zero/one/two-call route."""

    del scope_hint, continuation_hint
    started = time.monotonic()
    mime_type = _validate_page(page)
    selected_model = select_exam_prep_page_model(model)
    decision: PageLayoutDecision = classify_exam_page(
        image=page.image,
        native_text=page.native_text,
        right_native_text=page.right_column_native_text,
        left_native_text=page.left_column_native_text,
    )
    budget = _CallBudget()
    try:
        if decision.skipped_non_content:
            result = SourcePageExtraction(page_number=page.page_number, records=[])
        elif decision.layout == "double":
            result = _extract_double(page, model=selected_model, budget=budget)
        elif decision.layout == "single":
            result = _extract_single(
                page,
                mime_type=mime_type,
                model=selected_model,
                budget=budget,
            )
        else:
            result = _extract_uncertain(
                page,
                mime_type=mime_type,
                model=selected_model,
                budget=budget,
            )
        return ensure_source_extraction(
            reconcile_page_extraction(result, native_text=page.native_text)
        )
    finally:
        payload = {
            "contentClassification": decision.content_class,
            "layoutDecision": decision.layout,
            "layoutConfidence": decision.confidence,
            "classificationReasons": list(decision.reasons),
            "providerCallCount": budget.provider_calls,
            "retryCalls": budget.retry_calls,
            "columnCalls": budget.column_calls,
            "quarantinedRecords": budget.quarantined_records,
            "skippedNonContent": decision.skipped_non_content,
            "durationMs": int((time.monotonic() - started) * 1000),
        }
        _record_runtime(page.page_number, payload)
        logger.info(
            "exam_prep.page.routed pageNumber=%s contentClassification=%s "
            "layoutDecision=%s layoutConfidence=%.2f providerCallCount=%s "
            "retryCalls=%s columnCalls=%s quarantinedRecords=%s "
            "skippedNonContent=%s durationMs=%s reasons=%s",
            page.page_number,
            decision.content_class,
            decision.layout,
            decision.confidence,
            budget.provider_calls,
            budget.retry_calls,
            budget.column_calls,
            budget.quarantined_records,
            decision.skipped_non_content,
            payload["durationMs"],
            ",".join(decision.reasons),
        )
