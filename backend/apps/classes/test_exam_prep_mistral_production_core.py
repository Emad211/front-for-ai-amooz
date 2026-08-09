from __future__ import annotations

from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services.exam_prep_mistral_solution_headings import AlignedSolutionHeading


def test_question_region_parser_keeps_exact_1_to_4_options():
    stem, options, style = production.parse_question_region_text(
        "۱۲- متن سؤال؟ ۱) گزینه اول ۲) گزینه دوم ۳) گزینه سوم ۴) گزینه چهارم"
    )
    assert stem == "متن سؤال؟"
    assert style == "marker"
    assert [item["label"] for item in options] == ["1", "2", "3", "4"]
    assert [item["text_markdown"] for item in options] == [
        "گزینه اول",
        "گزینه دوم",
        "گزینه سوم",
        "گزینه چهارم",
    ]


def test_target_only_recovery_ignores_non_target_high_confidence_headings():
    headings = [
        {
            "rawQuestionNumber": 4,
            "optionLabel": 2,
            "optionLabelValid": True,
            "physicalPageNumber": 33,
            "column": "left",
        },
        {
            "rawQuestionNumber": 12,
            "optionLabel": 1,
            "optionLabelValid": True,
            "physicalPageNumber": 33,
            "column": "left",
        },
        {
            "rawQuestionNumber": 13,
            "optionLabel": 2,
            "optionLabelValid": True,
            "physicalPageNumber": 33,
            "column": "left",
        },
    ]
    assert production._resolve_target_headings(headings, [4]) == {
        4: ("2", 33, "left")
    }


def test_target_recovery_conflict_fails_closed():
    headings = [
        {
            "rawQuestionNumber": 57,
            "optionLabel": 2,
            "optionLabelValid": True,
            "physicalPageNumber": 40,
            "column": "left",
        },
        {
            "rawQuestionNumber": 57,
            "optionLabel": 3,
            "optionLabelValid": True,
            "physicalPageNumber": 40,
            "column": "left",
        },
    ]
    assert production._resolve_target_headings(headings, [57]) == {}


def test_target_crop_specs_use_only_neighboring_solution_columns():
    accepted = [
        AlignedSolutionHeading(
            physical_page_number=33,
            provider_block_index=1,
            column="right",
            raw_question_number=3,
            question_number=3,
            raw_option_label=1,
            option_label=1,
            option_label_normalized=False,
            option_label_valid=True,
            question_number_recovered=False,
            recovery_reason=None,
        ),
        AlignedSolutionHeading(
            physical_page_number=33,
            provider_block_index=2,
            column="left",
            raw_question_number=7,
            question_number=7,
            raw_option_label=2,
            option_label=2,
            option_label_normalized=False,
            option_label_valid=True,
            question_number_recovered=False,
            recovery_reason=None,
        ),
    ]
    assert production._target_crop_specs(accepted, [4, 5, 6]) == [
        (33, "right"),
        (33, "left"),
    ]


def test_duplicate_question_anchor_is_a_production_critical_code():
    assert "mistral_duplicate_question_anchor" in production._OWN_CRITICAL_CODES
