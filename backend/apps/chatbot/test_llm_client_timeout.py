"""Tests that generate_text honours `timeout` and `response_format` and no longer
hardcodes a 45s timeout or swallows the caller-supplied timeout. LLM is mocked."""
from unittest.mock import MagicMock, patch

import pytest

import apps.chatbot.services.llm_client as llm

pytestmark = pytest.mark.unit


def _fake_response(content="hello"):
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


@patch("apps.chatbot.services.llm_client.track_llm_usage")
@patch("apps.chatbot.services.llm_client._get_gapgpt_client")
def test_caller_timeout_is_forwarded(mock_factory, _mock_track):
    fake = _patched_client()
    mock_factory.return_value = fake
    res = llm.generate_text(
        messages=[{"role": "user", "content": "hi"}], model="m", feature="OTHER", timeout=123,
    )
    kwargs = fake.chat.completions.create.call_args.kwargs
    assert kwargs["timeout"] == 123
    assert res.text == "hello"


@patch("apps.chatbot.services.llm_client.track_llm_usage")
@patch("apps.chatbot.services.llm_client._get_gapgpt_client")
def test_default_timeout_is_not_45(mock_factory, _mock_track):
    fake = _patched_client()
    mock_factory.return_value = fake
    llm.generate_text(messages=[{"role": "user", "content": "hi"}], model="m", feature="OTHER")
    kwargs = fake.chat.completions.create.call_args.kwargs
    assert kwargs["timeout"] != 45
    assert kwargs["timeout"] == llm._default_llm_timeout()


@patch("apps.chatbot.services.llm_client.track_llm_usage")
@patch("apps.chatbot.services.llm_client._get_gapgpt_client")
def test_response_format_forwarded_only_when_set(mock_factory, _mock_track):
    fake = _patched_client()
    mock_factory.return_value = fake

    llm.generate_text(messages=[{"role": "user", "content": "hi"}], model="m", feature="OTHER")
    assert "response_format" not in fake.chat.completions.create.call_args.kwargs

    llm.generate_text(
        messages=[{"role": "user", "content": "hi"}], model="m", feature="OTHER",
        response_format={"type": "json_object"},
    )
    assert fake.chat.completions.create.call_args.kwargs["response_format"] == {"type": "json_object"}


@patch("apps.chatbot.services.llm_client.track_llm_usage")
@patch("apps.chatbot.services.llm_client._get_gapgpt_client")
def test_temperature_forwarded_only_when_set(mock_factory, _mock_track):
    fake = _patched_client()
    mock_factory.return_value = fake

    llm.generate_text(messages=[{"role": "user", "content": "hi"}], model="m", feature="OTHER")
    assert "temperature" not in fake.chat.completions.create.call_args.kwargs

    llm.generate_text(
        messages=[{"role": "user", "content": "hi"}],
        model="m",
        feature="OTHER",
        temperature=0,
    )
    assert fake.chat.completions.create.call_args.kwargs["temperature"] == 0


class _StatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class _ResponseStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.response = MagicMock(status_code=status_code)


@pytest.mark.parametrize("status_code", [408, 409, 429, 500, 502, 503, 504])
def test_llm_transient_classifier_retries_provider_and_transport_failures(status_code):
    assert llm.is_transient_llm_error(_StatusError(status_code)) is True
    assert llm.is_transient_llm_error(_ResponseStatusError(status_code)) is True


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_llm_transient_classifier_does_not_retry_permanent_http_errors(status_code):
    assert llm.is_transient_llm_error(_StatusError(status_code)) is False


def test_llm_transient_classifier_does_not_retry_response_format_rejection():
    assert llm.is_transient_llm_error(
        RuntimeError("400: response_format is not supported by this model")
    ) is False
