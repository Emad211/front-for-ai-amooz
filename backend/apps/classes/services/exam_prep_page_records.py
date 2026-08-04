"""Simple page-first contract for exam-preparation PDF extraction.

This module is intentionally pure. It does not read files, call an LLM, touch
Django models, dispatch Celery tasks, or select a pipeline version.

The intended replacement flow is:

    one rendered PDF page -> one PageExtraction -> deterministic assembly by
    (scope_key, question_number) -> existing ``exam_prep_json`` contract.

Runtime cutover is deliberately outside this module. The current production
pipeline remains unchanged until the page-level extractor is implemented and
validated in a later phase.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .exam_prep_utils import clean_exam_markdown


DEFAULT_SCOPE_KEY = "default"
RecordType = Literal["question", "answer", "solution", "question_answer"]


class PageOption(BaseModel):
    """One option exactly as extracted from one PDF page."""

    model_config = ConfigDict(extra="ignore")

    label: str
    text_markdown: str


class PageRecord(BaseModel):
    """One numbered question/answer fragment found on one page.

    ``question_number`` is required. This is the load-bearing product
    assumption confirmed for the target PDFs: question and answer sections share
    the same visible question number.
    """

    model_config = ConfigDict(extra="ignore")

    scope_key: str = DEFAULT_SCOPE_KEY
    question_number: int = Field(ge=1)
    record_type: RecordType
    question_text_markdown: str = ""
    options: list[PageOption] = Field(default_factory=list)
    correct_option_label: str | None = None
    correct_option_text_markdown: str = ""
    teacher_solution_markdown: str = ""
    final_answer_markdown: str = ""
    continues_from_previous_page: bool = False
    continues_on_next_page: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


class PageExtraction(BaseModel):
    """Complete structured output of exactly one PDF page."""

    model_config = ConfigDict(extra="ignore")

    page_number: int = Field(ge=1)
    records: list[PageRecord] = Field(default_factory=list)


class AssemblyIssue(BaseModel):
    """One deterministic reason that a merged question needs review."""

    model_config = ConfigDict(extra="forbid")

    code: str
    scope_key: str
    question_number: int
    source_pages: list[int]


class PageAssemblyResult(BaseModel):
    """Canonical projection plus explicit review issues."""

    model_config = ConfigDict(extra="forbid")

    projection: dict[str, Any]
    issues: list[AssemblyIssue]
    question_count: int
    questions_needing_review: int


@dataclass(slots=True)
class _Fragment:
    page_number: int
    record_index: int
    record: PageRecord


@dataclass(slots=True)
class _Bucket:
    scope_key: str
    question_number: int
    first_order: tuple[int, int]
    fragments: list[_Fragment] = field(default_factory=list)


def _clean_scope(value: Any) -> str:
    return clean_exam_markdown(value).strip() or DEFAULT_SCOPE_KEY


def _normalized_text(value: Any) -> str:
    return " ".join(clean_exam_markdown(value).split()).casefold()


def _append_unique(values: list[str], value: Any) -> None:
    cleaned = clean_exam_markdown(value)
    if not cleaned:
        return
    normalized = _normalized_text(cleaned)
    if normalized and all(_normalized_text(existing) != normalized for existing in values):
        values.append(cleaned)


def _append_issue(values: list[str], code: Any) -> None:
    cleaned = clean_exam_markdown(code).strip()
    if cleaned and cleaned not in values:
        values.append(cleaned)


def _scope_token(scope_key: str) -> str:
    token = re.sub(r"[^\w-]+", "-", scope_key.casefold(), flags=re.UNICODE).strip("-_")
    return token or DEFAULT_SCOPE_KEY


def _merge_options(fragments: list[_Fragment], issues: list[str]) -> list[dict[str, str]]:
    merged: OrderedDict[str, str] = OrderedDict()
    for fragment in fragments:
        for option in fragment.record.options:
            label = clean_exam_markdown(option.label)
            text = clean_exam_markdown(option.text_markdown)
            if not label or not text:
                continue
            existing = merged.get(label)
            if existing is None:
                merged[label] = text
                continue
            if _normalized_text(existing) == _normalized_text(text):
                continue
            existing_normalized = _normalized_text(existing)
            candidate_normalized = _normalized_text(text)
            if existing_normalized and existing_normalized in candidate_normalized:
                merged[label] = text
                continue
            if candidate_normalized and candidate_normalized in existing_normalized:
                continue
            _append_issue(issues, f"conflicting_option:{label}")
    return [
        {"label": label, "text_markdown": text}
        for label, text in merged.items()
    ]


def _pick_single_value(
    fragments: list[_Fragment],
    field_name: str,
    *,
    conflict_code: str,
    issues: list[str],
) -> str | None:
    values: list[str] = []
    for fragment in fragments:
        _append_unique(values, getattr(fragment.record, field_name))
    if len(values) > 1:
        _append_issue(issues, conflict_code)
    return values[0] if values else None


def _join_text_field(fragments: list[_Fragment], field_name: str) -> str:
    values: list[str] = []
    for fragment in fragments:
        _append_unique(values, getattr(fragment.record, field_name))
    return "\n\n".join(values)


def _assemble_bucket(bucket: _Bucket) -> tuple[dict[str, Any], list[str]]:
    fragments = sorted(
        bucket.fragments,
        key=lambda item: (item.page_number, item.record_index),
    )
    source_pages = sorted({fragment.page_number for fragment in fragments})
    issues: list[str] = []
    for fragment in fragments:
        for issue in fragment.record.issues:
            _append_issue(issues, issue)

    if fragments and fragments[0].record.continues_from_previous_page:
        _append_issue(issues, "missing_previous_continuation")
    if fragments and fragments[-1].record.continues_on_next_page:
        _append_issue(issues, "missing_next_continuation")

    question_text = _join_text_field(fragments, "question_text_markdown")
    options = _merge_options(fragments, issues)
    correct_option_label = _pick_single_value(
        fragments,
        "correct_option_label",
        conflict_code="conflicting_correct_option",
        issues=issues,
    )
    correct_option_text = _pick_single_value(
        fragments,
        "correct_option_text_markdown",
        conflict_code="conflicting_correct_option_text",
        issues=issues,
    )
    teacher_solution = _join_text_field(fragments, "teacher_solution_markdown")
    final_answer = _join_text_field(fragments, "final_answer_markdown")

    if not question_text:
        _append_issue(issues, "missing_question_text")
    if len(options) < 2:
        _append_issue(issues, "missing_options")
    if not any((correct_option_label, correct_option_text, final_answer, teacher_solution)):
        _append_issue(issues, "missing_answer")

    confidence = min((fragment.record.confidence for fragment in fragments), default=0.0)
    question_id = f"{_scope_token(bucket.scope_key)}-q-{bucket.question_number}"
    question = {
        "question_id": question_id,
        "scope_key": bucket.scope_key,
        "section_key": bucket.scope_key,
        "source_question_number": str(bucket.question_number),
        "question_text_markdown": question_text,
        "options": options,
        "correct_option_label": correct_option_label,
        "correct_option_text_markdown": correct_option_text,
        "teacher_solution_markdown": teacher_solution,
        "final_answer_markdown": final_answer,
        "confidence": confidence,
        "issues": issues,
        "source_pages": source_pages,
    }
    return question, issues


def assemble_page_extractions(
    pages: list[PageExtraction],
    *,
    title: str = "",
) -> PageAssemblyResult:
    """Merge page records by ``(scope_key, question_number)``.

    The function never guesses fuzzy matches. Same question numbers in different
    scopes stay separate. Conflicting values are retained deterministically and
    surfaced as review issues instead of silently overwriting one another.
    """

    ordered_pages = sorted(pages, key=lambda page: page.page_number)
    seen_page_numbers: set[int] = set()
    buckets: dict[tuple[str, int], _Bucket] = {}

    for page in ordered_pages:
        if page.page_number in seen_page_numbers:
            raise ValueError(f"Duplicate page_number: {page.page_number}")
        seen_page_numbers.add(page.page_number)
        for record_index, record in enumerate(page.records):
            scope_key = _clean_scope(record.scope_key)
            key = (scope_key.casefold(), record.question_number)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = _Bucket(
                    scope_key=scope_key,
                    question_number=record.question_number,
                    first_order=(page.page_number, record_index),
                )
                buckets[key] = bucket
            bucket.fragments.append(
                _Fragment(
                    page_number=page.page_number,
                    record_index=record_index,
                    record=record,
                )
            )

    questions: list[dict[str, Any]] = []
    assembly_issues: list[AssemblyIssue] = []
    for bucket in sorted(buckets.values(), key=lambda item: item.first_order):
        question, issue_codes = _assemble_bucket(bucket)
        questions.append(question)
        for code in issue_codes:
            assembly_issues.append(
                AssemblyIssue(
                    code=code,
                    scope_key=bucket.scope_key,
                    question_number=bucket.question_number,
                    source_pages=question["source_pages"],
                )
            )

    return PageAssemblyResult(
        projection={
            "exam_prep": {
                "title": clean_exam_markdown(title),
                "questions": questions,
            }
        },
        issues=assembly_issues,
        question_count=len(questions),
        questions_needing_review=sum(bool(question["issues"]) for question in questions),
    )
