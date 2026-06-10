"""Extract API-ready parts (audio + sampled frames) from lecture media for
multimodal transcription via the OpenAI-compatible Avalai gateway.

The gateway has NO video content type — only ``text``, ``image_url`` and
``input_audio``. So to transcribe a *video* we extract:
  * the audio track, re-encoded to a small mono mp3  -> sent as ``input_audio``,
  * a handful of sampled frames as JPEGs              -> sent as ``image_url``.

This preserves both speech AND on-screen visual content (slides/whiteboard),
which is why ``media_compressor`` deliberately never reduced video to audio-only.
Frame budget is governed by the existing env knobs:
``FRAME_EXTRACTION_FPS`` (default 0.25 = 1 frame / 4s), ``FRAME_HARD_CAP`` (16),
``FRAME_MAX_FRAMES_FOR_MODEL`` (40), ``MAX_TOTAL_FRAME_BYTES_MB`` (3).
"""
from __future__ import annotations

import logging
import os
import tempfile
from glob import glob

from .media_compressor import _get_duration, _get_file_size, _run_ffmpeg

logger = logging.getLogger(__name__)

_AUDIO_BITRATE_K = int(os.getenv("TRANSCRIPTION_AUDIO_BITRATE_K", "64"))


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


_EXT_MAP = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
}


def _ext_for(mime: str) -> str:
    return _EXT_MAP.get((mime or "").lower(), ".bin")


def _write_bytes_to_temp(media_bytes: bytes, input_mime: str) -> str:
    """Write ``media_bytes`` to a NamedTemporaryFile and return its path.

    The caller is responsible for unlinking the returned path. Used only by the
    bytes-based wrappers below so in-memory callers can reuse the path-based
    extractors without duplicating ffmpeg logic.
    """
    fh = tempfile.NamedTemporaryFile(delete=False, suffix=_ext_for(input_mime))
    try:
        fh.write(media_bytes)
        return fh.name
    finally:
        fh.close()


def extract_audio_mp3_from_path(in_path: str) -> tuple[bytes, str]:
    """Re-encode the audio track of the media file at ``in_path`` to a small mono mp3.

    ffmpeg reads the file directly — the media is NEVER loaded into Python RAM.
    Works for both video (audio track) and audio inputs. Returns ``(bytes, "mp3")``.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "audio.mp3")
        args = [
            "-nostdin",
            "-i", in_path,
            "-vn",                 # drop any video stream
            "-ac", "1",            # mono
            "-ar", "16000",        # 16 kHz is plenty for speech
            "-c:a", "libmp3lame",
            "-b:a", f"{_AUDIO_BITRATE_K}k",
            "-f", "mp3",
            out_path,
        ]
        ok, err = _run_ffmpeg(args, timeout=900, label="ExtractAudio")
        if not ok or not os.path.exists(out_path):
            raise RuntimeError(f"audio extraction failed: {err[:300]}")
        with open(out_path, "rb") as fh:
            return fh.read(), "mp3"


def extract_frames_jpeg_from_path(in_path: str) -> list[bytes]:
    """Sample up to ``FRAME_HARD_CAP`` frames from the video at ``in_path`` as JPEGs.

    ffmpeg reads the file directly (the video is NEVER loaded into RAM). To bound
    BOTH ffmpeg's decode working set AND CPU, when the duration is known we use
    **input-side ``-ss`` seeking**: one cheap ffmpeg invocation per evenly-spaced
    timestamp decodes only ~1 frame near a keyframe — instead of decoding the
    entire stream (the old post-decode ``fps`` filter forced a full-stream decode
    and dumped thousands of JPEGs to /tmp). Falls back to a single ``-frames:v``-
    capped ``fps`` pass when the duration can't be probed. Output stays within
    ``MAX_TOTAL_FRAME_BYTES_MB``.
    """
    cap = min(max(1, _env_int("FRAME_HARD_CAP", 16)), max(1, _env_int("FRAME_MAX_FRAMES_FOR_MODEL", 40)))
    max_total_bytes = _env_int("MAX_TOTAL_FRAME_BYTES_MB", 3) * 1024 * 1024

    duration = 0.0
    try:
        duration = _get_duration(in_path)
    except Exception:
        duration = 0.0

    frames: list[bytes] = []
    total = 0

    with tempfile.TemporaryDirectory() as tmp:
        if duration and duration > 1.0:
            # Duration-aware: ~cap evenly-spaced single-frame grabs via INPUT seek.
            for i in range(cap):
                ts = duration * (i + 0.5) / cap
                out_path = os.path.join(tmp, f"frame-{i:04d}.jpg")
                args = [
                    "-nostdin",
                    "-ss", f"{ts:.3f}",      # input-side seek (before -i): no full decode
                    "-i", in_path,
                    "-frames:v", "1",
                    "-an", "-sn", "-dn",     # skip audio/subtitle/data decode
                    "-vf", "scale='min(640,iw)':-2",
                    "-q:v", "5",
                    out_path,
                ]
                ok, _err = _run_ffmpeg(args, timeout=120, label=f"Frame{i:02d}")
                if not ok or not os.path.exists(out_path):
                    continue
                size = _get_file_size(out_path)
                if frames and total + size > max_total_bytes:
                    break
                with open(out_path, "rb") as fh:
                    frames.append(fh.read())
                total += size
        else:
            # Fallback (unknown duration): single pass at FRAME_EXTRACTION_FPS,
            # hard-capped output so a misdetected fps can never dump thousands.
            fps = _env_float("FRAME_EXTRACTION_FPS", 0.25)
            pattern = os.path.join(tmp, "frame-%04d.jpg")
            args = [
                "-nostdin",
                "-an", "-sn", "-dn",
                "-i", in_path,
                "-vf", f"fps={fps},scale='min(640,iw)':-2",
                "-frames:v", str(cap),
                "-q:v", "5",
                pattern,
            ]
            ok, err = _run_ffmpeg(args, timeout=900, label="ExtractFrames")
            if not ok:
                logger.warning("frame extraction failed (continuing audio-only): %s", err[:300])
                return []
            for p in sorted(glob(os.path.join(tmp, "frame-*.jpg")))[:cap]:
                size = _get_file_size(p)
                if frames and total + size > max_total_bytes:
                    break
                with open(p, "rb") as fh:
                    frames.append(fh.read())
                total += size

    logger.info("Extracted %d frame(s) (~%d bytes) for transcription.", len(frames), total)
    return frames


def extract_audio_mp3(media_bytes: bytes, input_mime: str) -> tuple[bytes, str]:
    """Bytes-based wrapper around :func:`extract_audio_mp3_from_path`.

    Kept for callers that already hold the media in memory (small audio chat
    uploads, the synchronous request path, tests). Writes the bytes to a temp
    file once and delegates. The memory-heavy Celery pipeline uses the
    ``*_from_path`` API directly so a large video is never resident in RAM.
    """
    path = _write_bytes_to_temp(media_bytes, input_mime)
    try:
        return extract_audio_mp3_from_path(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def extract_frames_jpeg(video_bytes: bytes, input_mime: str) -> list[bytes]:
    """Bytes-based wrapper around :func:`extract_frames_jpeg_from_path`."""
    path = _write_bytes_to_temp(video_bytes, input_mime)
    try:
        return extract_frames_jpeg_from_path(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
