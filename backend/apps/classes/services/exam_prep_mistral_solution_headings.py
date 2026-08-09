from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from .exam_prep_mistral_layout_analysis import (
    LayoutBlock,
    is_rtl_double_column,
    normalize_page_blocks,
)

_DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_SOLUTION_PAGE_HEADER_RE = re.compile(r"پاسخ", re.IGNORECASE)
_Q_FIRST_RE = re.compile(
    r"^\s*[#«»\"'()]*\s*(?P<question>[0-9۰-۹٠-٩]{1,3})\s*[»\"'()]*\s*"
    r"(?:[-–—]\s*)?گزین(?:ه|ۀ|هٔ)\s*[«»\"'()]*\s*"
    r"(?P<option>[0-9۰-۹٠-٩]{1,2})\s*[»\"'()]*",
    re.IGNORECASE,
)
_OPTION_FIRST_RE = re.compile(
    r"^\s*[#«»\"'()]*\s*(?P<option>[0-9۰-۹٠-٩]{1,2})\s*[»\"'()]*\s*"
    r"گزین(?:ه|ۀ|هٔ)\s*(?:[-–—]\s*)?"
    r"(?P<question>[0-9۰-۹٠-٩]{1,3})",
    re.IGNORECASE,
)


def _digits(value: Any) -> str:
    return str(value or "").translate(_DIGIT_TRANS)


def _integer(value: Any) -> int | None:
    match = re.search(r"\d+", _digits(value))
    return int(match.group(0)) if match else None


def is_solution_content_page(page: Mapping[str, Any]) -> bool:
    """Return true only for worked-answer pages, not the answer-booklet cover."""

    return bool(_SOLUTION_PAGE_HEADER_RE.search(str(page.get("header") or "")))


def parse_solution_heading(text: str) -> dict[str, Any] | None:
    """Parse both real OCR heading orders observed in the source document."""

    value = str(text or "").strip()
    for format_name, pattern in (
        ("question_first", _Q_FIRST_RE),
        ("option_first", _OPTION_FIRST_RE),
    ):
        match = pattern.match(value)
        if not match:
            continue
        question = _integer(match.group("question"))
        option = _integer(match.group("option"))
        if question is None or option is None:
            return None
        return {
            "rawQuestionNumber": question,
            "rawOptionLabel": option,
            "format": format_name,
        }
    return None


def normalize_solution_option_label(raw: int | None) -> tuple[int | None, bool, bool]:
    """Normalize only the observed 10/20/30/40 rendering of options 1..4."""

    if raw in {1, 2, 3, 4}:
        return raw, False, True
    if raw in {10, 20, 30, 40}:
        return raw // 10, True, True
    return raw, False, False


@dataclass(frozen=True, slots=True)
class SolutionHeadingCandidate:
    physical_page_number: int
    provider_block_index: int
    column: str
    y0: float
    raw_question_number: int
    raw_option_label: int
    heading_format: str


@dataclass(frozen=True, slots=True)
class AlignedSolutionHeading:
    physical_page_number: int
    provider_block_index: int
    column: str
    raw_question_number: int
    question_number: int
    raw_option_label: int
    option_label: int | None
    option_label_normalized: bool
    option_label_valid: bool
    question_number_recovered: bool
    recovery_reason: str | None


def _ordered_solution_blocks(page: Mapping[str, Any]) -> list[LayoutBlock]:
    blocks = normalize_page_blocks(page)
    if not is_rtl_double_column(blocks):
        return sorted(blocks, key=lambda block: (block.bbox[1], block.bbox[0]))
    span = sorted(
        (block for block in blocks if block.column == "span"),
        key=lambda block: (block.bbox[1], block.bbox[0]),
    )
    right = sorted(
        (block for block in blocks if block.column == "right"),
        key=lambda block: (block.bbox[1], block.bbox[0]),
    )
    left = sorted(
        (block for block in blocks if block.column == "left"),
        key=lambda block: (block.bbox[1], block.bbox[0]),
    )
    return span + right + left


def solution_heading_candidates(
    page: Mapping[str, Any],
    *,
    physical_page_number: int,
) -> list[SolutionHeadingCandidate]:
    if not is_solution_content_page(page):
        return []
    candidates: list[SolutionHeadingCandidate] = []
    for block in _ordered_solution_blocks(page):
        parsed = parse_solution_heading(block.content)
        if not parsed:
            continue
        candidates.append(
            SolutionHeadingCandidate(
                physical_page_number=physical_page_number,
                provider_block_index=block.provider_index,
                column=block.column,
                y0=block.bbox[1],
                raw_question_number=int(parsed["rawQuestionNumber"]),
                raw_option_label=int(parsed["rawOptionLabel"]),
                heading_format=str(parsed["format"]),
            )
        )
    return candidates


