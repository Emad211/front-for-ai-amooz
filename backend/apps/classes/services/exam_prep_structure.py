"""
Service for extracting exam prep Q&A structure from transcript markdown.

Rewritten to use the unified LLM client (GapGPT / OpenAI SDK)
via apps.commons.services.llm_client.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Tuple

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.chatbot.services.llm_client import generate_text
from .json_utils import extract_json_object

logger = logging.getLogger(__name__)

# Per-call timeout for LLM (seconds).
_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model(*names: str) -> str:
    """Select the LLM model from ENV only — no hardcoded defaults.

    Checks each of ``names`` in order, then falls back to ``MODEL_NAME``. If
    nothing is set, raises (a misconfigured deployment must fail loudly rather
    than silently calling a hardcoded model). Mirrors ``structure.py._select_model``.
    """
    for n in names:
        val = _get_env(n)
        if val:
            return val

    fallback = _get_env("MODEL_NAME")
    if fallback:
        return fallback

    raise RuntimeError(
        f"No LLM model defined in ENV. Checked: {names} and fallback MODEL_NAME."
    )


def _restore_latex_escapes(value: Any) -> Any:
    """Restore LaTeX commands inside JSON strings."""
    replacement_map = {
        "\t": "\\t",
        "\b": "\\b",
        "\f": "\\f",
        "\n": "\\n",
        "\r": "\\r",
    }
    if isinstance(value, str):
        for ctrl, esc in replacement_map.items():
            value = value.replace(ctrl, esc)
        return value
    if isinstance(value, dict):
        return {k: _restore_latex_escapes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_restore_latex_escapes(item) for item in value]
    return value


def _reinject_exam_assets(parsed: dict, transcript_markdown: str) -> dict:
    """Guarantee no extracted image is lost from the exam Q&A.

    The prompt asks the model to keep `![](url)` images verbatim, but we do not
    rely on it. If the transcript contains image URLs absent from the entire
    serialized exam JSON, append them to the last question's solution so they
    still reach the student. Conservative: only acts when an image would be lost.
    """
    import json as _json
    from .markdown_assets import image_refs, image_urls

    try:
        refs = image_refs(transcript_markdown)
        if not refs:
            return parsed
        blob = _json.dumps(parsed, ensure_ascii=False)
        present = set(image_urls(blob))
        missing = [r for r, u in zip(refs, image_urls(transcript_markdown)) if u not in present]
        if not missing:
            return parsed
        questions = (parsed.get("exam_prep") or {}).get("questions") or []
        if questions and isinstance(questions[-1], dict):
            sol = questions[-1].get("teacher_solution_markdown") or ""
            questions[-1]["teacher_solution_markdown"] = (
                sol.rstrip() + "\n\n" + "\n\n".join(missing)
            ).strip()
    except Exception:
        logger.exception("exam asset reinjection failed; returning as-is")
    return parsed


def _attempt_parse_with_repair(*, text: str) -> tuple[Optional[dict], Optional[str]]:
    """
    Try to parse JSON; return (parsed_json, preview_on_error).
    """
    try:
        return extract_json_object(text), None
    except Exception as exc:
        preview = (text or "")[:1200]
        return None, preview


def extract_exam_prep_structure(
    *, transcript_markdown: str
) -> tuple[dict[str, Any], str, str]:
    """
    Extract exam prep Q&A structure from transcript markdown.

    Returns:
        (exam_prep_json_obj, provider, model_name)
    """

    # Select model from ENV only (raises if unset — no hardcoded default).
    model = _select_model("STRUCTURE_MODEL", "REWRITE_MODEL")

    provider = preferred_provider()

    prompt = PROMPTS["exam_prep_structure"]["default"]

    base_messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": f"FULL_TRANSCRIPT_MARKDOWN:\n{transcript_markdown}",
        },
    ]

    # --------------------------------------------------------------
    # Attempt 1 — normal run
    # --------------------------------------------------------------
    try:
        resp = generate_text(
            model=model,
            messages=base_messages,
            timeout=_LLM_TIMEOUT_SECONDS,
            feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
        )
    except Exception as exc:
        raise RuntimeError(f"LLM call failed: {exc}") from exc

    text = resp.text if hasattr(resp, "text") else str(resp)
    parsed, preview = _attempt_parse_with_repair(text=text)

    if parsed is not None:
        parsed = _reinject_exam_assets(parsed, transcript_markdown)
        return _restore_latex_escapes(parsed), provider, model

    # --------------------------------------------------------------
    # Attempts 2..4 — JSON repair
    # --------------------------------------------------------------
    repair_systems = [
        "خروجی قبلی قرار بوده یک JSON معتبر باشد ولی قابل parse نیست. "
        "لطفاً فقط یک JSON معتبر بده. بدون توضیح، بدون ```.",
        "ONLY OUTPUT VALID JSON. No prose. Escape all backslashes inside strings.",
        "Return STRICT JSON ONLY. If any field breaks JSON, replace with safe string.",
    ]

    last_preview = preview
    last_error = None

    for i, repair_sys in enumerate(repair_systems, start=2):
        repair_messages = [
            {"role": "system", "content": repair_sys},
            {
                "role": "user",
                "content": f"INVALID_OUTPUT:\n{text or ''}",
            },
        ]

        try:
            repair_resp = generate_text(
                model=model,
                messages=repair_messages,
                timeout=_LLM_TIMEOUT_SECONDS,
                feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
            )
            repair_text = repair_resp.text
        except Exception as exc:
            last_error = exc
            continue

        parsed, preview = _attempt_parse_with_repair(text=repair_text)
        if parsed is not None:
            parsed = _reinject_exam_assets(parsed, transcript_markdown)
            return _restore_latex_escapes(parsed), provider, model

        text = repair_text
        last_preview = preview

    raise RuntimeError(
        f"LLM returned invalid JSON for exam prep structure. last_preview={last_preview!r}, last_error={last_error}"
    )
