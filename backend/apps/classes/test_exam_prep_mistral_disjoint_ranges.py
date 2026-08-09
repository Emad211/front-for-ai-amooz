from __future__ import annotations

from types import SimpleNamespace

from apps.classes.services import exam_prep_mistral_disjoint_ranges as ranges
from apps.classes.services.exam_prep_mistral_solution_headings import SolutionHeadingCandidate
from apps.classes.services.exam_prep_mistral_stage2_core import MistralDocumentEvidence


def _evidence():
    declared = [
        (1, 20),
        (21, 40),
        (41, 75),
        (76, 105),
        (251, 270),
        (271, 290),
    ]
    return MistralDocumentEvidence(
        layout={},
        booklet_ranges={
            "ranges": [
                {
                    "start": start,
                    "end": end,
                    "questionCount": end - start + 1,
                    "countMatchesRange": True,
                    "physicalPageNumber": 1,
                }
                for start, end in declared
            ]
        },
        solution_headings={},
    )


def _candidate(number: int, *, page: int, raw: int | None = None):
    return SolutionHeadingCandidate(
        physical_page_number=page,
        provider_block_index=number,
        column="right",
        y0=0.1,
        raw_question_number=number if raw is None else raw,
        raw_option_label=1,
        heading_format="question_first",
    )


def test_declared_ranges_merge_only_contiguous_booklets():
    observed = list(range(1, 106)) + list(range(251, 291))
    intervals = ranges.declared_question_intervals(_evidence(), observed)
    assert intervals == ((1, 105), (251, 290))
    assert ranges.scope_key_for_question(intervals, 1) == "range-1-105"
    assert ranges.scope_key_for_question(intervals, 105) == "range-1-105"
    assert ranges.scope_key_for_question(intervals, 251) == "range-251-290"
    assert ranges.scope_key_for_question(intervals, 290) == "range-251-290"
    assert ranges.scope_key_for_question(((1, 155),), 94) == "default"


def test_solution_alignment_does_not_invent_106_to_250_gap(monkeypatch):
    first = [_candidate(number, page=40) for number in range(1, 106)]
    second = [_candidate(number, page=54) for number in range(251, 291)]

    def fake_candidates(page, *, physical_page_number):
        return first if physical_page_number == 40 else second

    monkeypatch.setattr(ranges, "solution_heading_candidates", fake_candidates)
    result = SimpleNamespace(
        pages=(
            {"index": 39, "sourcePhysicalPage": 40},
            {"index": 53, "sourcePhysicalPage": 54},
        )
    )
    accepted, missing, invalid = ranges.aligned_solutions_for_intervals(
        result,
        ((1, 105), (251, 290)),
    )
    numbers = [item.question_number for item in accepted]
    assert numbers == list(range(1, 106)) + list(range(251, 291))
    assert missing == []
    assert invalid == []
    assert not any(106 <= value <= 250 for value in numbers)


def test_lost_leading_digit_at_second_booklet_start_is_preserved(monkeypatch):
    first = [_candidate(number, page=40) for number in range(1, 106)]
    # OCR loses the leading digits of 251. The next interval's own aligner must
    # see raw 1 so it can deterministically recover expected question 251.
    second = [_candidate(251, page=54, raw=1)] + [
        _candidate(number, page=54) for number in range(252, 291)
    ]

    def fake_candidates(page, *, physical_page_number):
        return first if physical_page_number == 40 else second

    monkeypatch.setattr(ranges, "solution_heading_candidates", fake_candidates)
    result = SimpleNamespace(
        pages=(
            {"index": 39, "sourcePhysicalPage": 40},
            {"index": 53, "sourcePhysicalPage": 54},
        )
    )
    accepted, missing, _invalid = ranges.aligned_solutions_for_intervals(
        result,
        ((1, 105), (251, 290)),
    )
    recovered = {item.question_number: item for item in accepted}
    assert 251 in recovered
    assert recovered[251].question_number_recovered is True
    assert recovered[251].recovery_reason == "lost_leading_digits"
    assert missing == []
