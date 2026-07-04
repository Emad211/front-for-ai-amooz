"""Adaptive weak-point extraction for the FINAL-EXAM grading shape.

`test_adaptive_quiz.py` covers the section-quiz path (`score_0_100`, threshold 70)
via the `compute_weak_points` wrapper. The final exam grades differently —
`score_points` out of `max_points` — and drives `compute_weak_points_from`
directly off `ClassFinalExam.exam`. That shape had no test. Pure unit, 0-token.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.classes.services.adaptive_quiz import _is_wrong, compute_weak_points_from

pytestmark = pytest.mark.unit


def _attempt(per_question):
    return SimpleNamespace(result={"per_question": per_question})


class TestIsWrongPointsShape:
    def test_partial_points_is_wrong(self):
        assert _is_wrong({"score_points": 3, "max_points": 5}) is True

    def test_full_points_is_not_wrong(self):
        assert _is_wrong({"score_points": 5, "max_points": 5}) is False

    def test_zero_points_is_wrong(self):
        assert _is_wrong({"score_points": 0, "max_points": 4}) is True

    def test_zero_max_points_cannot_tell_treated_not_wrong(self):
        # mx must be > 0; otherwise it's un-scoreable → not-wrong (avoid noise).
        assert _is_wrong({"score_points": 2, "max_points": 0}) is False

    def test_label_wins_over_points(self):
        # An explicit label overrides the points math either way.
        assert _is_wrong({"label": "correct", "score_points": 0, "max_points": 5}) is False
        assert _is_wrong({"label": "incorrect", "score_points": 5, "max_points": 5}) is True


class TestComputeWeakPointsFromFinalExamShape:
    def test_points_shape_joins_correct_answer_and_orders(self):
        exam = {"questions": [
            {"id": "e-1", "question": "انتگرال؟", "correct_answer": "F(x)+c", "difficulty": "hard"},
            {"id": "e-2", "question": "مشتق؟", "correct_answer": "2x", "difficulty": "medium"},
            {"id": "e-3", "question": "حد؟", "correct_answer": "0", "difficulty": "easy"},
        ]}
        attempts = [
            # newest: missed e-1 (partial) and e-2 (zero); e-3 full marks
            _attempt([
                {"id": "e-1", "score_points": 2, "max_points": 5, "student_answer": "F(x)"},
                {"id": "e-2", "score_points": 0, "max_points": 4},
                {"id": "e-3", "score_points": 3, "max_points": 3},
            ]),
            # older: missed e-1 again
            _attempt([
                {"id": "e-1", "score_points": 1, "max_points": 5},
                {"id": "e-2", "score_points": 4, "max_points": 4},
            ]),
        ]
        wp = compute_weak_points_from(exam, attempts)

        # e-1 missed twice → first; e-2 once; e-3 full marks → absent.
        assert [w["id"] for w in wp] == ["e-1", "e-2"]
        assert wp[0]["times_wrong"] == 2
        assert wp[0]["correct_answer"] == "F(x)+c"
        assert wp[0]["difficulty"] == "hard"
        assert wp[0]["student_answer"] == "F(x)"  # most-recent wrong answer
        assert wp[1]["id"] == "e-2"
        assert wp[1]["correct_answer"] == "2x"

    def test_all_full_marks_returns_empty(self):
        exam = {"questions": [{"id": "e-1", "correct_answer": "a"}]}
        attempts = [_attempt([{"id": "e-1", "score_points": 5, "max_points": 5}])]
        assert compute_weak_points_from(exam, attempts) == []

    def test_empty_attempts_returns_empty(self):
        exam = {"questions": [{"id": "e-1", "correct_answer": "a"}]}
        assert compute_weak_points_from(exam, []) == []
