from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional, Tuple

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.classes.services.media_compressor import prepare_media_parts_for_api

logger = logging.getLogger(__name__)

# Per-call timeout for LLM generate_content (seconds).
# Large video transcription can take a while, but we don't want to block forever.
# Default httpx timeout is only 5s — way too short for multi-MB video uploads.
_LLM_TIMEOUT_SECONDS = int(os.getenv('LLM_TIMEOUT_SECONDS', '60000000'))


def _get_env(name: str) -> str:
    value = (os.getenv(name) or '').strip()
    return value


def _get_clients() -> Tuple[Optional[genai.Client], Optional[genai.Client]]:
    gemini_api_key = _get_env('GEMINI_API_KEY')
    avalai_api_key = _get_env('AVALAI_API_KEY')
    avalai_base_url = _get_env('AVALAI_BASE_URL')

    provider = preferred_provider()
    logger.info(
        'LLM client init: provider=%s gemini_key=%s avalai_key=%s avalai_url=%s',
        provider,
        'set' if gemini_api_key else 'MISSING',
        'set' if avalai_api_key else 'MISSING',
        avalai_base_url or 'DEFAULT',
    )

    # Generous timeout for large video uploads to external APIs.
    # Default httpx timeout is only 5s which is too short for multi-MB uploads.
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
        logger.info('AvalAI client created with base_url=%s timeout=%ds', avalai_base_url, _LLM_TIMEOUT_SECONDS)

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


def transcribe_media_bytes(*, data: bytes, mime_type: str) -> tuple[str, str, str]:
    """Return (transcript_markdown, provider, model_name).

    If the input media exceeds API payload limits, it will be compressed and split
    into multiple video parts (never audio-only) before sending to the API.
    """
    original_size = len(data)
    media_parts = prepare_media_parts_for_api(data, mime_type)
    logger.info(
        'Prepared %d media part(s) for transcription (original=%d bytes)',
        len(media_parts),
        original_size,
    )
    
    model = _get_env('TRANSCRIPTION_MODEL') or _get_env('MODEL_NAME')
    if not model:
        model = 'models/gemini-2.5-flash'

    gemini_client, avalai_client = _get_clients()

    last_error: Optional[Exception] = None

    base_prompt = PROMPTS['transcribe_media']['default']

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _transcribe_with_client(client: genai.Client, provider_name: str) -> tuple[str, str, str]:
        texts: list[str] = []
        total = len(media_parts)

        for idx, (part_bytes, part_mime) in enumerate(media_parts, start=1):
            if total == 1:
                prompt = base_prompt
            else:
                prompt = (
                    base_prompt
                    + "\n\n---\n"
                    + f"این فایل بخش {idx} از {total} یک ویدیوی طولانی است. "
                    + "فقط محتوای همین بخش را ترنسکریپت کن و از تکرار بخش‌های قبلی خودداری کن. "
                    + "خروجی را به صورت Markdown بده."
                )

            media_part = types.Part.from_bytes(data=part_bytes, mime_type=part_mime)
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[prompt, media_part],
                    config=types.GenerateContentConfig(
                        # google-genai SDK expects timeout in MILLISECONDS
                        http_options={'timeout': _LLM_TIMEOUT_SECONDS * 1000},
                    ),
                )
                texts.append(_extract_text(resp))
            except Exception as e:
                logger.error(f"Transcription error with {provider_name} (part {idx}/{total}): {str(e)}")
                raise

        if len(texts) == 1:
            transcript = texts[0]
        else:
            transcript = "\n\n".join(
                [f"## Part {i + 1}/{len(texts)}\n\n{texts[i]}" for i in range(len(texts))]
            )

        return transcript, provider_name, model

    if gemini_client is not None:
        try:
            return _transcribe_with_client(gemini_client, 'gemini')
        except Exception as exc:
            last_error = exc

    if avalai_client is not None:
        try:
            return _transcribe_with_client(avalai_client, 'avalai')
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError('No LLM credentials configured. Set GEMINI_API_KEY and/or AVALAI_API_KEY.')
