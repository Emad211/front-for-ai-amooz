"""Exercise Hub — the in-exercise assistant chat.

Security (E5/E8): the reference answer is a STRUCTURAL guard, not a prompt
promise. ``build_question_context`` injects ``reference_answer_markdown`` ONLY
when ``reveal`` is True (deadline passed / graded). Before that a model that
never saw the answer cannot leak it under injection. The section/exercise
assistant toggle is enforced at the view layer (403), not here.

Design: docs/features/exercise-hub.md · ADR-0004. Model is ENV-only.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from apps.chatbot.services.memory_service import MemoryService
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from .schemas import AssistantChatOutput

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


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


def _safe_replace(template: str, values: dict[str, Any]) -> str:
    out = str(template or "")
    for k, v in values.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def build_thread_id(*, exercise_id: int, question_id, student_id: int) -> str:
    return f"exercise:{exercise_id}:{question_id}:{student_id}"


def build_question_context(question, *, reveal: bool) -> str:
    """Assemble the question context for the assistant.

    CRITICAL (security): the reference answer is added ONLY when ``reveal`` is
    True. Pre-reveal, it is never placed in the model's context at all.
    """
    parts = [f"سوال: {question.question_markdown}"]
    if question.options:
        parts.append(f"گزینه‌ها: {question.options}")
    if reveal and (question.reference_answer_markdown or "").strip():
        parts.append(
            "پاسخ مرجع (فقط برای تدریسِ پس از نمره‌دهی): "
            + question.reference_answer_markdown
        )
    return "\n".join(parts)


def handle_assistant_message(
    *,
    exercise_id: int,
    question,
    student_id: int,
    user_message: str,
    student_work: str = "",
    reveal: bool = False,
) -> dict[str, Any]:
    """Return ``{content, suggestions}`` for one assistant turn (mocked in tests)."""
    message = str(user_message or "").strip()
    if not message:
        return {"content": "پیامت خالیه. لطفاً سوالت رو بنویس.", "suggestions": []}

    thread_id = build_thread_id(
        exercise_id=exercise_id, question_id=getattr(question, "id", None),
        student_id=student_id,
    )
    memory = MemoryService(thread_id=thread_id)
    memory.add(role="user", content=message)

    summary, buffer = memory.get_history_for_llm()
    history = ("\n".join(p for p in [summary, buffer] if p)).strip()

    prompt = _safe_replace(
        PROMPTS["exercise_assistant_chat"]["default"],
        {
            "phase": "graded" if reveal else "solving",
            "question_context": build_question_context(question, reveal=reveal),
            "student_work": student_work or "<empty>",
            "history": history or "اولین پیام",
            "user_message": message,
        },
    )

    try:
        # Inside the try so a model-misconfig (all *_MODEL env unset) also degrades
        # gracefully instead of 500-ing (security-auditor E8 Low-1).
        model = _select_model("EXERCISE_CHAT_MODEL", "CHAT_MODEL")
        obj = generate_structured(
            schema=AssistantChatOutput, contents=prompt,
            feature=LLMUsageLog.Feature.CHAT_EXERCISE, model=model,
            timeout=_LLM_TIMEOUT_SECONDS,
        )
        content = (obj.content or "").strip()
        suggestions = [s for s in (obj.suggestions or []) if str(s).strip()]
    except Exception:
        logger.exception("Exercise assistant generation failed")
        return {"content": "متأسفم، الان نتونستم جواب بدم. دوباره تلاش کن.", "suggestions": []}

    if content:
        memory.add(role="assistant", content=content)
    return {"content": content, "suggestions": suggestions}
