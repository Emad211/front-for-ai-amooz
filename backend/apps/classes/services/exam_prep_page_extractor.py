"""Single-page extractor for the simple page-first exam-prep pipeline."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import re
import time

from PIL import UnidentifiedImageError

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.services.exam_prep_page_quality import (
    choose_better_page_extraction,
    page_is_answer_heavy,
    reconcile_page_extraction,
    summarize_page_quality,
)
from apps.classes.services.exam_prep_page_records import PageExtraction, PageRecord
from apps.classes.services.exam_prep_page_regions import (
    last_record_number,
    merge_page_region_extractions,
    split_vertical_columns,
)
from apps.classes.services.exam_prep_text_quality import (
    context_head,
    context_tail,
    native_text_for_model,
)
from apps.classes.services.exam_prep_utils import clean_exam_markdown
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import StructuredOutputError, generate_structured


logger = logging.getLogger("apps.classes.exam_prep")
_SUPPORTED_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_ANSWER_ONLY_HEADING_RE = re.compile(
    r"^\s*[-–—ـ]*\s*"
    r"(?:(?:س[ؤو]ال)\s*)?"
    r"(?P<number>[0-9۰-۹٠-٩]+)?\s*[-–—ـ.:：)\]]*\s*"
    r"(?:(?:پاسخ)\s*(?:صحیح|درست)?\s*[:：\-–—]*\s*)?"
    r"(?:گزین[ههۀ])\s*[«»\"'()\[\]]*\s*"
    r"(?P<label>[0-9۰-۹٠-٩]+|[الفبجده])"
    r"\s*[«»\"'()\[\]]*\s*"
    r"(?P<remainder>.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)


class ExamPrepPageConfigurationError(RuntimeError):
    """Raised when no multimodal model is configured."""


class InvalidRenderedExamPage(ValueError):
    """Raised before a provider call when page input is invalid."""


class ExtractedPageNumberMismatch(RuntimeError):
    """Raised when a provider attributes output to another page."""


@dataclass(frozen=True, slots=True)
class RenderedExamPage:
    page_number: int
    image: bytes
    mime_type: str = "image/png"
    native_text: str = ""
    previous_native_text: str = ""
    next_native_text: str = ""
    right_column_native_text: str = ""
    left_column_native_text: str = ""


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _bounded_non_negative_int_env(
    name: str,
    default: int,
    maximum: int,
) -> int:
    try:
        return max(0, min(maximum, int(os.getenv(name, str(default)))))
    except (TypeError, ValueError):
        return default


def _positive_float_env(name: str, default: float) -> float:
    try:
        return max(1.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _truthy_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_answer_label(value: str) -> str:
    text = clean_exam_markdown(value).translate(_DIGIT_TRANSLATION).strip()
    return str(int(text)) if text.isdigit() else text[:32]


def _sanitize_answer_only_records(result: PageExtraction) -> PageExtraction:
    """Convert a printed answer heading misclassified as a question."""

    records: list[PageRecord] = []
    changed = False
    for record in result.records:
        text = clean_exam_markdown(record.question_text_markdown)
        if len(record.options) >= 2 or not text:
            records.append(record)
            continue
        match = _ANSWER_ONLY_HEADING_RE.match(text)
        if match is None:
            records.append(record)
            continue
        printed_number = match.group("number")
        if printed_number:
            number = int(printed_number.translate(_DIGIT_TRANSLATION))
            if number != record.question_number:
                records.append(record)
                continue
        label = _normalize_answer_label(match.group("label"))
        remainder = clean_exam_markdown(match.group("remainder")).lstrip(
            " \t\r\n:：-–—"
        )
        solution = clean_exam_markdown(record.teacher_solution_markdown) or remainder
        records.append(
            record.model_copy(
                update={
                    "record_type": (
                        "solution"
                        if solution or record.final_answer_markdown
                        else "answer"
                    ),
                    "question_text_markdown": "",
                    "options": [],
                    "correct_option_label": record.correct_option_label or label,
                    "teacher_solution_markdown": solution,
                }
            )
        )
        changed = True
    return result.model_copy(update={"records": records}) if changed else result


def select_exam_prep_page_model(explicit_model: str | None = None) -> str:
    model = (
        (explicit_model or "").strip()
        or (os.getenv("EXAM_PREP_PAGE_MODEL") or "").strip()
        or (os.getenv("PDF_VISION_MODEL") or "").strip()
        or (os.getenv("MODEL_NAME") or "").strip()
    )
    if not model:
        raise ExamPrepPageConfigurationError(
            "Set EXAM_PREP_PAGE_MODEL, PDF_VISION_MODEL, or MODEL_NAME."
        )
    return model.removeprefix("models/")


def _validate_page(page: RenderedExamPage) -> str:
    if page.page_number < 1:
        raise InvalidRenderedExamPage("page_number must be one-based.")
    if not isinstance(page.image, bytes) or not page.image:
        raise InvalidRenderedExamPage("Rendered page image bytes are required.")
    mime_type = (page.mime_type or "").strip().lower()
    if mime_type == "image/jpg":
        mime_type = "image/jpeg"
    if mime_type not in _SUPPORTED_IMAGE_TYPES:
        raise InvalidRenderedExamPage(
            f"Unsupported rendered page MIME type: {mime_type or '(empty)'} ."
        )
    max_bytes = _positive_int_env(
        "EXAM_PREP_PAGE_MAX_IMAGE_BYTES",
        10 * 1024 * 1024,
    )
    if len(page.image) > max_bytes:
        raise InvalidRenderedExamPage(
            f"Rendered page image exceeds the {max_bytes}-byte limit."
        )
    return mime_type


def _native_text_evidence(page: RenderedExamPage) -> str:
    return native_text_for_model(
        page.native_text,
        max_chars=_positive_int_env(
            "EXAM_PREP_PAGE_NATIVE_TEXT_MAX_CHARS",
            30_000,
        ),
    )


def _page_messages(
    *,
    page: RenderedExamPage,
    mime_type: str,
    scope_hint: str,
    quality_pass: int,
    repair_codes: tuple[str, ...] = (),
    region: str = "full_page",
    continuation_hint: int | None = None,
) -> list[dict]:
    native_text = _native_text_evidence(page)
    previous_context = context_tail(page.previous_native_text)
    next_context = context_head(page.next_native_text)
    repair_instruction = ""
    if quality_pass > 0:
        codes = ", ".join(dict.fromkeys(repair_codes)) or "semantic_quality"
        repair_instruction = (
            "\nThis is a quality-repair pass. The previous schema-valid result "
            f"failed these semantic checks: {codes}. Re-read the original source "
            "and return a complete replacement. Do not copy poisoned native text."
        )
    native_instruction = (
        "\nNATIVE_TEXT_EVIDENCE_BEGIN\n"
        f"{native_text}\n"
        "NATIVE_TEXT_EVIDENCE_END\n"
        "Use this only when coherent; the image controls columns and grouping."
        if native_text
        else "\nNo trustworthy native text was available; rely on the image."
    )
    neighbor_instruction = (
        "\nPREVIOUS_PAGE_CONTEXT_BEGIN\n"
        f"{previous_context}\n"
        "PREVIOUS_PAGE_CONTEXT_END\n"
        "NEXT_PAGE_CONTEXT_BEGIN\n"
        f"{next_context}\n"
        "NEXT_PAGE_CONTEXT_END\n"
        "Neighbor context is only for continuation detection. "
        "Never extract a new record from it."
    )
    hint = str(continuation_hint) if continuation_hint else "none"
    return [
        {
            "role": "system",
            "content": PROMPTS["exam_prep_page_extraction"]["default"],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"PAGE_NUMBER: {page.page_number}\n"
                        f"REGION: {region}\n"
                        f"SCOPE_HINT: {scope_hint}\n"
                        f"CONTINUATION_HINT: {hint}\n"
                        f"QUALITY_PASS: {quality_pass}\n"
                        "Extract only records visibly supported by the current "
                        "image region."
                        f"{repair_instruction}{native_instruction}"
                        f"{neighbor_instruction}"
                    ),
                },
                part_from_bytes(data=page.image, mime_type=mime_type),
            ],
        },
    ]


def _tracking_context(
    *,
    page_number: int,
    quality_pass: int,
    region: str,
) -> dict[str, int | str]:
    context: dict[str, int | str] = {
        "stage": (
            "page_extraction"
            if quality_pass == 0
            else "page_quality_repair"
        ),
        "page_number": page_number,
        "region": region,
    }
    if quality_pass > 0:
        context["quality_pass"] = quality_pass
    return context


def _generate_page(
    *,
    page: RenderedExamPage,
    mime_type: str,
    model: str,
    scope_hint: str,
    quality_pass: int,
    repair_codes: tuple[str, ...] = (),
    region: str = "full_page",
    continuation_hint: int | None = None,
) -> PageExtraction:
    result = generate_structured(
        schema=PageExtraction,
        messages=_page_messages(
            page=page,
            mime_type=mime_type,
            scope_hint=scope_hint,
            quality_pass=quality_pass,
            repair_codes=repair_codes,
            region=region,
            continuation_hint=continuation_hint,
        ),
        model=model,
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        timeout=_positive_float_env(
            "EXAM_PREP_PAGE_TIMEOUT_SECONDS",
            180.0,
        ),
        temperature=0,
        max_repair=_bounded_non_negative_int_env(
            "EXAM_PREP_PAGE_REPAIR_ATTEMPTS",
            1,
            2,
        ),
        strict_json_schema=True,
        sensitive=True,
        max_output_tokens=_positive_int_env(
            "EXAM_PREP_PAGE_MAX_OUTPUT_TOKENS",
            12_000,
        ),
        detail=(
            "exam_prep_page_extraction"
            if region == "full_page" and quality_pass == 0
            else "exam_prep_page_region_extraction"
            if quality_pass == 0
            else "exam_prep_page_quality_repair"
        ),
        tracking_context=_tracking_context(
            page_number=page.page_number,
            quality_pass=quality_pass,
            region=region,
        ),
        provider_attempts=1,
    )
    if result.page_number != page.page_number:
        raise ExtractedPageNumberMismatch(
            f"Expected page {page.page_number}, received page {result.page_number}."
        )
    return reconcile_page_extraction(
        _sanitize_answer_only_records(result),
        native_text=page.native_text,
    )


def _has_explicit_answer_content(page: PageExtraction) -> bool:
    explicit = sum(
        record.record_type in {"answer", "solution"}
        for record in page.records
    )
    rich_solution = any(
        len(clean_exam_markdown(record.teacher_solution_markdown)) >= 24
        for record in page.records
    )
    return explicit >= 2 or rich_solution


def _extract_answer_columns(
    page: RenderedExamPage,
    *,
    full_page_result: PageExtraction,
    model: str,
    scope_hint: str,
    continuation_hint: int | None,
) -> tuple[PageExtraction, int]:
    if not _truthy_env("EXAM_PREP_SPLIT_ANSWER_COLUMNS_ENABLED", True):
        return full_page_result, 0
    if not _has_explicit_answer_content(full_page_result):
        return full_page_result, 0
    if not page_is_answer_heavy(full_page_result, native_text=page.native_text):
        return full_page_result, 0
    try:
        crops = split_vertical_columns(
            page.image,
            right_native_text=page.right_column_native_text,
            left_native_text=page.left_column_native_text,
        )
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning(
            "exam_prep.page.column_crop_failed pageNumber=%s errorCode=%s",
            page.page_number,
            type(exc).__name__,
        )
        return full_page_result, 0

    region_results: list[PageExtraction] = []
    hint = continuation_hint
    for crop in crops:
        region_page = RenderedExamPage(
            page_number=page.page_number,
            image=crop.image,
            mime_type="image/png",
            native_text=crop.native_text,
            previous_native_text=(
                page.previous_native_text
                if crop.region == "right_column"
                else ""
            ),
            next_native_text=(
                page.next_native_text
                if crop.region == "left_column"
                else ""
            ),
        )
        try:
            region_result = _generate_page(
                page=region_page,
                mime_type="image/png",
                model=model,
                scope_hint=scope_hint,
                quality_pass=0,
                region=crop.region,
                continuation_hint=hint,
            )
        except (StructuredOutputError, ExtractedPageNumberMismatch) as exc:
            logger.warning(
                "exam_prep.page.column_failed pageNumber=%s region=%s "
                "errorKind=%s",
                page.page_number,
                crop.region,
                getattr(exc, "error_kind", type(exc).__name__),
            )
            continue
        region_results.append(region_result)
        hint = last_record_number(region_result) or hint
    if not region_results:
        return full_page_result, 0
    merged = merge_page_region_extractions(
        full_page_result,
        region_results,
    )
    return (
        reconcile_page_extraction(merged, native_text=page.native_text),
        len(region_results),
    )


def extract_exam_prep_page(
    page: RenderedExamPage,
    *,
    model: str | None = None,
    scope_hint: str = "default",
    continuation_hint: int | None = None,
) -> PageExtraction:
    """Extract one page with small neighbor context and targeted column reads."""

    started_at = time.monotonic()
    mime_type = _validate_page(page)
    selected_model = select_exam_prep_page_model(model)
    safe_scope_hint = str(scope_hint or "default").strip()[:160] or "default"

    result = _generate_page(
        page=page,
        mime_type=mime_type,
        model=selected_model,
        scope_hint=safe_scope_hint,
        quality_pass=0,
        continuation_hint=continuation_hint,
    )
    result, column_calls = _extract_answer_columns(
        page,
        full_page_result=result,
        model=selected_model,
        scope_hint=safe_scope_hint,
        continuation_hint=continuation_hint,
    )
    quality = summarize_page_quality(result)
    repair_calls = 0
    maximum_repairs = _bounded_non_negative_int_env(
        "EXAM_PREP_PAGE_QUALITY_REPAIR_ATTEMPTS",
        1,
        2,
    )
    for quality_pass in range(1, maximum_repairs + 1):
        if quality.repairable_critical_count < 1:
            break
        try:
            candidate = _generate_page(
                page=page,
                mime_type=mime_type,
                model=selected_model,
                scope_hint=safe_scope_hint,
                quality_pass=quality_pass,
                repair_codes=quality.repairable_critical_codes,
                continuation_hint=continuation_hint,
            )
        except (StructuredOutputError, ExtractedPageNumberMismatch) as exc:
            logger.warning(
                "exam_prep.page.quality_repair_failed pageNumber=%s pass=%s "
                "errorKind=%s",
                page.page_number,
                quality_pass,
                getattr(exc, "error_kind", type(exc).__name__),
            )
            break
        repair_calls += 1
        result = choose_better_page_extraction(result, candidate)
        quality = summarize_page_quality(result)

    logger.info(
        "exam_prep.page.completed pageNumber=%s model=%s durationMs=%s "
        "imageBytes=%s nativeTextChars=%s recordCount=%s questionCount=%s "
        "criticalIssueCount=%s repairableCriticalCount=%s "
        "qualityRepairCalls=%s columnCalls=%s",
        page.page_number,
        selected_model,
        int((time.monotonic() - started_at) * 1000),
        len(page.image),
        len(page.native_text or ""),
        len(result.records),
        quality.question_count,
        quality.critical_count,
        quality.repairable_critical_count,
        repair_calls,
        column_calls,
    )
    return result
