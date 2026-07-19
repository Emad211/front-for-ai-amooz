"""Tests for the central structured-output layer (apps.commons.structured_llm).

All LLM calls are mocked — no network, no tokens.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ConfigDict, Field

from apps.commons import structured_llm
from apps.commons.structured_llm import (
    StructuredOutputError,
    generate_structured,
    parse_structured,
    validate_keep_dict,
)

pytestmark = pytest.mark.unit


class _Model(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    items: list[str] = Field(default_factory=list)


def _result(text: str):
    return SimpleNamespace(text=text, provider="test", model="m")


# --------------------------------------------------------------------------
# parse / validate (no LLM)
# --------------------------------------------------------------------------

def test_parse_structured_valid():
    m = parse_structured('{"name": "x", "items": ["a"]}', _Model)
    assert m.name == "x"
    assert m.items == ["a"]


def test_parse_structured_wrong_shape_raises():
    with pytest.raises(StructuredOutputError):
        parse_structured('{"items": ["a"]}', _Model)  # missing required 'name'


def test_parse_structured_non_json_raises():
    with pytest.raises(StructuredOutputError):
        parse_structured("I could not produce JSON, sorry.", _Model)


def test_validate_keep_dict_returns_original_dict():
    raw = '{"name": "x", "extra": 7, "items": ["a"]}'
    out = validate_keep_dict(raw, _Model)
    assert out == {"name": "x", "extra": 7, "items": ["a"]}  # original, not normalized


def test_validate_keep_dict_wrong_shape_raises():
    with pytest.raises(StructuredOutputError):
        validate_keep_dict('["not", "an", "object"]', _Model)


# --------------------------------------------------------------------------
# generate_structured (LLM mocked)
# --------------------------------------------------------------------------

def test_generate_structured_happy_path():
    with patch("apps.chatbot.services.llm_client.generate_text") as gt:
        gt.return_value = _result('{"name": "ok", "items": ["a", "b"]}')
        m = generate_structured(schema=_Model, contents="make json", feature="OTHER")
    assert m.name == "ok"
    assert m.items == ["a", "b"]
    assert gt.call_count == 1
    # JSON mode requested on the first attempt
    assert gt.call_args.kwargs.get("response_format") == {"type": "json_object"}


def test_generate_structured_forwards_temperature_to_all_calls():
    with patch("apps.chatbot.services.llm_client.generate_text") as gt:
        gt.return_value = _result('{"name": "ok", "items": []}')
        generate_structured(
            schema=_Model, contents="make json", feature="OTHER", temperature=0,
        )
    assert gt.call_args.kwargs["temperature"] == 0


def test_generate_structured_repairs_then_succeeds():
    calls = []

    def side_effect(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _result("here is your answer (not json)")
        return _result('{"name": "fixed", "items": []}')

    with patch("apps.chatbot.services.llm_client.generate_text", side_effect=side_effect):
        m = generate_structured(schema=_Model, contents="x", feature="OTHER", max_repair=1)
    assert m.name == "fixed"
    assert len(calls) == 2  # original + one repair round-trip


def test_generate_structured_raises_after_exhausting_repairs():
    with patch("apps.chatbot.services.llm_client.generate_text") as gt:
        gt.return_value = _result("never valid json")
        with pytest.raises(StructuredOutputError):
            generate_structured(schema=_Model, contents="x", feature="OTHER", max_repair=1)
    assert gt.call_count == 2  # original + one repair, both bad -> raise


def test_generate_structured_falls_back_when_response_format_unsupported():
    def side_effect(**kwargs):
        if kwargs.get("response_format") is not None:
            raise RuntimeError("400: response_format is not supported by this model")
        return _result('{"name": "ok"}')

    with patch("apps.chatbot.services.llm_client.generate_text", side_effect=side_effect) as gt:
        m = generate_structured(schema=_Model, contents="x", feature="OTHER")
    assert m.name == "ok"
    # first call with json mode (raised), second without it (succeeded)
    assert gt.call_count == 2
    assert gt.call_args_list[0].kwargs.get("response_format") == {"type": "json_object"}
    assert gt.call_args_list[1].kwargs.get("response_format") is None


def test_generate_structured_does_not_swallow_unrelated_errors():
    with patch("apps.chatbot.services.llm_client.generate_text") as gt:
        gt.side_effect = RuntimeError("SSL: UNEXPECTED_EOF_WHILE_READING")
        with pytest.raises(RuntimeError):
            generate_structured(schema=_Model, contents="x", feature="OTHER")
    # Only the first attempt; a genuine connection error is NOT treated as a
    # response_format fallback, so no second call.
    assert gt.call_count == 1
