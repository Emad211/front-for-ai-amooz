"""Pure page-first contract and deterministic exam assembly.

The production model stays deliberately simple:

    one rendered PDF page -> one PageExtraction -> deterministic assembly by
    (scope_key, question_number) -> existing ``exam_prep_json`` contract.

This module contains no file access, provider calls, Django models, Celery tasks,
or pipeline-version branching. It is responsible for accepting common harmless
shape variations from multimodal models and for keeping question pages separate
from answer/solution pages during assembly.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .exam_prep_utils import clean_exam_markdown


DEFAULT_SCOPE_KEY = "default"
RecordType = Literal["question", "answer", "solution", "question_answer"]
QUESTION_RECORD_TYPES = frozenset({"question", "question_answer"})
ANSWER_RECORD_TYPES = frozenset({"answer", "solution", "question_answer"})

_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_OPTION_LETTERS = frozenset({"الف", "ب", "ج", "د", "ه"})
_ANSWER_HEADING_RE = re.compile(
    r"^\s*[-–—ـ]*\s*"
    r"(?:(?:س[ؤو]ال)\s*)?"
    r"(?P<number>[0-9۰-۹٠-٩]+)?\s*[-–—ـ.:：)\]]*\s*"
    r"(?:(?:پاسخ)\s*(?:صحیح|درست)?\s*[:：\-–—]*\s*)?"
    r"(?:گزین[ههۀ])\s*[«»\"'()\[\]]*\s*"
    r"(?P<label>[0-9۰-۹٠-٩]+|[الفبجده])"
    r"\s*[«»\"'()\[\]]*",
    flags=re.IGNORECASE,
)
_OPTION_PREFIX_RE = re.compile(
    r"^\s*(?:(?:گزین[ههۀ])\s*)?"
    r"[«»\"'()\[\]]*\s*"
    r"(?P<label>[0-9۰-۹٠-٩]+|[الفبجده])"
    r"\s*[«»\"'()\[\].:：\-–—،]*\s*"
    r"(?P<text>.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_RECORD_TYPE_ALIASES = {
    "question": "question",
    "questions": "question",
    "سوال": "question",
    "سؤال": "question",
    "answer": "answer",
    "answer_key": "answer",
    "key": "answer",
    "پاسخ": "answer",
    "پاسخنامه": "answer",
    "پاسخ‌نامه": "answer",
    "solution": "solution",
    "worked_solution": "solution",
    "explanation": "solution",
    "حل": "solution",
    "راه حل": "solution",
    "راه‌حل": "solution",
    "question_answer": "question_answer",
    "question-and-answer": "question_answer",
    "combined": "question_answer",
}


def _latin_digits(value: Any) -> str:
    return str(value or "").translate(_DIGIT_TRANSLATION)


def _parse_positive_int(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    text = _latin_digits(value).strip()
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else value


def _normalize_option_label(value: Any) -> str:
    text = clean_exam_markdown(_latin_digits(value)).strip()
    text = re.sub(r"^گزین[ههۀ]\s*", "", text, flags=re.IGNORECASE)
    text = text.strip(" \t\r\n«»\"'()[]{}.:：،,-–—")
    if text.isdigit():
        return str(int(text))
    if text in _OPTION_LETTERS:
        return text
    return text[:32]


def _option_from_value(value: Any, *, fallback_label: str) -> dict[str, str] | None:
    if isinstance(value, BaseModel):
        value = value.model_dump()

    if isinstance(value, dict):
        if len(value) == 1 and not any(
            key in value
            for key in (
                "label",
                "option_label",
                "key",
                "number",
                "text_markdown",
                "text",
                "value",
                "option_text",
            )
        ):
            key, item = next(iter(value.items()))
            label = _normalize_option_label(key) or fallback_label
            text = clean_exam_markdown(item)
            return {"label": label, "text_markdown": text} if text else None

        label = _normalize_option_label(
            value.get("label")
            or value.get("option_label")
            or value.get("key")
            or value.get("number")
            or fallback_label
        )
        text = clean_exam_markdown(
            value.get("text_markdown")
            or value.get("text")
            or value.get("value")
            or value.get("option_text")
            or ""
        )
        return {"label": label, "text_markdown": text} if text else None

    text = clean_exam_markdown(value)
    if not text:
        return None
    match = _OPTION_PREFIX_RE.match(text)
    if match and clean_exam_markdown(match.group("text")):
        return {
            "label": _normalize_option_label(match.group("label")) or fallback_label,
            "text_markdown": clean_exam_markdown(match.group("text")),
        }
    return {"label": fallback_label, "text_markdown": text}


def _normalize_options(value: Any) -> list[dict[str, str]]:
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        values: list[Any] = [
            {"label": key, "text_markdown": item}
            for key, item in value.items()
        ]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        values = [value]

    normalized: list[dict[str, str]] = []
    used_labels: set[str] = set()
    for index, item in enumerate(values, start=1):
        option = _option_from_value(item, fallback_label=str(index))
        if option is None:
            continue
        label = option["label"] or str(index)
        if label in used_labels:
            label = str(index)
        used_labels.add(label)
        normalized.append({**option, "label": label})
    return normalized


def _answer_heading(value: Any, *, expected_question_number: int | None) -> tuple[str | None, str]:
    text = clean_exam_markdown(value)
    if not text:
        return None, ""
    match = _ANSWER_HEADING_RE.match(text[:240])
    if not match:
        return None, text
    heading_number = _parse_positive_int(match.group("number")) if match.group("number") else None
    if (
        expected_question_number is not None
        and isinstance(heading_number, int)
        and heading_number != expected_question_number
    ):
        return None, text
    label = _normalize_option_label(match.group("label"))
    remainder = clean_exam_markdown(text[match.end():]).lstrip(" \t\r\n:：-–—")
    return label or None, remainder


def _normalize_record_type(value: Any) -> str:
    text = clean_exam_markdown(value).strip().casefold().replace("|", "_")
    text = re.sub(r"\s+", " ", text)
    return _RECORD_TYPE_ALIASES.get(text, text)


class PageOption(BaseModel):
    """One option exactly as extracted from one PDF page."""

    model_config = ConfigDict(extra="ignore")

    label: str
    text_markdown: str

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: Any) -> str:
        return _normalize_option_label(value)

    @field_validator("text_markdown", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> str:
        return clean_exam_markdown(value)


class PageRecord(BaseModel):
    """One numbered question/answer fragment found on one page.

    ``question_number`` remains the load-bearing matching key. The before
    validator accepts harmless provider shape variations (for example options as
    strings or a label->text mapping) and normalizes them into the canonical
    contract before Pydantic validates the record.
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

    @model_validator(mode="before")
    @classmethod
    def normalize_provider_shape(cls, raw: Any) -> Any:
        if isinstance(raw, BaseModel):
            raw = raw.model_dump()
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        question_number = _parse_positive_int(
            data.get("question_number")
            or data.get("questionNumber")
            or data.get("number")
        )
        data["question_number"] = question_number
        expected_number = question_number if isinstance(question_number, int) else None

        data["scope_key"] = (
            clean_exam_markdown(data.get("scope_key") or data.get("scopeKey") or DEFAULT_SCOPE_KEY).strip()
            or DEFAULT_SCOPE_KEY
        )
        data["options"] = _normalize_options(
            data.get("options")
            if "options" in data
            else data.get("choices", data.get("answers", []))
        )

        aliases = {
            "question_text_markdown": ("question_text_markdown", "question_text", "question", "stem"),
            "correct_option_label": ("correct_option_label", "correctOptionLabel", "answer_label", "answer"),
            "correct_option_text_markdown": (
                "correct_option_text_markdown",
                "correct_option_text",
                "answer_text",
            ),
            "teacher_solution_markdown": (
                "teacher_solution_markdown",
                "solution_markdown",
                "solution",
                "explanation",
            ),
            "final_answer_markdown": ("final_answer_markdown", "final_answer"),
        }
        for canonical, names in aliases.items():
            if canonical in data and data.get(canonical) not in (None, ""):
                continue
            for name in names:
                if data.get(name) not in (None, ""):
                    data[canonical] = data[name]
                    break

        for field_name in (
            "question_text_markdown",
            "correct_option_text_markdown",
            "teacher_solution_markdown",
            "final_answer_markdown",
        ):
            data[field_name] = clean_exam_markdown(data.get(field_name) or "")

        explicit_type = _normalize_record_type(
            data.get("record_type") or data.get("recordType") or data.get("type") or ""
        )
        correct_label = _normalize_option_label(data.get("correct_option_label"))
        if not correct_label:
            for field_name in (
                "question_text_markdown",
                "final_answer_markdown",
                "teacher_solution_markdown",
                "correct_option_text_markdown",
            ):
                inferred, remainder = _answer_heading(
                    data.get(field_name),
                    expected_question_number=expected_number,
                )
                if inferred:
                    correct_label = inferred
                    if field_name == "question_text_markdown" and explicit_type in {"answer", "solution"}:
                        data[field_name] = remainder
                    break
        data["correct_option_label"] = correct_label or None

        has_question = bool(
            data["question_text_markdown"].strip()
            or len(data["options"]) >= 2
        )
        has_answer = bool(
            data["correct_option_label"]
            or data["correct_option_text_markdown"].strip()
            or data["teacher_solution_markdown"].strip()
            or data["final_answer_markdown"].strip()
        )
        if explicit_type not in QUESTION_RECORD_TYPES | ANSWER_RECORD_TYPES:
            explicit_type = (
                "question_answer"
                if has_question and has_answer
                else "question"
                if has_question
                else "solution"
                if data["teacher_solution_markdown"].strip()
                else "answer"
            )
        elif explicit_type == "question" and has_answer and has_question:
            explicit_type = "question_answer"
        elif explicit_type in {"answer", "solution"} and has_question and not has_answer:
            explicit_type = "question"
        data["record_type"] = explicit_type

        confidence = data.get("confidence", 0.0)
        if isinstance(confidence, str):
            confidence = confidence.strip().rstrip("%").translate(_DIGIT_TRANSLATION)
            try:
                confidence = float(confidence)
            except ValueError:
                confidence = 0.0
        if isinstance(confidence, (int, float)) and 1 < confidence <= 100:
            confidence = confidence / 100
        data["confidence"] = confidence
        return data

    @field_validator("correct_option_label", mode="before")
    @classmethod
    def normalize_correct_label(cls, value: Any) -> str | None:
        normalized = _normalize_option_label(value)
        return normalized or None


