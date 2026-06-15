from __future__ import annotations

import logging
import os
from typing import Any

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.chatbot.services.llm_client import generate_text

from .json_utils import extract_json_object

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model(*names: str) -> str:
    """
    Correct, architecture‑aligned model resolver:
    1) first available specific model
    2) fallback → MODEL_NAME
    3) else → error (mandatory: no hard‑coded defaults)
    """
    for n in names:
        val = _get_env(n)
        if val:
            return val

    fallback = _get_env("MODEL_NAME")
    if fallback:
        return fallback

    raise RuntimeError(
        f"No LLM model found in ENV. Checked: {names} and fallback MODEL_NAME"
    )


def _render_prompt(template: str, **values: Any) -> str:
    """
    Render prompt safely without using str.format().

    Many prompt templates contain JSON braces { } which would break
    format() so we do a safe key replacement instead.
    """

    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def _call_llm(
    *,
    model: str,
    prompt: str,
    feature: LLMUsageLog.Feature,
) -> str:
    provider = preferred_provider()

    messages = [
        {"role": "user", "content": prompt},
    ]

    resp = generate_text(
        model=model,
        messages=messages,
        timeout=_LLM_TIMEOUT_SECONDS,
        feature=feature,
    )

    text = resp.text if hasattr(resp, "text") else str(resp)

    return text.strip()


def _parse_json_result(text: str, *, root_key: str | None = None) -> dict[str, Any]:
    obj = extract_json_object(text)

    if isinstance(obj, dict):
        return obj

    if root_key:
        return {root_key: obj}

    return {"result": obj}


# ---------------------------------------------------------------------
# Quiz Generation
# ---------------------------------------------------------------------

def generate_section_quiz_questions(
    *, section_content: str, count: int = 5
) -> tuple[dict[str, Any], str, str]:

    model = _select_model("QUIZ_MODEL")

    provider = preferred_provider()

    prompt = _render_prompt(
        PROMPTS["section_quiz"]["default"],
        count=count,
        section_content=section_content,
    )

    try:
        text = _call_llm(
            model=model,
            prompt=prompt,
            feature=LLMUsageLog.Feature.QUIZ_GENERATION,
        )

        obj = _parse_json_result(text, root_key="questions")

        return obj, provider, model

    except Exception as exc:
        logger.exception("Quiz generation failed")
        raise RuntimeError(f"Quiz generation failed: {exc}") from exc


def generate_adaptive_section_quiz(
    *,
    section_content: str,
    weak_points: list[dict[str, Any]],
    count: int = 5,
    review_count: int = 1,
) -> tuple[dict[str, Any], str, str]:
    """Generate a NEW section quiz that targets the student's weak points.

    ``weak_points`` is the output of
    :func:`apps.classes.services.adaptive_quiz.compute_weak_points`. The return
    value and JSON shape are IDENTICAL to
    :func:`generate_section_quiz_questions` (``{"questions": [...]}``), so the
    view/storage that consume it need no special handling.
    """
    import json as _json

    model = _select_model("QUIZ_MODEL")
    provider = preferred_provider()

    # Compact each weak point to what the model needs (bound token usage).
    compact = [
        {
            "question": str(w.get("question") or "")[:400],
            "correct_answer": str(w.get("correct_answer") or "")[:200],
            "difficulty": w.get("difficulty") or "",
        }
        for w in (weak_points or [])
    ][:8]
    # Keep at least one targeted question; review never exceeds count-1.
    review_count = max(0, min(int(review_count), max(0, int(count) - 1)))

    prompt = _render_prompt(
        PROMPTS["section_quiz"]["adaptive"],
        count=count,
        review_count=review_count,
        weak_points_json=_json.dumps(compact, ensure_ascii=False),
        section_content=section_content,
    )

    try:
        text = _call_llm(
            model=model,
            prompt=prompt,
            feature=LLMUsageLog.Feature.QUIZ_GENERATION,
        )
        obj = _parse_json_result(text, root_key="questions")
        return obj, provider, model
    except Exception as exc:
        logger.exception("Adaptive quiz generation failed")
        raise RuntimeError(f"Adaptive quiz generation failed: {exc}") from exc


# ---------------------------------------------------------------------
# Open Text Grading
# ---------------------------------------------------------------------

