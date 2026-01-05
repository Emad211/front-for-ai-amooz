from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from google import genai

from apps.commons.llm_prompts import PROMPTS


def _get_env(name: str) -> str:
    return (os.getenv(name) or '').strip()


def _get_clients() -> Tuple[Optional[genai.Client], Optional[genai.Client]]:
    gemini_api_key = _get_env('GEMINI_API_KEY')
    avalai_api_key = _get_env('AVALAI_API_KEY')
    avalai_base_url = _get_env('AVALAI_BASE_URL')

    gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

    avalai_client: Optional[genai.Client] = None
    if avalai_api_key:
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


def extract_prerequisites(*, transcript_markdown: str) -> tuple[dict[str, Any], str, str]:
    model = _get_env('PREREQUISITES_MODEL') or _get_env('STRUCTURE_MODEL') or _get_env('REWRITE_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'models/gemini-2.5-flash'

    prompt = PROMPTS['prerequisites_prompt']['default']
    contents = [prompt, f"FULL_TRANSCRIPT_MARKDOWN:\n{transcript_markdown}"]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    if gemini_client is not None:
        try:
            resp = gemini_client.models.generate_content(model=model, contents=contents)
            return _safe_json_from_llm(_extract_text(resp)), 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            resp = avalai_client.models.generate_content(model=model, contents=contents)
            return _safe_json_from_llm(_extract_text(resp)), 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')


def generate_prerequisite_teaching(*, prerequisite_name: str) -> tuple[str, str, str]:
    model = _get_env('PREREQ_TEACHING_MODEL') or _get_env('STRUCTURE_MODEL') or _get_env('REWRITE_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'models/gemini-2.5-flash'

    prompt = PROMPTS['prerequisite_teaching']['default']
    contents = [prompt, f"PREREQUISITE_NAME:\n{prerequisite_name}"]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    if gemini_client is not None:
        try:
            resp = gemini_client.models.generate_content(model=model, contents=contents)
            return _strip_outer_fence(_extract_text(resp)), 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            resp = avalai_client.models.generate_content(model=model, contents=contents)
            return _strip_outer_fence(_extract_text(resp)), 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')


def _strip_outer_fence(text: str) -> str:
    s = (text or '').strip()
    if not s:
        return s

    # Remove a single outer ```...``` wrapper if the model mistakenly included it.
    if s.startswith('```') and s.endswith('```'):
        lines = s.splitlines()
        if len(lines) >= 3:
            return '\n'.join(lines[1:-1]).strip()

    return s


def _safe_json_from_llm(text: str) -> dict[str, Any]:
    from apps.classes.services.json_utils import extract_json_object

    obj = extract_json_object(text)
    if isinstance(obj, dict):
        return obj
    return {'prerequisites': obj}