class PageExtraction(BaseModel):
    """Complete structured output of exactly one physical PDF page."""

    model_config = ConfigDict(extra="ignore")

    page_number: int = Field(ge=1)
    records: list[PageRecord] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_page_shape(cls, raw: Any) -> Any:
        if isinstance(raw, BaseModel):
            raw = raw.model_dump()
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        data["page_number"] = _parse_positive_int(
            data.get("page_number") or data.get("pageNumber") or data.get("page")
        )
        records = data.get("records", data.get("items", []))
        if isinstance(records, dict):
            normalized_records = []
            for key, value in records.items():
                if isinstance(value, dict):
                    normalized_records.append({"question_number": key, **value})
                else:
                    normalized_records.append(
                        {
                            "question_number": key,
                            "record_type": "answer",
                            "final_answer_markdown": value,
                        }
                    )
            records = normalized_records
        data["records"] = records if isinstance(records, list) else []
        return data


class AssemblyIssue(BaseModel):
    """One deterministic reason that a merged question needs review."""

    model_config = ConfigDict(extra="forbid")

    code: str
    scope_key: str
    question_number: int
    source_pages: list[int]


class OrphanAnswer(BaseModel):
    """An answer/solution number with no corresponding question record."""

    model_config = ConfigDict(extra="forbid")

    scope_key: str
    question_number: int
    source_pages: list[int]
    correct_option_label: str | None = None
    has_solution: bool = False


