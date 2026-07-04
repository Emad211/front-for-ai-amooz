"""Exercise Hub — ingest: extract a structured exercise from source Markdown.

The OCR step (PDF/photo → Markdown) is fully reused from ``pdf_extraction.py`` (a
photo is treated as a page); this module owns only the *structure* step: turn that
Markdown into ``{exercise_title, sections[{questions[...]}]}`` validated against the
``ExerciseStructureOutput`` Pydantic schema via ``generate_structured`` (JSON-mode +
one repair round-trip + **raise**, never a silent ``{}``).

Design: docs/features/exercise-hub.md · ADR-0004. Prompt contract:
``PROMPTS['exercise_structure']['default']`` (byte-for-byte, guarded by
``test_prompts_contract.py``). Model is ENV-only (raise when unset).
"""
from __future__ import annotations

import base64
import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Any, Tuple

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from .schemas import ExerciseStructureOutput

logger = logging.getLogger(__name__)

_VALID_QUESTION_TYPES = {"descriptive", "multiple_choice", "fill_blank"}

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model(*names: str) -> str:
    """Select the LLM model from ENV only — no hardcoded default.

    Checks each of ``names`` in order, then falls back to ``MODEL_NAME``. Raises
    when nothing is set: a misconfigured deployment must fail loudly rather than
    silently calling a hardcoded model. Mirrors ``structure.py._select_model``.
    """
    for n in names:
        val = _get_env(n)
        if val:
            return val
    fallback = _get_env("MODEL_NAME")
    if fallback:
        return fallback
    raise RuntimeError(
        f"No LLM model defined in ENV. Checked: {names} and fallback MODEL_NAME."
    )


def structure_exercise_markdown(*, ingest_markdown: str) -> Tuple[dict[str, Any], str, str]:
    """Return ``(exercise_structure_dict, provider, model_name)``.

    ``ingest_markdown`` is the OCR/extraction Markdown of the uploaded exercise.
    Raises ``RuntimeError`` on total extraction failure (never returns empty).
    """
    model = _select_model("EXERCISE_STRUCTURE_MODEL", "STRUCTURE_MODEL")
    provider = preferred_provider()

    prompt = PROMPTS["exercise_structure"]["default"]
    full_prompt = f"{prompt}\n\nEXERCISE_SOURCE_MARKDOWN:\n{ingest_markdown}"

    logger.info(
        "EXERCISE_STRUCTURE start: model=%s source_chars=%d",
        model, len(ingest_markdown or ""),
    )
    try:
        obj = generate_structured(
            schema=ExerciseStructureOutput,
            contents=full_prompt,
            feature=LLMUsageLog.Feature.EXERCISE_STRUCTURE,
            model=model,
            timeout=_LLM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.exception("Exercise structure extraction failed")
        raise RuntimeError(f"Exercise structure extraction failed: {exc}") from exc

    return obj.model_dump(), provider, model


# ---------------------------------------------------------------------------
# OCR: source assets (PDF / photos) -> Markdown. PDF reuses pdf_extraction; a
# photo is treated as one page via a single standard-shape multimodal call.
# ---------------------------------------------------------------------------


def _ocr_image_to_markdown(*, data: bytes, mime_type: str) -> str:
    """One vision OCR call for a single image, using the pdf_extraction prompt
    and the standard OpenAI multimodal shape (``image_url`` data URI)."""
    from apps.chatbot.services.llm_client import generate_text

    model = _select_model("EXERCISE_VISION_MODEL", "IMAGE_MODEL")
    prompt = str(PROMPTS["pdf_extraction"]["default"])
    b64 = base64.b64encode(data).decode()
    messages = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
    ]}]
    resp = generate_text(
        messages=messages, model=model,
        feature=LLMUsageLog.Feature.EXERCISE_INGEST, timeout=_LLM_TIMEOUT_SECONDS,
    )
    return (resp.text if hasattr(resp, "text") else str(resp)).strip()


def ocr_assets_to_markdown(exercise) -> str:
    """Concatenate the OCR Markdown of every source asset of an exercise."""
    from .pdf_extraction import extract_pdf_to_markdown

    parts: list[str] = []
    for asset in exercise.assets.all():
        data = asset.file.read()
        if not data:
            continue
        if asset.kind == "pdf":
            markdown, *_rest = extract_pdf_to_markdown(data=data, mime_type="application/pdf")
        else:
            markdown = _ocr_image_to_markdown(data=data, mime_type="image/jpeg")
        if markdown and markdown.strip():
            parts.append(markdown.strip())
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Persist a validated exercise-structure dict into section/question rows.
# ---------------------------------------------------------------------------


def _coerce_question_type(value: Any) -> str:
    v = str(value or "").strip().lower()
    return v if v in _VALID_QUESTION_TYPES else "descriptive"


def _coerce_points(value: Any) -> Decimal:
    if value is None:
        return Decimal("1")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("1")


def persist_exercise_structure(exercise, structure: dict) -> tuple[int, int]:
    """Replace the exercise's sections/questions from a validated structure dict.

    Idempotent for re-runs: existing sections are cleared first (CASCADE drops
    their questions). Returns ``(section_count, question_count)``.
    """
    from ..models import ClassExerciseSection, ClassExerciseQuestion

    exercise.sections.all().delete()  # cascades questions
    n_sections = n_questions = 0
    for s_idx, section in enumerate(structure.get("sections") or []):
        if not isinstance(section, dict):
            continue
        sec = ClassExerciseSection.objects.create(
            exercise=exercise, order=s_idx,
            title=str(section.get("title") or "")[:255],
        )
        n_sections += 1
        for q_idx, q in enumerate(section.get("questions") or []):
            if not isinstance(q, dict):
                continue
            options = q.get("options")
            ClassExerciseQuestion.objects.create(
                section=sec, order=q_idx,
                question_markdown=str(q.get("question_text_markdown") or ""),
                question_type=_coerce_question_type(q.get("question_type")),
                options=options if isinstance(options, list) else [],
                reference_answer_markdown=str(q.get("reference_answer_markdown") or ""),
                max_points=_coerce_points(q.get("points")),
            )
            n_questions += 1
    return n_sections, n_questions
