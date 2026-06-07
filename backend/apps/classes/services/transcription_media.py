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

from .media_compressor import _get_file_size, _run_ffmpeg

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


def extract_audio_mp3(media_bytes: bytes, input_mime: str) -> tuple[bytes, str]:
    """Re-encode the audio track of ``media_bytes`` to a small mono mp3.

    Works for both video (audio track) and audio inputs. Returns ``(bytes, "mp3")``.
    Normalising to mp3 also fixes oversized raw audio that previously got rejected.
    """
    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "input" + _ext_for(input_mime))
        out_path = os.path.join(tmp, "audio.mp3")
        with open(in_path, "wb") as fh:
            fh.write(media_bytes)

        args = [
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


def extract_frames_jpeg(video_bytes: bytes, input_mime: str) -> list[bytes]:
    """Sample frames from a video as JPEGs, bounded by the FRAME_* env budget.

    Returns a list of JPEG byte blobs (possibly empty if extraction yields none).
    Selection: sample at ``FRAME_EXTRACTION_FPS``, then evenly downselect to
    ``FRAME_HARD_CAP`` frames, then trim from the end until the total is within
    ``MAX_TOTAL_FRAME_BYTES_MB``.
    """
    fps = _env_float("FRAME_EXTRACTION_FPS", 0.25)
    hard_cap = max(1, _env_int("FRAME_HARD_CAP", 16))
    max_for_model = max(1, _env_int("FRAME_MAX_FRAMES_FOR_MODEL", 40))
    cap = min(hard_cap, max_for_model)
    max_total_bytes = _env_int("MAX_TOTAL_FRAME_BYTES_MB", 3) * 1024 * 1024

    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "input" + _ext_for(input_mime))
        with open(in_path, "wb") as fh:
            fh.write(video_bytes)

        pattern = os.path.join(tmp, "frame-%04d.jpg")
        args = [
            "-i", in_path,
            # sample fps, downscale to <=640px wide (keep aspect, even dims), mid JPEG quality
            "-vf", f"fps={fps},scale='min(640,iw)':-2",
            "-q:v", "5",
            pattern,
        ]
        ok, err = _run_ffmpeg(args, timeout=900, label="ExtractFrames")
        if not ok:
            logger.warning("frame extraction failed (continuing audio-only): %s", err[:300])
            return []

        paths = sorted(glob(os.path.join(tmp, "frame-*.jpg")))
        if not paths:
            return []

        # Evenly downselect to the cap.
        if len(paths) > cap:
            step = len(paths) / cap
            paths = [paths[int(i * step)] for i in range(cap)]

        frames: list[bytes] = []
        total = 0
        for p in paths:
            size = _get_file_size(p)
            if frames and total + size > max_total_bytes:
                break  # stay within the byte budget
            with open(p, "rb") as fh:
                frames.append(fh.read())
            total += size

        logger.info("Extracted %d frame(s) (~%d bytes) for transcription.", len(frames), total)
        return frames
