from apps.classes.management.commands.probe_exam_prep_gemini_minimal_thinking import (
    _TARGETS,
    _minimal_extra_body,
    _parse_transcript,
    _reasoning_tokens,
)


def test_minimal_thinking_targets_are_small_and_discriminating():
    assert _TARGETS == ("q-094", "s-133")


def test_minimal_thinking_uses_google_generation_config_shape():
    assert _minimal_extra_body() == {
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": "minimal",
            }
        }
    }


def test_reasoning_token_extraction_is_content_free():
    root = {
        "usage": {
            "completion_tokens_details": {
                "reasoning_tokens": 123,
            }
        }
    }
    assert _reasoning_tokens(root) == 123
    assert _reasoning_tokens({}) == 0


def test_minimal_transcript_parser_tolerates_trailing_provider_junk():
    parsed = _parse_transcript(
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
