from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Optional, List, Dict

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
# Core LLM Call (با پشتیبانی از messages)
# ====================================================================
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=12),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_gapgpt_with_messages(
    *, 
    messages: List[Dict[str, str]], 
    used_model: str, 
    feature: str
) -> LlmResult:

    client = _get_gapgpt_client()
    timer = LLMTimer().start()

    try:
        response = client.chat.completions.create(
            model=used_model,
            messages=messages,
            timeout=45,
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
# Public API: generate_text (پذیرش تمام پارامترهای احتمالی)
# ====================================================================
def generate_text(
    *,
    messages: Optional[List[Dict[str, str]]] = None,
    contents: Optional[Any] = None,
    model: Optional[str] = None,
    feature: Optional[str] = None,
    timeout: Optional[int] = None,      # پذیرفته می‌شود ولی فعلاً نادیده گرفته می‌شود
    **kwargs,                           # جزئیات اضافی مثل detail را نادیده می‌گیرد
) -> LlmResult:
    """
    Unified LLM caller.

    Args:
        messages: List of message dicts with 'role' and 'content' (OpenAI format)
        contents: Legacy parameter – single content (wrapped as user message)
        model: Model name (optional)
        feature: Feature name for tracking
        timeout: Ignored (kept for compatibility)
        **kwargs: Any extra arguments (e.g., 'detail') are ignored

    Returns:
        LlmResult with text, provider, model
    """

    used_model = model or _default_model()
    resolved_feature = feature or _get_llm_feature()

    if messages is not None:
        final_messages = messages
    elif contents is not None:
        final_messages = [{"role": "user", "content": contents}]
    else:
        raise ValueError("Either 'messages' or 'contents' must be provided")

    # در آینده می‌توان از timeout استفاده کرد، ولی فعلاً نادیده گرفته می‌شود
    return _call_gapgpt_with_messages(
        messages=final_messages,
        used_model=used_model,
        feature=resolved_feature,
    )


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
# Public API: generate_json
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
# File upload support
# ====================================================================
def part_from_bytes(*, data: bytes, mime_type: str):
    return {
        "type": "input_file",
        "data": data,
        "mime_type": mime_type,
    }
