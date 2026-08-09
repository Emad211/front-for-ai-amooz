from __future__ import annotations

import pytest

from apps.classes.management.commands import replay_exam_prep_mistral_stage4_page_batch_live as live
from apps.classes.services.exam_prep_mistral_page_batch_transcriber import (
    BatchItem,
    PageBatchEnvelopeError,
    PageBatchResult,
)
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision


def _decision(number: int):
    return RegionRiskDecision(
        question_number=number,
        kind="solution",
        page_number=40,
        bbox=(0.1, 0.1, 0.8, 0.5),
        score=80,
        suspicious=True,
        hard_math=True,
        signals=("source_corruption",),
        region_issues=(),
        candidate_text="candidate",
    )


def _item(number: int):
    return BatchItem(
        target_id=f"s-{number:03d}-p040",
        kind="solution",
        question_number=number,
        question_text_markdown="",
        options=[],
        correct_option_label="2",
        teacher_solution_markdown="source",
        source_visual_required=False,
        visual_type="none",
        transcription_uncertain=False,
        uncertain_spans=[],
        uncertain_fragments=[],
    )


def test_partial_batch_round_trip_preserves_missing_ids():
    value = PageBatchResult(
        page_number=40,
        model="gemini-3-flash-preview",
        items=(_item(52),),
        request_id="req",
        usage={"inputTokens": 1, "outputTokens": 2, "reasoningTokens": 0, "totalTokens": 3},
        estimated_cost={"unit": 0.001, "irt": 10.0},
        requested_target_ids=("s-052-p040", "s-053-p040"),
        missing_target_ids=("s-053-p040",),
        invalid_target_ids=(),
    )
    restored = live._deserialize_batch(live._serialize_batch(value))
    assert restored.requested_target_ids == value.requested_target_ids
    assert restored.missing_target_ids == value.missing_target_ids
    assert restored.invalid_target_ids == ()


def test_cached_envelope_failure_is_replayed_without_new_network_call(tmp_path):
    calls = []
    counters = {}

    def base_call(**_kwargs):
        calls.append(1)
        raise PageBatchEnvelopeError(
            "structured_json_invalid",
            usage={"inputTokens": 100, "outputTokens": 50, "reasoningTokens": 0, "totalTokens": 150},
            estimated_cost={"unit": 0.004, "irt": 400.0},
            request_id="req-failed",
        )

    cached = live._cached_page_batch(
        cache_dir=tmp_path,
        base_call=base_call,
        counters=counters,
    )
    kwargs = {
        "page_number": 40,
        "targets": [(_decision(52), b"a"), (_decision(53), b"b")],
        "model": "gemini-3-flash-preview",
    }
    with pytest.raises(PageBatchEnvelopeError, match="structured_json_invalid"):
        cached(**kwargs)
    with pytest.raises(PageBatchEnvelopeError, match="structured_json_invalid"):
        cached(**kwargs)

    assert calls == [1]
    assert counters["networkPageRequests"] == 1
    assert counters["pageCacheHits"] == 1
    assert counters["networkEstimatedCostUnit"] == pytest.approx(0.004)
    assert counters["logicalEstimatedCostUnit"] == pytest.approx(0.008)
