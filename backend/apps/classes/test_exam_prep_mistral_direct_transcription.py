import pytest

from apps.classes.management.commands.probe_exam_prep_mistral_direct_transcription_calibration import (
    _MODELS,
    _MAX_OUTPUT_TOKENS,
    _TARGETS,
    _csv_values,
    _messages,
    _minimal_extra_body,
    _parse_transcription,
    _request_payload,
)
from apps.classes.services.exam_prep_mistral_direct_transcription import (
    DirectTranscription,
    numeric_signature,
    summarize_direct_transcriptions,
    text_similarity,
)


def test_direct_transcription_calibration_uses_four_discriminating_targets():
    assert _MODELS == ("gpt-5.4-mini", "gemini-3.6-flash")
    assert _MAX_OUTPUT_TOKENS == 2500
    assert _TARGETS == (
        "question:65",
        "question:94",
        "solution:57",
        "solution:133",
    )
    assert _minimal_extra_body() == {
        "generationConfig": {"thinkingConfig": {"thinkingLevel": "minimal"}}
    }
    assert _csv_values(" gemini-3.6-flash,gemini-3.6-flash, gpt-5.4-mini ") == (
        "gemini-3.6-flash",
        "gpt-5.4-mini",
    )


def test_direct_transcriber_sees_one_image_and_not_mistral_candidate():
    item = {
        "itemId": "q-094",
        "kind": "question",
        "questionNumber": 94,
        "physicalPageNumber": 20,
        "candidateText": "THIS MUST NOT BE SENT",
    }
    messages = _messages(item, b"png")
    assert "JSON" in messages[0]["content"]
    parts = messages[1]["content"]
    assert len([part for part in parts if part.get("type") == "image_url"]) == 1
    assert "THIS MUST NOT BE SENT" not in str(messages)
    assert "question_number=94" in parts[0]["text"]
    gemini = _request_payload(model="gemini-3.6-flash", item=item, crop_bytes=b"png")
    gpt = _request_payload(model="gpt-5.4-mini", item=item, crop_bytes=b"png")
    assert gemini["extra_body"] == _minimal_extra_body()
    assert "extra_body" not in gpt
    assert gemini["max_tokens"] == gpt["max_tokens"] == 2500


def test_direct_transcription_parser_tolerates_trailing_provider_junk():
    parsed = _parse_transcription(
        """
        {
          "transcription_markdown": "BM^2 = 2y^2",
          "source_visual_required": false,
          "visual_type": "none",
          "transcription_uncertain": false,
          "uncertain_fragments": []
        }
        trailing junk }
        """
    )
    assert parsed["transcriptionMarkdown"] == "BM^2 = 2y^2"
    assert parsed["sourceVisualRequired"] is False


def test_direct_transcription_parser_rejects_non_renderable_control_characters():
    with pytest.raises(ValueError):
        _parse_transcription(
            r'''
            {
              "transcription_markdown": "180^\b",
              "source_visual_required": false,
              "visual_type": "none",
              "transcription_uncertain": false,
              "uncertain_fragments": []
            }
            '''
        )


def test_similarity_and_numeric_signature_are_content_free_disagreement_signals():
    assert text_similarity("BM² = ۲y²", "BM² = 2y²") == 1.0
    assert numeric_signature("x = ۷۰ / ۷") != numeric_signature("x = ۳۰ / ۲")


def test_simple_tex_exponent_braces_are_equivalent_for_disagreement_signals():
    braced = r"3^{2} + r^{2} = 4^{2}"
    plain = r"3^2 + r^2 = 4^2"
    assert text_similarity(braced, plain) == 1.0
    assert numeric_signature(braced) == numeric_signature(plain)


def test_direct_transcription_summary_keeps_visual_and_numeric_disagreement_explicit():
    targets = [
        {"itemId": "q-065", "kind": "question", "questionNumber": 65, "physicalPageNumber": 13}
    ]
    rows = {
        "model-a": [
            {
                "itemId": "q-065",
                "transcriptionMarkdown": "65 test 2",
                "sourceVisualRequired": True,
                "visualType": "diagram",
                "transcriptionUncertain": False,
                "uncertainFragments": [],
            }
        ],
        "model-b": [
            {
                "itemId": "q-065",
                "transcriptionMarkdown": "65 test 3",
                "sourceVisualRequired": False,
                "visualType": "none",
                "transcriptionUncertain": True,
                "uncertainFragments": ["3"],
            }
        ],
    }
    summary = summarize_direct_transcriptions(targets=targets, transcripts_by_model=rows)
    assert summary["visualRequirementDisagreementCount"] == 1
    assert summary["visualTypeDisagreementCount"] == 1
    assert summary["numericSignatureDisagreementCount"] == 1
    assert summary["items"][0]["anyModelUncertain"] is True


def test_direct_transcription_schema_rejects_empty_transcript():
    try:
        DirectTranscription.model_validate(
            {
                "transcription_markdown": "",
                "source_visual_required": False,
                "visual_type": "none",
                "transcription_uncertain": False,
                "uncertain_fragments": [],
            }
        )
    except Exception:
        return
    raise AssertionError("empty transcription must be rejected")
