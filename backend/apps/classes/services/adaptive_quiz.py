"""Adaptive-quiz support: turn a student's past attempts into a weak-point list.

The teaching loop is: a student fails a chapter quiz → they see the correct
answers to every question → a NEW quiz is generated that targets exactly the
concepts they got wrong (plus a little review) → they take it → repeat until
they pass. This module owns the FIRST, deterministic half of that loop:
reading the stored attempt history and producing the structured weak-point
list that the adaptive generator (and the UI) consume.

It is pure Python over already-stored data — zero LLM calls, zero tokens — so
it is cheap to call and trivial to unit-test.

Data sources (both already persisted by ``StudentChapterQuizView``):
* ``ClassSectionQuiz.questions`` → ``{"questions": [{id, type, question,
  options, correct_answer, difficulty}, ...]}`` — carries the correct answer.
* ``ClassSectionQuizAttempt.result`` → ``{"per_question": [{id, type, question,
  student_answer, score_0_100, label, feedback}, ...], "passing_score": int}``
  — carries which question ids the student missed.
"""

from __future__ import annotations

from typing import Any

# A per-question score at or above this is "not a weak point" for objective
# items; open-ended items are graded 0-100 by the LLM, so the same threshold
# applies uniformly. Mirrors the quiz passing band used elsewhere.
WEAK_POINT_SCORE_THRESHOLD = 70


def _questions_by_id(quiz_questions: Any) -> dict[str, dict]:
    """Index the quiz's stored questions (incl. correct_answer) by id."""
    out: dict[str, dict] = {}
    items = (quiz_questions or {}).get("questions") if isinstance(quiz_questions, dict) else None
    if isinstance(items, list):
        for q in items:
            if isinstance(q, dict):
                qid = str(q.get("id") or "").strip()
                if qid:
                    out[qid] = q
    return out


def _is_wrong(pq: dict) -> bool:
    """Was this graded per-question result a miss?"""
    label = str(pq.get("label") or "").strip().lower()
    if label == "correct":
        return False
    if label == "incorrect":
        return True
    score = pq.get("score_0_100")
    if isinstance(score, (int, float)):
        return score < WEAK_POINT_SCORE_THRESHOLD
    # No label and no score → can't tell; treat as not-wrong to avoid noise.
    return False


def compute_weak_points(quiz, *, max_attempts: int = 3) -> list[dict]:
    """Aggregate the student's recent wrong answers on ``quiz`` into weak points.

    Looks at the most recent ``max_attempts`` attempts, finds every question the
    student missed, and joins it back to the stored question (for the correct
    answer + difficulty). Returns one entry per distinct missed question,
    sorted by how often it was missed (most-missed first):

        [{id, question, correct_answer, difficulty, student_answer, times_wrong}]

    Empty list if there are no attempts or nothing was missed. ``student_answer``
    is the most recent wrong answer (attempts are scanned newest-first).
    """
    q_by_id = _questions_by_id(getattr(quiz, "questions", None))

    try:
        attempts = list(quiz.attempts.order_by("-created_at")[:max_attempts])
    except Exception:
        attempts = []

    agg: dict[str, dict] = {}
    for att in attempts:
        result = getattr(att, "result", None)
        per_q = result.get("per_question") if isinstance(result, dict) else None
        if not isinstance(per_q, list):
            continue
        for pq in per_q:
            if not isinstance(pq, dict) or not _is_wrong(pq):
                continue
            qid = str(pq.get("id") or "").strip()
            if not qid:
                continue
            src = q_by_id.get(qid, {})
            if qid not in agg:
                agg[qid] = {
                    "id": qid,
                    "question": (src.get("question") or pq.get("question") or "").strip(),
                    "correct_answer": src.get("correct_answer"),
                    "difficulty": str(src.get("difficulty") or "").strip(),
                    # Newest-first scan → first sighting is the latest attempt.
                    "student_answer": str(pq.get("student_answer") or "").strip(),
                    "times_wrong": 0,
                }
            agg[qid]["times_wrong"] += 1

    return sorted(agg.values(), key=lambda e: e["times_wrong"], reverse=True)
