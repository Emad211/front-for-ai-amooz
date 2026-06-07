from __future__ import annotations

import os
import re
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


# Per-request client timeout (seconds). Long pipeline/transcription calls need a
# generous timeout; callers may override per call. (Previously a 45s literal was
# hardcoded in the create() call AND the caller-supplied timeout was silently
# dropped into **kwargs — both fixed.)
def _default_llm_timeout() -> float:
    try:
        return float(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
    except (TypeError, ValueError):
        return 600.0


# ====================================================================
# Helper to strip "models/" prefix if present
# ====================================================================
def _strip_model_prefix(model_name: str) -> str:
    """Remove any leading 'models/' prefix from model name."""
    if model_name.startswith("models/"):
        return model_name[7:]  # len("models/") == 7
    return model_name


# ====================================================================
# OpenAI-Compatible Client for GAPGPT
# ====================================================================
def _normalize_base_url(url: str) -> str:
    """Ensure the OpenAI-compatible ``/v{n}`` route is present.

    Some env values (e.g. ``https://api.avalai.ir``) omit the version segment,
    which makes the SDK POST to ``/chat/completions`` and 404 at the gateway.
    Idempotent: a URL already ending in ``/v1`` (gapgpt default) is unchanged.
    """
    u = (url or "").strip().rstrip("/")
    if not u:
        return u
    if not re.search(r"/v\d+$", u):
        u = u + "/v1"
    return u


def _get_gapgpt_client() -> OpenAI:
    api_key = _get_env("AVALAI_API_KEY")
    base_url = _normalize_base_url(_get_env("AVALAI_BASE_URL") or "https://api.gapgpt.app/v1")

    if not api_key:
        raise RuntimeError("AVALAI_API_KEY missing (expected to contain GAPGPT key).")

    return OpenAI(api_key=api_key, base_url=base_url)


# ====================================================================
# Selecting model
# ====================================================================
def _default_model() -> str:
    raw = _get_env("CHAT_MODEL") or "gemini-2.5-flash"
    return _strip_model_prefix(raw)


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
    messages: List[Dict[str, Any]],
    used_model: str,
    feature: str,
    timeout: Optional[float] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> LlmResult:

    # Strip any "models/" prefix just before sending
    clean_model = _strip_model_prefix(used_model)

    client = _get_gapgpt_client()
    timer = LLMTimer().start()

    create_kwargs: Dict[str, Any] = {
        "model": clean_model,
        "messages": messages,
        "timeout": timeout if timeout is not None else _default_llm_timeout(),
    }
    if response_format is not None:
        create_kwargs["response_format"] = response_format

    try:
        response = client.chat.completions.create(**create_kwargs)

        text = response.choices[0].message.content.strip()
        if not text:
            raise ValueError("Empty response from GAPGPT")

        track_llm_usage(
            resp=response,
            feature=feature,
            provider="gapgpt",
            model_name=clean_model,
            duration_ms=timer.elapsed_ms,
        )

        return LlmResult(
            text=text,
            provider="gapgpt",
            model=clean_model
        )

    except Exception as exc:
        track_llm_error(
            feature=feature,
            provider="gapgpt",
            model_name=clean_model,
            error_message=str(exc),
        )
        raise


# ====================================================================
# Public API: generate_text (پذیرش تمام پارامترهای احتمالی)
# ====================================================================
def generate_text(
    *,
    messages: Optional[List[Dict[str, Any]]] = None,
    contents: Optional[Any] = None,
    model: Optional[str] = None,
    feature: Optional[str] = None,
    timeout: Optional[float] = None,
    response_format: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> LlmResult:
    """
    Unified LLM caller.

    ``timeout`` (seconds) is now honoured and forwarded to the underlying client
    instead of being swallowed by ``**kwargs``. ``response_format`` enables JSON
    mode (``{"type": "json_object"}``) for structured-output callers.
    """
    used_model = model or _default_model()
    # Strip prefix here as well, in case model passed directly
    used_model = _strip_model_prefix(used_model)
    resolved_feature = feature or _get_llm_feature()

    if messages is not None:
        final_messages = messages
    elif contents is not None:
        final_messages = [{"role": "user", "content": contents}]
    else:
        raise ValueError("Either 'messages' or 'contents' must be provided")

    return _call_gapgpt_with_messages(
        messages=final_messages,
        used_model=used_model,
        feature=resolved_feature,
        timeout=timeout,
        response_format=response_format,
    )


# ====================================================================
# JSON REPAIR (بدون تغییر)
# ====================================================================
def _repair_json_with_llm(*, feature: str, model_output: str, schema_hint: str = "") -> dict[str, Any]:
    template = PROMPTS["json_repair"]["default"]
    # The template carries THREE placeholders: {feature}, {schema_hint}, {raw_text}.
    # Previously only {raw_text} was substituted, so the model received literal
    # "{feature}"/"{schema_hint}" text. Substitute all of them.
    prompt = (
        template
        .replace("{feature}", str(feature or "unknown"))
        .replace("{schema_hint}", schema_hint or "(no explicit schema; return a single valid JSON object)")
        .replace("{raw_text}", model_output)
    )

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
