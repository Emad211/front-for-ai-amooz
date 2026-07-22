from __future__ import annotations

import base64
import logging
import os
import tempfile
from typing import Callable, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

try:
    # billiard ships with celery; raised inside the task when the Celery soft
    # time limit fires. It MUST escape immediately (never be retried) so the
    # task can settle before the hard-limit SIGKILL.
    from billiard.exceptions import SoftTimeLimitExceeded
except Exception:  # pragma: no cover - celery/billiard always present in prod
    class SoftTimeLimitExceeded(BaseException):  # type: ignore[no-redef]
        pass

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.chatbot.services.llm_client import generate_text

from .transcription_media import (
    extract_audio_mp3,
    extract_frames_jpeg,
    extract_audio_mp3_from_path,
    extract_audio_mp3_chunks_from_path,
    extract_frames_jpeg_from_path,
    probe_media_duration,
)
from .text_sanitize import sanitize_llm_markdown

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))

# Trailing characters of the stitched transcript handed to the next chunk's
# prompt so the model continues mid-sentence instead of restarting.
_PREVIOUS_TAIL_CHARS = 800
_FIRST_PART_TAIL = "(این اولین قطعه است — از ابتدای گفتار شروع کنید.)"

# Type of the optional progress hook: ``cb(done_chunks, total_chunks)``.
# Returning ``False`` aborts the transcription (teacher cancelled the
# pipeline); any other return value (incl. None) continues.
ProgressCallback = Callable[[int, int], Optional[bool]]


class TranscriptionAborted(Exception):
    """Transcription stopped early because the progress callback said so.

    Raised between chunks when the caller's ``progress_cb`` returns ``False``
    (e.g. the teacher pressed cancel, or the session row disappeared). The
    Celery task layer maps this to the terminal CANCELLED status — it must NOT
    be retried like a transient LLM/network failure.
    """


# -------------------------------------------------------------------
# ENV helpers
# -------------------------------------------------------------------

def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _chunk_seconds() -> int:
    """Audio segment length for chunked transcription (clamped to sane bounds).

    Default 600 s (10 min): at the 64 kbps mono mp3 the extractor produces this
    is ~4.8 MB of audio (~6.4 MB base64) per request — far below gateway body
    limits, robust over flaky links, and short enough that the model keeps
    verbatim accuracy. The clamp guards against a stray env value (e.g. the
    historical dead knob TRANSCRIBE_CHUNK_SECONDS=20) ever producing hundreds
    of requests or a single giant one.
    """
    return max(120, min(_env_int("TRANSCRIPTION_CHUNK_SECONDS", 600), 1800))


def _max_duration_seconds() -> int:
    """Upper bound on media duration accepted by the pipeline (0 disables).

    Default 4 h — long enough for any real 500 MB lecture, short enough that a
    mis-uploaded 10-hour recording cannot occupy a pipeline worker for a day.
    """
    return max(0, _env_int("TRANSCRIPTION_MAX_DURATION_SECONDS", 4 * 3600))


def _frames_per_chunk() -> int:
    """Frames attached to EACH chunk request (video sources only)."""
    return max(0, min(_env_int("TRANSCRIPTION_FRAMES_PER_CHUNK", 8), 16))


def _notify_progress(progress_cb: ProgressCallback | None, done: int, total: int) -> None:
    """Invoke the progress hook; abort if it returns ``False``.

    Hook *errors* are swallowed (a broken heartbeat must never fail a
    transcription) — only an explicit ``False`` stops the run.
    """
    if progress_cb is None:
        return
    try:
        keep_going = progress_cb(done, total)
    except Exception:
        logger.warning("transcription progress callback raised; continuing", exc_info=True)
        return
    if keep_going is False:
        raise TranscriptionAborted(f"transcription aborted by caller at chunk {done}/{total}")


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
        # Retry transient LLM/network errors, but NEVER the Celery soft-time-
        # limit signal (it fires once; swallowing it means running blind into
        # the hard SIGKILL) and never a cooperative cancellation.
        retry=retry_if_exception(
            lambda e: not isinstance(e, (SoftTimeLimitExceeded, TranscriptionAborted))
        ),
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
    transcript = _run_transcription(model=model, provider=provider, messages=messages)
    return sanitize_llm_markdown(transcript), provider, model


