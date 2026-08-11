from apps.classes.services.exam_prep_mistral_solution_headings import (
    SolutionHeadingCandidate,
    align_solution_headings,
    normalize_solution_option_label,
    parse_solution_heading,
)


def _candidate(page, block, question, option, *, column="right"):
    return SolutionHeadingCandidate(
        physical_page_number=page,
        provider_block_index=block,
        column=column,
        y0=block / 100,
        raw_question_number=question,
        raw_option_label=option,
        heading_format="question_first",
    )


def test_solution_heading_supports_question_first_and_option_first():
    assert parse_solution_heading("# ۳- گزینه ۳۰") == {
        "rawQuestionNumber": 3,
        "rawOptionLabel": 30,
        "format": "question_first",
    }
    assert parse_solution_heading("«۴» گزینه - ۱۱۲") == {
        "rawQuestionNumber": 112,
        "rawOptionLabel": 4,
        "format": "option_first",
    }


def test_solution_heading_unwraps_outer_math_text_markup_and_braces():
    expected = {
        "rawQuestionNumber": 89,
        "rawOptionLabel": 3,
        "format": "question_first",
    }

    assert parse_solution_heading(r"$$\text{۸۹- گزینه «۳»}$$") == expected
    assert parse_solution_heading(r"\(\text{۸۹- گزینه «۳»}\)") == expected
    assert parse_solution_heading("{۸۹- گزینه «۳»}") == expected


def test_solution_option_normalizes_only_the_observed_zero_suffix_pattern():
    assert normalize_solution_option_label(30) == (3, True, True)
    assert normalize_solution_option_label(4) == (4, False, True)
    assert normalize_solution_option_label(5) == (5, False, False)


def test_alignment_keeps_real_missing_headings_explicit():
    candidates = [
        _candidate(33, 1, 1, 10),
        _candidate(33, 2, 2, 40),
        _candidate(33, 3, 3, 30, column="left"),
        _candidate(34, 4, 7, 40),
        _candidate(34, 5, 8, 20),
        _candidate(34, 6, 8, 30),
        _candidate(34, 7, 11, 30, column="left"),
    ]

    report = align_solution_headings(candidates)
    accepted = report["accepted"]

    assert [item.question_number for item in accepted] == [1, 2, 3, 7, 8, 9, 11]
    assert report["missingQuestionNumbers"] == [4, 5, 6, 10]
    assert any(
        item.question_number == 9
        and item.recovery_reason == "repeated_previous_number"
        for item in accepted
    )


def test_alignment_repairs_lost_leading_digits_and_flags_bad_answer_label():
    candidates = [
        _candidate(40, 1, 55, 4),
        _candidate(40, 2, 6, 4),
        _candidate(40, 3, 7, 5),
    ]

    report = align_solution_headings(
        candidates,
        first_expected_question=55,
        last_expected_question=57,
    )
    accepted = report["accepted"]

    assert [item.question_number for item in accepted] == [55, 56, 57]
    assert accepted[1].recovery_reason == "lost_leading_digits"
    assert accepted[2].recovery_reason == "lost_leading_digits"
    assert accepted[2].option_label_valid is False


def test_alignment_uses_next_anchor_for_97_to_94_case():
    candidates = [
        _candidate(46, 1, 97, 2),
        _candidate(46, 2, 95, 2),
        _candidate(46, 3, 96, 4),
        _candidate(46, 4, 97, 1, column="left"),
    ]

    report = align_solution_headings(candidates, first_expected_question=94)

    assert [item.question_number for item in report["accepted"]] == [94, 95, 96, 97]
    assert report["accepted"][0].recovery_reason == "next_anchor_confirms_expected"


def test_ambiguous_duplicate_does_not_fabricate_missing_heading():
    candidates = [
        _candidate(37, 1, 31, 3),
        _candidate(37, 2, 32, 3),
        _candidate(37, 3, 33, 1),
        _candidate(37, 4, 34, 4, column="left"),
        _candidate(37, 5, 35, 4, column="left"),
        _candidate(37, 6, 36, 1, column="left"),
        _candidate(37, 7, 37, 3, column="left"),
        _candidate(37, 8, 31, 3, column="left"),
    ]

    report = align_solution_headings(candidates, first_expected_question=30)

    assert [item.question_number for item in report["accepted"]] == list(range(31, 38))
    assert report["missingQuestionNumbers"] == [30]
    assert report["duplicateCandidates"][-1]["rawQuestionNumber"] == 31


def test_exact_duplicate_before_expected_anchor_is_skipped():
    candidates = [
        _candidate(49, 1, 109, 4),
        _candidate(49, 2, 110, 4),
        _candidate(49, 3, 111, 4),
        _candidate(49, 4, 111, 4),
        _candidate(49, 5, 112, 4, column="left"),
    ]

    report = align_solution_headings(candidates, first_expected_question=109)

    assert [item.question_number for item in report["accepted"]] == [109, 110, 111, 112]
    assert len(report["duplicateCandidates"]) == 1
