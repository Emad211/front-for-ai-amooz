"""Exercise Hub — grading: score a student's submission against the teacher's
reference answers. Design: docs/features/exercise-hub.md · ADR-0004.

Cost discipline: multiple_choice / fill_blank are graded DETERMINISTICALLY (no
LLM); only descriptive questions go to the LLM, batched by
``EXERCISE_GRADING_BATCH_SIZE``. Totals are summed in Python, never by the model.

Security (E5 gate carry-ins):
* Low-1 — the reference answer / grading notes are NEVER written into
  ``result['per_question']`` (that dict is echoed to the student). Only
  score/feedback/label live there.
* Low-2 — answer images are magic-byte sniffed (Pillow verify) before being sent
  to the vision model.
"""
from __future__ import annotations

import json
import logging
import os
import re
from decimal import Decimal
from typing import Any

from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from .schemas import ExerciseGradingOutput

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
_DETERMINISTIC_TYPES = {"multiple_choice", "fill_blank"}


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model(*names: str) -> str:
    for n in names:
        val = _get_env(n)
        if val:
            return val
    fallback = _get_env("MODEL_NAME")
    if fallback:
        return fallback
    raise RuntimeError(f"No LLM model defined in ENV. Checked: {names} and MODEL_NAME.")


def _batch_size() -> int:
    try:
        return max(1, int(os.getenv("EXERCISE_GRADING_BATCH_SIZE", "5")))
    except (TypeError, ValueError):
        return 5


def grading_enabled() -> bool:
    """The ``EXERCISE_LLM_GRADING`` kill-switch (default on). Off = leave the
    submission in SUBMITTED for manual grading."""
    return _get_env("EXERCISE_LLM_GRADING").lower() not in {"0", "false", "no", "off"}


def is_real_image(data: bytes) -> bool:
    """Low-2: verify the bytes are a real image before sending to the LLM."""
    if not data:
        return False
    try:
        from PIL import Image  # lazy — Pillow is a heavy import
        import io
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        return False


def _norm(text: str) -> str:
    """Normalize for deterministic comparison (whitespace + Persian/Arabic digits)."""
    s = str(text or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    trans = {ord(a): ord(b) for a, b in zip("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")}
    return s.translate(trans)


def _student_text(answers: dict, question_id) -> str:
    entry = answers.get(str(question_id)) if isinstance(answers, dict) else None
    if isinstance(entry, dict):
        return str(entry.get("text") or "").strip()
    if isinstance(entry, str):
        return entry.strip()
    return ""


def _grade_deterministic(question, student_answer: str) -> dict:
    """Exact/normalized match for MCQ + fill-blank. No LLM."""
    max_pts = float(question.max_points or 0)
    correct = _norm(student_answer) == _norm(question.reference_answer_markdown) \
        and bool(student_answer.strip())
    score = max_pts if correct else 0.0
    return {
        "question_id": str(question.id),
        "llm_score": None,
        "score_points": score,
        "max_points": max_pts,
        "label": "correct" if correct else "incorrect",
        "feedback": "" if correct else "پاسخ شما با کلید صحیح مطابقت ندارد.",
        "missing_points": [],
        "teacher_score": None,
        "teacher_feedback": None,
    }


def _grade_descriptive_batch(items: list[dict]) -> dict[str, dict]:
    """One structured LLM call for a batch of descriptive items -> {qid: entry}.

    NOTE: reference answers are sent to the model for judgment but are NEVER
    copied into the returned entries (Low-1)."""
    model = _select_model("EXERCISE_GRADING_MODEL")
    prompt = str(PROMPTS["exercise_grading"]["default"]).replace(
        "{grading_items_json}", json.dumps(items, ensure_ascii=False),
    )
    obj = generate_structured(
        schema=ExerciseGradingOutput, contents=prompt,
        feature=LLMUsageLog.Feature.EXERCISE_GRADING, model=model,
        timeout=_LLM_TIMEOUT_SECONDS,
    )
    out: dict[str, dict] = {}
    by_max = {it["question_id"]: it["max_points"] for it in items}
    for pq in obj.per_question:
        qid = str(pq.question_id or "")
        if not qid:
            continue
        max_pts = float(by_max.get(qid, pq.max_points or 0) or 0)
        raw = float(pq.score_points if pq.score_points is not None else 0)
        score = max(0.0, min(raw, max_pts))  # clamp to [0, max]
        out[qid] = {
            "question_id": qid,
            "llm_score": score,
            "score_points": score,
            "max_points": max_pts,
            "label": pq.label or "",
            "feedback": pq.feedback or "",
            "missing_points": list(pq.missing_points or []),
            "teacher_score": None,
            "teacher_feedback": None,
        }
    return out


def grade_submission(submission) -> dict:
    """Grade one submission. Returns ``{'per_question', 'score_points',
    'max_points'}`` — safe to store on the submission (no reference data)."""
    from ..models import ClassExerciseQuestion

    questions = list(
        ClassExerciseQuestion.objects
        .filter(section__exercise=submission.exercise)
        .order_by("section__order", "order")
    )
    answers = submission.answers if isinstance(submission.answers, dict) else {}

    per_question: list[dict] = []
    descriptive_items: list[dict] = []
    descriptive_qs: dict[str, Any] = {}

    for q in questions:
        stext = _student_text(answers, q.id)
        if q.question_type in _DETERMINISTIC_TYPES:
            per_question.append(_grade_deterministic(q, stext))
        else:
            qid = str(q.id)
            descriptive_qs[qid] = q
            descriptive_items.append({
                "question_id": qid,
                "question_text": q.question_markdown,
                "reference_answer": q.reference_answer_markdown,
                "max_points": float(q.max_points or 0),
                "student_answer": stext,
            })

    # Batch the descriptive items through the LLM.
    graded: dict[str, dict] = {}
    bs = _batch_size()
    for i in range(0, len(descriptive_items), bs):
        graded.update(_grade_descriptive_batch(descriptive_items[i:i + bs]))

    # Fill any descriptive question the model omitted with a zero (fail closed).
    for qid, q in descriptive_qs.items():
        entry = graded.get(qid) or {
            "question_id": qid, "llm_score": 0.0, "score_points": 0.0,
            "max_points": float(q.max_points or 0), "label": "incorrect",
            "feedback": "", "missing_points": [],
            "teacher_score": None, "teacher_feedback": None,
        }
        per_question.append(entry)

    total = sum(float(e["score_points"] or 0) for e in per_question)
    max_total = sum(float(e["max_points"] or 0) for e in per_question)
    return {
        "per_question": per_question,
        "score_points": round(total, 2),
        "max_points": round(max_total, 2),
    }


def apply_grading_result(submission, result: dict) -> None:
    """Persist a grading result onto the submission (status stays the caller's)."""
    from django.utils import timezone
    submission.result = {"per_question": result["per_question"]}
    submission.score_points = Decimal(str(result["score_points"]))
    submission.max_points = Decimal(str(result["max_points"]))
    submission.graded_at = timezone.now()
