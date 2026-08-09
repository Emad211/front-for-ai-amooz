from __future__ import annotations

import base64
import io
import json

import pytest
from pypdf import PdfReader, PdfWriter

from apps.classes.services.exam_prep_mistral_ocr_transport import (
    HTTPResponse,
    MistralOCR4Config,
    MistralOCR4ProviderError,
    fetch_ocr4_document,
    plan_pdf_chunks,
)


def _pdf(page_count: int) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _payload_page_count(payload) -> int:
    encoded = payload["document"]["document_url"].split(",", 1)[1]
    data = base64.b64decode(encoded)
    return len(PdfReader(io.BytesIO(data)).pages)


def _ok(payload, *, request_id="req", cost="0.01") -> HTTPResponse:
    count = _payload_page_count(payload)
    root = {
        "model": "mistral-ocr-4-0",
        "pages": [
            {"index": index, "blocks": [{"type": "text", "content": str(index)}]}
            for index in range(count)
        ],
        "estimated_cost": {"unit": cost},
    }
    return HTTPResponse(
        200,
        {"x-request-id": request_id},
        json.dumps(root).encode("utf-8"),
    )


class MemoryCheckpointStore:
    def __init__(self):
        self.values = {}

    def _key(self, *, source_sha256, contract_fingerprint, chunk):
        return source_sha256, contract_fingerprint, chunk.index, chunk.sha256

    def load(self, **kwargs):
        return self.values.get(self._key(**kwargs))

    def save(self, *, payload, **kwargs):
        self.values[self._key(**kwargs)] = payload

    def delete(self, **kwargs):
        self.values.pop(self._key(**kwargs), None)


def _config(**overrides):
    base = dict(
        max_attempts=2,
        retry_backoff_seconds=0,
        retry_jitter_seconds=0,
        checkpoint_enabled=True,
    )
    base.update(overrides)
    return MistralOCR4Config(**base)


def test_55_pages_plan_as_30_plus_25_before_network():
    chunks = plan_pdf_chunks(_pdf(55))
    assert [chunk.physical_pages for chunk in chunks] == [
        tuple(range(1, 31)),
        tuple(range(31, 56)),
    ]


def test_transient_502_retries_only_current_chunk():
    calls = []

    def transport(_url, _headers, payload, _timeout):
        calls.append(_payload_page_count(payload))
        if len(calls) == 1:
            return HTTPResponse(502, {}, b"bad gateway")
        return _ok(payload, request_id="req-ok")

    result = fetch_ocr4_document(
        _pdf(2),
        config=_config(max_pages_per_request=30),
        api_key="test",
        checkpoint_store=MemoryCheckpointStore(),
        transport=transport,
        sleeper=lambda _seconds: None,
    )

    assert calls == [2, 2]
    assert result.provider_call_count == 2
    assert result.retry_count == 1
    assert [page["sourcePhysicalPage"] for page in result.pages] == [1, 2]


@pytest.mark.parametrize("status", [400, 409])
def test_request_or_conflict_errors_are_never_retried(status):
    calls = []

    def transport(_url, _headers, _payload, _timeout):
        calls.append(status)
        return HTTPResponse(status, {}, b"{}")

    with pytest.raises(MistralOCR4ProviderError) as captured:
        fetch_ocr4_document(
            _pdf(1),
            config=_config(max_attempts=3),
            api_key="test",
            checkpoint_store=MemoryCheckpointStore(),
            transport=transport,
            sleeper=lambda _seconds: None,
        )

    assert calls == [status]
    assert captured.value.retryable is False
    assert captured.value.attempts == 1


def test_successful_first_chunk_is_reused_after_later_chunk_failure():
    data = _pdf(31)
    store = MemoryCheckpointStore()
    first_run_calls = []

    def first_transport(_url, _headers, payload, _timeout):
        page_count = _payload_page_count(payload)
        first_run_calls.append(page_count)
        if page_count == 1:
            return HTTPResponse(400, {}, b"{}")
        return _ok(payload, request_id="chunk-1")

    with pytest.raises(MistralOCR4ProviderError):
        fetch_ocr4_document(
            data,
            config=_config(max_attempts=1),
            api_key="test",
            checkpoint_store=store,
            transport=first_transport,
        )
    assert first_run_calls == [30, 1]

    second_run_calls = []

    def second_transport(_url, _headers, payload, _timeout):
        second_run_calls.append(_payload_page_count(payload))
        return _ok(payload, request_id="chunk-2")

    result = fetch_ocr4_document(
        data,
        config=_config(max_attempts=1),
        api_key="test",
        checkpoint_store=store,
        transport=second_transport,
    )

    assert second_run_calls == [1]
    assert result.checkpoint_reuse_count == 1
    assert result.provider_call_count == 1
    assert len(result.pages) == 31
    assert [page["sourcePhysicalPage"] for page in result.pages] == list(range(1, 32))


def test_missing_page_in_success_response_fails_without_retry_or_checkpoint():
    store = MemoryCheckpointStore()
    calls = []

    def transport(_url, _headers, _payload, _timeout):
        calls.append(1)
        root = {"model": "mistral-ocr-4-0", "pages": [{"index": 0}]}
        return HTTPResponse(200, {}, json.dumps(root).encode())

    with pytest.raises(MistralOCR4ProviderError) as captured:
        fetch_ocr4_document(
            _pdf(2),
            config=_config(max_attempts=3),
            api_key="test",
            checkpoint_store=store,
            transport=transport,
        )

    assert calls == [1]
    assert captured.value.retryable is False
    assert store.values == {}
