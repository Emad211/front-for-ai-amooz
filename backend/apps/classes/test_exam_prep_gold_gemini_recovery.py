from apps.classes.management.commands.probe_exam_prep_gold_gemini_recovery import (
    _MODEL,
    _messages,
    _minimal_extra_body,
)
from apps.classes.services.exam_prep_mistral_gold_baseline import (
    GOLD_GEMINI_RECOVERY_IDS,
    GOLD_LOCAL_VISUAL_REPAIR_IDS,
)


def test_gold_recovery_uses_only_gemini_minimal_and_40_failures():
    assert _MODEL == "gemini-3-flash-preview"
    assert len(GOLD_GEMINI_RECOVERY_IDS) == 40
    assert GOLD_LOCAL_VISUAL_REPAIR_IDS == ("q-081",)
    assert "q-081" not in GOLD_GEMINI_RECOVERY_IDS
    assert _minimal_extra_body() == {
        "generationConfig": {"thinkingConfig": {"thinkingLevel": "minimal"}}
    }


def test_gold_recovery_prompt_has_one_image_and_never_shows_mistral_candidate():
    meta = {"kind": "question", "questionNumber": 94, "physicalPageNumber": 20}
    messages = _messages(item_id="q-094", meta=meta, crop_bytes=b"png")
    assert "previous OCR candidate is intentionally hidden" in messages[0]["content"]
    assert "JSON" in messages[0]["content"]
    parts = messages[1]["content"]
    assert len([part for part in parts if part.get("type") == "image_url"]) == 1
    assert "Mistral" not in str(parts)