class PageAssemblyResult(BaseModel):
    """Canonical projection plus deterministic integrity metadata."""

    model_config = ConfigDict(extra="forbid")

    projection: dict[str, Any]
    issues: list[AssemblyIssue]
    question_count: int
    questions_needing_review: int
    matched_answer_count: int = 0
    orphan_answers: list[OrphanAnswer] = Field(default_factory=list)
    question_number_gaps: dict[str, list[int]] = Field(default_factory=dict)
    publication_ready: bool = False


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


def _fragments_for_types(
    fragments: list[_Fragment],
    allowed_types: frozenset[str],
) -> list[_Fragment]:
    return [
        fragment
        for fragment in fragments
        if fragment.record.record_type in allowed_types
    ]


def _merge_options(fragments: list[_Fragment], issues: list[str]) -> list[dict[str, str]]:
    merged: OrderedDict[str, str] = OrderedDict()
    for fragment in fragments:
        for option in fragment.record.options:
            label = _normalize_option_label(option.label)
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


def _has_question_evidence(fragments: list[_Fragment]) -> bool:
    return any(
        fragment.record.record_type in QUESTION_RECORD_TYPES
        and (
            bool(fragment.record.question_text_markdown.strip())
            or len(fragment.record.options) >= 2
        )
        for fragment in fragments
    )


