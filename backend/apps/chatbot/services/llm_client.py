from __future__ import annotations

import base64
import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Optional, List, Dict

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

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


def _openai_sdk_max_retries() -> int:
    """Keep retry ownership in this module instead of multiplying SDK retries."""
    try:
        return max(0, int(os.getenv("OPENAI_SDK_MAX_RETRIES", "0")))
    except (TypeError, ValueError):
        return 0


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

    return OpenAI(api_key=api_key, base_url=base_url, max_retries=_openai_sdk_max_retries())


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
# Multimodal content normalization
# ====================================================================
def _normalize_content(content: Any) -> Any:
    """Normalize a message ``content`` into a valid OpenAI shape.

    A plain string stays a string. A LIST may contain raw strings and/or media
    parts produced by ``part_from_bytes``; OpenAI requires every list item to be
    a typed part, so raw strings are wrapped as ``{"type": "text", ...}``. Dict
    parts (image_url / input_audio / text) pass through unchanged.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[Any] = []
        for item in content:
            if isinstance(item, str):
                parts.append({"type": "text", "text": item})
            else:
                parts.append(item)
        return parts
    return content


def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg, dict) and "content" in msg:
            out.append({**msg, "content": _normalize_content(msg["content"])})
        else:
            out.append(msg)
    return out


def _response_format_unsupported(exc: Exception) -> bool:
    """Heuristic: did the provider reject the ``response_format`` parameter?"""
    msg = str(exc).lower()
    if "response_format" in msg or "response format" in msg:
        return True
    if "json_object" in msg or "json mode" in msg:
        return True
    if ("unsupported" in msg or "unknown" in msg or "not supported" in msg) and "param" in msg:
        return True
    return False


class ProviderTransientError(RuntimeError):
    """A provider/network failure that is safe for Celery pipeline retry."""


_RETRYABLE_HTTP_STATUSES = {408, 409, 429}


def _http_status_from_exception(exc: BaseException) -> int | None:
    raw = getattr(exc, "status_code", None)
    if isinstance(raw, int):
        return raw
    response = getattr(exc, "response", None)
    raw = getattr(response, "status_code", None)
    return raw if isinstance(raw, int) else None


def is_transient_llm_error(exc: BaseException) -> bool:
    """Return True only for provider failures worth retrying.

    Permanent request/config/application failures must fail fast. Retrying a
    malformed multimodal payload, missing key, 401, 413, or parser failure just
    burns worker slots and tokens while delaying the teacher-facing failure.
    """
    if isinstance(exc, ProviderTransientError):
        return True
    if isinstance(exc, Exception) and _response_format_unsupported(exc):
        return False
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        status = _http_status_from_exception(exc)
        return status in _RETRYABLE_HTTP_STATUSES or (status is not None and status >= 500)
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True

    status = _http_status_from_exception(exc)
    if status is None:
        return False
    return status in _RETRYABLE_HTTP_STATUSES or status >= 500


def _should_retry_llm_call(exc: BaseException) -> bool:
    """Retry only transient provider/network failures.

    Retrying a 400 about an unsupported parameter just wastes calls; ``generate_json``
    handles that case by retrying once WITHOUT json mode, so fail fast here.
    """
    return is_transient_llm_error(exc)


# ====================================================================
# Core LLM Call (با پشتیبانی از messages)
# ====================================================================
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=12),
    retry=retry_if_exception(_should_retry_llm_call),
    reraise=True,
)
def _call_gapgpt_with_messages(
    *,
    messages: List[Dict[str, Any]],
    used_model: str,
    feature: str,
    timeout: Optional[float] = None,
    temperature: Optional[float] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> LlmResult:

    # Strip any "models/" prefix just before sending
    clean_model = _strip_model_prefix(used_model)

    client = _get_gapgpt_client()
    timer = LLMTimer().start()

    create_kwargs: Dict[str, Any] = {
        "model": clean_model,
        "messages": _normalize_messages(messages),
        "timeout": timeout if timeout is not None else _default_llm_timeout(),
    }
    if response_format is not None:
        create_kwargs["response_format"] = response_format
    if temperature is not None:
        create_kwargs["temperature"] = temperature

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
        if is_transient_llm_error(exc):
            raise ProviderTransientError(str(exc)) from exc
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
    temperature: Optional[float] = None,
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
        temperature=temperature,
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
def _json_object_mode_enabled() -> bool:
    return (os.getenv("LLM_JSON_OBJECT_MODE", "1") or "1").strip().lower() in {"1", "true", "yes"}


def generate_json(*, feature: str, contents: Any) -> dict[str, Any]:
    """Free-text → dict, now using provider JSON mode when available.

    Requesting ``response_format={"type": "json_object"}`` makes the model emit
    parseable JSON far more reliably, so the repair round-trip (and the silent
    ``{}`` fallback) fire much less often. If the provider/model rejects
    ``response_format``, we transparently retry without it.
    """
    set_llm_feature(feature)

    use_json_mode = _json_object_mode_enabled()
    try:
        out = generate_text(
            contents=contents,
            feature=feature,
            response_format={"type": "json_object"} if use_json_mode else None,
        ).text
    except Exception as exc:
        if use_json_mode and _response_format_unsupported(exc):
            out = generate_text(contents=contents, feature=feature).text
        else:
            raise

    if not out.strip():
        return _repair_json_with_llm(feature=feature, model_output=out)

    try:
        obj = extract_json_object(out)
        return obj if isinstance(obj, dict) else {"result": obj}
    except Exception:
        return _repair_json_with_llm(feature=feature, model_output=out)


# ====================================================================
# File upload support (standard OpenAI multimodal shapes)
# ====================================================================
def _audio_format_from_mime(mime_type: str) -> str:
    mt = (mime_type or "").lower().strip()
    mapping = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/wave": "wav",
        "audio/ogg": "ogg",
        "audio/webm": "webm",
        "audio/flac": "flac",
        "audio/mp4": "mp4",
        "audio/m4a": "m4a",
        "audio/x-m4a": "m4a",
    }
    if mt in mapping:
        return mapping[mt]
    return mt.split("/")[-1] or "mp3"


def part_from_bytes(*, data: bytes, mime_type: str):
    """Build a STANDARD OpenAI multimodal content part from raw bytes.

    The Avalai gateway silently ignores the legacy ``{type:'input_file',data,
    mime_type}`` shape (the historical cause of empty/hallucinated vision
    output). Images MUST use ``image_url`` with a base64 data URI and audio MUST
    use ``input_audio`` — mirroring the already-fixed transcription path.
    See AvalAI-Developer-Documentation.md.
    """
    mt = (mime_type or "").lower().strip() or "application/octet-stream"
    b64 = base64.b64encode(data).decode("ascii")

    if mt.startswith("audio/"):
        return {
            "type": "input_audio",
            "input_audio": {"data": b64, "format": _audio_format_from_mime(mt)},
        }

    # Images (and any other type) → data-URI image_url (the shape the gateway honors).
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mt};base64,{b64}"},
    }
