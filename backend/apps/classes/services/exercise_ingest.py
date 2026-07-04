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

import logging
import os
from typing import Any, Tuple

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from .schemas import ExerciseStructureOutput

logger = logging.getLogger(__name__)

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