def transcribe_media_file(
    *,
    path: str,
    mime_type: str,
    progress_cb: ProgressCallback | None = None,
) -> Tuple[str, str, str]:
    """Transcribe lecture media from an on-disk file path (memory-safe).

    Identical output contract to :func:`transcribe_media_bytes`, but ffmpeg reads
    the file directly so the full video is NEVER materialized in worker RAM — this
    is the path used by the Celery pipeline to avoid OOM-killing the worker pod
    during frame extraction.

    Long media (anything meaningfully longer than ``TRANSCRIPTION_CHUNK_SECONDS``)
    is transcribed **chunk by chunk**: the audio track is split into sequential
    mp3 segments, each sent as its own small request together with the frames of
    that time window and the tail of the transcript so far. A 2-3 h lecture
    therefore never produces the old single 40-100 MB request (gateway 413 /
    ``SSL: UNEXPECTED_EOF`` / silent output-token truncation) and gets dense,
    time-aligned visual coverage instead of 16 frames total.

    ``progress_cb(done, total)`` is invoked after every chunk; returning
    ``False`` raises :class:`TranscriptionAborted` (used for mid-step cancel and
    the stale-session heartbeat).
    """
    model = _select_model()
    provider = preferred_provider()

    is_audio = (mime_type or "").lower().startswith("audio/")
    duration = probe_media_duration(path)

    max_duration = _max_duration_seconds()
    if max_duration and duration and duration > max_duration:
        raise RuntimeError(
            f'مدت فایل حدود {duration / 3600:.1f} ساعت است که از حداکثر مجاز '
            f'({max_duration // 3600} ساعت) بیشتر است. '
            'لطفاً جلسه را به فایل‌های کوتاه‌تر تقسیم کنید و جداگانه بارگذاری کنید.'
        )

    chunk_seconds = _chunk_seconds()
    needs_chunking = bool(duration and duration > chunk_seconds * 1.5)
    if not needs_chunking and not duration:
        # ffprobe could not read a duration (rare container/metadata quirks).
        # For a BIG file the single-request path would rebuild exactly the
        # giant payload this module exists to avoid — chunk blindly instead:
        # the segment muxer needs no duration; only per-window frame sampling
        # is skipped (positions would be unknowable).
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
        except OSError:
            size_mb = 0.0
        if size_mb > max(1, _env_int("TRANSCRIPTION_FORCE_CHUNK_MB", 80)):
            logger.warning(
                "TRANSCRIBE: duration unknown but file is %.0f MB — forcing chunked mode (no frames).",
                size_mb,
            )
            needs_chunking = True

    if needs_chunking:
        return _transcribe_media_file_chunked(
            path=path,
            is_audio=is_audio,
            duration=duration,
            chunk_seconds=chunk_seconds,
            model=model,
            provider=provider,
            progress_cb=progress_cb,
        )

    # --- Single-shot path (short media, or duration unprobeable) -----------
    base_prompt = PROMPTS["transcribe_media"]["default"]
    _notify_progress(progress_cb, 0, 1)

    audio_bytes, audio_format = extract_audio_mp3_from_path(path)

    # Last-resort guard for unprobeable durations (e.g. browser MediaRecorder
    # webm/opus files often carry no duration header and can be small on disk
    # while holding HOURS of speech): if the extracted mp3 is clearly long,
    # never send it as one giant request — switch to chunked mode.
    max_single_mb = max(1, _env_int("TRANSCRIPTION_SINGLE_MAX_AUDIO_MB", 12))
    if len(audio_bytes) > max_single_mb * 1024 * 1024:
        logger.warning(
            "TRANSCRIBE: extracted audio is %.1f MB (> %d MB single-shot limit) — switching to chunked mode.",
            len(audio_bytes) / (1024 * 1024), max_single_mb,
        )
        del audio_bytes
        return _transcribe_media_file_chunked(
            path=path,
            is_audio=is_audio,
            duration=duration,
            chunk_seconds=chunk_seconds,
            model=model,
            provider=provider,
            progress_cb=progress_cb,
        )

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
        "TRANSCRIBE(file) start: model=%s is_audio=%s duration=%.0fs frames=%d",
        model, is_audio, duration, len(frames_b64),
    )
    transcript = sanitize_llm_markdown(
        _run_transcription(model=model, provider=provider, messages=messages)
    )
    _notify_progress(progress_cb, 1, 1)
    return transcript, provider, model


