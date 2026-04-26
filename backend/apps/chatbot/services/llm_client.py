from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.json_utils import extract_json_object
from apps.commons.token_tracker import (
    track_llm_usage,
    track_llm_error,
    LLMTimer,
)
from apps.commons.models import LLMUsageLog


# ====================================================================
# Thread-local feature tracking
# ====================================================================
_feature_local = threading.local()


def set_llm_feature(feature: str) -> None:
    _feature_local.feature = feature


def _get_llm_feature() -> str:
    return getattr(_feature_local, "feature", LLMUsageLog.Feature.OTHER)


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


# ====================================================================
# OpenAI-Compatible Client for GAPGPT
# ====================================================================
def _get_gapgpt_client() -> OpenAI:
    """
    This uses the SAME env names as the original project:
        AVALAI_API_KEY   -> now contains GapGPT key
        AVALAI_BASE_URL  -> now contains https://api.gapgpt.app/v1
    """

    api_key = _get_env("AVALAI_API_KEY")
    base_url = _get_env("AVALAI_BASE_URL") or "https://api.gapgpt.app/v1"

    if not api_key:
        raise RuntimeError("AVALAI_API_KEY missing (expected to contain GAPGPT key).")

    return OpenAI(api_key=api_key, base_url=base_url)


# ====================================================================
# Selecting model
# ====================================================================
def _default_model() -> str:
    return _get_env("CHAT_MODEL") or "gemini-2.5-flash"


# ====================================================================
# Result DTO
# ====================================================================
@dataclass(frozen=True)
class LlmResult:
    text: str
    provider: str
    model: str


# ====================================================================
# Core LLM Call
# ====================================================================
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=12),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_gapgpt(*, contents: Any, used_model: str, feature: str) -> LlmResult:

    client = _get_gapgpt_client()
    timer = LLMTimer().start()

    try:
        response = client.chat.completions.create(
            model=used_model,
            messages=[
                {"role": "user", "content": contents}
            ],
            timeout=45,   # hard timeout
        )

        text = response.choices[0].message.content.strip()

        if not text:
            raise ValueError("Empty response from GAPGPT")

        track_llm_usage(
            resp=response,
            feature=feature,
            provider="gapgpt",
            model_name=used_model,
            duration_ms=timer.elapsed_ms,
        )

        return LlmResult(
            text=text,
            provider="gapgpt",
            model=used_model
        )

    except Exception as exc:

        track_llm_error(
            feature=feature,
            provider="gapgpt",
            model_name=used_model,
            error_message=str(exc),
        )

        raise


# ====================================================================
# Public API: generate_text (same signature)
# ====================================================================
def generate_text(*, contents: Any, model: Optional[str] = None, feature: Optional[str] = None) -> LlmResult:

    used_model = model or _default_model()
    resolved_feature = feature or _get_llm_feature()

    try:
        return _call_gapgpt(
            contents=contents,
            used_model=used_model,
            feature=resolved_feature,
        )
    except Exception as exc:
        print(f"[LLM ERROR] GAPGPT failed for model={used_model}: {exc}")
        raise


# ====================================================================
# JSON REPAIR
# ====================================================================
def _repair_json_with_llm(*, feature: str, model_output: str) -> dict[str, Any]:

    template = PROMPTS["json_repair"]["default"]

    prompt = template.replace("{raw_text}", model_output)

    repaired = generate_text(
        contents=prompt,
        feature=LLMUsageLog.Feature.JSON_REPAIR,
    ).text

    try:
        obj = extract_json_object(repaired)
        return obj if isinstance(obj, dict) else {"result": obj}
    except Exception:
        return {}


# ====================================================================
# Public API: generate_json (same signature)
# ====================================================================
def generate_json(*, feature: str, contents: Any) -> dict[str, Any]:

    set_llm_feature(feature)
    out = generate_text(contents=contents, feature=feature).text

    if not out.strip():
        return _repair_json_with_llm(feature=feature, model_output=out)

    try:
        obj = extract_json_object(out)
        return obj if isinstance(obj, dict) else {"result": obj}
    except Exception:
        return _repair_json_with_llm(feature=feature, model_output=out)


# ====================================================================
# File upload support (same signature)
# ====================================================================
def part_from_bytes(*, data: bytes, mime_type: str):
    return {
        "type": "input_file",
        "data": data,
        "mime_type": mime_type,
    }
