from __future__ import annotations

import logging
import os
import re
from typing import Any, Tuple

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.chatbot.services.llm_client import generate_text
from apps.commons.structured_llm import StructuredOutputError, validate_keep_dict

from .schemas import StructureOutput

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


# -------------------------------------------------------------------
# ENV + Model Selection (Architecture‑Correct — NO DEFAULTS)
# -------------------------------------------------------------------

def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model(*names: str) -> str:
    """
    Select model using ONLY ENV variables:
      STRUCTURE_MODEL → REWRITE_MODEL → MODEL_NAME
    No defaults. If nothing is defined → error (intentional).
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


# -------------------------------------------------------------------
# Prompt Rendering (Safe replacement)
# -------------------------------------------------------------------

def _render_prompt(template: str, **values: Any) -> str:
    rendered = template
    for key, val in values.items():
        rendered = rendered.replace("{" + key + "}", str(val))
    return rendered


# -------------------------------------------------------------------
# Central LLM Caller
# -------------------------------------------------------------------

def _call_llm(
    *,
    model: str,
    prompt: str,
    feature: LLMUsageLog.Feature,
) -> str:

    resp = generate_text(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        timeout=_LLM_TIMEOUT_SECONDS,
        feature=feature,
    )

    text = resp.text if hasattr(resp, "text") else str(resp)
    return text.strip()


# -------------------------------------------------------------------
# Main Function — Structure Generator
# -------------------------------------------------------------------

def structure_transcript_markdown(
    *,
    transcript_markdown: str
) -> Tuple[dict[str, Any], str, str]:
    """
    Returns (structure_json_obj, provider, model_name)
    """

    model = _select_model("STRUCTURE_MODEL", "REWRITE_MODEL")

    provider = preferred_provider()

    base_prompt = PROMPTS["structure_content"]["default"]

    # avoid .format() → safe manual replacement
    prompt = _render_prompt(
        base_prompt,
        transcript_markdown=transcript_markdown,
    )

    full_prompt = (
        f"{prompt}\n\nFULL_TRANSCRIPT_MARKDOWN:\n{transcript_markdown}"
    )

    logger.info(
        "STRUCTURE start: model=%s transcript_chars=%d prompt_chars=%d",
        model, len(transcript_markdown or ""), len(full_prompt),
    )
    try:
        text = _call_llm(
            model=model,
            prompt=full_prompt,
            feature=LLMUsageLog.Feature.STRUCTURE,
        )
        logger.info("STRUCTURE response: chars=%d has_brace=%s",
                    len(text or ""), ("{" in (text or "")))

        try:
            # Validate the SHAPE (not just "is it parseable"), but keep the model's
            # exact dict so downstream consumers see unmodified data.
            obj = validate_keep_dict(text, StructureOutput)
        except StructuredOutputError:
            # The model sometimes replies with prose / fenced text / wrong shape.
            # Log exactly what came back, then do one strict repair pass.
            logger.error(
                "STRUCTURE invalid/no-JSON in primary response (chars=%d). HEAD=%r TAIL=%r",
                len(text or ""), (text or "")[:2000], (text or "")[-800:],
            )
            repair_prompt = (
                "The text below was supposed to be a single JSON object matching the "
                "course-structure schema (top-level keys: root_object, outline; each "
                "outline item has a units list) but is malformed or wrapped in prose. "
                "Return ONLY one valid JSON object (no markdown fences, no commentary).\n\n"
                + text
            )
            repaired = _call_llm(
                model=model,
                prompt=repair_prompt,
                feature=LLMUsageLog.Feature.STRUCTURE,
            )
            try:
                obj = validate_keep_dict(repaired, StructureOutput)
            except StructuredOutputError:
                logger.error(
                    "STRUCTURE invalid/no-JSON after repair (chars=%d). HEAD=%r",
                    len(repaired or ""), (repaired or "")[:2000],
                )
                raise

        obj = _restore_latex_escapes(obj)
        obj = _reinject_unit_assets(obj)

        return obj, provider, model

    except Exception as exc:
        logger.exception("Structure generation failed")
        raise RuntimeError(f"Structure generation failed: {exc}") from exc


# -------------------------------------------------------------------
# Asset preservation (deterministic safety net)
# -------------------------------------------------------------------

def _reinject_unit_assets(obj: Any) -> Any:
    """Ensure images/tables in each unit's verbatim source survive the rewrite.

    The LLM is instructed to preserve `![](url)` images and GFM tables in
    content_markdown, but we do NOT rely on it: any asset present in a unit's
    source_markdown yet missing from its content_markdown is appended back.
    """
    from .markdown_assets import reinject

    try:
        outline = obj.get("outline") if isinstance(obj, dict) else None
        if not isinstance(outline, list):
            return obj
        for section in outline:
            for unit in (section or {}).get("units", []) or []:
                if not isinstance(unit, dict):
                    continue
                src = unit.get("source_markdown") or ""
                content = unit.get("content_markdown") or ""
                if "![" in src or "|" in src:
                    unit["content_markdown"] = reinject(src, content)
    except Exception:  # never let preservation break structuring
        logger.exception("asset reinjection failed; returning structure as-is")
    return obj


# -------------------------------------------------------------------
# LaTeX Fixer (unchanged)
# -------------------------------------------------------------------

def _restore_latex_escapes(value: Any) -> Any:
    """
    Repair LaTeX commands inside JSON strings.
    """

    if isinstance(value, str):
        return (
            value.replace("\t", "\\t")
                 .replace("\b", "\\b")
                 .replace("\f", "\\f")
        )

    if isinstance(value, list):
        return [_restore_latex_escapes(v) for v in value]

    if isinstance(value, dict):
        return {k: _restore_latex_escapes(v) for k, v in value.items()}

    return value
