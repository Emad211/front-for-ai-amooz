from __future__ import annotations

from types import SimpleNamespace

from apps.classes.services.exam_prep_mistral_stage4_field_safety import (
    compare_field,
    sanitize_source_markdown,
    uncertain_fields,
)


def test_numeric_order_only_difference_is_not_a_hard_conflict():
    agreement = compare_field(
        "teacher_solution_markdown",
        "x = 2 ، y = 3",
        "y=3 و x=2",
    )
    assert agreement.numeric_equal is True
    assert agreement.keyed_numeric_compared is True
    assert agreement.keyed_numeric_equal is True
    assert agreement.critical_conflict is False


def test_same_numbers_with_swapped_variable_bindings_remain_a_conflict():
    agreement = compare_field(
        "teacher_solution_markdown",
        "x=2 و y=3",
        "x=3 و y=2",
    )
    assert agreement.numeric_equal is True
    assert agreement.keyed_numeric_compared is True
    assert agreement.keyed_numeric_equal is False
    assert agreement.critical_conflict is True


def test_real_numeric_difference_remains_a_hard_conflict():
    agreement = compare_field(
        "teacher_solution_markdown",
        "x=2 و y=3",
        "x=2 و y=4",
    )
    assert agreement.numeric_equal is False
    assert agreement.critical_conflict is True


def test_answer_label_disagreement_is_not_a_hard_math_conflict():
    agreement = compare_field("correct_option_label", "1", "3")
    assert agreement.numeric_equal is False
    assert agreement.critical_conflict is False


def test_sanitizer_strips_fake_visual_url_author_and_page_metadata():
    value = (
        "راه حل واقعی\n"
        "حل‌کننده: نام شخص\n"
        "![](https://extracted-image-link)\n"
        "(فیزیک ۳، صفحه‌های ۴۰ تا ۴۵)"
    )
    cleaned, flags = sanitize_source_markdown(value)
    assert cleaned == "راه حل واقعی"
    assert "https://" not in cleaned
    assert "صفحه" not in cleaned
    assert "حل‌کننده" not in cleaned
    assert set(flags) >= {
        "removed_markdown_image",
        "removed_author_metadata",
        "removed_page_metadata",
    }


def test_uncertainty_is_field_specific_when_spans_exist():
    item = SimpleNamespace(
        uncertain_spans=(
            SimpleNamespace(field="option_3"),
            SimpleNamespace(field="teacher_solution_markdown"),
        ),
        transcription_uncertain=True,
    )
    assert uncertain_fields(item) == frozenset({"option_3", "teacher_solution_markdown"})


def test_coarse_uncertainty_fails_closed_when_no_field_span_exists():
    item = SimpleNamespace(uncertain_spans=(), transcription_uncertain=True)
    assert uncertain_fields(item) == frozenset({"*"})
