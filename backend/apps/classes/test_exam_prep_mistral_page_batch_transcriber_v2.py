from __future__ import annotations

import pytest

from apps.classes.services.exam_prep_mistral_page_batch_transcriber import (
    PageBatchEnvelopeError,
)
from apps.classes.services.exam_prep_mistral_page_batch_transcriber_v2 import (
    _backfill_request_metadata,
    _generation_config,
    _image_part_high,
    _normalize_items_envelope,
    _require_image_provenance,
    _usage_with_modalities,
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


def test_restored_generation_config_uses_proven_response_schema_contract():
    config = _generation_config(3200)
    assert "responseSchema" in config
    assert "responseJsonSchema" not in config
    assert config["responseMimeType"] == "application/json"


def test_image_part_forces_high_media_resolution_without_changing_crop_bytes():
    part = _image_part_high(b"png")
    assert part["inlineData"]["mimeType"] == "image/png"
    assert part["inlineData"]["data"]
    assert part["mediaResolution"] == {"level": "media_resolution_high"}


def test_usage_with_modalities_records_processed_image_tokens():
    root = {
        "usageMetadata": {
            "promptTokenCount": 1500,
            "candidatesTokenCount": 100,
            "totalTokenCount": 1600,
            "promptTokensDetails": [
                {"modality": "TEXT", "tokenCount": 300},
                {"modality": "IMAGE", "tokenCount": 1200},
            ],
        }
    }
    usage = _usage_with_modalities(root)
    assert usage["promptModalityDetailsPresent"] == 1
    assert usage["textInputTokens"] == 300
    assert usage["imageInputTokens"] == 1200


def test_usage_with_modalities_accepts_snake_case_provider_shape():
    root = {
        "usageMetadata": {
            "prompt_tokens_details": [
                {"modality": "IMAGE", "token_count": 1120},
            ]
        }
    }
    assert _usage_with_modalities(root)["imageInputTokens"] == 1120


def test_image_provenance_is_hard_gate():
    proven = {
        "usageMetadata": {
            "promptTokensDetails": [{"modality": "IMAGE", "tokenCount": 1120}]
        }
    }
    usage = _require_image_provenance(proven, request_id="req", finish_reason="STOP")
    assert usage["imageInputTokens"] == 1120

    with pytest.raises(PageBatchEnvelopeError) as absent:
        _require_image_provenance({}, request_id="req", finish_reason="STOP")
    assert "no_prompt_modality_details" in absent.value.reason_code

    zero = {
        "usageMetadata": {
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 330}]
        }
    }
    with pytest.raises(PageBatchEnvelopeError) as text_only:
        _require_image_provenance(zero, request_id="req", finish_reason="STOP")
    assert "image_tokens_zero" in text_only.value.reason_code


def test_unique_kind_and_question_number_recovers_changed_target_id_losslessly():
    decision = _decision(21)
    raw = {"items": [_raw_item(decision, target_id="invented-id")]}
    items, missing, invalid = _validate_items_with_identity_fallback(
        raw, decisions=[decision]
    )
    assert [item.target_id for item in items] == [decision.target_id]
    assert missing == ()
    assert invalid == ()


def test_request_known_metadata_can_be_backfilled_but_content_is_never_invented():
    decision = _decision(21)
    raw = {
        "target_id": decision.target_id,
        "question_text_markdown": "متن",
        "options": [],
        "correct_option_label": "",
        "teacher_solution_markdown": "",
    }
    normalized = _backfill_request_metadata(raw, decision=decision)
    assert normalized["kind"] == "question"
    assert normalized["question_number"] == 21
    assert normalized["source_visual_required"] is False
    assert normalized["visual_type"] == "none"
    assert normalized["question_text_markdown"] == "متن"
    assert normalized["options"] == []


def test_empty_items_is_diagnostic_failure_not_success():
    decision = _decision(21)
    with pytest.raises(PageBatchEnvelopeError) as exc:
        _validate_items_with_identity_fallback({"items": []}, decisions=[decision])
    assert "no_usable_requested_items:rawCount=0:no_raw_items" in exc.value.reason_code


def test_ambiguous_identity_never_guesses_and_fails_closed():
    first = _decision(21)
    second = RegionRiskDecision(
        question_number=21,
        kind="question",
        page_number=7,
        bbox=(0.2, 0.2, 0.7, 0.6),
        score=80,
        suspicious=True,
        hard_math=False,
        signals=("ocr_disagreement",),
        region_issues=(),
        candidate_text="candidate-2",
    )
    raw = {"items": [_raw_item(first, target_id="invented-id")]}
    with pytest.raises(PageBatchEnvelopeError) as exc:
        _validate_items_with_identity_fallback(raw, decisions=[first, second])
    assert "identity_unmatched" in exc.value.reason_code
    assert "matches=2" in exc.value.reason_code