def _orphan_answer(bucket: _Bucket) -> OrphanAnswer:
    fragments = sorted(bucket.fragments, key=lambda item: (item.page_number, item.record_index))
    answer_fragments = _fragments_for_types(fragments, ANSWER_RECORD_TYPES)
    labels: list[str] = []
    for fragment in answer_fragments:
        _append_unique(labels, fragment.record.correct_option_label)
    return OrphanAnswer(
        scope_key=bucket.scope_key,
        question_number=bucket.question_number,
        source_pages=sorted({fragment.page_number for fragment in answer_fragments}),
        correct_option_label=labels[0] if labels else None,
        has_solution=any(
            bool(fragment.record.teacher_solution_markdown.strip())
            for fragment in answer_fragments
        ),
    )


def _assemble_bucket(bucket: _Bucket) -> tuple[dict[str, Any], list[str], bool]:
    fragments = sorted(
        bucket.fragments,
        key=lambda item: (item.page_number, item.record_index),
    )
    question_fragments = _fragments_for_types(fragments, QUESTION_RECORD_TYPES)
    answer_fragments = _fragments_for_types(fragments, ANSWER_RECORD_TYPES)
    source_pages = sorted({fragment.page_number for fragment in fragments})
    issues: list[str] = []
    for fragment in fragments:
        for issue in fragment.record.issues:
            _append_issue(issues, issue)

    if question_fragments and question_fragments[0].record.continues_from_previous_page:
        _append_issue(issues, "missing_previous_continuation")
    if question_fragments and question_fragments[-1].record.continues_on_next_page:
        _append_issue(issues, "missing_next_continuation")

    # Question pages are the sole authority for question text and options.
    question_text = _join_text_field(question_fragments, "question_text_markdown")
    options = _merge_options(question_fragments, issues)

    # Answer/solution pages are the sole authority for the answer fields.
    correct_option_label = _pick_single_value(
        answer_fragments,
        "correct_option_label",
        conflict_code="conflicting_correct_option",
        issues=issues,
    )
    correct_option_text = _pick_single_value(
        answer_fragments,
        "correct_option_text_markdown",
        conflict_code="conflicting_correct_option_text",
        issues=issues,
    )
    teacher_solution = _join_text_field(answer_fragments, "teacher_solution_markdown")
    final_answer = _join_text_field(answer_fragments, "final_answer_markdown")

    if not question_text:
        _append_issue(issues, "missing_question_text")
    if len(options) < 2:
        _append_issue(issues, "missing_options")
    if not any((correct_option_label, correct_option_text, final_answer, teacher_solution)):
        _append_issue(issues, "missing_answer")
    option_labels = {option["label"] for option in options}
    if correct_option_label and option_labels and correct_option_label not in option_labels:
        _append_issue(issues, "correct_option_not_in_options")

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
    matched_answer = bool(answer_fragments) and bool(
        correct_option_label or correct_option_text or final_answer or teacher_solution
    )
    return question, issues, matched_answer


