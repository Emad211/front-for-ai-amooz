from __future__ import annotations

import pytest

from apps.classes.management.commands.replay_exam_prep_mistral_stage4_live import (
    _cached_transcriber,
)
from apps.classes.services.exam_prep_mistral_region_transcriber import (
    RegionTranscriptionResult,
)


def _result(*, model="gemini-3-flash-preview"):
    return RegionTranscriptionResult(
        kind="solution",
        question_number=81,
        page_number=44,
        model=model,
        transcript={
            "transcriptionMarkdown": "پاسخ",
            "sourceVisualRequired": False,
            "visualType": "none",
            "transcriptionUncertain": False,
            "uncertainFragments": [],
        },
        response_id="resp-1",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        reasoning_tokens=0,
    )


def _kwargs():
    return {
        "image": b"png",
        "kind": "solution",
        "question_number": 81,
        "page_number": 44,
        "model": "gemini-3-flash-preview",
        "thinking_minimal": True,
    }


def test_successful_provider_call_is_reused_without_second_network_request(tmp_path):
    calls = []
    counters = {}

    def base_call(**kwargs):
        calls.append(kwargs)
        return _result(model=kwargs["model"])

    cached = _cached_transcriber(
        cache_dir=tmp_path,
        base_call=base_call,
        counters=counters,
    )

    first = cached(**_kwargs())
    second = cached(**_kwargs())

    assert first.transcript == second.transcript
    assert len(calls) == 1
    assert counters["networkRequests"] == 1
    assert counters["cacheHits"] == 1


def test_failed_provider_call_is_checkpointed_and_not_retried_on_resume(tmp_path):
    calls = []
    counters = {}

    def base_call(**kwargs):
        calls.append(kwargs)
        raise ValueError("non-conforming JSON")

    cached = _cached_transcriber(
        cache_dir=tmp_path,
        base_call=base_call,
        counters=counters,
    )

    with pytest.raises(ValueError, match="non-conforming JSON"):
        cached(**_kwargs())
    with pytest.raises(RuntimeError, match="cached_stage4_provider_failure"):
        cached(**_kwargs())

    assert len(calls) == 1
    assert counters["networkRequests"] == 1
    assert counters["cacheHits"] == 1
