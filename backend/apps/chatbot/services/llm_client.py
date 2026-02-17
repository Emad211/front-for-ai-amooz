from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from google import genai
from google.genai import types
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

# Thread-local feature context for tracking
import threading
_feature_local = threading.local()


def set_llm_feature(feature: str) -> None:
    """Set the current LLM feature for token tracking."""
    _feature_local.feature = feature


def _get_llm_feature() -> str:
    return getattr(_feature_local, 'feature', LLMUsageLog.Feature.OTHER)


def _get_env(name: str) -> str:
    return (os.getenv(name) or '').strip()


def _safe_template_replace(template: str, values: dict[str, Any]) -> str:
    """Replace `{name}` placeholders without calling `.format()`.

    Some prompts contain JSON examples with `{}` which would break `.format()`.
    """

    out = str(template or '')
    for key, val in (values or {}).items():
        if not isinstance(key, str):
            continue
        out = out.replace('{' + key + '}', str(val))
    return out


def _schema_hint_for_feature(feature: str) -> str:
    """Return a small JSON shape hint to guide repair."""

    f = (feature or '').strip()
    if f == 'chat_intent':
        return '{"intent": "<string>"}'
    if f == 'chat_system_prompt':
        return '{"content": "<string>", "suggestions": ["<string>"]}'
    # Generic fallback: return a JSON object.
    return '{"...": "..."}'


def _get_clients() -> Tuple[Optional[genai.Client], Optional[genai.Client]]:
    gemini_api_key = _get_env('GEMINI_API_KEY')
    avalai_api_key = _get_env('AVALAI_API_KEY')
    avalai_base_url = _get_env('AVALAI_BASE_URL')

    provider = preferred_provider()

    gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key and provider != 'avalai' else None

    avalai_client: Optional[genai.Client] = None
    if avalai_api_key and provider != 'gemini':
        http_options = {'base_url': avalai_base_url} if avalai_base_url else None
        avalai_client = genai.Client(api_key=avalai_api_key, http_options=http_options)

    return gemini_client, avalai_client


def _extract_text(resp: Any) -> str:
    text = (getattr(resp, 'text', '') or '').strip()
    if text:
        return text

    candidates = getattr(resp, 'candidates', None) or []
    buf: list[str] = []
    for c in candidates:
        content = getattr(c, 'content', None)
        parts = getattr(content, 'parts', None) if content else None
        if not parts:
            continue
        for p in parts:
            t = getattr(p, 'text', None)
            if t:
                buf.append(t)
    return ('\n'.join(buf)).strip()


def _default_model() -> str:
    model = _get_env('CHAT_MODEL') or _get_env('MODEL_NAME')
    return model or 'models/gemini-2.5-flash'


@dataclass(frozen=True)
class LlmResult:
    text: str
    provider: str
    model: str


def generate_text(*, contents: Any, model: Optional[str] = None, feature: Optional[str] = None) -> LlmResult:
    used_model = model or _default_model()
    gemini_client, avalai_client = _get_clients()

    provider = preferred_provider()
    last_error: Optional[Exception] = None
    resolved_feature = feature or _get_llm_feature()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _call_llm(client: genai.Client, prov: str) -> LlmResult:
        timer = LLMTimer().start()
        try:
            resp = client.models.generate_content(model=used_model, contents=contents)
            text = _extract_text(resp)
            if not text:
                raise ValueError(f'Empty response from {prov}')
            track_llm_usage(
                resp=resp,
                feature=resolved_feature,
                provider=prov,
                model_name=used_model,
                duration_ms=timer.elapsed_ms,
            )
            return LlmResult(text=text, provider=prov, model=used_model)
        except Exception as exc:
            err_msg = str(exc)
            if "SSL" in err_msg or "EOF" in err_msg or "ConnectError" in err_msg:
                print(f"[CHATBOT][RETRY] {prov} encountered connection issue: {err_msg}. Retrying...")
            raise

    if provider != 'avalai' and gemini_client is not None:
        try:
            return _call_llm(gemini_client, 'gemini')
        except Exception as exc:
            print(f"[CHATBOT][LLM] gemini failed model={used_model!r} after retries: {type(exc).__name__}: {exc}")
            track_llm_error(
                feature=resolved_feature,
                provider='gemini',
                model_name=used_model,
                error_message=str(exc),
            )
            last_error = exc

    if provider != 'gemini' and avalai_client is not None:
        try:
            return _call_llm(avalai_client, 'avalai')
        except Exception as exc:
            print(f"[CHATBOT][LLM] avalai failed model={used_model!r} after retries: {type(exc).__name__}: {exc}")
            track_llm_error(
                feature=resolved_feature,
                provider='avalai',
                model_name=used_model,
                error_message=str(exc),
            )
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')


def _repair_json_with_llm(*, feature: str, model_output: str) -> dict[str, Any]:
    template = PROMPTS['json_repair']['default']
    prompt = _safe_template_replace(
        template,
        {
            'feature': feature,
            'schema_hint': _schema_hint_for_feature(feature),
            'raw_text': model_output,
        },
    )
    repaired = generate_text(contents=prompt, feature=LLMUsageLog.Feature.JSON_REPAIR).text
    try:
        obj = extract_json_object(repaired)
        return obj if isinstance(obj, dict) else {'result': obj}
    except Exception as exc:
        print(f"[CHATBOT][LLM] json_repair failed feature={feature!r}: {type(exc).__name__}: {exc}")
        return {}


def generate_json(*, feature: str, contents: Any) -> dict[str, Any]:
    """Generate JSON via the LLM; uses `json_repair` prompt if needed."""

    set_llm_feature(feature)
    out = generate_text(contents=contents, feature=feature).text
    if not (out or '').strip():
        return _repair_json_with_llm(feature=feature, model_output=out)
    try:
        obj = extract_json_object(out)
        return obj if isinstance(obj, dict) else {'result': obj}
    except Exception:
        return _repair_json_with_llm(feature=feature, model_output=out)


def part_from_bytes(*, data: bytes, mime_type: str) -> types.Part:
    return types.Part.from_bytes(data=data, mime_type=mime_type)
