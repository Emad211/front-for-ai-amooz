"""
Service for extracting exam prep Q&A structure from transcript markdown.

Uses the 'exam_prep_structure' prompt to convert instructor problem-solving
transcripts into structured Q&A JSON format.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Tuple

from google import genai
from google.genai import types

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.token_tracker import tracked_generate_content

from .json_utils import extract_json_object

logger = logging.getLogger(__name__)

# Per-call timeout for LLM generate_content (seconds).
# Default httpx timeout is only 5s — too short for larger payloads.
_LLM_TIMEOUT_SECONDS = int(os.getenv('LLM_TIMEOUT_SECONDS', '600'))


def _get_env(name: str) -> str:
    return (os.getenv(name) or '').strip()


def _get_clients() -> Tuple[Optional[genai.Client], Optional[genai.Client]]:
    """Initialize Gemini and/or AvalAI clients based on env config."""
    gemini_api_key = _get_env('GEMINI_API_KEY')
    avalai_api_key = _get_env('AVALAI_API_KEY')
    avalai_base_url = _get_env('AVALAI_BASE_URL')

    provider = preferred_provider()
    logger.info(
        'Exam prep LLM init: provider=%s gemini_key=%s avalai_key=%s avalai_url=%s',
        provider,
        'set' if gemini_api_key else 'MISSING',
        'set' if avalai_api_key else 'MISSING',
        avalai_base_url or 'DEFAULT',
    )

    _client_timeout_ms = _LLM_TIMEOUT_SECONDS * 1000

    gemini_client = None
    if gemini_api_key and provider != 'avalai':
        gemini_client = genai.Client(
            api_key=gemini_api_key,
            http_options={'timeout': _client_timeout_ms},
        )

    avalai_client: Optional[genai.Client] = None
    if avalai_api_key and provider != 'gemini':
        avalai_http: dict = {'timeout': _client_timeout_ms}
        if avalai_base_url:
            avalai_http['base_url'] = avalai_base_url
        avalai_client = genai.Client(api_key=avalai_api_key, http_options=avalai_http)
        logger.info('Exam prep AvalAI client created with base_url=%s timeout=%ds', avalai_base_url, _LLM_TIMEOUT_SECONDS)

    return gemini_client, avalai_client


def _extract_text(resp: Any) -> str:
    """Extract text from LLM response (Gemini or AvalAI)."""
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


def _restore_latex_escapes(value: Any) -> Any:
    """Repair LaTeX commands inside JSON strings.

    LLMs often emit JSON strings containing LaTeX like "\\text{...}".
    In JSON, sequences like \\t, \\b, \\f are parsed into control characters
    (TAB, BACKSPACE, FORMFEED), causing "\\text" -> "<TAB>ext".
    This traverses the parsed object and restores those characters back into
    their escaped LaTeX forms.
    """
    replacement_map = {
        '\t': '\\t',
        '\b': '\\b',
        '\f': '\\f',
        '\n': '\\n',
        '\r': '\\r',
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


def extract_exam_prep_structure(*, transcript_markdown: str) -> tuple[dict[str, Any], str, str]:
    """
    Extract exam prep Q&A structure from transcript markdown.

    Args:
        transcript_markdown: Raw transcript of instructor solving problems.

    Returns:
        Tuple of (exam_prep_json_obj, provider, model_name).

    Raises:
        RuntimeError: If no LLM credentials are configured.
    """
    model = _get_env('STRUCTURE_MODEL') or _get_env('REWRITE_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'models/gemini-2.5-flash'

    prompt = PROMPTS['exam_prep_structure']['default']

    contents = [prompt, f"FULL_TRANSCRIPT_MARKDOWN:\n{transcript_markdown}"]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    def _parse_with_repair(*, client: genai.Client, _provider_name: str) -> dict[str, Any]:
        """Parse JSON from model output with multiple safe retries.

        Goal: Step 2 should not fail due to minor JSON formatting issues.
        We retry a few times with increasingly strict instructions.
        """

        last_exc: Optional[Exception] = None
        last_preview: str = ''

        def _attempt_parse(text: str) -> Optional[dict[str, Any]]:
            nonlocal last_exc, last_preview
            try:
                return extract_json_object(text)
            except Exception as exc:
                last_exc = exc
                last_preview = (text or '')[:1200]
                return None

        # Attempt 1: normal generation
        resp = tracked_generate_content(
            client,
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                # google-genai SDK expects timeout in MILLISECONDS
                http_options={'timeout': _LLM_TIMEOUT_SECONDS * 1000},
            ),
            feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
            provider=_provider_name,
        )
        txt = _extract_text(resp)
        obj = _attempt_parse(txt)
        if obj is not None:
            return obj

        # Attempt 2..4: repair passes (same model), stricter each time
        repair_templates = [
            (
                "خروجی قبلی قرار بوده یک JSON معتبر باشد ولی قابل parse نیست. "
                "لطفاً فقط و فقط یک JSON معتبر برگردان. "
                "هیچ متن اضافی، توضیح، یا ``` نده. "
                "همه بکاسلشها (مثل LaTeX: \\cdot, \\times) را داخل رشتهها درست escape کن. "
                "ساختار/کلیدها را حفظ کن.\n\n"
            ),
            (
                "ONLY OUTPUT VALID JSON. No prose. No markdown. No code fences. "
                "Ensure all backslashes inside JSON strings are escaped (\\\\).\n\n"
            ),
            (
                "Return strict JSON ONLY. If any field would break JSON, replace it with a safe string. "
                "Do not truncate the JSON; it must be complete and parseable.\n\n"
            ),
        ]

        for template in repair_templates:
            repair_contents = [
                "You are a strict JSON repair tool.",
                template + "INVALID_OUTPUT:\n" + (txt or ''),
            ]
            resp2 = tracked_generate_content(
                client,
                model=model,
                contents=repair_contents,
                config=types.GenerateContentConfig(
                    http_options={'timeout': _LLM_TIMEOUT_SECONDS * 1000},
                ),
                feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
                provider=_provider_name,
                detail='json_repair_pass',
            )
            txt2 = _extract_text(resp2)
            obj2 = _attempt_parse(txt2)
            if obj2 is not None:
                return obj2
            txt = txt2

        raise RuntimeError(
            "LLM returned invalid JSON for exam prep structure. "
            f"last_error={last_exc!s}; last_preview={last_preview!r}"
        )

    if gemini_client is not None:
        try:
            obj = _parse_with_repair(client=gemini_client, _provider_name='gemini')
            obj = _restore_latex_escapes(obj)
            return obj, 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            obj = _parse_with_repair(client=avalai_client, _provider_name='avalai')
            obj = _restore_latex_escapes(obj)
            return obj, 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')
