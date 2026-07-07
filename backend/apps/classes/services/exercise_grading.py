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

Handwriting photos (E13): answers carrying ``images`` (storage paths uploaded via
``StudentExerciseImageView``) are vision-extracted to text BEFORE grading — one
standard-shape multimodal call per question (``exercise_handwriting_vision``
prompt, NEVER carrying the reference answer). A vision failure degrades that
question to text-only grading; it never fails the whole submission.
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
from decimal import Decimal
from typing import Any

from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from .file_validation import is_real_image
from .schemas import ExerciseGradingOutput, HandwritingTranscriptionOutput

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


# ---------------------------------------------------------------------------
# Handwriting photos -> text (vision extract, E13)
# ---------------------------------------------------------------------------


def _max_images_per_question() -> int:
    try:
        return max(1, int(os.getenv("EXERCISE_MAX_IMAGES_PER_QUESTION", "3")))
    except (TypeError, ValueError):
        return 3


def _student_images(answers: dict, question, student_id: int) -> list[str]:
    """Storage paths of the answer photos uploaded for one question."""
    entry = answers.get(str(question.id)) if isinstance(answers, dict) else None
    if not isinstance(entry, dict):
        return []
    images = entry.get("images")
    if not isinstance(images, list):
        return []
    prefix = f"exercises/answers/{question.section.exercise_id}/{student_id}/{question.id}_"
    return [
        p for p in images
        if isinstance(p, str) and p.startswith(prefix)
    ]


def _read_answer_image(path: str) -> bytes:
    """Read one stored answer image (kept tiny so tests can stub storage)."""
    from django.core.files.storage import default_storage
    with default_storage.open(path) as fh:
        return fh.read()


def _image_data_url(path: str, data: bytes) -> str:
    mime, _enc = mimetypes.guess_type(path)
    if not (mime or "").startswith("image/"):
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _transcribe_answer_images(question, image_paths: list[str]) -> str:
    """Vision-extract the student's handwritten answer photo(s) into text.

    ONE standard-shape OpenAI multimodal call per question (``image_url`` data
    URIs — the legacy ``attachments`` shape is silently ignored by the Avalai
    gateway). Every image passes the ``is_real_image`` sniff (Low-2), capped at
    ``EXERCISE_MAX_IMAGES_PER_QUESTION``. LEAK GUARD: the prompt carries ONLY
    the question text — never the reference answer or grading notes. Raises on
    LLM failure; the caller degrades that question to text-only grading.
    """
    cap = _max_images_per_question()
    parts: list[dict] = []
    for path in image_paths:
        if len(parts) >= cap:
            break
        try:
            data = _read_answer_image(path)
        except Exception:
            logger.warning("Answer image unreadable, skipping: %s", path)
            continue
        if not is_real_image(data):  # Low-2: sniff before any LLM call
            logger.warning("Answer image failed the image sniff, skipping: %s", path)
            continue
        parts.append({"type": "image_url", "image_url": {"url": _image_data_url(path, data)}})
    if not parts:
        return ""

    model = _select_model("EXERCISE_VISION_MODEL", "IMAGE_MODEL")
    prompt = str(PROMPTS["exercise_handwriting_vision"]["default"]).replace(
        "{question_text}", str(question.question_markdown or ""),
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}] + parts}]
    obj = generate_structured(
        schema=HandwritingTranscriptionOutput, messages=messages,
        feature=LLMUsageLog.Feature.EXERCISE_HANDWRITING_VISION, model=model,
        timeout=_LLM_TIMEOUT_SECONDS,
    )
    return (obj.text or "").strip()


def _effective_answer_text(question, answers: dict, *, student_id: int) -> str:
    """Typed text + vision-extracted photo text for one question.

    Rules:
    * Photo-only answer -> the extracted text IS the answer (verbatim, so the
      deterministic MCQ/fill-blank comparison still works).
    * Typed + photo on a DESCRIPTIVE question -> extracted text is appended
      under a clear Persian delimiter for the grader.
    * Typed + photo on a deterministic question -> the typed text is
      authoritative for exact-match grading; skip the vision call (cost).
    * Any vision failure -> grade whatever typed text exists (never fail the
      whole submission because of one bad image).
    """
    stext = _student_text(answers, question.id)
    image_paths = _student_images(answers, question, student_id)
    if not image_paths:
        return stext
    if stext and question.question_type in _DETERMINISTIC_TYPES:
        return stext
    try:
        extracted = _transcribe_answer_images(question, image_paths)
    except Exception as exc:
        if isinstance(exc, RuntimeError) and "No LLM model defined" in str(exc):
            raise
        logger.warning(
            "Handwriting vision failed for question %s; grading text only",
            question.id, exc_info=True,
        )
        return stext
    if not extracted:
        return stext
    if not stext:
        return extracted
    return f"{stext}\n\n[متن استخراج‌شده از تصویر پاسخ]\n{extracted}"


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
        .select_related("section")
        .filter(section__exercise=submission.exercise)
        .order_by("section__order", "order")
    )
    answers = submission.answers if isinstance(submission.answers, dict) else {}

    per_question: list[dict] = []
    descriptive_items: list[dict] = []
    descriptive_qs: dict[str, Any] = {}

    for q in questions:
        # Vision-extract any handwriting photos into the answer text first
        # (fail-open per question — see _effective_answer_text).
        stext = _effective_answer_text(q, answers, student_id=submission.student_id)
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
