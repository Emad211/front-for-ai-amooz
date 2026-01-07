from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from google import genai
from google.genai import types

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider


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


def generate_text(*, contents: Any, model: Optional[str] = None) -> LlmResult:
    used_model = model or _default_model()
    gemini_client, avalai_client = _get_clients()

    provider = preferred_provider()

    last_error: Optional[Exception] = None

    if provider != 'avalai' and gemini_client is not None:
        try:
            resp = gemini_client.models.generate_content(model=used_model, contents=contents)
            text = _extract_text(resp)
            if not text:
                raise ValueError('Empty response from gemini')
            return LlmResult(text=text, provider='gemini', model=used_model)
        except Exception as exc:
            print(f"[CHATBOT][LLM] gemini failed model={used_model!r}: {type(exc).__name__}: {exc}")
            last_error = exc

    if provider != 'gemini' and avalai_client is not None:
        try:
            resp = avalai_client.models.generate_content(model=used_model, contents=contents)
            text = _extract_text(resp)
            if not text:
                raise ValueError('Empty response from avalai')
            return LlmResult(text=text, provider='avalai', model=used_model)
        except Exception as exc:
            print(f"[CHATBOT][LLM] avalai failed model={used_model!r}: {type(exc).__name__}: {exc}")
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
    repaired = generate_text(contents=prompt).text
    try:
        return json.loads(repaired)
    except Exception as exc:
        print(f"[CHATBOT][LLM] json_repair failed feature={feature!r}: {type(exc).__name__}: {exc}")
        return {}


def generate_json(*, feature: str, contents: Any) -> dict[str, Any]:
    """Generate JSON via the LLM; uses `json_repair` prompt if needed."""

    out = generate_text(contents=contents).text
    if not (out or '').strip():
        return _repair_json_with_llm(feature=feature, model_output=out)
    try:
        return json.loads(out)
    except Exception:
        return _repair_json_with_llm(feature=feature, model_output=out)


def part_from_bytes(*, data: bytes, mime_type: str) -> types.Part:
    return types.Part.from_bytes(data=data, mime_type=mime_type)
