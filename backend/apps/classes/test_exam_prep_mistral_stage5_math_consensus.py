from __future__ import annotations

from apps.classes.services import exam_prep_mistral_stage5 as stage5


def test_stage5_accepts_equivalent_latex_fraction_signs_and_reordered_bindings():
    left = r"""
    با توجه به شکل، معادله خط y = \frac{-3}{4}x است.
    x = \frac{-8}{5} و y = \frac{6}{5}.
    بنابراین \alpha = \frac{-8}{5} و \beta = \frac{6}{5}
    و \alpha + \beta = \frac{-2}{5}.
    """
    right = r"""
    با توجه به شکل، معادله خط y=-\frac{3}{4}x است.
    x=-\frac{8}{5} و y=\frac{6}{5}.
    بنابراین \alpha+\beta=-\frac{2}{5} و \beta=\frac{6}{5}
    و \alpha=-\frac{8}{5}.
    """

    assert stage5._field_agrees("teacher_solution_markdown", left, right) is True


def test_stage5_rejects_same_numbers_with_swapped_variable_bindings():
    left = r"x=-\frac{8}{5}, y=\frac{6}{5}, \alpha+\beta=-\frac{2}{5}"
    right = r"x=\frac{6}{5}, y=-\frac{8}{5}, \alpha+\beta=-\frac{2}{5}"

    assert stage5._field_agrees("teacher_solution_markdown", left, right) is False


def test_stage5_rejects_real_sign_change_even_when_wording_matches():
    left = r"x=-\frac{8}{5}, y=\frac{6}{5}, \alpha+\beta=-\frac{2}{5}"
    right = r"x=\frac{8}{5}, y=\frac{6}{5}, \alpha+\beta=-\frac{2}{5}"

    assert stage5._field_agrees("teacher_solution_markdown", left, right) is False
