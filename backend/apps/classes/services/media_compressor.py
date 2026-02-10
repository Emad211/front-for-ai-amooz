"""
Media compression utilities using FFmpeg.

This module provides functions to compress video/audio files before sending
to external APIs to avoid payload size limits (e.g., 413 errors).
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from glob import glob
from typing import Iterable, Tuple

logger = logging.getLogger(__name__)

# Maximum media payload size in bytes for API submission.
# Keep headroom for prompt/JSON overhead to reduce 413 risk.
MAX_PAYLOAD_SIZE_BYTES = 16 * 1024 * 1024

# Target video bitrate for compression (in kbps)
TARGET_VIDEO_BITRATE_KBPS = 500

# Target audio bitrate (in kbps)
TARGET_AUDIO_BITRATE_KBPS = 64

# Maximum video duration we'll process (seconds). Videos longer than this
# are rejected upfront to avoid blocking a Celery worker for hours.
MAX_VIDEO_DURATION_SECONDS = int(os.getenv('MAX_VIDEO_DURATION_SECONDS', '7200'))  # 2h default


def _get_ffmpeg_path() -> str:
    """Return FFmpeg executable path."""
    return os.getenv('FFMPEG_PATH', 'ffmpeg')


def _get_file_size(path: str) -> int:
    """Get file size in bytes."""
    return os.path.getsize(path)


def _run_ffmpeg(args: list[str], timeout: int = 1800) -> Tuple[bool, str]:
    """
    Run FFmpeg with given arguments.
    
    Returns:
        Tuple of (success: bool, error_message: str)
    """
    ffmpeg = _get_ffmpeg_path()
    cmd = [ffmpeg, '-y'] + args  # -y to overwrite output files
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return False, result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
        return True, ''
    except subprocess.TimeoutExpired:
        return False, f'FFmpeg timed out after {timeout}s'
    except Exception as exc:
        return False, str(exc)


def prepare_media_parts_for_api(
    input_data: bytes,
    input_mime_type: str,
    max_part_size_bytes: int = MAX_PAYLOAD_SIZE_BYTES,
) -> list[tuple[bytes, str]]:
    """Prepare one or more media parts that each fit within the API payload limit.

    Important:
    - This function NEVER converts video into audio-only.
    - If the media is too large, it will be compressed and/or split into multiple video parts.

    Returns a list of (bytes, mime_type). For small inputs, the list has exactly one part.
    """

    if len(input_data) <= max_part_size_bytes:
        return [(input_data, input_mime_type)]

    if input_mime_type.startswith('audio/'):
        raise RuntimeError(
            'فایل صوتی برای ارسال به مدل خیلی بزرگ است. '
            'برای حفظ فریم‌ها لازم است ویدیو را ارسال کنیم؛ لطفاً ویدیو را بارگذاری کنید '
            'یا فایل را کوتاه‌تر کنید.'
        )

    ext_map = {
        'video/mp4': '.mp4',
        'video/webm': '.webm',
        'video/quicktime': '.mov',
        'video/x-msvideo': '.avi',
        'video/x-matroska': '.mkv',
    }
    input_ext = ext_map.get(input_mime_type, '.mp4')

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f'input{input_ext}')
        output_video_path = os.path.join(tmpdir, 'output.mp4')

        with open(input_path, 'wb') as f:
            f.write(input_data)

        # Pre-check: reject extremely long videos that would block workers.
        duration = _get_duration(input_path)
        if duration > MAX_VIDEO_DURATION_SECONDS:
            hours = MAX_VIDEO_DURATION_SECONDS // 3600
            raise RuntimeError(
                f'ویدیو بیش از حد طولانی است ({duration:.0f} ثانیه). '
                f'حداکثر مدت مجاز {hours} ساعت می‌باشد. '
                'لطفاً ویدیو را کوتاه‌تر کنید.'
            )

        # Try: compress as a single video first.
        compressed_data, out_mime = _try_compress_video(input_path, output_video_path, max_part_size_bytes)
        if compressed_data is not None:
            return [(compressed_data, out_mime)]

        # Fallback: split into multiple video parts (keeps all frames across parts).
        return _split_and_compress_video_into_parts(
            input_path=input_path,
            workdir=tmpdir,
            max_part_size_bytes=max_part_size_bytes,
        )


def _split_and_compress_video_into_parts(
    *,
    input_path: str,
    workdir: str,
    max_part_size_bytes: int,
) -> list[tuple[bytes, str]]:
    """Split a video into multiple MP4 parts, each under the size limit."""

    # Start with ~3 minutes per chunk; adapt if still too large.
    segment_seconds = 180
    min_segment_seconds = 10

    while True:
        pattern = os.path.join(workdir, 'part-%03d.mp4')
        for existing in glob(os.path.join(workdir, 'part-*.mp4')):
            try:
                os.remove(existing)
            except OSError:
                pass

        args = [
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '28',
            '-c:a', 'aac',
            '-b:a', f'{TARGET_AUDIO_BITRATE_KBPS}k',
            '-vf', 'scale=trunc(iw/4)*2:trunc(ih/4)*2',
            '-f', 'segment',
            '-segment_time', str(segment_seconds),
            '-reset_timestamps', '1',
            '-movflags', '+faststart',
            pattern,
        ]

        success, error = _run_ffmpeg(args)
        if not success:
            raise RuntimeError(f'FFmpeg failed while splitting video: {error}')

        part_paths = sorted(glob(os.path.join(workdir, 'part-*.mp4')))
        if not part_paths:
            raise RuntimeError('FFmpeg produced no output parts while splitting video.')

        sizes = [(_get_file_size(p), p) for p in part_paths]
        max_size = max(s for s, _ in sizes)
        logger.info(
            'Video split into %d parts (segment=%ss), max_part=%d bytes',
            len(part_paths),
            segment_seconds,
            max_size,
        )

        if max_size <= max_part_size_bytes:
            parts: list[tuple[bytes, str]] = []
            for _, p in sizes:
                with open(p, 'rb') as f:
                    parts.append((f.read(), 'video/mp4'))
            return parts

        if segment_seconds <= min_segment_seconds:
            raise RuntimeError(
                'با وجود تقسیم‌بندی، هر بخش ویدیو هنوز از محدودیت حجم درخواست بزرگ‌تر است. '
                'برای جلوگیری از 413 لازم است ویدیو کوتاه‌تر/کم‌حجم‌تر باشد یا محدودیت سمت ارائه‌دهنده افزایش یابد.'
            )

        segment_seconds = max(min_segment_seconds, segment_seconds // 2)


def _try_compress_video(
    input_path: str,
    output_path: str,
    max_size_bytes: int,
) -> Tuple[bytes | None, str]:
    """
    Try to compress video to fit within size limit.
    
    Returns (None, '') if compression fails or result is still too large.
    """
    # Calculate target bitrate based on duration
    duration = _get_duration(input_path)
    if duration <= 0:
        duration = 1200  # Default 20 minutes if can't detect
    
    # Target total bitrate in kbps (leave some margin)
    # Formula: size_bytes = bitrate_kbps * duration_sec / 8 * 1000
    # So: bitrate_kbps = size_bytes * 8 / duration_sec / 1000
    target_total_bitrate = int((max_size_bytes * 8) / duration / 1000 * 0.9)  # 90% margin
    
    # Split between video and audio
    audio_bitrate = min(TARGET_AUDIO_BITRATE_KBPS, target_total_bitrate // 4)
    video_bitrate = target_total_bitrate - audio_bitrate
    
    # Minimum video bitrate for acceptable quality
    if video_bitrate < 100:
        logger.info(f'Target video bitrate {video_bitrate}kbps too low, skipping video compression')
        return None, ''
    
    logger.info(f'Compressing video: duration={duration}s, target_bitrate={video_bitrate}k video + {audio_bitrate}k audio')
    
    # FFmpeg compression with CRF and target bitrate
    args = [
        '-i', input_path,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '28',  # Higher CRF = more compression
        '-b:v', f'{video_bitrate}k',
        '-maxrate', f'{video_bitrate * 2}k',
        '-bufsize', f'{video_bitrate * 4}k',
        '-c:a', 'aac',
        '-b:a', f'{audio_bitrate}k',
        '-vf', 'scale=trunc(iw/4)*2:trunc(ih/4)*2',  # Reduce resolution by half, ensure even dimensions
        '-movflags', '+faststart',
        output_path,
    ]
    
    success, error = _run_ffmpeg(args)
    if not success:
        logger.warning(f'Video compression failed: {error}')
        return None, ''
    
    output_size = _get_file_size(output_path)
    logger.info(f'Compressed video size: {output_size} bytes')
    
    if output_size > max_size_bytes:
        logger.info(f'Compressed video still too large ({output_size} > {max_size_bytes})')
        return None, ''
    
    with open(output_path, 'rb') as f:
        return f.read(), 'video/mp4'


def _get_duration(file_path: str) -> float:
    """Get media duration in seconds using ffprobe."""
    ffprobe = _get_ffmpeg_path().replace('ffmpeg', 'ffprobe')
    
    cmd = [
        ffprobe,
        '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path,
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as exc:
        logger.warning(f'Could not get duration: {exc}')
    
    return 0.0
