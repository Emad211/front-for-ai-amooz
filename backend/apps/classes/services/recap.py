from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from google import genai

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.token_tracker import tracked_generate_content


def _get_env(name: str) -> str:
    return (os.getenv(name) or '').strip()


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


def _safe_json_from_llm(text: str) -> dict[str, Any]:
    from apps.classes.services.json_utils import extract_json_object

    obj = extract_json_object(text)
    if isinstance(obj, dict):
        return obj
    return {'recap': obj}


def generate_recap_from_structure(*, structure_json: str) -> tuple[dict[str, Any], str, str]:
    model = (
        _get_env('RECAP_MODEL')
        or _get_env('STRUCTURE_MODEL')
        or _get_env('REWRITE_MODEL')
        or _get_env('MODEL_NAME')
    )
    if not model:
        model = 'models/gemini-2.5-flash'

    prompt = PROMPTS['recap_and_notes']['default']
    contents = [prompt, f"COURSE_STRUCTURE_JSON:\n{structure_json}"]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    if gemini_client is not None:
        try:
            resp = tracked_generate_content(gemini_client, model=model, contents=contents, feature=LLMUsageLog.Feature.RECAP, provider='gemini')
            return _safe_json_from_llm(_extract_text(resp)), 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            resp = tracked_generate_content(avalai_client, model=model, contents=contents, feature=LLMUsageLog.Feature.RECAP, provider='avalai')
            return _safe_json_from_llm(_extract_text(resp)), 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')


def recap_json_to_markdown(recap_obj: dict[str, Any]) -> str:
    recap = recap_obj.get('recap') if isinstance(recap_obj, dict) else None
    if not isinstance(recap, dict):
        return ''

    title = str(recap.get('title') or '').strip()
    overview = str(recap.get('overview_markdown') or '').strip()
    key_notes = str(recap.get('key_notes_markdown') or '').strip()
    common_mistakes = str(recap.get('common_mistakes_markdown') or '').strip()
    quick_self_check = str(recap.get('quick_self_check_markdown') or '').strip()
    formula_sheet = str(recap.get('formula_sheet_markdown') or '').strip()

    parts: list[str] = []
    if title:
        parts.append(f"# {title}")

    if overview:
        parts.append("## جمع‌بندی کوتاه")
        parts.append(overview)

    if key_notes:
        parts.append("## نکات کلیدی")
        parts.append(key_notes)

    by_unit = recap.get('by_unit')
    if isinstance(by_unit, list) and by_unit:
        parts.append("## مرور بر اساس درس‌ها")
        for item in by_unit:
            if not isinstance(item, dict):
                continue
            section_title = str(item.get('section_title') or '').strip()
            unit_title = str(item.get('unit_title') or '').strip()
            unit_recap = str(item.get('unit_recap_markdown') or '').strip()
            unit_points = str(item.get('unit_key_points_markdown') or '').strip()

            heading = unit_title
            if section_title:
                heading = f"{section_title} — {unit_title}" if unit_title else section_title

            if heading:
                parts.append(f"### {heading}")
            if unit_recap:
                parts.append(unit_recap)
            if unit_points:
                parts.append(unit_points)

    if common_mistakes:
        parts.append("## اشتباهات رایج")
        parts.append(common_mistakes)

    if quick_self_check:
        parts.append("## خودسنجی سریع")
        parts.append(quick_self_check)

    if formula_sheet:
        parts.append("## برگه فرمول‌ها")
        parts.append(formula_sheet)

    return "\n\n".join([p for p in parts if str(p).strip()]).strip()