def align_solution_headings(
    candidates: Sequence[SolutionHeadingCandidate],
    *,
    first_expected_question: int = 1,
    last_expected_question: int | None = None,
) -> dict[str, Any]:
    """Align OCR solution headings against the monotonic printed sequence.

    A number is recovered only when neighboring anchors make that correction
    deterministic. Provider duplicates and missing headings remain explicit;
    geometry alone never fabricates a missing solution boundary.
    """

    expected = max(1, int(first_expected_question))
    accepted: list[AlignedSolutionHeading] = []
    duplicate_candidates: list[dict[str, int]] = []
    missing_numbers: list[int] = []
    recoveries: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates):
        raw = candidate.raw_question_number
        next_raw = (
            candidates[index + 1].raw_question_number
            if index + 1 < len(candidates)
            else None
        )
        question: int | None = None
        recovery_reason: str | None = None

        if raw == expected:
            question = raw
        elif (
            0 <= raw <= 9
            and expected >= 10
            and str(expected).endswith(str(raw))
        ):
            question = expected
            recovery_reason = "lost_leading_digits"
        elif raw == expected - 1:
            if next_raw == expected:
                duplicate_candidates.append(
                    {
                        "physicalPageNumber": candidate.physical_page_number,
                        "providerBlockIndex": candidate.provider_block_index,
                        "rawQuestionNumber": raw,
                    }
                )
                continue
            question = expected
            recovery_reason = "repeated_previous_number"
        elif next_raw == expected + 1 and raw != expected:
            question = expected
            recovery_reason = "next_anchor_confirms_expected"
        elif raw > expected:
            missing_numbers.extend(range(expected, raw))
            question = raw
            recovery_reason = "missing_heading_before_anchor"
        else:
            duplicate_candidates.append(
                {
                    "physicalPageNumber": candidate.physical_page_number,
                    "providerBlockIndex": candidate.provider_block_index,
                    "rawQuestionNumber": raw,
                }
            )
            continue

        normalized_option, option_normalized, option_valid = normalize_solution_option_label(
            candidate.raw_option_label
        )
        aligned = AlignedSolutionHeading(
            physical_page_number=candidate.physical_page_number,
            provider_block_index=candidate.provider_block_index,
            column=candidate.column,
            raw_question_number=raw,
            question_number=question,
            raw_option_label=candidate.raw_option_label,
            option_label=normalized_option,
            option_label_normalized=option_normalized,
            option_label_valid=option_valid,
            question_number_recovered=recovery_reason not in {None, "missing_heading_before_anchor"},
            recovery_reason=recovery_reason,
        )
        accepted.append(aligned)
        if aligned.question_number_recovered:
            recoveries.append(
                {
                    "physicalPageNumber": aligned.physical_page_number,
                    "providerBlockIndex": aligned.provider_block_index,
                    "rawQuestionNumber": aligned.raw_question_number,
                    "questionNumber": aligned.question_number,
                    "reason": aligned.recovery_reason,
                }
            )
        expected = question + 1

    if last_expected_question is not None and expected <= last_expected_question:
        missing_numbers.extend(range(expected, last_expected_question + 1))

    return {
        "accepted": accepted,
        "missingQuestionNumbers": sorted(set(missing_numbers)),
        "duplicateCandidates": duplicate_candidates,
        "recoveries": recoveries,
        "nextExpectedQuestion": expected,
    }


def audit_solution_headings(
    root: Mapping[str, Any],
    *,
    original_page_numbers: Sequence[int] | None = None,
    first_expected_question: int = 1,
    last_expected_question: int | None = None,
) -> dict[str, Any]:
    raw_pages = [
        page for page in (root.get("pages") or []) if isinstance(page, Mapping)
    ]
    raw_pages.sort(key=lambda page: int(page.get("index") or 0))
    mapping = list(original_page_numbers or [])
    candidates: list[SolutionHeadingCandidate] = []
    solution_pages: list[int] = []
    for position, page in enumerate(raw_pages):
        provider_index = int(page.get("index") or 0)
        physical_page = (
            int(mapping[position]) if position < len(mapping) else provider_index + 1
        )
        page_candidates = solution_heading_candidates(
            page,
            physical_page_number=physical_page,
        )
        if is_solution_content_page(page):
            solution_pages.append(physical_page)
        candidates.extend(page_candidates)

    aligned = align_solution_headings(
        candidates,
        first_expected_question=first_expected_question,
        last_expected_question=last_expected_question,
    )
    accepted: list[AlignedSolutionHeading] = aligned["accepted"]
    invalid_options = [
        {
            "physicalPageNumber": item.physical_page_number,
            "questionNumber": item.question_number,
            "rawOptionLabel": item.raw_option_label,
        }
        for item in accepted
        if not item.option_label_valid
    ]
    per_page: dict[int, dict[str, int]] = {}
    for page in solution_pages:
        per_page[page] = {"candidateCount": 0, "acceptedCount": 0}
    for candidate in candidates:
        per_page.setdefault(
            candidate.physical_page_number,
            {"candidateCount": 0, "acceptedCount": 0},
        )["candidateCount"] += 1
    for item in accepted:
        per_page.setdefault(
            item.physical_page_number,
            {"candidateCount": 0, "acceptedCount": 0},
        )["acceptedCount"] += 1

    return {
        "schemaVersion": 1,
        "contentFree": True,
        "solutionPageCount": len(solution_pages),
        "solutionPages": solution_pages,
        "rawCandidateCount": len(candidates),
        "acceptedHeadingCount": len(accepted),
        "uniqueAcceptedQuestionCount": len(
            {item.question_number for item in accepted}
        ),
        "missingSolutionHeadingNumbers": aligned["missingQuestionNumbers"],
        "recoveredQuestionNumbers": [
            item["questionNumber"] for item in aligned["recoveries"]
        ],
        "recoveryCount": len(aligned["recoveries"]),
        "duplicateCandidateCount": len(aligned["duplicateCandidates"]),
        "normalizedOptionLabelCount": sum(
            item.option_label_normalized for item in accepted
        ),
        "invalidOptionLabels": invalid_options,
        "perPage": [
            {"physicalPageNumber": page, **counts}
            for page, counts in sorted(per_page.items())
        ],
    }
