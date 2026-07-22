"""Extract validated exam-prep questions from audio/video transcript Markdown."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from billiard.exceptions import SoftTimeLimitExceeded

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured

from .exam_prep_utils import clean_exam_markdown, normalize_exam_prep_question
from .schemas import ExamPrepOutput
from .text_sanitize import sanitize_llm_markdown


logger = logging.getLogger(__name__)
_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _select_model(*names: str) -> str:
    for name in names:
        if value := _get_env(name):
            return value
    if fallback := _get_env("MODEL_NAME"):
        return fallback
    raise RuntimeError(
        f"No LLM model defined in ENV. Checked: {names} and fallback MODEL_NAME."
    )


def _window_chars() -> int:
    return max(4_000, min(_env_int("EXAM_PREP_WINDOW_CHARS", 20_000), 40_000))


def _window_overlap() -> int:
    return max(0, min(_env_int("EXAM_PREP_WINDOW_OVERLAP", 4_000), 8_000))


def _split_transcript(text: str, *, window_chars: int, overlap: int) -> list[str]:
    """Split on nearby paragraph boundaries while retaining boundary overlap."""
    if len(text) <= window_chars:
        return [text] if text.strip() else []

    windows: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + window_chars, len(text))
        if end < len(text):
            search_start = start + int(window_chars * 0.8)
            boundary = text.rfind("\n\n", search_start, end)
            if boundary < 0:
                boundary = text.rfind("\n", search_start, end)
            if boundary > start:
                end = boundary
        windows.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [window for window in windows if window.strip()]


def _clean(value: Any) -> str:
    """Compatibility seam used by regression tests and field normalization."""
    return clean_exam_markdown(value)


def _extract_window(
    *, window_text: str, model: str, part: int, total: int
) -> tuple[list[dict[str, Any]], str]:
    label = (
        f"PART {part}/{total} OF FULL_TRANSCRIPT_MARKDOWN"
        if total > 1
        else "FULL_TRANSCRIPT_MARKDOWN"
    )
    try:
        result = generate_structured(
            schema=ExamPrepOutput,
            messages=[
                {"role": "system", "content": PROMPTS["exam_prep_structure"]["default"]},
                {"role": "user", "content": f"{label}:\n{window_text}"},
            ],
            model=model,
            feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
            timeout=_LLM_TIMEOUT_SECONDS,
            temperature=0,
        )
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        logger.warning("exam-prep structure window %d/%d failed: %s", part, total, exc)
        return [], ""

    return [question.model_dump() for question in result.exam_prep.questions], _clean(
        result.exam_prep.title
    )


def _question_key(question: dict[str, Any]) -> str:
    return " ".join(question["question_text_markdown"].lower().split())


def _merge_question(existing: dict[str, Any], candidate: dict[str, Any]) -> None:
    for field in (
        "correct_option_label",
        "correct_option_text_markdown",
        "final_answer_markdown",
    ):
        if not existing.get(field) and candidate.get(field):
            existing[field] = candidate[field]
    if len(candidate.get("options") or []) > len(existing.get("options") or []):
        existing["options"] = candidate["options"]
    if len(candidate.get("teacher_solution_markdown") or "") > len(
        existing.get("teacher_solution_markdown") or ""
    ):
        existing["teacher_solution_markdown"] = candidate["teacher_solution_markdown"]


def _reinject_exam_assets(parsed: dict, transcript_markdown: str) -> dict:
    """Keep extracted images even if the structure model omits their references."""
    from .markdown_assets import image_refs, image_urls

    try:
        refs = image_refs(transcript_markdown)
        present = set(image_urls(json.dumps(parsed, ensure_ascii=False)))
        missing = [
            ref
            for ref, url in zip(refs, image_urls(transcript_markdown))
            if url not in present
        ]
        questions = (parsed.get("exam_prep") or {}).get("questions") or []
        if missing and questions:
            solution = questions[-1].get("teacher_solution_markdown") or ""
            questions[-1]["teacher_solution_markdown"] = (
                solution.rstrip() + "\n\n" + "\n\n".join(missing)
            ).strip()
    except Exception:
        logger.exception("exam-prep asset reinjection failed")
    return parsed


def extract_exam_prep_structure(
    *, transcript_markdown: str
) -> tuple[dict[str, Any], str, str]:
    """Return validated, deduplicated Q&A from an audio/video transcript."""
    model = _select_model("STRUCTURE_MODEL", "REWRITE_MODEL")
    provider = preferred_provider()
    transcript = sanitize_llm_markdown(transcript_markdown)
    if not transcript:
        return {"exam_prep": {"title": "", "questions": []}}, provider, model

    window_chars = _window_chars()
    windows = _split_transcript(
        transcript,
        window_chars=window_chars,
        overlap=min(_window_overlap(), window_chars // 2),
    )
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    title = ""

    for part, window in enumerate(windows, start=1):
        raw_questions, window_title = _extract_window(
            window_text=window,
            model=model,
            part=part,
            total=len(windows),
        )
        title = title or window_title
        for raw in raw_questions:
            normalized = normalize_exam_prep_question(raw, index=len(order) + 1)
            if normalized is None:
                continue
            key = _question_key(normalized)
            if key in merged:
                _merge_question(merged[key], normalized)
            else:
                merged[key] = normalized
                order.append(key)

    questions = []
    for index, key in enumerate(order, start=1):
        question = merged[key]
        question["question_id"] = f"q-{index}"
        questions.append(question)
    if not questions:
        raise RuntimeError(
            "هیچ سؤال معتبری از محتوای ویدیو یا صوت استخراج نشد. لطفاً کیفیت فایل را بررسی کنید."
        )

    return _reinject_exam_assets(
        {"exam_prep": {"title": title, "questions": questions}}, transcript
    ), provider, model
