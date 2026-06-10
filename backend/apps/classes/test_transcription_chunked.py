"""Regression tests for chunked transcription of long / large media (≤500 MB).

The old single-request flow base64'd the ENTIRE audio track of a lecture into
ONE chat-completion call: a 2-3 h video produced a 40-100 MB JSON body that the
gateway rejects (413 / ``SSL: UNEXPECTED_EOF`` over flaky links) and whose
verbatim output exceeds the model's output-token budget (silent transcript
truncation). Long media is now split into sequential ~10-min mp3 segments —
each sent with the frames of ITS OWN time window plus the tail of the
transcript so far — with a heartbeat/cancel hook between chunks that (a) bumps
``updated_at`` so ``cleanup_stale_sessions`` never reaps a live run and
(b) lets the teacher's cancel take effect mid-step.

All mocked — no ffmpeg, no LLM, no network, no tokens.
"""
from __future__ import annotations

import base64
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from model_bakery import baker

from apps.classes.models import ClassCreationSession
from apps.classes.services import transcription
from apps.classes.services import transcription_media
from apps.classes.services.transcription import TranscriptionAborted

Status = ClassCreationSession.Status
PipelineType = ClassCreationSession.PipelineType


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


def _fake_chunk_extractor(contents: list[bytes]):
    """Build a fake ``extract_audio_mp3_chunks_from_path`` writing real files."""

    def _fake(path, *, chunk_seconds, workdir):
        paths = []
        for i, data in enumerate(contents):
            p = os.path.join(workdir, f"audio-{i:04d}.mp3")
            with open(p, "wb") as fh:
                fh.write(data)
            paths.append(p)
        return paths

    return _fake


