from __future__ import annotations

import logging
import os
from typing import Any, Optional

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.services.llm_client import generate_text

from apps.classes.services.json_utils import extract_json_object

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model(*names: str, default: str = "gpt-4.1") -> str:
    for n in names:
        val = _get_env(n)
        if val:
            return val
    return default


def _strip_outer_fence(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s

    if s.startswith("
```") and s.endswith("
```"):
        lines = s.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()

    return s


def _safe_json_from_llm(text: str) -> dict[str, Any]:
    """
    Strict JSON extraction with safety wrapping.
    Guarantees dict output.
    """
    obj = extract_json_object(text)

    if isinstance(obj, dict):
        return obj

    return {"prerequisites": obj}


def _call_llm(
    *,
    model: str,
    system_prompt: str,
    user_content: str,
    feature: LLMUsageLog.Feature,
) -> str:
    """
    Unified LLM invocation.
    Centralizes provider selection, logging, timeout, and error surface.
    """

    provider = preferred_provider()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    resp = generate_text(
        model=model,
        messages=messages,
        timeout=_LLM_TIMEOUT_SECONDS,
        feature=feature,
    )

    text = resp.text if hasattr(resp, "text") else str(resp)
    return text.strip()


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def extract_prerequisites(
    *, transcript_markdown: str
) -> tuple[dict[str, Any], str, str]:
    """
    Extract prerequisite structure JSON from transcript.
    """

    model = _select_model(
        "PREREQUISITES_MODEL",
        "STRUCTURE_MODEL",
        "REWRITE_MODEL",
        "MODEL_NAME",
    )

    provider = preferred_provider()

    prompt = PROMPTS["prerequisites_prompt"]["default"]

    user_content = f"FULL_TRANSCRIPT_MARKDOWN:\n{transcript_markdown}"

    try:
        raw_text = _call_llm(
            model=model,
            system_prompt=prompt,
            user_content=user_content,
            feature=LLMUsageLog.Feature.PREREQ_EXTRACT,
        )

        parsed = _safe_json_from_llm(raw_text)

        return parsed, provider, model

    except Exception as exc:
        logger.exception("Prerequisite extraction failed")
        raise RuntimeError(f"Prerequisite extraction failed: {exc}") from exc


def generate_prerequisite_teaching(
    *, prerequisite_name: str
) -> tuple[str, str, str]:
    """
    Generate structured teaching content for a single prerequisite.
    """

    model = _select_model(
        "PREREQ_TEACHING_MODEL",
        "STRUCTURE_MODEL",
        "REWRITE_MODEL",
        "MODEL_NAME",
    )

    provider = preferred_provider()

    prompt = PROMPTS["prerequisite_teaching"]["default"]

    user_content = f"PREREQUISITE_NAME:\n{prerequisite_name}"

    try:
        raw_text = _call_llm(
           model=model,
            system_prompt=prompt,
            user_content=user_content,
            feature=LLMUsageLog.Feature.PREREQ_TEACH,
        )

        cleaned = _strip_outer_fence(raw_text)

        return cleaned, provider, model

    except Exception as exc:
        logger.exception("Prerequisite teaching generation failed")
        raise RuntimeError(f"Prerequisite teaching failed: {exc}") from exc
