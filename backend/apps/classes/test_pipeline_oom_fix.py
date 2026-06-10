"""Regression tests for the celery-worker OOM-at-frame-extraction fix.

The pipeline step-1 worker used to slurp the ENTIRE uploaded video back into
RAM (``_read_file_bytes``) after streaming it to a temp disk file, hold it
across both ffmpeg runs, and (with --concurrency=2 in a 4Gi pod) OOM-kill the
container during frame extraction. The fix:
  * threads the on-disk temp PATH through the worker → ``transcribe_media_file``
    (ffmpeg reads the file directly; the video is never resident in RAM),
  * extracts frames via input-side ``-ss`` seeks (no full-stream decode).

All mocked — no ffmpeg, no LLM, no network, no tokens.
"""
from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from apps.classes.models import ClassCreationSession
from apps.classes.services import transcription
from apps.classes.services import transcription_media

Status = ClassCreationSession.Status
PipelineType = ClassCreationSession.PipelineType


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


# ---------------------------------------------------------------------------
# transcribe_media_file: path-based, same AvalAI multimodal contract
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("apps.classes.services.transcription.generate_text")
@patch("apps.classes.services.transcription.extract_frames_jpeg_from_path")
@patch("apps.classes.services.transcription.extract_audio_mp3_from_path")
def test_transcribe_media_file_uses_path_and_standard_shape(mock_audio, mock_frames, mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/gemini-2.5-flash")
    mock_audio.return_value = (b"AUD", "mp3")
    mock_frames.return_value = [b"F1", b"F2"]
    mock_gen.return_value = SimpleNamespace(text="TRANSCRIPT")

    transcript, _provider, model = transcription.transcribe_media_file(
        path="/tmp/fake-video.mp4", mime_type="video/mp4",
    )

    assert transcript == "TRANSCRIPT"
    assert model == "models/gemini-2.5-flash"
    # The path-based extractors are used, and receive the PATH (not bytes).
    mock_audio.assert_called_once_with("/tmp/fake-video.mp4")
    mock_frames.assert_called_once_with("/tmp/fake-video.mp4")
    # AvalAI multimodal contract preserved: text + input_audio + image_url(s).
    content = mock_gen.call_args.kwargs["messages"][0]["content"]
    assert [c["type"] for c in content] == ["text", "input_audio", "image_url", "image_url"]
    assert content[1]["input_audio"]["data"] == base64.b64encode(b"AUD").decode()
    assert content[2]["image_url"]["url"] == "data:image/jpeg;base64," + base64.b64encode(b"F1").decode()
    assert mock_gen.call_args.kwargs.get("timeout") == transcription._LLM_TIMEOUT_SECONDS


@pytest.mark.unit
@patch("apps.classes.services.transcription.generate_text")
@patch("apps.classes.services.transcription.extract_frames_jpeg_from_path")
@patch("apps.classes.services.transcription.extract_audio_mp3_from_path")
def test_transcribe_media_file_audio_skips_frames(mock_audio, mock_frames, mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/gemini-2.5-flash")
    mock_audio.return_value = (b"AUD", "mp3")
    mock_gen.return_value = SimpleNamespace(text="T")

    transcription.transcribe_media_file(path="/tmp/voice.ogg", mime_type="audio/ogg")

    mock_frames.assert_not_called()
    content = mock_gen.call_args.kwargs["messages"][0]["content"]
    assert [c["type"] for c in content] == ["text", "input_audio"]


# ---------------------------------------------------------------------------
# Worker step-1 must NOT read the whole media file into RAM (the OOM driver)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_class_step1_does_not_slurp_media_bytes_into_ram(monkeypatch):
    """process_class_step1_transcription (video) must pass the temp PATH to
    transcribe_media_file and never call _read_file_bytes for media."""
    from apps.classes import tasks

    session = baker.make(
        ClassCreationSession,
        pipeline_type=PipelineType.CLASS,
        status=Status.TRANSCRIBING,
        source_type=ClassCreationSession.SourceType.MEDIA,
        source_mime_type="video/mp4",
    )

    monkeypatch.setattr(tasks, "_read_session_file_to_disk", lambda s: "/tmp/fake-video.mp4")

    def _boom(_path):
        raise AssertionError("media path must NOT read the whole file into RAM")
    monkeypatch.setattr(tasks, "_read_file_bytes", _boom)

    captured = {}

    def _fake_transcribe_media_file(*, path, mime_type, progress_cb=None):
        captured["path"] = path
        captured["mime_type"] = mime_type
        captured["has_progress_cb"] = progress_cb is not None
        return "TRANSCRIPT", "avalai", "models/x"
    monkeypatch.setattr(
        "apps.classes.services.transcription.transcribe_media_file",
        _fake_transcribe_media_file,
    )

    result = tasks.process_class_step1_transcription.apply(args=[session.id]).result

    assert result["status"] == "success"
    assert captured["path"] == "/tmp/fake-video.mp4"  # streamed from disk, not RAM
    session.refresh_from_db()
    assert session.status == Status.TRANSCRIBED
    assert session.transcript_markdown == "TRANSCRIPT"


@pytest.mark.django_db
def test_pdf_step1_still_reads_bytes(monkeypatch):
    """PDFs are small, so the PDF branch may still read bytes — confirm media-vs-PDF
    branching is correct and PDF goes through the PDF engine, not transcription."""
    from apps.classes import tasks

    session = baker.make(
        ClassCreationSession,
        pipeline_type=PipelineType.CLASS,
        status=Status.TRANSCRIBING,
        source_type=ClassCreationSession.SourceType.PDF,
        source_mime_type="application/pdf",
    )

    monkeypatch.setattr(tasks, "_read_session_file_to_disk", lambda s: "/tmp/fake.pdf")
    monkeypatch.setattr(tasks, "_read_file_bytes", lambda p: b"%PDF-1.7 fake")

    def _fake_pdf(*, data, mime_type, asset_prefix):
        return "PDF-MARKDOWN", "avalai", "models/x", 3
    monkeypatch.setattr("apps.classes.services.pdf_extraction.extract_pdf_to_markdown", _fake_pdf)

    result = tasks.process_class_step1_transcription.apply(args=[session.id]).result
    assert result["status"] == "success"
    session.refresh_from_db()
    assert session.transcript_markdown == "PDF-MARKDOWN"
    assert session.source_page_count == 3


# ---------------------------------------------------------------------------
# Frame extraction is duration-aware (input -ss seeks, no full-stream decode)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_extract_frames_duration_aware_uses_input_seek(monkeypatch):
    """With a known duration, frames are grabbed via input-side -ss seeks: one
    cheap single-frame ffmpeg call per timestamp, with audio/subtitle decode off."""
    monkeypatch.setattr(transcription_media, "_get_duration", lambda p: 600.0)
    monkeypatch.setenv("FRAME_HARD_CAP", "4")

    calls = []

    def _fake_ffmpeg(args, timeout=900, label="FFmpeg"):
        calls.append(args)
        # ffmpeg writes the output jpeg (last arg) — emulate it.
        with open(args[-1], "wb") as fh:
            fh.write(b"JPEGDATA")
        return True, ""

    monkeypatch.setattr(transcription_media, "_run_ffmpeg", _fake_ffmpeg)

    frames = transcription_media.extract_frames_jpeg_from_path("/tmp/fake-video.mp4")

    assert len(frames) == 4               # exactly FRAME_HARD_CAP, one per seek
    assert all(f == b"JPEGDATA" for f in frames)
    assert len(calls) == 4                # 4 independent single-frame ffmpeg calls
    first = calls[0]
    assert "-ss" in first                 # INPUT-side seek → no full-stream decode
    assert "-frames:v" in first and first[first.index("-frames:v") + 1] == "1"
    assert "-an" in first                 # audio decode skipped
    # -ss must come BEFORE -i (input seeking, not output seeking)
    assert first.index("-ss") < first.index("-i")


@pytest.mark.unit
def test_extract_frames_fallback_when_duration_unknown(monkeypatch):
    """If duration can't be probed, fall back to a single capped fps pass."""
    monkeypatch.setattr(transcription_media, "_get_duration", lambda p: 0.0)
    monkeypatch.setenv("FRAME_HARD_CAP", "8")

    captured = {}

    def _fake_ffmpeg(args, timeout=900, label="FFmpeg"):
        captured["args"] = args
        # fallback uses a frame-%04d.jpg pattern (last arg); write two frames.
        pattern = args[-1]
        for i in range(2):
            with open(pattern.replace("%04d", f"{i:04d}"), "wb") as fh:
                fh.write(b"J")
        return True, ""

    monkeypatch.setattr(transcription_media, "_run_ffmpeg", _fake_ffmpeg)

    frames = transcription_media.extract_frames_jpeg_from_path("/tmp/fake-video.mp4")

    assert len(frames) == 2
    args = captured["args"]
    assert any(a.startswith("fps=") for a in args)        # single-pass fps sampling
    assert "-frames:v" in args and args[args.index("-frames:v") + 1] == "8"  # hard-capped
    assert "-an" in args
