"""The transcription call must use the STANDARD OpenAI multimodal shape
(`input_audio` + `image_url`), never the legacy `attachments/input_media/
data_base64` shape that the Avalai gateway silently ignores.

ffmpeg extraction and the LLM call are mocked — no ffmpeg, no network, no tokens.
"""
import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.classes.services import transcription
from apps.classes.services.transcription import _build_transcription_messages

pytestmark = pytest.mark.unit


def test_build_messages_uses_standard_shape():
    msgs = _build_transcription_messages(
        prompt="P", audio_b64="AAA", audio_format="mp3", frames_b64=["F1", "F2"],
    )
    content = msgs[0]["content"]
    assert content[0] == {"type": "text", "text": "P"}
    assert content[1] == {"type": "input_audio", "input_audio": {"data": "AAA", "format": "mp3"}}
    assert content[2]["type"] == "image_url"
    assert content[2]["image_url"]["url"] == "data:image/jpeg;base64,F1"
    # No legacy keys anywhere.
    blob = json.dumps(msgs)
    for legacy in ("attachments", "input_media", "data_base64"):
        assert legacy not in blob


def test_build_messages_audio_only_has_no_images():
    msgs = _build_transcription_messages(
        prompt="P", audio_b64="AAA", audio_format="mp3", frames_b64=[],
    )
    types = [c["type"] for c in msgs[0]["content"]]
    assert types == ["text", "input_audio"]


@patch("apps.classes.services.transcription.generate_text")
@patch("apps.classes.services.transcription.extract_frames_jpeg")
@patch("apps.classes.services.transcription.extract_audio_mp3")
def test_video_sends_audio_and_frames(mock_audio, mock_frames, mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/gemini-2.5-flash")
    mock_audio.return_value = (b"AUDIOBYTES", "mp3")
    mock_frames.return_value = [b"FRAME1", b"FRAME2"]
    mock_gen.return_value = SimpleNamespace(text="TRANSCRIPT")

    transcript, provider, model = transcription.transcribe_media_bytes(
        data=b"rawvideo", mime_type="video/mp4",
    )

    assert transcript == "TRANSCRIPT"
    assert model == "models/gemini-2.5-flash"
    mock_audio.assert_called_once()
    mock_frames.assert_called_once()

    messages = mock_gen.call_args.kwargs["messages"]
    content = messages[0]["content"]
    kinds = [c["type"] for c in content]
    assert kinds == ["text", "input_audio", "image_url", "image_url"]
    assert content[1]["input_audio"]["data"] == base64.b64encode(b"AUDIOBYTES").decode()
    assert content[2]["image_url"]["url"] == "data:image/jpeg;base64," + base64.b64encode(b"FRAME1").decode()
    # timeout is now forwarded (no longer swallowed/hardcoded).
    assert mock_gen.call_args.kwargs.get("timeout") == transcription._LLM_TIMEOUT_SECONDS


@patch("apps.classes.services.transcription.generate_text")
@patch("apps.classes.services.transcription.extract_frames_jpeg")
@patch("apps.classes.services.transcription.extract_audio_mp3")
def test_audio_input_skips_frame_extraction(mock_audio, mock_frames, mock_gen, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "models/gemini-2.5-flash")
    mock_audio.return_value = (b"AUDIOBYTES", "mp3")
    mock_gen.return_value = SimpleNamespace(text="T")

    transcription.transcribe_media_bytes(data=b"rawaudio", mime_type="audio/ogg")

    mock_frames.assert_not_called()
    content = mock_gen.call_args.kwargs["messages"][0]["content"]
    assert [c["type"] for c in content] == ["text", "input_audio"]
