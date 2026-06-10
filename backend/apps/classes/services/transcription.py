from __future__ import annotations

import base64
import logging
import os
from typing import Tuple

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.chatbot.services.llm_client import generate_text

from .transcription_media import (
    extract_audio_mp3,
    extract_frames_jpeg,
    extract_audio_mp3_from_path,
    extract_frames_jpeg_from_path,
)

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


# -------------------------------------------------------------------
# ENV helpers
# -------------------------------------------------------------------

def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model() -> str:
    """Model selection (ENV only)."""
    model = _get_env("TRANSCRIPTION_MODEL") or _get_env("MODEL_NAME")
    if model:
        return model
    raise RuntimeError(
        "No transcription model defined. Set TRANSCRIPTION_MODEL or MODEL_NAME."
    )


# -------------------------------------------------------------------
# Standard OpenAI multimodal message shape
# -------------------------------------------------------------------
#
# The Avalai gateway (OpenAI-compatible) ONLY understands the standard content
# shapes — `image_url` for images and `input_audio` for audio. The legacy
# `attachments: [{type: input_media, data_base64}]` shape this module used to send
# was silently ignored by the gateway (hallucinated/empty transcripts; large
# payloads also surfaced as `SSL: UNEXPECTED_EOF_WHILE_READING`). See
# AvalAI-Developer-Documentation.md.

def _build_transcription_messages(
    *,
    prompt: str,
    audio_b64: str,
    audio_format: str,
    frames_b64: list[str],
    image_format: str = "jpeg",
) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": prompt}]
    if audio_b64:
        content.append(
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_format}}
        )
    for fb in frames_b64:
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/{image_format};base64,{fb}"}}
        )
    return [{"role": "user", "content": content}]


def _call_llm(*, model: str, messages: list[dict], detail: str) -> str:
    resp = generate_text(
        model=model,
        messages=messages,
        timeout=_LLM_TIMEOUT_SECONDS,  # now actually honoured by the client
        feature=LLMUsageLog.Feature.TRANSCRIPTION,
    )
    text = resp.text if hasattr(resp, "text") else str(resp)
    return (text or "").strip()


# -------------------------------------------------------------------
# Main Transcription
# -------------------------------------------------------------------

def _run_transcription(*, model: str, provider: str, messages: list[dict]) -> str:
    """Call the LLM with retry/backoff and return the transcript text.

    Shared by the bytes- and path-based entry points so they behave identically.
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _do_call() -> str:
        try:
            return _call_llm(model=model, messages=messages, detail="single")
        except Exception as e:
            logger.error("Transcription error with %s: %s", provider, str(e))
            raise

    return _do_call()


def transcribe_media_bytes(*, data: bytes, mime_type: str) -> Tuple[str, str, str]:
    """Transcribe in-memory lecture media; return (transcript_markdown, provider, model).

    Kept for callers that already hold the bytes (small audio chat uploads, the
    synchronous request path, tests). The memory-heavy Celery pipeline uses
    :func:`transcribe_media_file` so a large video is never resident in RAM.

    Video -> audio (mp3, input_audio) + sampled frames (jpeg, image_url).
    Audio -> normalised mp3 (input_audio) only.
    """
    model = _select_model()
    provider = preferred_provider()
    base_prompt = PROMPTS["transcribe_media"]["default"]

    is_audio = (mime_type or "").lower().startswith("audio/")

    # Extract audio track (mp3) for everything; extract frames only for video.
    audio_bytes, audio_format = extract_audio_mp3(data, mime_type)
    audio_b64 = base64.b64encode(audio_bytes).decode()

    frames_b64: list[str] = []
    if not is_audio:
        try:
            frames = extract_frames_jpeg(data, mime_type)
            frames_b64 = [base64.b64encode(f).decode() for f in frames]
        except Exception:
            # Visual frames are a bonus; never fail transcription if they error.
            logger.exception("frame extraction failed; proceeding audio-only")

    messages = _build_transcription_messages(
        prompt=base_prompt,
        audio_b64=audio_b64,
        audio_format=audio_format,
        frames_b64=frames_b64,
    )

    logger.info(
        "TRANSCRIBE start: model=%s is_audio=%s audio_bytes=%d frames=%d",
        model, is_audio, len(audio_bytes), len(frames_b64),
    )
    return _run_transcription(model=model, provider=provider, messages=messages), provider, model


def transcribe_media_file(*, path: str, mime_type: str) -> Tuple[str, str, str]:
    """Transcribe lecture media from an on-disk file path (memory-safe).

    Identical output contract to :func:`transcribe_media_bytes`, but ffmpeg reads
    the file directly so the full video is NEVER materialized in worker RAM — this
    is the path used by the Celery pipeline to avoid OOM-killing the worker pod
    during frame extraction.
    """
    model = _select_model()
    provider = preferred_provider()
    base_prompt = PROMPTS["transcribe_media"]["default"]

    is_audio = (mime_type or "").lower().startswith("audio/")

    audio_bytes, audio_format = extract_audio_mp3_from_path(path)
    audio_b64 = base64.b64encode(audio_bytes).decode()
    del audio_bytes  # free the raw audio before frame extraction

    frames_b64: list[str] = []
    if not is_audio:
        try:
            for frame in extract_frames_jpeg_from_path(path):
                frames_b64.append(base64.b64encode(frame).decode())
        except Exception:
            # Visual frames are a bonus; never fail transcription if they error.
            logger.exception("frame extraction failed; proceeding audio-only")

    messages = _build_transcription_messages(
        prompt=base_prompt,
        audio_b64=audio_b64,
        audio_format=audio_format,
        frames_b64=frames_b64,
    )

    logger.info(
        "TRANSCRIBE(file) start: model=%s is_audio=%s frames=%d",
        model, is_audio, len(frames_b64),
    )
    return _run_transcription(model=model, provider=provider, messages=messages), provider, model
