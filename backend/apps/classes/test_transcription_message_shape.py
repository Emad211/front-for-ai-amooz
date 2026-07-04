"""Direct unit tests for the Avalai/OpenAI multimodal message BUILDER
(`_build_transcription_messages`).

The chunked-flow tests assert the shape end-to-end through mocks; this pins the
builder itself and — most importantly — asserts the **legacy shape is gone**.
Per avalai-multimodal-format.md: the gateway silently ignores the old
``attachments:[{type:input_media,data_base64}]`` shape, which produced
hallucinated/empty transcripts. So a byte-for-byte guard that the built message
uses ONLY the standard ``input_audio`` / ``image_url`` content parts — and none of
the legacy keys anywhere — is the regression lock. Pure unit, 0-token, no media.
"""
from __future__ import annotations

import json

import pytest

from apps.classes.services.transcription import _build_transcription_messages

pytestmark = pytest.mark.unit


def _content(messages):
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    return messages[0]["content"]


def test_video_shape_is_text_audio_then_frames():
    msgs = _build_transcription_messages(
        prompt='transcribe', audio_b64='AUDIO', audio_format='mp3',
        frames_b64=['F1', 'F2'],
    )
    content = _content(msgs)
    assert [c['type'] for c in content] == ['text', 'input_audio', 'image_url', 'image_url']
    assert content[1]['input_audio'] == {'data': 'AUDIO', 'format': 'mp3'}
    assert content[2]['image_url']['url'] == 'data:image/jpeg;base64,F1'
    assert content[3]['image_url']['url'] == 'data:image/jpeg;base64,F2'


def test_audio_only_has_no_image_parts():
    msgs = _build_transcription_messages(
        prompt='p', audio_b64='A', audio_format='mp3', frames_b64=[],
    )
    content = _content(msgs)
    assert [c['type'] for c in content] == ['text', 'input_audio']


def test_no_audio_yields_text_only_when_frames_empty():
    msgs = _build_transcription_messages(
        prompt='p', audio_b64='', audio_format='mp3', frames_b64=[],
    )
    content = _content(msgs)
    assert [c['type'] for c in content] == ['text']


def test_legacy_attachments_shape_is_absent():
    """The exact bug guard: none of the silently-ignored legacy keys may appear."""
    msgs = _build_transcription_messages(
        prompt='p', audio_b64='A', audio_format='mp3', frames_b64=['F1'],
    )
    blob = json.dumps(msgs)
    for legacy in ('attachments', 'input_media', 'data_base64', 'inline_data', 'mime_type'):
        assert legacy not in blob, f'legacy multimodal key {legacy!r} leaked into the request'
    # And the standard keys ARE present.
    assert 'input_audio' in blob and 'image_url' in blob


def test_image_format_override_is_honored():
    msgs = _build_transcription_messages(
        prompt='p', audio_b64='', audio_format='mp3', frames_b64=['X'],
        image_format='png',
    )
    content = _content(msgs)
    assert content[1]['image_url']['url'] == 'data:image/png;base64,X'
