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
import hashlib
import json
import logging
import mimetypes
import os
import re
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from apps.chatbot.services.llm_client import ProviderTransientError, is_transient_llm_error
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from .file_validation import is_real_image
from .schemas import ExerciseGradingOutput, HandwritingTranscriptionOutput

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
_DETERMINISTIC_TYPES = {"multiple_choice", "fill_blank"}
_GRADING_ALGORITHM_VERSION = "exercise-grading-v2"
_OCR_ALGORITHM_VERSION = "exercise-ocr-v1"


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


def _load_image_contents(
    image_paths: list[str],
) -> tuple[list[dict[str, str | bool]], dict[str, bytes]]:
    """Read each influential image once for both cache identity and OCR."""
    identities: list[dict[str, str | bool]] = []
    blobs: dict[str, bytes] = {}
    for path in image_paths:
        try:
            data = _read_answer_image(path)
        except FileNotFoundError:
            logger.warning("Answer image unreadable, skipping: %s", path)
            identities.append({"path": path, "unreadable": True})
            continue
        except Exception as exc:
            # Do not turn a temporary S3/MinIO outage into a reusable empty
            # answer and a false zero. The task-level retry owns recovery.
            raise ProviderTransientError("Answer image storage read failed.") from exc
        blobs[path] = data
        identities.append({
            "path": path,
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return identities, blobs


def _image_data_url(path: str, data: bytes) -> str:
    mime, _enc = mimetypes.guess_type(path)
    if not (mime or "").startswith("image/"):
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _transcribe_answer_images(
    question,
    image_paths: list[str],
    image_blobs: dict[str, bytes] | None = None,
) -> str:
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
        if image_blobs is None:
            try:
                data = _read_answer_image(path)
            except Exception:
                logger.warning("Answer image unreadable, skipping: %s", path)
                continue
        else:
            data = image_blobs.get(path)
            if data is None:
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
        timeout=_LLM_TIMEOUT_SECONDS, temperature=0,
    )
    return (obj.text or "").strip()


def _grade_deterministic(question, student_answer: str) -> dict:
    """Exact/normalized match for MCQ + fill-blank. No LLM."""
    max_pts = float(question.max_points or 0)
    correct = _norm(student_answer) == _norm(question.reference_answer_markdown) \
        and bool(student_answer.strip())
    score = max_pts if correct else 0.0
    return {
        "question_id": str(question.id),
        # Keep the immutable automatic baseline for override reset/reuse. The
        # field name is legacy; deterministic question types do not call an LLM.
        "llm_score": score,
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
        timeout=_LLM_TIMEOUT_SECONDS, temperature=0,
    )
    out: dict[str, dict] = {}
    by_max = {it["question_id"]: it["max_points"] for it in items}
    for pq in obj.per_question:
        qid = str(pq.question_id or "")
        if not qid or qid not in by_max or qid in out:
            raise RuntimeError("Grading output contained an unknown or duplicate question_id.")
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
    if set(out) != set(by_max):
        raise RuntimeError("Grading output omitted one or more questions.")
    return out


def _sha256_json(value: Any) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _prompt_version(key: str) -> str:
    return _sha256_json(str(PROMPTS[key]["default"]))


def _configured_model(*names: str) -> str:
    for name in (*names, "MODEL_NAME"):
        value = _get_env(name)
        if value:
            return value
    return ""


def _question_fingerprint(question, answers: dict, *, student_id: int,
                          image_identities: list[dict[str, str | bool]] | None = None) -> str:
    """Hash all inputs that can legitimately change a question's AI grade."""
    images = (
        image_identities
        if image_identities is not None
        else _load_image_contents(_student_images(answers, question, student_id))[0]
    )
    uses_grading_llm = question.question_type not in _DETERMINISTIC_TYPES
    uses_vision = bool(images)
    return _sha256_json({
        "algorithm": _GRADING_ALGORITHM_VERSION,
        "grading_prompt": (
            _prompt_version("exercise_grading") if uses_grading_llm else None
        ),
        "grading_model": (
            _configured_model("EXERCISE_GRADING_MODEL") if uses_grading_llm else None
        ),
        "vision_algorithm": _OCR_ALGORITHM_VERSION if uses_vision else None,
        "vision_prompt": (
            _prompt_version("exercise_handwriting_vision") if uses_vision else None
        ),
        "vision_model": (
            _configured_model("EXERCISE_VISION_MODEL", "IMAGE_MODEL")
            if uses_vision else None
        ),
        "question": {
            "id": str(question.id),
            "type": question.question_type,
            "text": question.question_markdown or "",
            "options": question.options if isinstance(question.options, list) else [],
            "reference_answer": question.reference_answer_markdown or "",
            "grading_notes": question.grading_notes or "",
            "max_points": str(question.max_points or 0),
        },
        "answer": {
            "text": _student_text(answers, question.id),
            "images": images,
        },
    })


def _ocr_fingerprint(question, image_identities: list[dict[str, str | bool]]) -> str:
    return _sha256_json({
        "algorithm": _OCR_ALGORITHM_VERSION,
        "prompt": _prompt_version("exercise_handwriting_vision"),
        "model": _configured_model("EXERCISE_VISION_MODEL", "IMAGE_MODEL"),
        "question_text": question.question_markdown or "",
        "images": image_identities,
    })


def _result_map(result: dict) -> dict[str, dict]:
    rows = result.get("per_question") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("question_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("question_id") is not None
    }


def build_question_snapshot(exercise) -> list[dict]:
    """Capture the exact question/rubric contract used by one attempt."""
    from ..models import ClassExerciseQuestion

    questions = (
        ClassExerciseQuestion.objects.select_related("section")
        .filter(section__exercise=exercise)
        .order_by("section__order", "order", "id")
    )
    return [
        {
            "id": question.id,
            "section_order": question.section.order,
            "order": question.order,
            "question_type": question.question_type,
            "question_markdown": question.question_markdown or "",
            "options": question.options if isinstance(question.options, list) else [],
            "reference_answer_markdown": question.reference_answer_markdown or "",
            "grading_notes": question.grading_notes or "",
            "max_points": str(question.max_points or 0),
        }
        for question in questions
    ]


def questions_from_snapshot(snapshot: list, *, exercise_id: int) -> list:
    """Rehydrate immutable JSON into the narrow question interface grading uses."""
    questions = []
    for row in snapshot if isinstance(snapshot, list) else []:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        try:
            max_points = Decimal(str(row.get("max_points") or 0))
        except (InvalidOperation, TypeError, ValueError):
            max_points = Decimal("0")
        questions.append(SimpleNamespace(
            id=row["id"],
            order=int(row.get("order") or 0),
            question_type=str(row.get("question_type") or "descriptive"),
            question_markdown=str(row.get("question_markdown") or ""),
            options=row.get("options") if isinstance(row.get("options"), list) else [],
            reference_answer_markdown=str(row.get("reference_answer_markdown") or ""),
            grading_notes=str(row.get("grading_notes") or ""),
            max_points=max_points,
            section=SimpleNamespace(exercise_id=exercise_id),
        ))
    return questions


def _without_teacher_override(entry: dict) -> dict:
    copied = dict(entry)
    copied["teacher_score"] = None
    copied["teacher_feedback"] = None
    llm_score = copied.get("llm_score")
    if llm_score is not None:
        copied["score_points"] = llm_score
    return copied


def _combine_answer_text(question, typed_text: str, extracted_text: str) -> str:
    if not extracted_text or (typed_text and question.question_type in _DETERMINISTIC_TYPES):
        return typed_text
    if not typed_text:
        return extracted_text
    return f"{typed_text}\n\n[متن استخراج‌شده از تصویر پاسخ]\n{extracted_text}"


def _save_attempt_progress(attempt, per_question: dict[str, dict], fingerprints: dict,
                           ocr_text: dict, metadata: dict) -> None:
    attempt.result = {"per_question": list(per_question.values())}
    attempt.question_fingerprints = fingerprints
    attempt.ocr_text = ocr_text
    attempt.grader_metadata = metadata
    attempt.save(update_fields=[
        "result", "question_fingerprints", "ocr_text", "grader_metadata", "updated_at",
    ])


def grade_attempt(attempt) -> dict:
    """Grade only changed questions and persist reusable progress per batch."""
    from ..models import StudentExerciseAttempt

    submission = attempt.submission
    questions = questions_from_snapshot(
        attempt.question_snapshot,
        exercise_id=submission.exercise_id,
    )
    if not questions:
        # Compatibility for a task queued before the coordinated migration.
        attempt.question_snapshot = build_question_snapshot(submission.exercise)
        attempt.save(update_fields=["question_snapshot", "updated_at"])
        questions = questions_from_snapshot(
            attempt.question_snapshot,
            exercise_id=submission.exercise_id,
        )
    answers = attempt.answers if isinstance(attempt.answers, dict) else {}
    previous = (
        StudentExerciseAttempt.objects.filter(
            submission=submission,
            attempt_number__lt=attempt.attempt_number,
            status=StudentExerciseAttempt.Status.GRADED,
        ).order_by("-attempt_number").first()
    )
    previous_result = _result_map(previous.result) if previous else {}
    previous_fingerprints = dict(previous.question_fingerprints or {}) if previous else {}
    previous_metadata = dict(previous.grader_metadata or {}) if previous else {}
    previous_ocr = dict(previous.ocr_text or {}) if previous else {}

    current_result = _result_map(attempt.result)
    fingerprints = dict(attempt.question_fingerprints or {})
    ocr_text = dict(attempt.ocr_text or {})
    metadata = dict(attempt.grader_metadata or {})
    question_meta = dict(metadata.get("questions") or {})
    per_question: dict[str, dict] = {}
    descriptive_items: list[dict] = []
    descriptive_qs: dict[str, Any] = {}
    for question in questions:
        qid = str(question.id)
        typed_text = _student_text(answers, question.id)
        image_paths = _student_images(answers, question, submission.student_id)
        if typed_text and question.question_type in _DETERMINISTIC_TYPES:
            # Attached images do not affect an authoritative typed MCQ/fill answer.
            image_paths = []
        image_identities, image_blobs = _load_image_contents(image_paths)
        fingerprint = _question_fingerprint(
            question,
            answers,
            student_id=submission.student_id,
            image_identities=image_identities,
        )
        fingerprints[qid] = fingerprint

        cached_current = current_result.get(qid)
        if cached_current and attempt.question_fingerprints.get(qid) == fingerprint:
            per_question[qid] = cached_current
            question_meta[qid] = {**dict(question_meta.get(qid) or {}), "resumed": True}
            continue

        previous_fingerprint = previous_fingerprints.get(qid)
        if previous_fingerprint == fingerprint and qid in previous_result:
            per_question[qid] = _without_teacher_override(previous_result[qid])
            if qid in previous_ocr:
                ocr_text[qid] = previous_ocr[qid]
            question_meta[qid] = {
                "reusedFromAttemptId": previous.id,
                "reused": True,
                "ocrReused": qid in previous_ocr,
            }
            continue

        extracted_text = ""
        ocr_was_reused = False
        ocr_fp = _ocr_fingerprint(question, image_identities) if image_paths else ""
        current_q_meta = dict(question_meta.get(qid) or {})
        previous_q_meta = dict((previous_metadata.get("questions") or {}).get(qid) or {})
        if image_paths and not (typed_text and question.question_type in _DETERMINISTIC_TYPES):
            if current_q_meta.get("ocrFingerprint") == ocr_fp and qid in ocr_text:
                extracted_text = str(ocr_text[qid] or "")
                ocr_was_reused = True
            elif previous_q_meta.get("ocrFingerprint") == ocr_fp and qid in previous_ocr:
                extracted_text = str(previous_ocr[qid] or "")
                ocr_text[qid] = extracted_text
                ocr_was_reused = True
            else:
                try:
                    extracted_text = _transcribe_answer_images(
                        question,
                        image_paths,
                        image_blobs=image_blobs,
                    )
                except Exception as exc:
                    if is_transient_llm_error(exc):
                        raise
                    if isinstance(exc, RuntimeError) and "No LLM model defined" in str(exc):
                        raise
                    logger.warning(
                        "Handwriting vision failed for question %s; grading text only",
                        question.id, exc_info=True,
                    )
                    extracted_text = ""
                ocr_text[qid] = extracted_text

        student_answer = _combine_answer_text(question, typed_text, extracted_text)
        question_meta[qid] = {
            "reused": False,
            "ocrReused": ocr_was_reused,
            "ocrFingerprint": ocr_fp or None,
        }
        if question.question_type in _DETERMINISTIC_TYPES:
            per_question[qid] = _grade_deterministic(question, student_answer)
        else:
            descriptive_qs[qid] = question
            descriptive_items.append({
                "question_id": qid,
                "question_text": question.question_markdown,
                "reference_answer": question.reference_answer_markdown,
                "grading_notes": question.grading_notes,
                "max_points": float(question.max_points or 0),
                "student_answer": student_answer,
            })

    reused_questions = sum(
        1 for value in question_meta.values()
        if isinstance(value, dict) and value.get("reused") is True
    )
    regraded_questions = len(questions) - reused_questions
    ocr_reuse = sum(
        1 for value in question_meta.values()
        if isinstance(value, dict) and value.get("ocrReused") is True
    )
    metadata.update({
        "algorithmVersion": _GRADING_ALGORITHM_VERSION,
        "ocrAlgorithmVersion": _OCR_ALGORITHM_VERSION,
        "gradingPromptVersion": _prompt_version("exercise_grading"),
        "visionPromptVersion": _prompt_version("exercise_handwriting_vision"),
        "gradingModel": _configured_model("EXERCISE_GRADING_MODEL"),
        "visionModel": _configured_model("EXERCISE_VISION_MODEL", "IMAGE_MODEL"),
        "temperature": 0,
        "questions": question_meta,
        "reusedQuestions": reused_questions,
        "regradedQuestions": regraded_questions,
        "ocrReuse": ocr_reuse,
    })
    _save_attempt_progress(attempt, per_question, fingerprints, ocr_text, metadata)

    batch_size = _batch_size()
    for index in range(0, len(descriptive_items), batch_size):
        graded = _grade_descriptive_batch(descriptive_items[index:index + batch_size])
        per_question.update(graded)
        _save_attempt_progress(attempt, per_question, fingerprints, ocr_text, metadata)

    for qid, question in descriptive_qs.items():
        if qid not in per_question:
            per_question[qid] = {
                "question_id": qid, "llm_score": 0.0, "score_points": 0.0,
                "max_points": float(question.max_points or 0), "label": "incorrect",
                "feedback": "", "missing_points": [],
                "teacher_score": None, "teacher_feedback": None,
            }

    ordered = [per_question[str(question.id)] for question in questions]
    total = sum(float(entry.get("score_points") or 0) for entry in ordered)
    max_total = sum(float(entry.get("max_points") or 0) for entry in ordered)
    score_delta = (
        round(total - float(previous.score_points), 2)
        if previous and previous.score_points is not None else None
    )
    metadata['scoreDelta'] = score_delta
    attempt.grader_metadata = metadata
    attempt.save(update_fields=['grader_metadata', 'updated_at'])
    logger.info(
        "Exercise attempt grading metrics attempt_id=%s reused_questions=%s "
        "regraded_questions=%s ocr_reuse=%s score_delta=%s",
        attempt.id, reused_questions, regraded_questions, ocr_reuse, score_delta,
    )
    return {
        "per_question": ordered,
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
