from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from google import genai

from apps.commons.llm_prompts import PROMPTS

from .json_utils import extract_json_object


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


def structure_transcript_markdown(*, transcript_markdown: str) -> tuple[dict[str, Any], str, str]:
    """Return (structure_json_obj, provider, model_name)."""

    model = _get_env('STRUCTURE_MODEL') or _get_env('REWRITE_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'models/gemini-2.5-flash'

    prompt = PROMPTS['structure_content']['default']

    contents = [prompt, f"FULL_TRANSCRIPT_MARKDOWN:\n{transcript_markdown}"]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    if gemini_client is not None:
        try:
            resp = gemini_client.models.generate_content(model=model, contents=contents)
            txt = _extract_text(resp)
            obj = extract_json_object(txt)
            obj = _restore_latex_escapes(obj)
            return obj, 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            resp = avalai_client.models.generate_content(model=model, contents=contents)
            txt = _extract_text(resp)
            obj = extract_json_object(txt)
            obj = _restore_latex_escapes(obj)
            return obj, 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')


def _restore_latex_escapes(value: Any) -> Any:
    """Repair LaTeX commands inside JSON strings.

    LLMs often emit JSON strings containing LaTeX like "\text{...}".
    In JSON, sequences like \t, \b, \f are parsed into control characters
    (TAB, BACKSPACE, FORMFEED), causing "\text" -> "<TAB>ext".
    This traverses the parsed object and restores those characters back into
    backslash sequences so KaTeX can render properly.
    """

    if isinstance(value, str):
        return value.replace('\t', '\\t').replace('\b', '\\b').replace('\f', '\\f')

    if isinstance(value, list):
        return [_restore_latex_escapes(v) for v in value]

    if isinstance(value, dict):
        return {k: _restore_latex_escapes(v) for k, v in value.items()}

    return value
