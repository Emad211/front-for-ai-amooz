from __future__ import annotations

import pytest

from apps.classes.services.exam_prep_mistral_page_batch_transcriber import (
    PageBatchEnvelopeError,
)
from apps.classes.services.exam_prep_mistral_page_batch_transcriber_v2 import (
    _normalize_items_envelope,
    _response_schema_for,
    _validate_items_with_identity_fallback,
)
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision


def _decision(number: int, *, kind: str = "question") -> RegionRiskDecision:
    return RegionRiskDecision(
        question_number=number,
        kind=kind,
        page_number=6,
        bbox=(0.1, 0.1, 0.8, 0.7),
        score=80,
        suspicious=True,
        hard_math=False,
        signals=("ocr_disagreement",),
        region_issues=(),
        candidate_text="candidate",
    )


def _raw_item(decision: RegionRiskDecision, *, target_id: str | None = None):
    return {
        "target_id": decision.target_id if target_id is None else target_id,
        "kind": decision.kind,
        "question_number": decision.question_number,
        "question_text_markdown": "متن سؤال",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "",
        "teacher_solution_markdown": "",
        "source_visual_required": False,
        "visual_type": "none",
        "transcription_uncertain": False,
        "uncertain_spans": [],
        "uncertain_fragments": [],
    }


def test_normalize_accepts_canonical_items_object():
    raw = {"items": [{"target_id": "q-1"}]}
    assert _normalize_items_envelope(raw, target_count=1) is raw


def test_normalize_accepts_bare_item_array_losslessly():
    raw = [{"target_id": "q-1"}, {"target_id": "q-2"}]
    assert _normalize_items_envelope(raw, target_count=2) == {"items": raw}


def test_normalize_accepts_single_item_object_only_for_one_target():
    raw = {"target_id": "q-1", "kind": "question"}
    assert _normalize_items_envelope(raw, target_count=1) == {"items": [raw]}
    with pytest.raises(PageBatchEnvelopeError):
        _normalize_items_envelope(raw, target_count=2)


def test_normalize_rejects_unknown_wrapper_fail_closed():
    with pytest.raises(PageBatchEnvelopeError) as exc:
        _normalize_items_envelope({"results": []}, target_count=1)
    assert "object_keys=results" in exc.value.reason_code


def test_request_specific_schema_requires_exact_item_count_and_target_ids():
    decisions = [_decision(21), _decision(22)]
    schema = _response_schema_for(decisions)
    items = schema["properties"]["items"]
    item = items["items"]
    assert items["minItems"] == 2
    assert items["maxItems"] == 2
    assert item["properties"]["target_id"]["enum"] == [
        decisions[0].target_id,
        decisions[1].target_id,
    ]
    assert item["properties"]["question_number"]["enum"] == [21, 22]


def test_unique_kind_and_question_number_recovers_changed_target_id_losslessly():
    decision = _decision(21)
    raw = {"items": [_raw_item(decision, target_id="invented-id")]}
    items, missing, invalid = _validate_items_with_identity_fallback(
        raw, decisions=[decision]
    )
    assert [item.target_id for item in items] == [decision.target_id]
    assert missing == ()
    assert invalid == ()


def test_ambiguous_identity_never_guesses():
    first = _decision(21)
    second = RegionRiskDecision(
        question_number=21,
        kind="question",
        page_number=6,
        bbox=(0.2, 0.2, 0.7, 0.6),
        score=80,
        suspicious=True,
        hard_math=False,
        signals=("ocr_disagreement",),
        region_issues=(),
        candidate_text="candidate-2",
    )
    # Force two distinct requested IDs with the same semantic identity to prove
    # the fallback refuses to choose between them.
    second = second.__class__(
        question_number=second.question_number,
        kind=second.kind,
        page_number=7,
        bbox=second.bbox,
        score=second.score,
        suspicious=second.suspicious,
        hard_math=second.hard_math,
        signals=second.signals,
        region_issues=second.region_issues,
        candidate_text=second.candidate_text,
    )
    raw = {"items": [_raw_item(first, target_id="invented-id")]}
    items, missing, invalid = _validate_items_with_identity_fallback(
        raw, decisions=[first, second]
    )
    assert items == ()
    assert set(missing) == {first.target_id, second.target_id}
    assert invalid == ()
