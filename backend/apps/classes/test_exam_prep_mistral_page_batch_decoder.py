from __future__ import annotations

import json
import pytest

from apps.classes.services.exam_prep_mistral_json_lexical import (
    decode_structured_json_text,
)


def test_decoder_accepts_plain_and_fenced_json():
    payload = {"items": [{"target_id": "s-001-p001"}]}
    text = json.dumps(payload, ensure_ascii=False)
    assert decode_structured_json_text(text) == payload
    assert decode_structured_json_text(f"```json\n{text}\n```") == payload


def test_decoder_escapes_raw_control_chars_inside_string_only():
    text = '{"items":[{"teacher_solution_markdown":"خط اول\nخط دوم"}]}'
    decoded = decode_structured_json_text(text)
    assert decoded["items"][0]["teacher_solution_markdown"] == "خط اول\nخط دوم"


def test_decoder_preserves_raw_latex_backslashes_in_malformed_provider_json():
    # Deliberately use single raw backslashes in the JSON source. ``\\frac`` and
    # ``\\text`` would otherwise be interpreted as JSON form-feed/tab escapes.
    text = r'{"items":[{"teacher_solution_markdown":"\frac{1}{2}+\sqrt{x}+\text{m}"}]}'
    decoded = decode_structured_json_text(text)
    assert decoded["items"][0]["teacher_solution_markdown"] == r"\frac{1}{2}+\sqrt{x}+\text{m}"


def test_decoder_removes_only_trailing_syntactic_commas():
    text = '{"items":[{"target_id":"q-1",},],}'
    assert decode_structured_json_text(text) == {"items": [{"target_id": "q-1"}]}


def test_decoder_accepts_one_complete_root_with_harmless_wrapper():
    text = 'JSON response:\n{"items":[]}\n```'
    assert decode_structured_json_text(text) == {"items": []}


def test_decoder_rejects_semantically_incomplete_json():
    with pytest.raises(json.JSONDecodeError):
        decode_structured_json_text('{"items":[{"target_id":"q-1"}')
