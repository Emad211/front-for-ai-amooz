from __future__ import annotations

import logging
import os
from typing import Any, Tuple

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.chatbot.services.llm_client import generate_text

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model(*names: str) -> str:
    for n in names:
        val = _get_env(n)
        if val:
            return val

    fallback = _get_env("MODEL_NAME")
    if fallback:
        return fallback

    raise RuntimeError(
        f"No LLM model found in ENV. Checked: {names} and fallback MODEL_NAME"
    )


def _render_prompt(template: str, **values: Any) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def _call_llm(
    *,
    model: str,
    prompt: str,
    feature: LLMUsageLog.Feature,
) -> str:

    messages = [
        {"role": "user", "content": prompt},
    ]

    resp = generate_text(
        model=model,
        messages=messages,
        timeout=_LLM_TIMEOUT_SECONDS,
        feature=feature,
    )

    text = resp.text if hasattr(resp, "text") else str(resp)
    return text.strip()


def _safe_json_from_llm(text: str) -> dict[str, Any]:
    from apps.classes.services.json_utils import extract_json_object

    obj = extract_json_object(text)

    if isinstance(obj, dict):
        return obj

    return {"recap": obj}


def generate_recap_from_structure(*, structure_json: str) -> Tuple[dict[str, Any], str, str]:

    model = _select_model(
        "RECAP_MODEL",
        "STRUCTURE_MODEL",
        "REWRITE_MODEL",
    )

    provider = preferred_provider()

    base_prompt = PROMPTS["recap_and_notes"]["default"]

    prompt = _render_prompt(
        base_prompt,
        structure_json=structure_json,
    )

    full_prompt = f"{prompt}\n\nCOURSE_STRUCTURE_JSON:\n{structure_json}"

    try:
        text = _call_llm(
            model=model,
            prompt=full_prompt,
            feature=LLMUsageLog.Feature.RECAP,
        )

        obj = _safe_json_from_llm(text)

        return obj, provider, model

    except Exception as exc:
        logger.exception("Recap generation failed")
        raise RuntimeError(f"Recap generation failed: {exc}") from exc


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
