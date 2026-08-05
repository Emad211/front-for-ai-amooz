"""Source-region contract for the simple page-first pipeline.

The base PageRecord/PageExtraction contract remains unchanged for compatibility.
This module subclasses it with an optional normalized bounding box and later
attaches those regions to the canonical assembled question JSON.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .exam_prep_page_records import (
    ANSWER_RECORD_TYPES,
    QUESTION_RECORD_TYPES,
    PageAssemblyResult,
    PageExtraction,
    PageRecord,
)
from .exam_prep_utils import clean_exam_markdown


class SourceBBox(BaseModel):
    """Normalized page coordinates in the closed interval 0..1."""

    model_config = ConfigDict(extra="ignore")

    x0: float = Field(ge=0.0, le=1.0)
    y0: float = Field(ge=0.0, le=1.0)
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def normalize_shape(cls, raw: Any) -> Any:
        if raw in (None, "", []):
            return raw
        if isinstance(raw, BaseModel):
            raw = raw.model_dump()
        if isinstance(raw, (list, tuple)) and len(raw) == 4:
            raw = {"x0": raw[0], "y0": raw[1], "x1": raw[2], "y1": raw[3]}
        if not isinstance(raw, dict):
            return raw
        return {
            "x0": raw.get("x0", raw.get("left", 0.0)),
            "y0": raw.get("y0", raw.get("top", 0.0)),
            "x1": raw.get("x1", raw.get("right", 1.0)),
            "y1": raw.get("y1", raw.get("bottom", 1.0)),
        }

    @model_validator(mode="after")
    def validate_area(self) -> "SourceBBox":
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("source_bbox must have positive width and height")
        return self

    def padded(self, amount: float = 0.025) -> "SourceBBox":
        pad = max(0.0, min(0.15, float(amount)))
        return SourceBBox(
            x0=max(0.0, self.x0 - pad),
            y0=max(0.0, self.y0 - pad),
            x1=min(1.0, self.x1 + pad),
            y1=min(1.0, self.y1 + pad),
        )


class SourcePageRecord(PageRecord):
    """Page record plus the visible block that supports it."""

    source_bbox: SourceBBox | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_source_bbox_alias(cls, raw: Any) -> Any:
        if isinstance(raw, BaseModel):
            raw = raw.model_dump()
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        if "source_bbox" not in data:
            data["source_bbox"] = data.get("sourceBBox", data.get("bbox"))
        return data


class SourcePageExtraction(PageExtraction):
    """Page extraction whose records preserve normalized source regions."""

    records: list[SourcePageRecord] = Field(default_factory=list)


def ensure_source_extraction(value: PageExtraction | SourcePageExtraction) -> SourcePageExtraction:
    if isinstance(value, SourcePageExtraction):
        return value
    return SourcePageExtraction.model_validate(value.model_dump())


def remap_extraction_bboxes(
    page: PageExtraction | SourcePageExtraction,
    *,
    region_x0: float,
    region_x1: float,
) -> SourcePageExtraction:
    """Map crop-relative x coordinates back to full-page coordinates."""

    source = ensure_source_extraction(page)
    start = max(0.0, min(1.0, float(region_x0)))
    end = max(start, min(1.0, float(region_x1)))
    width = end - start
    records: list[SourcePageRecord] = []
    for record in source.records:
        bbox = record.source_bbox
        if bbox is None:
            records.append(record)
            continue
        mapped = SourceBBox(
            x0=start + bbox.x0 * width,
            y0=bbox.y0,
            x1=start + bbox.x1 * width,
            y1=bbox.y1,
        )
        records.append(record.model_copy(update={"source_bbox": mapped}))
    return source.model_copy(update={"records": records})


def _role(record: PageRecord) -> str:
    if record.record_type in QUESTION_RECORD_TYPES:
        return "question"
    if record.record_type in ANSWER_RECORD_TYPES:
        return "answer"
    return record.record_type


def _scope(value: Any) -> str:
    return clean_exam_markdown(value).strip() or "default"


def build_source_region_index(
    pages: Iterable[PageExtraction | SourcePageExtraction],
) -> dict[tuple[str, int], list[dict[str, Any]]]:
    """Collect unique source blocks by (scope, printed question number)."""

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, int, int, str, str]] = set()
    for page in pages:
        source = ensure_source_extraction(page)
        for record in source.records:
            scope = _scope(record.scope_key)
            bbox = record.source_bbox.model_dump() if record.source_bbox else None
            bbox_key = repr(bbox)
            role = _role(record)
            dedupe_key = (
                scope.casefold(),
                record.question_number,
                source.page_number,
                role,
                bbox_key,
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            grouped[(scope.casefold(), record.question_number)].append(
                {
                    "page_number": source.page_number,
                    "role": role,
                    "record_type": record.record_type,
                    "bbox": bbox,
                    "confidence": record.confidence,
                }
            )
    return grouped


def attach_source_regions(
    result: PageAssemblyResult,
    *,
    pages: Iterable[PageExtraction | SourcePageExtraction],
) -> PageAssemblyResult:
    """Attach source blocks without changing the existing question contract."""

    index = build_source_region_index(pages)
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    questions: list[dict[str, Any]] = []
    for question in exam.get("questions") or []:
        if not isinstance(question, dict):
            continue
        try:
            number = int(question.get("source_question_number") or 0)
        except (TypeError, ValueError):
            number = 0
        scope = _scope(question.get("scope_key"))
        regions = index.get((scope.casefold(), number), [])
        questions.append({**question, "source_regions": regions})
    exam["questions"] = questions
    projection["exam_prep"] = exam
    return result.model_copy(update={"projection": projection})
