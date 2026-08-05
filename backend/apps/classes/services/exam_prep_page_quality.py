"""Semantic quality gate for the simple page-first exam-prep pipeline.

Schema validity is necessary but not sufficient. This module performs small,
deterministic repairs, rejects poisoned native Persian text, recomputes canonical
issues, and decides whether a second source-reading pass is warranted.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .exam_prep_page_records import (
    ANSWER_RECORD_TYPES,
    QUESTION_RECORD_TYPES,
    PageExtraction,
    PageOption,
    PageRecord,
)
from .exam_prep_text_quality import (
    has_broken_persian_text,
    has_duplicate_clean_and_broken_text,
    native_text_for_model,
)
from .exam_prep_utils import clean_exam_markdown


_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_PERSIAN_OPTION_LABELS = ("الف", "ب", "ج", "د", "ه", "و")
_STRUCTURAL_ISSUE_ALIASES = {
    "missing_options_text": "missing_option_text",
    "missing_options": "missing_options",
    "missing_option": "missing_options",
    "missing_question": "missing_question_text",
    "missing_question_text": "missing_question_text",
    "missing_answer": "missing_answer",
    "missing_solution": "missing_solution_text",
    "missing_solution_text": "missing_solution_text",
    "correct_option_not_in_options": "correct_option_not_in_options",
    "invalid_correct_option": "correct_option_not_in_options",
    "placeholder_options": "placeholder_option_text",
    "placeholder_option_text": "placeholder_option_text",
    "unexpected_option_count": "unexpected_option_count",
    "duplicate_option_label": "duplicate_option_label",
    "visual_evidence_required": "visual_evidence_required",
    "broken_persian_text": "broken_persian_text",
    "broken_rtl_text": "broken_persian_text",
    "duplicate_mixed_text": "duplicate_mixed_text",
}
_CANONICAL_CRITICAL_CODES = frozenset(
    {
        "missing_question_text",
        "missing_options",
        "missing_option_text",
        "missing_solution_text",
        "placeholder_option_text",
        "unexpected_option_count",
        "duplicate_option_label",
        "correct_option_not_in_options",
        "visual_evidence_required",
        "broken_persian_text",
        "duplicate_mixed_text",
    }
)
_REPAIRABLE_CRITICAL_CODES = _CANONICAL_CRITICAL_CODES - {
    "visual_evidence_required",
}
_MARKER_ONLY_RE = re.compile(
    r"^\s*(?:گزین[ههۀ]\s*)?[«»\"'()\[\]{}]*\s*"
    r"(?P<label>[0-9۰-۹٠-٩]+|[الفبجدهو])"
    r"\s*[«»\"'()\[\]{}.:：،,\-–—]*\s*$",
    flags=re.IGNORECASE,
)
_NATIVE_QUESTION_HEADING_RE = re.compile(
    r"(?m)^\s*(?:"
    r"[-–—ـ]\s*(?P<prefix_number>[0-9۰-۹٠-٩]{1,3})"
    r"|"
    r"(?P<suffix_number>[0-9۰-۹٠-٩]{1,3})\s*[-–—ـ]"
    r")\s+"
)
_NATIVE_OPTION_START_RE = re.compile(
    r"(?m)^\s*(?P<label>[1-6۱-۶١-٦])\)\s*"
)
# Only deictic references that require a nearby visual are critical. Generic
# mentions such as "تصویر کاریوتیپ" are not enough.
_VISUAL_REFERENCE_RE = re.compile(
    r"(?:"
    r"(?:با\s+توجه\s+به|مطابق|براساس)\s+(?:شکل|نمودار|تصویر)\s*(?:مقابل|زیر|بالا|رو\s*به\s*رو)?"
    r"|شکل\s*(?:مقابل|زیر|بالا|رو\s*به\s*رو)"
    r"|نمودار\s+(?:مقابل|زیر|بالا|نشان\s+داده\s+شده)"
    r"|طیف\s+طول\s+موج\s+(?:مرئی\s+)?(?:مقابل|نمایش\s+داده\s+شده)"
    r")",
    flags=re.IGNORECASE,
)
_COUNT_QUESTION_RE = re.compile(
    r"(?:چند\s+(?:مورد|عبارت|گزینه)|تعداد\s+(?:موارد|عبارت|گزینه))",
    flags=re.IGNORECASE,
)
_BROKEN_PREFIX_RE = re.compile(
    r"^\s*[اآبپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]\)\s*\S",
)
_FOOTER_RE = re.compile(
    r"(?m)^\s*(?:Telegram\s*:|www\.|@konkur|صفحه\s*:).*$",
    flags=re.IGNORECASE,
)
_SOLUTION_PAGE_RE = re.compile(
    r"(?:پاسخ\s*تشریحی|بررسی\s+(?:سایر\s+)?گزینه|گزینه\s*[«\"']?\d+[»\"']?\s*[:：])",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class NativeQuestionEvidence:
    question_number: int
    question_text: str
    options: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PageQualitySummary:
    critical_codes: tuple[str, ...]
    repairable_critical_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]
    question_count: int
    option_character_count: int
    solution_character_count: int

    @property
    def critical_count(self) -> int:
        return len(self.critical_codes)

    @property
    def repairable_critical_count(self) -> int:
        return len(self.repairable_critical_codes)

    @property
    def rank(self) -> tuple[int, int, int, int, int]:
        """Lower is better, richer complete output breaks ties."""

        return (
            self.critical_count,
            self.repairable_critical_count,
            -self.solution_character_count,
            -self.option_character_count,
            -self.question_count,
        )


def _latin_digits(value: Any) -> str:
    return str(value or "").translate(_DIGIT_TRANSLATION)


def _normalized_label(value: Any) -> str:
    text = clean_exam_markdown(_latin_digits(value)).strip()
    text = re.sub(r"^گزین[ههۀ]\s*", "", text, flags=re.IGNORECASE)
    text = text.strip(" \t\r\n«»\"'()[]{}.:：،,-–—")
    if text.isdigit():
        return str(int(text))
    return text


def _normalized_text(value: Any) -> str:
    return " ".join(clean_exam_markdown(value).split()).casefold()


def _marker_only(value: Any) -> str | None:
    match = _MARKER_ONLY_RE.fullmatch(clean_exam_markdown(value))
    if match is None:
        return None
    label = _normalized_label(match.group("label"))
    return label or None


def _expected_label_sequence(count: int) -> tuple[tuple[str, ...], ...]:
    numeric = tuple(str(index) for index in range(1, count + 1))
    persian = tuple(_PERSIAN_OPTION_LABELS[:count])
    return numeric, persian


def _labels_are_coherent(options: list[PageOption]) -> bool:
    labels = tuple(_normalized_label(option.label) for option in options)
    if not labels or any(not label for label in labels):
        return False
    return labels in _expected_label_sequence(len(labels))


def _options_are_placeholders(options: list[PageOption]) -> bool:
    return bool(options) and all(
        _marker_only(option.text_markdown) is not None
        for option in options
    )


def _has_broken_option_prefix(options: list[PageOption]) -> bool:
    return any(
        _BROKEN_PREFIX_RE.match(clean_exam_markdown(option.text_markdown))
        for option in options
    )


def _collapse_interleaved_options(
    options: list[PageOption],
) -> tuple[list[PageOption], bool]:
    """Repair ``[marker, text, marker, text, ...]`` provider output."""

    if len(options) < 4 or len(options) % 2:
        return options, False
    pair_count = len(options) // 2
    if not 2 <= pair_count <= 6:
        return options, False

    markers: list[str] = []
    repaired: list[PageOption] = []
    for index in range(pair_count):
        marker_option = options[index * 2]
        text_option = options[index * 2 + 1]
        marker = _marker_only(marker_option.text_markdown)
        text = clean_exam_markdown(text_option.text_markdown)
        if marker is None or not text:
            return options, False
        markers.append(marker)
        repaired.append(PageOption(label=marker, text_markdown=text))

    if tuple(markers) not in _expected_label_sequence(pair_count):
        return options, False
    return repaired, True


def parse_native_question_evidence(
    native_text: str,
) -> dict[int, NativeQuestionEvidence]:
    """Extract only clear line-oriented question/option blocks."""

    text = native_text_for_model(native_text)
    if not text:
        return {}
    text = _FOOTER_RE.sub("", text)
    headings = list(_NATIVE_QUESTION_HEADING_RE.finditer(text))
    evidence: dict[int, NativeQuestionEvidence] = {}
    for index, heading in enumerate(headings):
        raw_number = heading.group("prefix_number") or heading.group("suffix_number")
        number = int(_latin_digits(raw_number))
        block_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end():block_end].strip()
        option_starts = list(_NATIVE_OPTION_START_RE.finditer(block))
        options: list[tuple[str, str]] = []
        question_text = block
        if option_starts:
            question_text = block[: option_starts[0].start()].strip()
            for option_index, option_start in enumerate(option_starts):
                value_end = (
                    option_starts[option_index + 1].start()
                    if option_index + 1 < len(option_starts)
                    else len(block)
                )
                label = _normalized_label(option_start.group("label"))
                option_text = clean_exam_markdown(block[option_start.end():value_end]).strip()
                if label and option_text:
                    options.append((label, option_text))
        labels = tuple(label for label, _value in options)
        if options and labels not in _expected_label_sequence(len(options)):
            options = []
        evidence[number] = NativeQuestionEvidence(
            question_number=number,
            question_text=question_text,
            options=tuple(options),
        )
    return evidence


def _native_options(evidence: NativeQuestionEvidence | None) -> list[PageOption]:
    if evidence is None:
        return []
    return [PageOption(label=label, text_markdown=text) for label, text in evidence.options]


def _options_differ_materially(current: list[PageOption], native: list[PageOption]) -> bool:
    if len(current) != len(native):
        return True
    for current_option, native_option in zip(current, native):
        if _normalized_label(current_option.label) != _normalized_label(native_option.label):
            return True
        current_text = _normalized_text(current_option.text_markdown)
        native_text = _normalized_text(native_option.text_markdown)
        if not current_text or not native_text:
            return True
        if current_text == native_text or current_text in native_text or native_text in current_text:
            continue
        return True
    return False


def _provider_warning_issues(values: list[str]) -> list[str]:
    warnings: list[str] = []
    for value in values:
        raw = clean_exam_markdown(value).strip()
        if not raw:
            continue
        normalized = re.sub(r"[^a-z0-9_:-]+", "_", raw.casefold()).strip("_")
        canonical = _STRUCTURAL_ISSUE_ALIASES.get(normalized)
        if canonical in _CANONICAL_CRITICAL_CODES:
            continue
        warning = f"provider_warning:{normalized or 'unspecified'}"
        if warning not in warnings:
            warnings.append(warning)
    return warnings


def _text_fields(record: PageRecord) -> tuple[str, ...]:
    return (
        record.question_text_markdown,
        *(option.text_markdown for option in record.options),
        record.correct_option_text_markdown,
        record.teacher_solution_markdown,
        record.final_answer_markdown,
    )


def page_expects_solutions(page: PageExtraction, *, native_text: str = "") -> bool:
    reliable_native = native_text_for_model(native_text)
    if reliable_native and _SOLUTION_PAGE_RE.search(reliable_native):
        return True
    return any(
        record.record_type in ANSWER_RECORD_TYPES
        and len(clean_exam_markdown(record.teacher_solution_markdown)) >= 80
        for record in page.records
    )


def page_is_answer_heavy(page: PageExtraction, *, native_text: str = "") -> bool:
    answer_count = sum(record.record_type in ANSWER_RECORD_TYPES for record in page.records)
    question_count = sum(record.record_type in QUESTION_RECORD_TYPES for record in page.records)
    if answer_count >= 3 and answer_count >= question_count * 2:
        return True
    reliable_native = native_text_for_model(native_text)
    heading_count = len(re.findall(r"(?m)^\s*\d{1,3}\s*[-–—.:)]\s*گزین[ههۀ]", reliable_native))
    return heading_count >= 3


def _question_issues(record: PageRecord) -> list[str]:
    issues = _provider_warning_issues(record.issues)
    text = clean_exam_markdown(record.question_text_markdown)
    options = record.options
    if not text:
        issues.append("missing_question_text")
    if len(options) < 2:
        issues.append("missing_options")
    elif len(options) > 6:
        issues.append("unexpected_option_count")
    labels = [_normalized_label(option.label) for option in options]
    if labels and len(labels) != len(set(labels)):
        issues.append("duplicate_option_label")
    if options and any(not clean_exam_markdown(option.text_markdown).strip() for option in options):
        issues.append("missing_option_text")
    if options and _options_are_placeholders(options) and _COUNT_QUESTION_RE.search(text) is None:
        issues.append("placeholder_option_text")
    if _VISUAL_REFERENCE_RE.search(text):
        issues.append("visual_evidence_required")
    correct = _normalized_label(record.correct_option_label)
    if correct and labels and correct not in labels:
        issues.append("correct_option_not_in_options")
    if any(has_broken_persian_text(value) for value in _text_fields(record)):
        issues.append("broken_persian_text")
    if any(has_duplicate_clean_and_broken_text(value) for value in _text_fields(record)):
        issues.append("duplicate_mixed_text")
    if record.confidence < 0.55:
        issues.append("low_confidence")
    return list(dict.fromkeys(issues))


def _answer_issues(record: PageRecord, *, expect_solution: bool) -> list[str]:
    issues = _provider_warning_issues(record.issues)
    solution = clean_exam_markdown(record.teacher_solution_markdown)
    if expect_solution and record.correct_option_label and len(solution) < 24:
        issues.append("missing_solution_text")
    if any(has_broken_persian_text(value) for value in _text_fields(record)):
        issues.append("broken_persian_text")
    if any(has_duplicate_clean_and_broken_text(value) for value in _text_fields(record)):
        issues.append("duplicate_mixed_text")
    if record.confidence < 0.55:
        issues.append("low_confidence")
    return list(dict.fromkeys(issues))


def reconcile_page_extraction(
    page: PageExtraction,
    *,
    native_text: str = "",
) -> PageExtraction:
    """Repair deterministic shape failures and recompute canonical issues."""

    native_by_number = parse_native_question_evidence(native_text)
    expect_solution = page_expects_solutions(page, native_text=native_text)
    reconciled: list[PageRecord] = []
    changed = False
    for record in page.records:
        if record.record_type in ANSWER_RECORD_TYPES and record.record_type not in QUESTION_RECORD_TYPES:
            updated = record.model_copy(
                update={"issues": _answer_issues(record, expect_solution=expect_solution)}
            )
            reconciled.append(updated)
            changed = changed or updated != record
            continue
        if record.record_type not in QUESTION_RECORD_TYPES:
            normalized_issues = _provider_warning_issues(record.issues)
            updated = record if normalized_issues == record.issues else record.model_copy(update={"issues": normalized_issues})
            reconciled.append(updated)
            changed = changed or updated != record
            continue

        options, collapsed = _collapse_interleaved_options(list(record.options))
        evidence = native_by_number.get(record.question_number)
        native_options = _native_options(evidence)
        suspect = bool(
            collapsed
            or len(options) < 2
            or len(options) > 6
            or not _labels_are_coherent(options)
            or _has_broken_option_prefix(options)
            or (
                _options_are_placeholders(options)
                and _COUNT_QUESTION_RE.search(clean_exam_markdown(record.question_text_markdown)) is None
            )
        )
        if native_options and (suspect or _options_differ_materially(options, native_options)):
            options = native_options

        candidate = record.model_copy(update={"options": options})
        updated = candidate.model_copy(update={"issues": _question_issues(candidate)})
        reconciled.append(updated)
        changed = changed or updated != record
    return page.model_copy(update={"records": reconciled}) if changed else page


def summarize_page_quality(page: PageExtraction) -> PageQualitySummary:
    critical: list[str] = []
    repairable: list[str] = []
    warnings: list[str] = []
    question_count = 0
    option_character_count = 0
    solution_character_count = 0
    for record in page.records:
        if record.record_type in QUESTION_RECORD_TYPES:
            question_count += 1
            option_character_count += sum(
                len(clean_exam_markdown(option.text_markdown)) for option in record.options
            )
        if record.record_type in ANSWER_RECORD_TYPES:
            solution_character_count += len(clean_exam_markdown(record.teacher_solution_markdown))
        for code in record.issues:
            if code in _CANONICAL_CRITICAL_CODES:
                critical.append(code)
                if code in _REPAIRABLE_CRITICAL_CODES:
                    repairable.append(code)
            else:
                warnings.append(code)
    return PageQualitySummary(
        critical_codes=tuple(critical),
        repairable_critical_codes=tuple(repairable),
        warning_codes=tuple(warnings),
        question_count=question_count,
        option_character_count=option_character_count,
        solution_character_count=solution_character_count,
    )


def choose_better_page_extraction(current: PageExtraction, candidate: PageExtraction) -> PageExtraction:
    current_quality = summarize_page_quality(current)
    candidate_quality = summarize_page_quality(candidate)
    return candidate if candidate_quality.rank < current_quality.rank else current
