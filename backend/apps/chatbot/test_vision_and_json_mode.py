"""Tests for the multimodal-delivery fix + JSON-mode in the LLM client.

All LLM calls mocked — no network, no tokens.
"""
from unittest.mock import MagicMock, patch

import pytest

import apps.chatbot.services.llm_client as llm

pytestmark = pytest.mark.unit


def _fake_response(content="ok"):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    return resp


def _patched_client():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_response()
    return fake_client


# ---------------------------------------------------------------------------
# part_from_bytes — standard OpenAI shapes (NOT the ignored legacy shape)
# ---------------------------------------------------------------------------

def test_part_from_bytes_image_is_data_uri_image_url():
    part = llm.part_from_bytes(data=b"\x89PNG\r\n", mime_type="image/png")
    assert part["type"] == "image_url"
    assert part["image_url"]["url"].startswith("data:image/png;base64,")
    # never the legacy shape the gateway ignores
    assert "input_file" not in part.values()


def test_part_from_bytes_audio_is_input_audio():
    part = llm.part_from_bytes(data=b"ID3stuff", mime_type="audio/mpeg")
    assert part["type"] == "input_audio"
    assert part["input_audio"]["format"] == "mp3"
    assert part["input_audio"]["data"]  # base64 string


# ---------------------------------------------------------------------------
# content normalization — raw strings in a list become text parts
# ---------------------------------------------------------------------------

def test_normalize_content_wraps_raw_strings():
    media = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}}
    out = llm._normalize_content(["please read this", media])
    assert out[0] == {"type": "text", "text": "please read this"}
    assert out[1] is media  # media part passes through unchanged


def test_normalize_content_leaves_plain_string():
    assert llm._normalize_content("just text") == "just text"


@patch("apps.chatbot.services.llm_client.track_llm_usage")
@patch("apps.chatbot.services.llm_client._get_gapgpt_client")
def test_multimodal_contents_sent_as_typed_parts(mock_factory, _mock_track):
    fake = _patched_client()
    mock_factory.return_value = fake
    media = llm.part_from_bytes(data=b"x", mime_type="image/jpeg")
    llm.generate_text(contents=["caption", media], feature="OTHER")
    sent = fake.chat.completions.create.call_args.kwargs["messages"]
    content = sent[0]["content"]
    # every list item is a typed part (no bare string)
    assert all(isinstance(p, dict) and "type" in p for p in content)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"


# ---------------------------------------------------------------------------
# generate_json — JSON mode + graceful fallback
# ---------------------------------------------------------------------------

@patch("apps.chatbot.services.llm_client.track_llm_usage")
@patch("apps.chatbot.services.llm_client._get_gapgpt_client")
def test_generate_json_requests_json_object_mode(mock_factory, _mock_track):
    fake = MagicMock()
    fake.chat.completions.create.return_value = _fake_response('{"a": 1}')
    mock_factory.return_value = fake
    out = llm.generate_json(feature="OTHER", contents="make json")
    assert out == {"a": 1}
    assert fake.chat.completions.create.call_args.kwargs["response_format"] == {"type": "json_object"}


@patch("apps.chatbot.services.llm_client.track_llm_usage")
@patch("apps.chatbot.services.llm_client.track_llm_error")
@patch("apps.chatbot.services.llm_client._get_gapgpt_client")
def test_generate_json_falls_back_when_response_format_unsupported(mock_factory, _err, _mock_track):
    calls = {"n": 0}

    def create(**kwargs):
        calls["n"] += 1
        if "response_format" in kwargs:
            raise RuntimeError("400: response_format is not supported by this model")
        return _fake_response('{"ok": true}')

    fake = MagicMock()
    fake.chat.completions.create.side_effect = create
    mock_factory.return_value = fake

    out = llm.generate_json(feature="OTHER", contents="x")
    assert out == {"ok": True}
    # first attempt (json mode) raised, retried without it
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# memory summary — no str.format crash on braces in chat text
# ---------------------------------------------------------------------------

def test_memory_safe_template_replace_survives_braces():
    from apps.chatbot.services.memory_service import _safe_template_replace

    tpl = "Old: {old_summary}\nNew: {new_turns}"
    # new_turns contains literal braces (LaTeX/code) that would crash str.format
    out = _safe_template_replace(
        tpl, {"old_summary": "s", "new_turns": "user: solve {x} where f(x)={x^2}"}
    )
    assert "solve {x} where f(x)={x^2}" in out
    assert "{old_summary}" not in out
