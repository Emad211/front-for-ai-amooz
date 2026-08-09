"""Compatibility for exams with multiple disjoint question-number ranges.

Stage 2's original research document had one contiguous 1..N numbering range.
Some Kانون PDFs combine independent booklets in one file (for example 1..105 and
251..290). This module keeps the frozen Stage-2 core intact while using declared
booklet tables to align solution headings inside each real interval and to assign
separate scope keys only when a document is genuinely disjoint.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_stage2_core as core
from .exam_prep_mistral_ocr_transport import OCR4DocumentResult
from .exam_prep_mistral_solution_headings import (
    AlignedSolutionHeading,
    align_solution_headings,
    solution_heading_candidates,
)
from .exam_prep_page_source import SourcePageExtraction
from .exam_prep_utils import clean_exam_markdown


_OBSERVED_GAP_THRESHOLD = 20
_MIN_FALLBACK_CLUSTER_SIZE = 3


def _merge_ranges(values: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: list[list[int]] = []
    for start, end in sorted((int(a), int(b)) for a, b in values if 1 <= int(a) <= int(b)):
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return tuple((start, end) for start, end in merged)


def _observed_clusters(question_numbers: Sequence[int]) -> list[tuple[int, int, int]]:
    """Return robust observed number clusters separated by a very large gap.

    A few missed OCR anchors must never create a synthetic booklet. The fallback
    therefore requires at least three observed questions in a cluster and a gap
    greater than 20 question numbers before splitting.
    """

    observed = sorted({int(value) for value in question_numbers if int(value) > 0})
    if not observed:
        return []
    groups: list[list[int]] = [[observed[0]]]
    for value in observed[1:]:
        if value - groups[-1][-1] > _OBSERVED_GAP_THRESHOLD:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [
        (group[0], group[-1], len(group))
        for group in groups
        if len(group) >= _MIN_FALLBACK_CLUSTER_SIZE
    ]


def declared_question_intervals(
    evidence: core.MistralDocumentEvidence,
    question_numbers: Sequence[int],
) -> tuple[tuple[int, int], ...]:
    """Return real booklet intervals without fabricating OCR gaps.

    Declared booklet tables are authoritative when present. A deterministic
    observed-anchor fallback only augments a declared set when a large, dense
    cluster of numbered questions is completely outside every parsed table. This
    covers alternate booklet-table layouts while preventing one noisy anchor from
    creating a new scope.
    """

    rows = [
        item
        for item in (evidence.booklet_ranges.get("ranges") or [])
        if isinstance(item, Mapping) and item.get("countMatchesRange") is True
    ]
    declared: list[tuple[int, int]] = []
    for item in rows:
        start = core._integer(item.get("start"))
        end = core._integer(item.get("end"))
        if start is not None and end is not None and 1 <= start <= end:
            declared.append((start, end))
    merged_declared = list(_merge_ranges(declared))

    observed = sorted({int(value) for value in question_numbers if int(value) > 0})
    if not observed:
        return tuple(merged_declared)

    if not merged_declared:
        clusters = _observed_clusters(observed)
        if len(clusters) >= 2:
            return tuple((start, end) for start, end, _count in clusters)
        return ((min(observed), max(observed)),)

    # Keep only declared intervals that actually contain observed questions.
    relevant = [
        (start, end)
        for start, end in merged_declared
        if any(start <= value <= end for value in observed)
    ]

    # If an entire dense observed cluster lies outside every parsed declaration,
    # add it as a fallback booklet interval. This is exactly the situation in
    # Kانون files whose cover uses the compact ``نام درس / شماره سؤال`` schema.
    for start, end, _count in _observed_clusters(observed):
        if any(not (end < a or start > b) for a, b in relevant):
            continue
        relevant.append((start, end))

    if not relevant:
        return ((min(observed), max(observed)),)
    return _merge_ranges(relevant)


def scope_key_for_question(
    intervals: Sequence[tuple[int, int]],
    question_number: int,
) -> str:
    if len(intervals) <= 1:
        return "default"
    for start, end in intervals:
        if start <= question_number <= end:
            return f"range-{start}-{end}"
    return "default"


def _looks_like_next_range_start(
    *,
    raw: int,
    next_start: int | None,
    current_end: int,
    last_accepted: int,
) -> bool:
    if next_start is None:
        return False
    if raw >= next_start:
        return True
    if last_accepted < current_end - 2 or not 0 <= raw <= 9:
        return False
    return str(next_start).endswith(str(raw))


def aligned_solutions_for_intervals(
    result: OCR4DocumentResult,
    intervals: Sequence[tuple[int, int]],
) -> tuple[list[AlignedSolutionHeading], list[int], list[int]]:
    """Align headings per real interval without fabricating intentional gaps."""

    candidates = []
    for page in result.pages:
        physical = int(page.get("sourcePhysicalPage") or int(page.get("index") or 0) + 1)
        candidates.extend(solution_heading_candidates(page, physical_page_number=physical))

    if not intervals:
        return [], [], []
    ordered_ranges = sorted((int(start), int(end)) for start, end in intervals)
    cursor = 0
    accepted: list[AlignedSolutionHeading] = []
    missing: set[int] = set()
    invalid: set[int] = set()

    for index, (start, end) in enumerate(ordered_ranges):
        next_start = ordered_ranges[index + 1][0] if index + 1 < len(ordered_ranges) else None
        selected = []
        last_accepted = start - 1

        while cursor < len(candidates):
            candidate = candidates[cursor]
            raw = int(candidate.raw_question_number)
            if _looks_like_next_range_start(
                raw=raw,
                next_start=next_start,
                current_end=end,
                last_accepted=last_accepted,
            ):
                break

            selected.append(candidate)
            cursor += 1
            trial = align_solution_headings(
                selected,
                first_expected_question=start,
                last_expected_question=None,
            )
            in_range = [
                item.question_number
                for item in (trial.get("accepted") or [])
                if start <= item.question_number <= end
            ]
            if in_range:
                last_accepted = max(in_range)
            if last_accepted >= end:
                break

        aligned = align_solution_headings(
            selected,
            first_expected_question=start,
            last_expected_question=end,
        )
        accepted.extend(
            item
            for item in (aligned.get("accepted") or [])
            if start <= item.question_number <= end
        )
        missing.update(
            int(value)
            for value in (aligned.get("missingQuestionNumbers") or [])
            if start <= int(value) <= end
        )
        invalid.update(
            item.question_number
            for item in (aligned.get("accepted") or [])
            if start <= item.question_number <= end and not item.option_label_valid
        )

    return accepted, sorted(missing), sorted(invalid)


def build_page_extractions_disjoint(
    *,
    result: OCR4DocumentResult,
    evidence: core.MistralDocumentEvidence,
    recovered_targets: Mapping[int, tuple[str, int, str]],
    intervals: Sequence[tuple[int, int]],
) -> list[SourcePageExtraction]:
    """Stage-2 assembly with range-aware solution alignment and scope keys."""

    records_by_page: dict[int, list[dict[str, Any]]] = {}
    pages = core._analysis_pages(evidence)
    question_numbers: list[int] = []

    for page_number, page in sorted(pages.items()):
        if str(page.get("pageRole") or "") != "question":
            continue
        for region in page.get("regions") or []:
            if not isinstance(region, Mapping) or str(region.get("kind") or "") != "question":
                continue
            record = core._question_record(region)
            if record is None:
                continue
            number = int(record["question_number"])
            record["scope_key"] = scope_key_for_question(intervals, number)
            question_numbers.append(number)
            records_by_page.setdefault(page_number, []).append(record)

    if not question_numbers:
        return []
    accepted, _missing, _invalid = aligned_solutions_for_intervals(result, intervals)
    accepted_numbers: set[int] = set()
    for heading in accepted:
        accepted_numbers.add(heading.question_number)
        page = pages.get(heading.physical_page_number)
        region = core._solution_region(page, heading)
        recovered = recovered_targets.get(heading.question_number)
        if recovered is not None:
            label = recovered[0]
        elif heading.option_label_valid and heading.option_label in {1, 2, 3, 4}:
            label = str(heading.option_label)
        else:
            label = None
        issues = [
            str(code)
            for code in ((region.get("issues") or []) if isinstance(region, Mapping) else [])
            if str(code).strip()
        ]
        if heading.question_number_recovered:
            issues.append("solution_heading_number_recovered")
        if recovered is not None:
            issues.append("targeted_solution_heading_recovered")
        if label is None:
            issues.append("mistral_solution_heading_unresolved")
        records_by_page.setdefault(heading.physical_page_number, []).append(
            {
                "scope_key": scope_key_for_question(intervals, heading.question_number),
                "question_number": heading.question_number,
                "record_type": "solution",
                "correct_option_label": label,
                "teacher_solution_markdown": (
                    clean_exam_markdown(region.get("text") or "")
                    if isinstance(region, Mapping)
                    else ""
                ),
                "final_answer_markdown": f"گزینه {label}" if label else "",
                "confidence": 0.0,
                "issues": list(dict.fromkeys(issues)),
                "source_bbox": (
                    core._normalized_bbox(region.get("bbox"))
                    if isinstance(region, Mapping)
                    else core._column_bbox(heading.column)
                ),
            }
        )

    for question_number, (label, page_number, side) in recovered_targets.items():
        if question_number in accepted_numbers:
            continue
        records_by_page.setdefault(page_number, []).append(
            {
                "scope_key": scope_key_for_question(intervals, question_number),
                "question_number": question_number,
                "record_type": "answer",
                "correct_option_label": label,
                "final_answer_markdown": f"گزینه {label}",
                "confidence": 0.0,
                "issues": ["targeted_solution_heading_recovered"],
                "source_bbox": core._column_bbox(side),
            }
        )

    return [
        SourcePageExtraction.model_validate(
            {"page_number": page_number, "records": records}
        )
        for page_number, records in sorted(records_by_page.items())
    ]


__all__ = [
    "aligned_solutions_for_intervals",
    "build_page_extractions_disjoint",
    "declared_question_intervals",
    "scope_key_for_question",
]
