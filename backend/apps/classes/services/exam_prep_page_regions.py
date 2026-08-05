"""Small helpers for dense two-column exam answer pages."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import io
from typing import Iterable

from PIL import Image

from .exam_prep_page_records import (
    ANSWER_RECORD_TYPES,
    QUESTION_RECORD_TYPES,
    PageExtraction,
    PageOption,
    PageRecord,
)
from .exam_prep_page_source import (
    SourcePageExtraction,
    SourcePageRecord,
    ensure_source_extraction,
)
from .exam_prep_text_quality import has_broken_persian_text
from .exam_prep_utils import clean_exam_markdown


@dataclass(frozen=True, slots=True)
class ColumnCrop:
    region: str
    image: bytes
    native_text: str
    reading_order: int
    page_x0: float
    page_x1: float


def split_vertical_columns(
    image_bytes: bytes,
    *,
    right_native_text: str = "",
    left_native_text: str = "",
    overlap_ratio: float = 0.035,
) -> tuple[ColumnCrop, ColumnCrop]:
    """Return Persian reading order and full-page x coordinates."""

    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert("RGB")
    try:
        width, height = image.size
        overlap = max(8, int(width * max(0.0, min(0.1, overlap_ratio))))
        middle = width // 2
        right_start = max(0, middle - overlap)
        left_end = min(width, middle + overlap)
        right = image.crop((right_start, 0, width, height))
        left = image.crop((0, 0, left_end, height))
        try:
            right_buffer = io.BytesIO()
            left_buffer = io.BytesIO()
            right.save(right_buffer, format="PNG", optimize=True)
            left.save(left_buffer, format="PNG", optimize=True)
            return (
                ColumnCrop(
                    region="right_column",
                    image=right_buffer.getvalue(),
                    native_text=right_native_text,
                    reading_order=0,
                    page_x0=right_start / width,
                    page_x1=1.0,
                ),
                ColumnCrop(
                    region="left_column",
                    image=left_buffer.getvalue(),
                    native_text=left_native_text,
                    reading_order=1,
                    page_x0=0.0,
                    page_x1=left_end / width,
                ),
            )
        finally:
            right.close()
            left.close()
    finally:
        image.close()


def _role_group(record: PageRecord) -> str:
    if record.record_type in QUESTION_RECORD_TYPES:
        return "question"
    if record.record_type in ANSWER_RECORD_TYPES:
        return "answer"
    return record.record_type


def _text_score(value: str) -> tuple[int, int]:
    text = clean_exam_markdown(value)
    return (0 if has_broken_persian_text(text) else 1, len(text))


def _best_text(values: Iterable[str]) -> str:
    unique: list[str] = []
    for value in values:
        text = clean_exam_markdown(value)
        if text and text not in unique:
            unique.append(text)
    return max(unique, key=_text_score, default="")


def _best_options(records: list[PageRecord]) -> list[PageOption]:
    def rank(record: PageRecord) -> tuple[int, int, int]:
        option_text = sum(
            len(clean_exam_markdown(item.text_markdown))
            for item in record.options
        )
        broken = sum(
            has_broken_persian_text(item.text_markdown)
            for item in record.options
        )
        return (-broken, len(record.options), option_text)

    best = max(records, key=rank, default=None)
    return list(best.options) if best is not None else []


def _best_bbox(records: list[PageRecord]):
    candidates = [
        getattr(item, "source_bbox", None)
        for item in records
        if getattr(item, "source_bbox", None) is not None
    ]
    if not candidates:
        return None

    def area(bbox) -> float:
        return (bbox.x1 - bbox.x0) * (bbox.y1 - bbox.y0)

    # Region reads normally provide a tighter box than the full-page fallback.
    # Ignore implausibly tiny marker-only boxes when a complete alternative exists.
    complete = [bbox for bbox in candidates if area(bbox) >= 0.005]
    return min(complete or candidates, key=area)


def _merge_record_candidates(records: list[PageRecord]) -> SourcePageRecord:
    base = max(
        records,
        key=lambda item: (
            len(item.teacher_solution_markdown),
            len(item.question_text_markdown),
            len(item.options),
            item.confidence,
        ),
    )
    source_base = SourcePageRecord.model_validate(base.model_dump())
    role = _role_group(base)
    record_type = (
        "question_answer"
        if any(item.record_type == "question_answer" for item in records)
        else "question"
        if role == "question"
        else "solution"
        if any(item.teacher_solution_markdown for item in records)
        else "answer"
    )
    correct = next(
        (
            clean_exam_markdown(item.correct_option_label)
            for item in records
            if clean_exam_markdown(item.correct_option_label)
        ),
        None,
    )
    issues: list[str] = []
    for item in records:
        for code in item.issues:
            if code not in issues:
                issues.append(code)
    return source_base.model_copy(
        update={
            "record_type": record_type,
            "question_text_markdown": _best_text(
                item.question_text_markdown for item in records
            ),
            "options": _best_options(records),
            "correct_option_label": correct,
            "correct_option_text_markdown": _best_text(
                item.correct_option_text_markdown for item in records
            ),
            "teacher_solution_markdown": _best_text(
                item.teacher_solution_markdown for item in records
            ),
            "final_answer_markdown": _best_text(
                item.final_answer_markdown for item in records
            ),
            "continues_from_previous_page": any(
                item.continues_from_previous_page for item in records
            ),
            "continues_on_next_page": any(
                item.continues_on_next_page for item in records
            ),
            "confidence": max(item.confidence for item in records),
            "issues": issues,
            "source_bbox": _best_bbox(records),
        }
    )


def merge_page_region_extractions(
    full_page: PageExtraction,
    region_pages: Iterable[PageExtraction],
) -> SourcePageExtraction:
    """Merge full-page fallback with ordered column reads by number and role."""

    candidates: OrderedDict[
        tuple[str, int, str],
        list[PageRecord],
    ] = OrderedDict()
    pages = [
        *(ensure_source_extraction(page) for page in region_pages),
        ensure_source_extraction(full_page),
    ]
    for page in pages:
        for record in page.records:
            key = (
                clean_exam_markdown(record.scope_key).casefold() or "default",
                record.question_number,
                _role_group(record),
            )
            candidates.setdefault(key, []).append(record)
    merged = [
        _merge_record_candidates(items)
        for items in candidates.values()
    ]
    return SourcePageExtraction(
        page_number=full_page.page_number,
        records=merged,
    )


def last_record_number(page: PageExtraction) -> int | None:
    """Return a continuation hint only when the source explicitly continues."""

    for record in reversed(page.records):
        if (
            record.question_number > 0
            and record.continues_on_next_page
        ):
            return record.question_number
    return None
