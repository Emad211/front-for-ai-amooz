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
import time
from glob import glob
from typing import Tuple

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


def _run_ffmpeg(args: list[str], timeout: int = 1800, label: str = 'FFmpeg') -> Tuple[bool, str]:
    """Run FFmpeg with given arguments and log progress.

    Uses ``subprocess.Popen`` so we can emit periodic heartbeat logs
    while FFmpeg is running.  This prevents the Celery worker from
    appearing "stuck" during long encoding jobs.

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    ffmpeg = _get_ffmpeg_path()
    cmd = [ffmpeg, '-y'] + args  # -y to overwrite output files

    logger.info('%s command started: %s', label, ' '.join(cmd[:8]) + ' ...')
    t0 = time.monotonic()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Poll the process and log heartbeat every 30 seconds
        heartbeat_interval = 30  # seconds
        last_heartbeat = t0
        while True:
            try:
                proc.wait(timeout=heartbeat_interval)
                # Process finished
                break
            except subprocess.TimeoutExpired:
                now = time.monotonic()
                elapsed = now - t0
                if elapsed > timeout:
                    proc.kill()
                    proc.wait(timeout=10)
                    return False, f'{label} timed out after {timeout}s'
                if now - last_heartbeat >= heartbeat_interval:
                    logger.info(
                        '%s still running… elapsed=%.0fs / timeout=%ds',
                        label, elapsed, timeout,
                    )
                    last_heartbeat = now

        elapsed = time.monotonic() - t0
        _, stderr_bytes = proc.communicate(timeout=10)
        stderr_text = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

        if proc.returncode != 0:
            logger.warning('%s failed (rc=%d) after %.1fs', label, proc.returncode, elapsed)
            return False, stderr_text[-2000:] if len(stderr_text) > 2000 else stderr_text

        logger.info('%s finished successfully in %.1fs', label, elapsed)
        return True, ''

    except Exception as exc:
        elapsed = time.monotonic() - t0
        logger.error('%s crashed after %.1fs: %s', label, elapsed, exc)
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

    Strategy (fast → slow):
    1. If file ≤ limit → return as-is.
    2. Try single-file compression → return if small enough.
    3. **Fast split**: stream-copy split (no re-encode, near-instant).
       If every part ≤ limit → done.
    4. **Slow split**: re-encode split with ultrafast preset.

    Returns a list of (bytes, mime_type). For small inputs, the list has exactly one part.
    """

    input_size = len(input_data)
    if input_size <= max_part_size_bytes:
        logger.info('Media size %d ≤ limit %d, no processing needed.', input_size, max_part_size_bytes)
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

        logger.info(
            'Media exceeds API limit (%d > %d bytes, duration=%.1fs). '
            'Attempting compression/split strategies.',
            input_size,
            max_part_size_bytes,
            duration,
        )

        # ── Strategy 1: single-file compression ───────────────────────
        compressed_data, out_mime = _try_compress_video(input_path, output_video_path, max_part_size_bytes)
        if compressed_data is not None:
            return [(compressed_data, out_mime)]

        # ── Strategy 2: fast stream-copy split (no re-encode) ─────────
        logger.info(
            'Strategy 2: trying fast stream-copy split (no re-encode)…'
        )
        fast_parts = _try_fast_split(
            input_path=input_path,
            workdir=tmpdir,
            max_part_size_bytes=max_part_size_bytes,
            duration=duration,
        )
        if fast_parts is not None:
            logger.info('Fast stream-copy split succeeded with %d parts.', len(fast_parts))
            return fast_parts

        # ── Strategy 3: slow re-encode split (last resort) ────────────
        logger.info(
            'Strategy 3: fast split parts too large, falling back to '
            're-encode split (this may take several minutes on limited CPU)…'
        )
        return _split_and_compress_video_into_parts(
            input_path=input_path,
            workdir=tmpdir,
            max_part_size_bytes=max_part_size_bytes,
        )


def _try_fast_split(
    *,
    input_path: str,
    workdir: str,
    max_part_size_bytes: int,
    duration: float,
) -> list[tuple[bytes, str]] | None:
    """Attempt a stream-copy split (no re-encoding).

    Stream-copy is near-instant because FFmpeg just copies raw stream
    packets without decoding/encoding.  However, each output part keeps
    the original bitrate, so parts may exceed the size limit for
    high-bitrate sources.

    Returns a list of (bytes, mime_type) if all parts fit, or ``None``
    if any part exceeds the limit (caller should fall back to re-encode).
    """
    # Estimate how short segments need to be so each fits in the limit.
    # original_bitrate ≈ file_size / duration (bytes/s)
    file_size = _get_file_size(input_path)
    if duration <= 0:
        duration = 600  # fallback
    original_bps = file_size / duration  # bytes per second
    # segment_seconds such that segment_seconds * original_bps ≤ max_part_size_bytes
    segment_seconds = max(10, int(max_part_size_bytes / original_bps * 0.85))
    segment_seconds = min(segment_seconds, 300)  # cap at 5 minutes

    logger.info(
        'Fast split: file=%d bytes, bps=%.0f, segment=%ds (estimated)',
        file_size, original_bps, segment_seconds,
    )

    pattern = os.path.join(workdir, 'fast-%03d.mp4')
    args = [
        '-i', input_path,
        '-c', 'copy',              # stream copy — no re-encode
        '-f', 'segment',
        '-segment_time', str(segment_seconds),
        '-reset_timestamps', '1',
        '-movflags', '+faststart',
        pattern,
    ]

    success, error = _run_ffmpeg(args, timeout=120, label='FastSplit')
    if not success:
        logger.warning('Fast split failed: %s', error[:300])
        return None

    part_paths = sorted(glob(os.path.join(workdir, 'fast-*.mp4')))
    if not part_paths:
        logger.warning('Fast split produced no output files.')
        return None

    sizes = [(_get_file_size(p), p) for p in part_paths]
    max_size = max(s for s, _ in sizes)
    logger.info(
        'Fast split: %d parts, max_part=%d bytes (limit=%d)',
        len(part_paths), max_size, max_part_size_bytes,
    )

    if max_size > max_part_size_bytes:
        # Clean up fast-split files so they don't interfere with slow path
        for _, p in sizes:
            try:
                os.remove(p)
            except OSError:
                pass
        return None

    parts: list[tuple[bytes, str]] = []
    for _, p in sizes:
        with open(p, 'rb') as f:
            parts.append((f.read(), 'video/mp4'))
    return parts


