from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from google import genai

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider

from .json_utils import extract_json_object


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


def _render_prompt(template: str, **values: Any) -> str:
    """Render a prompt template without interpreting JSON braces.

    We avoid `str.format()` because many prompt templates intentionally contain
    literal JSON objects using `{` / `}` which would be treated as format fields.
    """

    rendered = template
    for key, value in values.items():
        rendered = rendered.replace('{' + key + '}', str(value))
    return rendered


def generate_section_quiz_questions(*, section_content: str, count: int = 5) -> tuple[dict[str, Any], str, str]:
    """Return (quiz_obj, provider, model_name).

    quiz_obj schema comes from PROMPTS['section_quiz'].
    """

    model = _get_env('QUIZ_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'models/gemini-2.5-flash'

    prompt = _render_prompt(
        PROMPTS['section_quiz']['default'],
        count=count,
        section_content=section_content,
    )
    contents = [prompt]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    if gemini_client is not None:
        try:
            resp = gemini_client.models.generate_content(model=model, contents=contents)
            obj = extract_json_object(_extract_text(resp))
            if isinstance(obj, dict):
                return obj, 'gemini', model
            return {'questions': obj}, 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            resp = avalai_client.models.generate_content(model=model, contents=contents)
            obj = extract_json_object(_extract_text(resp))
            if isinstance(obj, dict):
                return obj, 'avalai', model
            return {'questions': obj}, 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')


def grade_open_text_answer(*, question: str, reference_answer: str, student_answer: str) -> tuple[dict[str, Any], str, str]:
    """Grade an open-ended answer using PROMPTS['text_grading']."""

    model = _get_env('GRADING_MODEL') or _get_env('QUIZ_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'models/gemini-2.5-flash'

    prompt = _render_prompt(
        PROMPTS['text_grading']['default'],
        question=question,
        reference_answer=reference_answer,
        student_answer=student_answer,
    )
    contents = [prompt]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    if gemini_client is not None:
        try:
            resp = gemini_client.models.generate_content(model=model, contents=contents)
            obj = extract_json_object(_extract_text(resp))
            if isinstance(obj, dict):
                return obj, 'gemini', model
            return {'result': obj}, 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            resp = avalai_client.models.generate_content(model=model, contents=contents)
            obj = extract_json_object(_extract_text(resp))
            if isinstance(obj, dict):
                return obj, 'avalai', model
            return {'result': obj}, 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')


def generate_final_exam_pool(*, combined_content: str, pool_size: int = 12) -> tuple[dict[str, Any], str, str]:
    """Return (exam_obj, provider, model_name).

    exam_obj schema comes from PROMPTS['final_exam_pool'].
    """

    model = _get_env('FINAL_EXAM_MODEL') or _get_env('QUIZ_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'models/gemini-2.5-flash'

    prompt = _render_prompt(
        PROMPTS['final_exam_pool']['default'],
        pool_size=pool_size,
        combined_content=combined_content,
    )
    contents = [prompt]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    if gemini_client is not None:
        try:
            resp = gemini_client.models.generate_content(model=model, contents=contents)
            obj = extract_json_object(_extract_text(resp))
            if isinstance(obj, dict):
                return obj, 'gemini', model
            return {'questions': obj}, 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            resp = avalai_client.models.generate_content(model=model, contents=contents)
            obj = extract_json_object(_extract_text(resp))
            if isinstance(obj, dict):
                return obj, 'avalai', model
            return {'questions': obj}, 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')


# ---------------------------------------------------------------------------
# Hint generation for per-question feedback (exam prep)
# ---------------------------------------------------------------------------

def generate_answer_hint(
    *,
    question: str,
    reference_answer: str,
    student_answer: str,
    attempt_number: int = 1,
) -> tuple[dict[str, Any], str, str]:
    """Return (hint_obj, provider, model_name).

    hint_obj schema: {"hint": str, "encouragement": str}
    Uses the 'exam_prep_hint' prompt template.
    """

    model = _get_env('HINT_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'gemini-2.0-flash-lite'

    prompt = _render_prompt(
        PROMPTS['exam_prep_hint']['default'],
        question=question,
        reference_answer=reference_answer,
        student_answer=student_answer,
        attempt_number=attempt_number,
    )
    contents = [prompt]

    gemini_client, avalai_client = _get_clients()
    last_error: Optional[Exception] = None

    if gemini_client is not None:
        try:
            resp = gemini_client.models.generate_content(model=model, contents=contents)
            obj = extract_json_object(_extract_text(resp))
            if not isinstance(obj, dict):
                obj = {'hint': str(obj), 'encouragement': ''}
            return obj, 'gemini', model
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            resp = avalai_client.models.generate_content(model=model, contents=contents)
            obj = extract_json_object(_extract_text(resp))
            if not isinstance(obj, dict):
                obj = {'hint': str(obj), 'encouragement': ''}
            return obj, 'avalai', model
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')
