from __future__ import annotations

import json
import pytest

from apps.classes.services.exam_prep_mistral_page_batch_transcriber import (
    _decode_structured_text,
)


def test_decoder_accepts_plain_and_fenced_json():
    payload = {"items": [{"target_id": "s-001-p001"}]}
    text = json.dumps(payload, ensure_ascii=False)
    assert _decode_structured_text(text) == payload
    assert _decode_structured_text(f"```json\n{text}\n```") == payload


def test_decoder_escapes_raw_control_chars_inside_string_only():
    text = '{"items":[{"teacher_solution_markdown":"خط اول\nخط دوم"}]}'
    decoded = _decode_structured_text(text)
    assert decoded["items"][0]["teacher_solution_markdown"] == "خط اول\nخط دوم"


def test_decoder_removes_only_trailing_syntactic_commas():
    text = '{"items":[{"target_id":"q-1",},],}'
    assert _decode_structured_text(text) == {"items": [{"target_id": "q-1"}]}


def test_decoder_accepts_one_complete_root_with_harmless_wrapper():
    text = 'JSON response:\n{"items":[]}\n```'
    assert _decode_structured_text(text) == {"items": []}


def test_decoder_rejects_semantically_incomplete_json():
    with pytest.raises(json.JSONDecodeError):
        _decode_structured_text('{"items":[{"target_id":"q-1"}')
