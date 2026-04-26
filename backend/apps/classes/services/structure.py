from __future__ import annotations

import logging
import os
from typing import Any, Tuple

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.services.llm_client import generate_text

from .json_utils import extract_json_object

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

    try:
        text = _call_llm(
            model=model,
            prompt=full_prompt,
            feature=LLMUsageLog.Feature.STRUCTURE,
        )

        obj = extract_json_object(text)
        obj = _restore_latex_escapes(obj)

        return obj, provider, model

    except Exception as exc:
        logger.exception("Structure generation failed")
        raise RuntimeError(f"Structure generation failed: {exc}") from exc


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
