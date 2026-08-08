from apps.classes.management.commands.probe_exam_prep_mistral_fidelity_single_item_calibration import (
    _CALIBRATION_MODELS,
    _CALIBRATION_TARGETS,
    _messages,
    _parse_single_review,
)


def test_single_item_calibration_is_small_and_discriminating():
    assert _CALIBRATION_MODELS == ("gpt-5.4-mini", "gemini-3-flash-preview")
    assert _CALIBRATION_TARGETS == (
        "question:65",
        "question:94",
        "solution:57",
        "solution:133",
    )


def test_single_item_prompt_binds_exactly_one_image_and_mentions_json():
    item = {
        "itemId": "q-065",
        "kind": "question",
        "questionNumber": 65,
        "physicalPageNumber": 13,
        "candidateText": "candidate",
    }
    messages = _messages(item, b"png-bytes")
    assert "JSON" in messages[0]["content"]
    parts = messages[1]["content"]
    assert len([part for part in parts if part.get("type") == "image_url"]) == 1
    assert "question_number=65" in parts[0]["text"]


def test_single_review_parser_does_not_require_echoed_item_id():
    content = """
    {
      "verdict": "major_error",
      "candidate_usable_without_repair": false,
      "source_visual_required": true,
      "errors": [
        {
          "category": "formula",
          "severity": "critical",
          "candidate_fragment": "x^7",
          "source_reading": "x^2",
          "note": "wrong exponent"
        }
      ]
    }
    trailing provider junk }
    """
    parsed = _parse_single_review(content, item_id="s-133")
    assert parsed["itemId"] == "s-133"
    assert parsed["verdict"] == "major_error"
    assert parsed["errors"][0]["sourceReading"] == "x^2"