def _number_gaps(questions: list[dict[str, Any]]) -> dict[str, list[int]]:
    by_scope: dict[str, set[int]] = defaultdict(set)
    for question in questions:
        try:
            number = int(question.get("source_question_number") or 0)
        except (TypeError, ValueError):
            continue
        if number > 0:
            by_scope[str(question.get("scope_key") or DEFAULT_SCOPE_KEY)].add(number)

    gaps: dict[str, list[int]] = {}
    for scope_key, numbers in by_scope.items():
        if len(numbers) < 2:
            continue
        low, high = min(numbers), max(numbers)
        if high - low > 500:
            continue
        missing = [number for number in range(low, high + 1) if number not in numbers]
        if missing:
            gaps[scope_key] = missing
    return gaps


def assemble_page_extractions(
    pages: list[PageExtraction],
    *,
    title: str = "",
) -> PageAssemblyResult:
    """Merge records by ``(scope_key, question_number)`` without fuzzy matching.

    Page order and section order are irrelevant. Question evidence may appear
    before or after its answer. Answer-only buckets are reported as orphans and
    never become fabricated questions.
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
    orphan_answers: list[OrphanAnswer] = []
    matched_answer_count = 0
    for bucket in sorted(buckets.values(), key=lambda item: item.first_order):
        if not _has_question_evidence(bucket.fragments):
            if any(
                fragment.record.record_type in ANSWER_RECORD_TYPES
                for fragment in bucket.fragments
            ):
                orphan_answers.append(_orphan_answer(bucket))
            continue

        question, issue_codes, matched_answer = _assemble_bucket(bucket)
        questions.append(question)
        matched_answer_count += int(matched_answer)
        for code in issue_codes:
            assembly_issues.append(
                AssemblyIssue(
                    code=code,
                    scope_key=bucket.scope_key,
                    question_number=bucket.question_number,
                    source_pages=question["source_pages"],
                )
            )

    gaps = _number_gaps(questions)
    for scope_key, numbers in gaps.items():
        for number in numbers:
            assembly_issues.append(
                AssemblyIssue(
                    code="missing_question_number",
                    scope_key=scope_key,
                    question_number=number,
                    source_pages=[],
                )
            )

    critical_codes = {
        "missing_question_text",
        "missing_options",
        "missing_answer",
        "missing_previous_continuation",
        "missing_next_continuation",
        "conflicting_correct_option",
        "conflicting_correct_option_text",
        "correct_option_not_in_options",
        "missing_question_number",
    }
    critical_issue_count = sum(issue.code in critical_codes for issue in assembly_issues)
    questions_needing_review = sum(bool(question["issues"]) for question in questions)

    return PageAssemblyResult(
        projection={
            "exam_prep": {
                "title": clean_exam_markdown(title),
                "questions": questions,
            }
        },
        issues=assembly_issues,
        question_count=len(questions),
        questions_needing_review=questions_needing_review,
        matched_answer_count=matched_answer_count,
        orphan_answers=orphan_answers,
        question_number_gaps=gaps,
        publication_ready=bool(questions) and critical_issue_count == 0,
    )


def build_page_first_audit(
    result: PageAssemblyResult,
    *,
    failed_page_numbers: list[int] | None = None,
) -> dict[str, Any]:
    """Return the existing frontend audit shape without a legacy artifact."""

    failed_pages = sorted({int(number) for number in (failed_page_numbers or []) if int(number) > 0})
    critical_codes = {
        "missing_question_text",
        "missing_options",
        "missing_answer",
        "missing_previous_continuation",
        "missing_next_continuation",
        "conflicting_correct_option",
        "conflicting_correct_option_text",
        "correct_option_not_in_options",
        "missing_question_number",
        "failed_chunk",
    }
    issues = [
        {
            "code": issue.code,
            "severity": "critical" if issue.code in critical_codes else "warning",
            "scopeKey": issue.scope_key,
            "questionNumber": issue.question_number,
            "sourcePages": issue.source_pages,
        }
        for issue in result.issues
    ]
    for page_number in failed_pages:
        issues.append(
            {
                "code": "failed_chunk",
                "severity": "critical",
                "scopeKey": DEFAULT_SCOPE_KEY,
                "questionNumber": 0,
                "sourcePages": [page_number],
            }
        )
    for orphan in result.orphan_answers:
        issues.append(
            {
                "code": "out_of_scope_answer",
                "severity": "warning",
                "scopeKey": orphan.scope_key,
                "questionNumber": orphan.question_number,
                "sourcePages": orphan.source_pages,
            }
        )
    critical_count = sum(issue["severity"] == "critical" for issue in issues)
    return {
        "status": "passed" if result.question_count > 0 and critical_count == 0 else "needs_review",
        "questionCount": result.question_count,
        "matchedAnswerCount": result.matched_answer_count,
        "outOfScopeAnswerCount": len(result.orphan_answers),
        "criticalIssueCount": critical_count,
        "issues": issues,
        "failedPageNumbers": failed_pages,
        "questionNumberGaps": result.question_number_gaps,
    }


def render_page_first_transcript(
    result: PageAssemblyResult,
    *,
    failed_page_numbers: list[int] | None = None,
) -> str:
    """Render the canonical dictionary into readable, deterministic Markdown."""

    audit = build_page_first_audit(result, failed_page_numbers=failed_page_numbers)
    exam = result.projection.get("exam_prep") or {}
    title = clean_exam_markdown(exam.get("title") or "آمادگی آزمون")
    lines = [
        f"# {title}",
        "",
        "## خلاصهٔ استخراج",
        "",
        f"- تعداد سؤال‌های معتبر: **{result.question_count}**",
        f"- پاسخ‌های متصل‌شده: **{result.matched_answer_count}**",
        f"- پاسخ‌های بدون سؤال که کنار گذاشته شدند: **{len(result.orphan_answers)}**",
        f"- موارد بحرانی: **{audit['criticalIssueCount']}**",
    ]
    if audit["failedPageNumbers"]:
        pages = "، ".join(str(number) for number in audit["failedPageNumbers"])
        lines.append(f"- صفحه‌های پردازش‌نشده: **{pages}**")
    lines.extend(["", "---", ""])

    for question in exam.get("questions") or []:
        number = clean_exam_markdown(question.get("source_question_number") or "؟")
        lines.extend([
            f"## سؤال {number}",
            "",
            clean_exam_markdown(question.get("question_text_markdown") or "_صورت سؤال استخراج نشده است._"),
            "",
        ])
        for option in question.get("options") or []:
            label = clean_exam_markdown(option.get("label") or "")
            text = clean_exam_markdown(option.get("text_markdown") or "")
            if label and text:
                lines.append(f"{label}) {text}")
        correct = clean_exam_markdown(question.get("correct_option_label") or "")
        if correct:
            lines.extend(["", f"**پاسخ صحیح:** گزینه {correct}"])
        solution = clean_exam_markdown(question.get("teacher_solution_markdown") or "")
        if solution:
            lines.extend(["", "**راه‌حل تشریحی:**", "", solution])
        source_pages = question.get("source_pages") or []
        if source_pages:
            lines.extend(["", f"_صفحات منبع: {', '.join(map(str, source_pages))}_"])
        issue_codes = question.get("issues") or []
        if issue_codes:
            lines.extend(["", f"_نیازمند بازبینی: {', '.join(map(str, issue_codes))}_"])
        lines.extend(["", "---", ""])

    if result.orphan_answers:
        lines.extend([
            "## پاسخ‌های بدون صورت سؤال",
            "",
            "این رکوردها عمداً سؤال جدید نساختند:",
            "",
        ])
        for orphan in result.orphan_answers:
            answer = f"، گزینه {orphan.correct_option_label}" if orphan.correct_option_label else ""
            pages = "، ".join(map(str, orphan.source_pages)) or "نامشخص"
            lines.append(
                f"- سؤال {orphan.question_number}{answer} — صفحات پاسخ: {pages}"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"