def grade_open_text_answer(
    *, question: str, reference_answer: str, student_answer: str
) -> tuple[dict[str, Any], str, str]:

    model = _select_model("GRADING_MODEL", "QUIZ_MODEL")

    provider = preferred_provider()

    prompt = _render_prompt(
        PROMPTS["text_grading"]["default"],
        question=question,
        reference_answer=reference_answer,
        student_answer=student_answer,
    )

    try:
        text = _call_llm(
            model=model,
            prompt=prompt,
            feature=LLMUsageLog.Feature.QUIZ_GRADING,
        )

        obj = _parse_json_result(text, root_key="result")

        return obj, provider, model

    except Exception as exc:
        logger.exception("Quiz grading failed")
        raise RuntimeError(f"Quiz grading failed: {exc}") from exc


# ---------------------------------------------------------------------
# Final Exam Pool
# ---------------------------------------------------------------------

def generate_final_exam_pool(
    *, combined_content: str, pool_size: int = 12
) -> tuple[dict[str, Any], str, str]:

    model = _select_model("FINAL_EXAM_MODEL", "QUIZ_MODEL")

    provider = preferred_provider()

    prompt = _render_prompt(
        PROMPTS["final_exam_pool"]["default"],
        pool_size=pool_size,
        combined_content=combined_content,
    )

    try:
        text = _call_llm(
            model=model,
            prompt=prompt,
            feature=LLMUsageLog.Feature.FINAL_EXAM_GENERATION,
        )

        obj = _parse_json_result(text, root_key="questions")

        return obj, provider, model

    except Exception as exc:
        logger.exception("Final exam pool generation failed")
        raise RuntimeError(f"Final exam pool generation failed: {exc}") from exc


def generate_adaptive_final_exam(
    *,
    combined_content: str,
    weak_points: list[dict[str, Any]],
    pool_size: int = 12,
    review_count: int = 2,
) -> tuple[dict[str, Any], str, str]:
    """Generate a NEW final exam pool targeting the student's weak points.

    Same return + JSON shape as :func:`generate_final_exam_pool`.
    """
    import json as _json

    model = _select_model("FINAL_EXAM_MODEL", "QUIZ_MODEL")
    provider = preferred_provider()

    compact = [
        {
            "question": str(w.get("question") or "")[:400],
            "correct_answer": str(w.get("correct_answer") or "")[:200],
        }
        for w in (weak_points or [])
    ][:12]
    review_count = max(0, min(int(review_count), max(0, int(pool_size) - 1)))

    prompt = _render_prompt(
        PROMPTS["final_exam_pool"]["adaptive"],
        pool_size=pool_size,
        review_count=review_count,
        weak_points_json=_json.dumps(compact, ensure_ascii=False),
        combined_content=combined_content,
    )

    try:
        text = _call_llm(
            model=model,
            prompt=prompt,
            feature=LLMUsageLog.Feature.FINAL_EXAM_GENERATION,
        )
        obj = _parse_json_result(text, root_key="questions")
        return obj, provider, model
    except Exception as exc:
        logger.exception("Adaptive final exam generation failed")
        raise RuntimeError(f"Adaptive final exam generation failed: {exc}") from exc


# ---------------------------------------------------------------------
# Hint Generation
# ---------------------------------------------------------------------

def generate_answer_hint(
    *,
    question: str,
    reference_answer: str,
    student_answer: str,
    attempt_number: int = 1,
) -> tuple[dict[str, Any], str, str]:

    model = _select_model("HINT_MODEL")

    provider = preferred_provider()

    prompt = _render_prompt(
        PROMPTS["exam_prep_hint"]["default"],
        question=question,
        reference_answer=reference_answer,
        student_answer=student_answer,
        attempt_number=attempt_number,
    )

    try:
        text = _call_llm(
            model=model,
            prompt=prompt,
            feature=LLMUsageLog.Feature.HINT_GENERATION,
        )

        obj = extract_json_object(text)

        if not isinstance(obj, dict):
            obj = {"hint": str(obj), "encouragement": ""}

        return obj, provider, model

    except Exception as exc:
        logger.exception("Hint generation failed")
        raise RuntimeError(f"Hint generation failed: {exc}") from exc