def _split_and_compress_video_into_parts(
    *,
    input_path: str,
    workdir: str,
    max_part_size_bytes: int,
) -> list[tuple[bytes, str]]:
    """Split a video into multiple MP4 parts, each under the size limit.

    Uses ``-preset ultrafast`` for maximum encoding speed on constrained
    K8s pods.  Quality is slightly worse than ``fast`` but encoding is
    3-5× faster, which is critical to avoid worker timeouts.
    """

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

        logger.info(
            'Re-encode split: segment_time=%ds, preset=ultrafast, crf=30. '
            'This will take several minutes for long videos…',
            segment_seconds,
        )
        args = [
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',   # ← was 'fast', now 3-5× faster
            '-crf', '30',             # ← was 28, slightly more compression
            '-c:a', 'aac',
            '-b:a', f'{TARGET_AUDIO_BITRATE_KBPS}k',
            '-vf', 'scale=trunc(iw/4)*2:trunc(ih/4)*2',
            '-f', 'segment',
            '-segment_time', str(segment_seconds),
            '-reset_timestamps', '1',
            '-movflags', '+faststart',
            pattern,
        ]

        success, error = _run_ffmpeg(
            args, timeout=1800, label=f'ReEncodeSplit(seg={segment_seconds}s)',
        )
        if not success:
            raise RuntimeError(f'FFmpeg failed while splitting video: {error}')

        part_paths = sorted(glob(os.path.join(workdir, 'part-*.mp4')))
        if not part_paths:
            raise RuntimeError('FFmpeg produced no output parts while splitting video.')

        sizes = [(_get_file_size(p), p) for p in part_paths]
        max_size = max(s for s, _ in sizes)
        logger.info(
            'Re-encode split finished: %d parts (segment=%ds), max_part=%d bytes (limit=%d)',
            len(part_paths),
            segment_seconds,
            max_size,
            max_part_size_bytes,
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
    """Try to compress video to fit within size limit.

    Returns (None, '') if compression fails or result is still too large.
    """
    # Calculate target bitrate based on duration
    duration = _get_duration(input_path)
    if duration <= 0:
        duration = 1200  # Default 20 minutes if can't detect

    # Target total bitrate in kbps (leave some margin)
    target_total_bitrate = int((max_size_bytes * 8) / duration / 1000 * 0.9)

    # Split between video and audio
    audio_bitrate = min(TARGET_AUDIO_BITRATE_KBPS, target_total_bitrate // 4)
    video_bitrate = target_total_bitrate - audio_bitrate

    # Minimum video bitrate for acceptable quality
    if video_bitrate < 100:
        logger.info(
            'Target video bitrate %dkbps too low for single-file compression '
            '(duration=%.0fs, file=%d bytes). Will try split strategies instead.',
            video_bitrate, duration, _get_file_size(input_path),
        )
        return None, ''

    logger.info(
        'Compressing video: duration=%.0fs, target_bitrate=%dk video + %dk audio',
        duration, video_bitrate, audio_bitrate,
    )

    # FFmpeg compression with ultrafast preset for speed
    args = [
        '-i', input_path,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '30',
        '-b:v', f'{video_bitrate}k',
        '-maxrate', f'{video_bitrate * 2}k',
        '-bufsize', f'{video_bitrate * 4}k',
        '-c:a', 'aac',
        '-b:a', f'{audio_bitrate}k',
        '-vf', 'scale=trunc(iw/4)*2:trunc(ih/4)*2',
        '-movflags', '+faststart',
        output_path,
    ]

    success, error = _run_ffmpeg(args, label='Compress')
    if not success:
        logger.warning('Video compression failed: %s', error[:300])
        return None, ''

    output_size = _get_file_size(output_path)
    logger.info('Compressed video size: %d bytes (limit=%d)', output_size, max_size_bytes)

    if output_size > max_size_bytes:
        logger.info('Compressed video still too large (%d > %d)', output_size, max_size_bytes)
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