# ---------------------------------------------------------------------------
# Chunked orchestration: split → per-window frames → continuity → stitching
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("apps.classes.services.transcription.generate_text")
def test_long_video_is_chunked_with_continuity_and_windowed_frames(mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/gemini-2.5-flash")
    monkeypatch.setenv("TRANSCRIPTION_CHUNK_SECONDS", "600")
    monkeypatch.setenv("TRANSCRIPTION_FRAMES_PER_CHUNK", "8")
    monkeypatch.setattr(transcription, "probe_media_duration", lambda p: 1500.0)
    monkeypatch.setattr(
        transcription, "extract_audio_mp3_chunks_from_path",
        _fake_chunk_extractor([b"A0", b"A1", b"A2"]),
    )

    frame_calls: list[dict] = []

    def _fake_frames(path, **kwargs):
        frame_calls.append({"path": path, **kwargs})
        return [b"FRAME"]

    monkeypatch.setattr(transcription, "extract_frames_jpeg_from_path", _fake_frames)
    mock_gen.side_effect = [
        SimpleNamespace(text="PART1"),
        SimpleNamespace(text="PART2"),
        SimpleNamespace(text="PART3"),
    ]

    transcript, provider, model = transcription.transcribe_media_file(
        path="/tmp/long-video.mp4", mime_type="video/mp4",
    )

    # One LLM request per chunk; stitched in order.
    assert mock_gen.call_count == 3
    assert transcript == "PART1\n\nPART2\n\nPART3"
    assert model == "models/gemini-2.5-flash"

    # Part numbering + continuity tail flow through the chunked prompt.
    prompts = [
        c.kwargs["messages"][0]["content"][0]["text"] for c in mock_gen.call_args_list
    ]
    assert "قطعه 1 از 3" in prompts[0]
    assert "این اولین قطعه است" in prompts[0]
    assert "قطعه 2 از 3" in prompts[1] and "PART1" in prompts[1]
    assert "قطعه 3 از 3" in prompts[2] and "PART2" in prompts[2]

    # Every chunk request carries ITS OWN audio segment + its window's frames.
    for i, call in enumerate(mock_gen.call_args_list):
        content = call.kwargs["messages"][0]["content"]
        assert [c["type"] for c in content] == ["text", "input_audio", "image_url"]
        assert content[1]["input_audio"]["data"] == base64.b64encode(f"A{i}".encode()).decode()
        assert content[1]["input_audio"]["format"] == "mp3"

    # Frames are sampled inside each chunk's time window (1500 s / 600 s → 3).
    assert [c["start_ts"] for c in frame_calls] == [0, 600, 1200]
    assert [c["end_ts"] for c in frame_calls] == [600, 1200, 1500]
    assert all(c["max_frames"] == 8 for c in frame_calls)


@pytest.mark.unit
@pytest.mark.parametrize("duration", [300.0, 880.0])
@patch("apps.classes.services.transcription.generate_text")
@patch("apps.classes.services.transcription.extract_frames_jpeg_from_path")
@patch("apps.classes.services.transcription.extract_audio_mp3_from_path")
def test_short_video_stays_single_shot(mock_audio, mock_frames, mock_gen, monkeypatch, duration):
    """Media at or below ~1.5× the chunk size keeps the proven single request."""
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/gemini-2.5-flash")
    monkeypatch.setenv("TRANSCRIPTION_CHUNK_SECONDS", "600")
    monkeypatch.setattr(transcription, "probe_media_duration", lambda p: duration)

    chunk_spy_called = {"v": False}
    monkeypatch.setattr(
        transcription, "extract_audio_mp3_chunks_from_path",
        lambda *a, **k: chunk_spy_called.__setitem__("v", True),
    )

    mock_audio.return_value = (b"AUD", "mp3")
    mock_frames.return_value = [b"F1"]
    mock_gen.return_value = SimpleNamespace(text="T")

    transcript, _p, _m = transcription.transcribe_media_file(
        path="/tmp/short.mp4", mime_type="video/mp4",
    )

    assert transcript == "T"
    assert mock_gen.call_count == 1
    assert chunk_spy_called["v"] is False
    # Whole-file frame sampling, exactly as before (positional path only).
    mock_frames.assert_called_once_with("/tmp/short.mp4")
    prompt = mock_gen.call_args.kwargs["messages"][0]["content"][0]["text"]
    assert "حالت قطعه‌به‌قطعه" not in prompt


@pytest.mark.unit
@patch("apps.classes.services.transcription.generate_text")
def test_duration_over_cap_is_rejected_before_any_llm_call(mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/x")
    monkeypatch.setenv("TRANSCRIPTION_MAX_DURATION_SECONDS", str(4 * 3600))
    monkeypatch.setattr(transcription, "probe_media_duration", lambda p: 5 * 3600.0)

    with pytest.raises(RuntimeError) as exc:
        transcription.transcribe_media_file(path="/tmp/huge.mp4", mime_type="video/mp4")

    assert "ساعت" in str(exc.value)
    mock_gen.assert_not_called()


@pytest.mark.unit
@patch("apps.classes.services.transcription.generate_text")
def test_audio_source_chunked_without_frames(mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/x")
    monkeypatch.setenv("TRANSCRIPTION_CHUNK_SECONDS", "600")
    monkeypatch.setattr(transcription, "probe_media_duration", lambda p: 2000.0)
    monkeypatch.setattr(
        transcription, "extract_audio_mp3_chunks_from_path",
        _fake_chunk_extractor([b"A0", b"A1", b"A2", b"A3"]),
    )

    def _no_frames(*a, **k):  # pragma: no cover - guard
        raise AssertionError("frames must not be extracted for audio sources")

    monkeypatch.setattr(transcription, "extract_frames_jpeg_from_path", _no_frames)
    mock_gen.side_effect = [SimpleNamespace(text=f"P{i}") for i in range(4)]

    transcript, _p, _m = transcription.transcribe_media_file(
        path="/tmp/lecture.mp3", mime_type="audio/mpeg",
    )

    assert transcript == "P0\n\nP1\n\nP2\n\nP3"
    for call in mock_gen.call_args_list:
        content = call.kwargs["messages"][0]["content"]
        assert [c["type"] for c in content] == ["text", "input_audio"]


# ---------------------------------------------------------------------------
# Progress hook: heartbeat + mid-step cancellation
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("apps.classes.services.transcription.generate_text")
def test_progress_cb_false_aborts_between_chunks(mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/x")
    monkeypatch.setenv("TRANSCRIPTION_CHUNK_SECONDS", "600")
    monkeypatch.setattr(transcription, "probe_media_duration", lambda p: 1800.0)
    monkeypatch.setattr(
        transcription, "extract_audio_mp3_chunks_from_path",
        _fake_chunk_extractor([b"A0", b"A1", b"A2"]),
    )
    monkeypatch.setattr(transcription, "extract_frames_jpeg_from_path", lambda *a, **k: [])
    mock_gen.return_value = SimpleNamespace(text="PART")

    seen: list[tuple[int, int]] = []

    def _cb(done, total):
        seen.append((done, total))
        return done < 1  # allow start + chunk 1, then cancel

    with pytest.raises(TranscriptionAborted):
        transcription.transcribe_media_file(
            path="/tmp/long.mp4", mime_type="video/mp4", progress_cb=_cb,
        )

    # Aborted right after the first chunk: exactly one LLM call burned.
    assert mock_gen.call_count == 1
    assert seen == [(0, 3), (1, 3)]


@pytest.mark.unit
@patch("apps.classes.services.transcription.generate_text")
def test_progress_cb_errors_never_fail_transcription(mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/x")
    monkeypatch.setattr(transcription, "probe_media_duration", lambda p: 0.0)
    monkeypatch.setattr(
        transcription, "extract_audio_mp3_from_path", lambda p: (b"AUD", "mp3"),
    )
    mock_gen.return_value = SimpleNamespace(text="T")

    def _broken_cb(done, total):
        raise ValueError("heartbeat infra hiccup")

    transcript, _p, _m = transcription.transcribe_media_file(
        path="/tmp/voice.ogg", mime_type="audio/ogg", progress_cb=_broken_cb,
    )
    assert transcript == "T"


@pytest.mark.unit
def test_chunk_seconds_env_is_clamped(monkeypatch):
    """A stray env value (e.g. the dead TRANSCRIBE_CHUNK_SECONDS=20 pattern)
    must never produce hundreds of requests or one giant request."""
    monkeypatch.setenv("TRANSCRIPTION_CHUNK_SECONDS", "20")
    assert transcription._chunk_seconds() == 120
    monkeypatch.setenv("TRANSCRIPTION_CHUNK_SECONDS", "99999")
    assert transcription._chunk_seconds() == 1800
    monkeypatch.setenv("TRANSCRIPTION_CHUNK_SECONDS", "not-a-number")
    assert transcription._chunk_seconds() == 600


# ---------------------------------------------------------------------------
# transcription_media: segment pass + windowed frame sampling
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_extract_audio_chunks_single_segment_pass(monkeypatch, tmp_path):
    captured = {}

    def _fake_ffmpeg(args, timeout=900, label="FFmpeg"):
        captured["args"] = args
        pattern = args[-1]
        for i in range(3):
            with open(pattern.replace("%04d", f"{i:04d}"), "wb") as fh:
                fh.write(b"MP3")
        return True, ""

    monkeypatch.setattr(transcription_media, "_run_ffmpeg", _fake_ffmpeg)

    paths = transcription_media.extract_audio_mp3_chunks_from_path(
        "/tmp/video.mp4", chunk_seconds=600, workdir=str(tmp_path),
    )

    assert len(paths) == 3
    assert paths == sorted(paths)
    args = captured["args"]
    # ONE re-encode pass: mono 16 kHz mp3, cut by the segment muxer — no video.
    assert "-f" in args and args[args.index("-f") + 1] == "segment"
    assert args[args.index("-segment_time") + 1] == "600"
    assert "-vn" in args and "libmp3lame" in args
    assert args[args.index("-ac") + 1] == "1"


@pytest.mark.unit
def test_extract_audio_chunks_failure_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        transcription_media, "_run_ffmpeg", lambda *a, **k: (False, "boom"),
    )
    with pytest.raises(RuntimeError):
        transcription_media.extract_audio_mp3_chunks_from_path(
            "/tmp/video.mp4", chunk_seconds=600, workdir=str(tmp_path),
        )


@pytest.mark.unit
def test_windowed_frames_seek_inside_window(monkeypatch):
    """Window mode seeks evenly INSIDE [start_ts, end_ts) — per-chunk visuals."""
    monkeypatch.setattr(transcription_media, "_get_duration", lambda p: 1200.0)

    calls = []

    def _fake_ffmpeg(args, timeout=900, label="FFmpeg"):
        calls.append(args)
        with open(args[-1], "wb") as fh:
            fh.write(b"JPEG")
        return True, ""

    monkeypatch.setattr(transcription_media, "_run_ffmpeg", _fake_ffmpeg)

    frames = transcription_media.extract_frames_jpeg_from_path(
        "/tmp/video.mp4", start_ts=600, end_ts=900, max_frames=3,
    )

    assert len(frames) == 3
    seeks = [float(a[a.index("-ss") + 1]) for a in calls]
    assert seeks == [650.0, 750.0, 850.0]  # 600 + 300·(i+0.5)/3
    for a in calls:
        assert a.index("-ss") < a.index("-i")  # input-side seek preserved
        assert "-an" in a


@pytest.mark.unit
def test_windowed_frames_empty_for_degenerate_window(monkeypatch):
    monkeypatch.setattr(transcription_media, "_get_duration", lambda p: 1200.0)
    monkeypatch.setattr(
        transcription_media, "_run_ffmpeg",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run ffmpeg")),
    )
    assert transcription_media.extract_frames_jpeg_from_path(
        "/tmp/video.mp4", start_ts=1199.5, end_ts=1200.0, max_frames=4,
    ) == []


# ---------------------------------------------------------------------------
# Celery task layer: heartbeat + CANCELLED (never retried) for both pipelines
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize(
    "pipeline_type,start_status,task_name",
    [
        (PipelineType.CLASS, Status.TRANSCRIBING, "process_class_step1_transcription"),
        (PipelineType.EXAM_PREP, Status.EXAM_TRANSCRIBING, "process_exam_prep_step1_transcription"),
    ],
)
def test_step1_abort_marks_cancelled_without_retry(monkeypatch, pipeline_type, start_status, task_name):
    from apps.classes import tasks

    session = baker.make(
        ClassCreationSession,
        pipeline_type=pipeline_type,
        status=start_status,
        source_type=ClassCreationSession.SourceType.MEDIA,
        source_mime_type="video/mp4",
    )
    monkeypatch.setattr(tasks, "_read_session_file_to_disk", lambda s: "/tmp/fake.mp4")

    calls = {"n": 0}

    def _aborting_transcribe(*, path, mime_type, progress_cb=None):
        calls["n"] += 1
        raise TranscriptionAborted("teacher cancelled")

    monkeypatch.setattr(
        "apps.classes.services.transcription.transcribe_media_file",
        _aborting_transcribe,
    )

    task = getattr(tasks, task_name)
    result = task.apply(args=[session.id]).result

    assert result["status"] == "cancelled"
    assert calls["n"] == 1  # terminal: not retried as a transient failure
    session.refresh_from_db()
    assert session.status == Status.CANCELLED


@pytest.mark.django_db
def test_step1_heartbeat_bumps_updated_at_and_detects_cancel():
    from apps.classes import tasks

    session = baker.make(
        ClassCreationSession,
        pipeline_type=PipelineType.CLASS,
        status=Status.TRANSCRIBING,
        source_type=ClassCreationSession.SourceType.MEDIA,
    )
    before = session.updated_at

    heartbeat = tasks._make_step1_heartbeat(session.id)

    # Running normally: keeps going AND refreshes updated_at so the
    # cleanup_stale_sessions reaper never kills a live chunked run.
    assert heartbeat(1, 6) is True
    session.refresh_from_db()
    assert session.updated_at > before

    # Teacher pressed cancel → next chunk boundary stops the run.
    ClassCreationSession.objects.filter(id=session.id).update(cancel_requested=True)
    assert heartbeat(2, 6) is False

    # Session deleted mid-run → stop wasting LLM calls.
    missing = tasks._make_step1_heartbeat(987_654_321)
    assert missing(1, 6) is False


@pytest.mark.django_db
def test_step1_passes_heartbeat_into_transcription(monkeypatch):
    """The Celery task must actually wire the heartbeat into the service call."""
    from apps.classes import tasks

    session = baker.make(
        ClassCreationSession,
        pipeline_type=PipelineType.CLASS,
        status=Status.TRANSCRIBING,
        source_type=ClassCreationSession.SourceType.MEDIA,
        source_mime_type="video/mp4",
    )
    monkeypatch.setattr(tasks, "_read_session_file_to_disk", lambda s: "/tmp/fake.mp4")

    captured = {}

    def _fake_transcribe(*, path, mime_type, progress_cb=None):
        captured["progress_cb"] = progress_cb
        # Simulate the service heartbeating once per chunk.
        assert progress_cb(1, 4) is True
        return "TRANSCRIPT", "avalai", "models/x"

    monkeypatch.setattr(
        "apps.classes.services.transcription.transcribe_media_file", _fake_transcribe,
    )

    result = tasks.process_class_step1_transcription.apply(args=[session.id]).result

    assert result["status"] == "success"
    assert captured["progress_cb"] is not None
    session.refresh_from_db()
    assert session.status == Status.TRANSCRIBED
