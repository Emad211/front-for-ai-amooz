from __future__ import annotations

import pytest

from apps.classes.services.exam_prep_mistral_page_batch_transcriber import (
    BatchItem,
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


def test_backfill_normalizes_known_option_text_key_aliases():
    """Regression: digit-only "چند مورد" options sometimes use text/value keys.

    Live evidence (20Tir1404 Q28, Q87): Gemini returned options as
    ``{"label": "۱", "text": "۴"}`` or ``{"label": "۱", "value": "۴"}`` instead
    of the required ``text_markdown`` key, causing every option to fail Pydantic
    validation and the whole page batch to be discarded even though the model
    read the source correctly. The rename must be lossless: no value invented.
    """

    decision = _decision(21)
    raw = {
        "target_id": decision.target_id,
        "question_text_markdown": "متن",
        "options": [
            {"label": "۱", "text": "۴"},
            {"label": "۲", "value": "۳"},
            {"label": "۳", "text_markdown": "۲"},
            {"label": "۴", "content": "۱"},
        ],
        "correct_option_label": "",
        "teacher_solution_markdown": "",
    }
    normalized = _backfill_request_metadata(raw, decision=decision)
    assert [option["text_markdown"] for option in normalized["options"]] == [
        "۴",
        "۳",
        "۲",
        "۱",
    ]

    item = BatchItem.model_validate({**_raw_item(decision), **normalized})
    assert [option.text_markdown for option in item.options] == ["۴", "۳", "۲", "۱"]


def test_backfill_does_not_overwrite_a_real_text_markdown_with_an_alias():
    decision = _decision(21)
    raw = {
        "target_id": decision.target_id,
        "options": [{"label": "۱", "text_markdown": "واقعی", "text": "جعلی"}],
    }
    normalized = _backfill_request_metadata(raw, decision=decision)
    assert normalized["options"][0]["text_markdown"] == "واقعی"


def test_backfill_normalizes_bare_option_list_by_position():
    """Regression: Q120/Q122 (20Tir1404) returned options as a flat value list
    with no object/label wrapper at all, failing every option with a pydantic
    model_type error. Position becomes the label (1-based), matching the fixed
    1..4 printed layout assumed everywhere else in this pipeline.
    """

    decision = _decision(21)
    raw = {
        "target_id": decision.target_id,
        "options": ["۴", "۳", "۲", "۱"],
    }
    normalized = _backfill_request_metadata(raw, decision=decision)
    assert normalized["options"] == [
        {"label": "1", "text_markdown": "۴"},
        {"label": "2", "text_markdown": "۳"},
        {"label": "3", "text_markdown": "۲"},
        {"label": "4", "text_markdown": "۱"},
    ]
    item = BatchItem.model_validate({**_raw_item(decision), **normalized})
    assert [option.text_markdown for option in item.options] == ["۴", "۳", "۲", "۱"]


def test_backfill_maps_unknown_uncertain_reason_to_other():
    """Regression: an out-of-enum uncertain_spans.reason (e.g. a free-form
    string the model invented) must not discard an otherwise valid item.
    """

    decision = _decision(21)
    raw = {
        "target_id": decision.target_id,
        "uncertain_spans": [
            {
                "field": "question_text_markdown",
                "fragment": "...",
                "reason": "not_a_real_enum_value",
            }
        ],
    }
    normalized = _backfill_request_metadata(raw, decision=decision)
    assert normalized["uncertain_spans"][0]["reason"] == "other"
    item = BatchItem.model_validate({**_raw_item(decision), **normalized})
    assert item.uncertain_spans[0].reason == "other"


def test_backfill_drops_uncertain_span_missing_required_field():
    """Regression: an uncertain_spans entry missing "field" (Q081/S081-p044
    live case) carries no usable identity and cannot be safely defaulted; it
    must be dropped rather than reject the whole otherwise-valid item.
    """

    decision = _decision(21)
    raw = {
        "target_id": decision.target_id,
        "uncertain_spans": [
            {"fragment": "...", "reason": "unreadable_glyph"},
            {
                "field": "correct_option_label",
                "fragment": "...",
                "reason": "unreadable_glyph",
            },
        ],
    }
    normalized = _backfill_request_metadata(raw, decision=decision)
    assert len(normalized["uncertain_spans"]) == 1
    assert normalized["uncertain_spans"][0]["field"] == "correct_option_label"
    item = BatchItem.model_validate({**_raw_item(decision), **normalized})
    assert len(item.uncertain_spans) == 1


def test_backfill_treats_explicit_null_string_field_as_empty_default():
    """Regression: Q65-p013 returned teacher_solution_markdown=null on a
    question item, tripping strict string validation even though the field
    already defaults to "" when simply absent.
    """

    decision = _decision(21)
    raw = {
        "target_id": decision.target_id,
        "question_text_markdown": "متن",
        "teacher_solution_markdown": None,
        "correct_option_label": None,
    }
    normalized = _backfill_request_metadata(raw, decision=decision)
    assert normalized["teacher_solution_markdown"] == ""
    assert normalized["correct_option_label"] == ""
    item = BatchItem.model_validate({**_raw_item(decision), **normalized})
    assert item.teacher_solution_markdown == ""
    assert item.correct_option_label == ""


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