def _transcribe_media_file_chunked(
    *,
    path: str,
    is_audio: bool,
    duration: float,
    chunk_seconds: int,
    model: str,
    provider: str,
    progress_cb: ProgressCallback | None,
) -> Tuple[str, str, str]:
    """Sequentially transcribe long media as small audio(+frames) requests.

    Each request stays a few MB (10-min 64 kbps mono mp3 ≈ 6.4 MB base64 plus
    a frame budget), so gateway limits, flaky-link TLS drops, and output-token
    truncation cannot break a 500 MB / multi-hour lecture. Chunks run strictly
    in order because each prompt carries the tail of the transcript so far —
    that continuity is what keeps the stitched output reading as ONE document.
    """
    chunked_template = PROMPTS["transcribe_media"]["chunked"]
    frames_per_chunk = 0 if is_audio else _frames_per_chunk()

    with tempfile.TemporaryDirectory() as workdir:
        chunk_paths = extract_audio_mp3_chunks_from_path(
            path, chunk_seconds=chunk_seconds, workdir=workdir,
        )
        total = len(chunk_paths)
        logger.info(
            "TRANSCRIBE(chunked) start: model=%s is_audio=%s duration=%.0fs chunks=%d chunk_seconds=%d frames_per_chunk=%d",
            model, is_audio, duration, total, chunk_seconds, frames_per_chunk,
        )
        _notify_progress(progress_cb, 0, total)

        parts: list[str] = []
        tail = _FIRST_PART_TAIL
        for idx, chunk_path in enumerate(chunk_paths):
            with open(chunk_path, "rb") as fh:
                audio_b64 = base64.b64encode(fh.read()).decode()

            frames_b64: list[str] = []
            if frames_per_chunk > 0 and duration:
                try:
                    window_start = idx * chunk_seconds
                    window_end = min((idx + 1) * chunk_seconds, duration)
                    for frame in extract_frames_jpeg_from_path(
                        path,
                        start_ts=window_start,
                        end_ts=window_end,
                        max_frames=frames_per_chunk,
                    ):
                        frames_b64.append(base64.b64encode(frame).decode())
                except Exception:
                    # Frames are a bonus; never fail a chunk over them.
                    logger.exception(
                        "frame extraction failed for chunk %d/%d; continuing audio-only",
                        idx + 1, total,
                    )

            prompt = (
                chunked_template
                .replace("{part_number}", str(idx + 1))
                .replace("{total_parts}", str(total))
                .replace("{previous_transcript_tail}", tail)
            )
            messages = _build_transcription_messages(
                prompt=prompt,
                audio_b64=audio_b64,
                audio_format="mp3",
                frames_b64=frames_b64,
            )
            logger.info(
                "TRANSCRIBE(chunked) part %d/%d: frames=%d audio_b64_chars=%d",
                idx + 1, total, len(frames_b64), len(audio_b64),
            )
            try:
                part_text = _run_transcription(model=model, provider=provider, messages=messages)
            except Exception as exc:
                # A genuinely silent/music-only chunk (class break, paused
                # recording) makes the model return nothing, which the LLM
                # client raises as "Empty response". That is a VALID outcome
                # for one chunk — record it as empty instead of failing the
                # whole multi-hour transcription.
                if "empty response" in str(exc).lower():
                    logger.warning(
                        "TRANSCRIBE(chunked) part %d/%d returned no text (silent chunk?) — continuing.",
                        idx + 1, total,
                    )
                    part_text = ""
                else:
                    raise
            # Sanitize before this chunk enters both the stored transcript and
            # the continuity tail supplied to the next chunk.
            part_text = sanitize_llm_markdown(part_text)
            # The chunked prompt instructs the model to answer a literal
            # no-speech marker for silent chunks — normalise it away.
            if part_text == "[بدون گفتار]":
                part_text = ""
            parts.append(part_text)

            stitched_so_far = "\n\n".join(p for p in parts if p)
            if stitched_so_far:
                tail = stitched_so_far[-_PREVIOUS_TAIL_CHARS:]
            _notify_progress(progress_cb, idx + 1, total)

    transcript = "\n\n".join(p for p in parts if p).strip()
    if not transcript:
        raise RuntimeError(
            'هیچ گفتار قابل رونویسی در فایل پیدا نشد. لطفاً فایل را بررسی کنید و دوباره تلاش کنید.'
        )
    logger.info(
        "TRANSCRIBE(chunked) done: chunks=%d transcript_chars=%d", total, len(transcript),
    )
    return transcript, provider, model
