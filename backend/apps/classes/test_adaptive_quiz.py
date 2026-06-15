"""Tests for adaptive-quiz support (weak-point extraction).

Pure unit tests over stub objects — no DB, no LLM, no tokens. They lock the
join between a quiz's stored questions (correct_answer) and the student's
attempt history (which ids were missed).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.classes.services.adaptive_quiz import compute_weak_points, _is_wrong

pytestmark = pytest.mark.unit


class _Attempts:
    """Minimal stand-in for the related manager: order_by(...) then slice."""

    def __init__(self, items):
        self._items = items

    def order_by(self, *_args):
        # Tests pass attempts already newest-first.
        return self

    def __getitem__(self, key):
        return self._items[key]


def _quiz(questions, attempts):
    return SimpleNamespace(questions={"questions": questions}, attempts=_Attempts(attempts))


def _attempt(per_question):
    return SimpleNamespace(result={"per_question": per_question})


def test_is_wrong_label_and_score():
    assert _is_wrong({"label": "incorrect"}) is True
    assert _is_wrong({"label": "correct"}) is False
    assert _is_wrong({"score_0_100": 40}) is True
    assert _is_wrong({"score_0_100": 70}) is False
    assert _is_wrong({"score_0_100": 95}) is False
    # label wins over score, and unknown → not wrong (avoid noise)
    assert _is_wrong({"label": "correct", "score_0_100": 0}) is False
    assert _is_wrong({}) is False


def test_no_attempts_returns_empty():
    quiz = _quiz([{"id": "q-1", "question": "x", "correct_answer": "a"}], [])
    assert compute_weak_points(quiz) == []


def test_all_correct_returns_empty():
    quiz = _quiz(
        [{"id": "q-1", "question": "x", "correct_answer": "a"}],
        [_attempt([{"id": "q-1", "label": "correct", "score_0_100": 100}])],
    )
    assert compute_weak_points(quiz) == []


def test_weak_points_joined_with_correct_answer_and_sorted():
    questions = [
        {"id": "q-1", "question": "ریشه‌های معادله؟", "correct_answer": "x=۵", "difficulty": "medium"},
        {"id": "q-2", "question": "مشتق؟", "correct_answer": "۲x", "difficulty": "hard"},
        {"id": "q-3", "question": "حد؟", "correct_answer": "۰", "difficulty": "easy"},
    ]
    attempts = [
        # newest: missed q-1 and q-2
        _attempt([
            {"id": "q-1", "label": "incorrect", "student_answer": "x=۳"},
            {"id": "q-2", "score_0_100": 20, "student_answer": "x"},
            {"id": "q-3", "label": "correct"},
        ]),
        # older: missed q-1 again
        _attempt([
            {"id": "q-1", "label": "incorrect", "student_answer": "x=۲"},
            {"id": "q-2", "label": "correct"},
        ]),
    ]
    wp = compute_weak_points(_quiz(questions, attempts))

    # q-1 missed twice, q-2 once → q-1 first; q-3 never missed → absent.
    assert [w["id"] for w in wp] == ["q-1", "q-2"]
    assert wp[0]["times_wrong"] == 2
    assert wp[0]["correct_answer"] == "x=۵"
    assert wp[0]["difficulty"] == "medium"
    # student_answer is the most recent wrong answer (newest-first scan)
    assert wp[0]["student_answer"] == "x=۳"
    assert wp[1]["id"] == "q-2"
    assert wp[1]["correct_answer"] == "۲x"


def test_max_attempts_window_is_respected():
    questions = [{"id": "q-1", "question": "x", "correct_answer": "a"}]
    # 5 attempts each missing q-1, but window=2 → times_wrong capped at 2.
    attempts = [_attempt([{"id": "q-1", "label": "incorrect"}]) for _ in range(5)]
    wp = compute_weak_points(_quiz(questions, attempts), max_attempts=2)
    assert wp[0]["times_wrong"] == 2


def test_missing_source_question_still_reported():
    # Attempt references a qid not in the stored questions (edge case) — still
    # reported, falling back to the per-question text, correct_answer None.
    quiz = _quiz([], [_attempt([{"id": "q-9", "label": "incorrect", "question": "?"}])])
    wp = compute_weak_points(quiz)
    assert len(wp) == 1
    assert wp[0]["id"] == "q-9"
    assert wp[0]["correct_answer"] is None
