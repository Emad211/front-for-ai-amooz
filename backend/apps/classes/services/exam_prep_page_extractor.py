"""Single-page extractor for the simplified exam-preparation pipeline."""
from __future__ import annotations

from dataclasses import dataclass
import os
import re

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.services.exam_prep_page_records import PageExtraction, PageRecord
from apps.classes.services.exam_prep_utils import clean_exam_markdown
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured


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
    """Raised when the page extractor has no configured multimodal model."""


class InvalidRenderedExamPage(ValueError):
    """Raised before a provider call when page input is invalid."""


class ExtractedPageNumberMismatch(RuntimeError):
    """Raised when the model attributes a response to a different page."""


@dataclass(frozen=True, slots=True)
class RenderedExamPage:
    page_number: int
    image: bytes
    mime_type: str = "image/png"


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _non_negative_int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _positive_float_env(name: str, default: float) -> float:
    try:
        return max(1.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _normalize_answer_label(value: str) -> str:
    text = clean_exam_markdown(value).translate(_DIGIT_TRANSLATION).strip()
    if text.isdigit():
        return str(int(text))
    return text[:32]


def _sanitize_answer_only_records(result: PageExtraction) -> PageExtraction:
    """Correct an obvious answer heading even when the model calls it a question.

    This is intentionally narrow: it runs only when there are fewer than two
    options and the text starts with a printed answer heading such as
    ``18- گزینه 3``. Ordinary question stems containing the word ``گزینه`` are
    untouched.
    """

    sanitized: list[PageRecord] = []
    changed = False
    for record in result.records:
        text = clean_exam_markdown(record.question_text_markdown)
        if len(record.options) >= 2 or not text:
            sanitized.append(record)
            continue
        match = _ANSWER_ONLY_HEADING_RE.match(text)
        if match is None:
            sanitized.append(record)
            continue
        printed_number = match.group("number")
        if printed_number:
            normalized_number = int(printed_number.translate(_DIGIT_TRANSLATION))
            if normalized_number != record.question_number:
                sanitized.append(record)
                continue

        label = _normalize_answer_label(match.group("label"))
        remainder = clean_exam_markdown(match.group("remainder")).lstrip(
            " \t\r\n:：-–—"
        )
        solution = clean_exam_markdown(record.teacher_solution_markdown)
        if not solution and remainder:
            solution = remainder
        record_type = (
            "solution"
            if solution or record.final_answer_markdown
            else "answer"
        )
        sanitized.append(
            record.model_copy(
                update={
                    "record_type": record_type,
                    "question_text_markdown": "",
                    "options": [],
                    "correct_option_label": record.correct_option_label or label,
                    "teacher_solution_markdown": solution,
                }
            )
        )
        changed = True
    return result.model_copy(update={"records": sanitized}) if changed else result


def select_exam_prep_page_model(explicit_model: str | None = None) -> str:
    """Select one multimodal model from environment without a hardcoded model."""

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

    max_bytes = _positive_int_env("EXAM_PREP_PAGE_MAX_IMAGE_BYTES", 10 * 1024 * 1024)
    if len(page.image) > max_bytes:
        raise InvalidRenderedExamPage(
            f"Rendered page image exceeds the {max_bytes}-byte limit."
        )
    return mime_type


def extract_exam_prep_page(
    page: RenderedExamPage,
    *,
    model: str | None = None,
    scope_hint: str = "default",
) -> PageExtraction:
    """Extract every numbered record visible on exactly one rendered page."""

    mime_type = _validate_page(page)
    selected_model = select_exam_prep_page_model(model)
    safe_scope_hint = str(scope_hint or "default").strip()[:160] or "default"

    result = generate_structured(
        schema=PageExtraction,
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
                        "text": (
                            f"PAGE_NUMBER: {page.page_number}\n"
                            f"SCOPE_HINT: {safe_scope_hint}\n"
                            "Extract only records visibly supported by this page."
                        ),
                    },
                    part_from_bytes(data=page.image, mime_type=mime_type),
                ],
            },
        ],
        model=selected_model,
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        timeout=_positive_float_env("EXAM_PREP_PAGE_TIMEOUT_SECONDS", 180.0),
        temperature=0,
        max_repair=_non_negative_int_env("EXAM_PREP_PAGE_REPAIR_ATTEMPTS", 1),
        strict_json_schema=True,
        sensitive=True,
        max_output_tokens=_positive_int_env(
            "EXAM_PREP_PAGE_MAX_OUTPUT_TOKENS",
            12_000,
        ),
        detail="exam_prep_page_extraction",
        tracking_context={
            "stage": "page_extraction",
            "page_number": page.page_number,
        },
        provider_attempts=1,
    )

    if result.page_number != page.page_number:
        raise ExtractedPageNumberMismatch(
            f"Expected page {page.page_number}, received page {result.page_number}."
        )
    return _sanitize_answer_only_records(result)
