from __future__ import annotations

import base64
import logging
import os
from typing import Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.services.llm_client import generate_text
from apps.classes.services.media_compressor import prepare_media_parts_for_api

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


# -------------------------------------------------------------------
# ENV helpers
# -------------------------------------------------------------------

def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model() -> str:
    """
    Model selection (ENV only).
    """
    model = _get_env("TRANSCRIPTION_MODEL") or _get_env("MODEL_NAME")
    if model:
        return model

    raise RuntimeError(
        "No transcription model defined. Set TRANSCRIPTION_MODEL or MODEL_NAME."
    )


# -------------------------------------------------------------------
# Central LLM caller
# -------------------------------------------------------------------

def _call_llm(
    *,
    model: str,
    prompt: str,
    media_bytes: bytes,
    mime_type: str,
    detail: str,
) -> str:

    media_b64 = base64.b64encode(media_bytes).decode()

    resp = generate_text(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "attachments": [
                    {
                        "type": "input_media",
                        "mime_type": mime_type,
                        "data_base64": media_b64,
                    }
                ],
            }
        ],
        timeout=_LLM_TIMEOUT_SECONDS,
        feature=LLMUsageLog.Feature.TRANSCRIPTION,
        detail=detail,
    )

    text = resp.text if hasattr(resp, "text") else str(resp)
    return text.strip()


# -------------------------------------------------------------------
# Main Transcription
# -------------------------------------------------------------------

def transcribe_media_bytes(*, data: bytes, mime_type: str) -> Tuple[str, str, str]:
    """
    Return (transcript_markdown, provider, model_name)

    If media is too large it will be compressed/split into multiple parts.
    """

    original_size = len(data)

    media_parts = prepare_media_parts_for_api(data, mime_type)

    logger.info(
        "Prepared %d media part(s) for transcription (original=%d bytes)",
        len(media_parts),
        original_size,
    )

    model = _select_model()
    provider = preferred_provider()

    base_prompt = PROMPTS["transcribe_media"]["default"]

    total = len(media_parts)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _transcribe_part(idx: int, part_bytes: bytes, part_mime: str) -> str:

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

        try:
            return _call_llm(
                model=model,
                prompt=prompt,
                media_bytes=part_bytes,
                mime_type=part_mime,
                detail=f"part {idx}/{total}",
            )
        except Exception as e:
            logger.error(
                "Transcription error (%s part %d/%d): %s",
                provider,
                idx,
                total,
                str(e),
            )
            raise

    texts: list[str] = []

    for idx, (part_bytes, part_mime) in enumerate(media_parts, start=1):
        texts.append(_transcribe_part(idx, part_bytes, part_mime))

    if len(texts) == 1:
        transcript = texts[0]
    else:
        transcript = "\n\n".join(
            [f"## Part {i+1}/{len(texts)}\n\n{texts[i]}" for i in range(len(texts))]
        )

    return transcript, provider, model
