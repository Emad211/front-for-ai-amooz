from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.classes.services import exam_prep_mistral_page_batch_transcriber_v4 as v4
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision


def _decision() -> RegionRiskDecision:
    return RegionRiskDecision(
        question_number=21,
        kind="question",
        page_number=6,
        bbox=(0.1, 0.1, 0.9, 0.7),
        score=80,
        suspicious=True,
        hard_math=True,
        signals=("ocr_disagreement",),
        region_issues=(),
        candidate_text="candidate",
    )


def _item(decision: RegionRiskDecision) -> dict:
    return {
        "target_id": decision.target_id,
        "kind": "question",
        "question_number": 21,
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


def _root(decision: RegionRiskDecision, *, image_tokens: int) -> dict:
    import json

    return {
        "model": "gemini-3.6-flash",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": json.dumps({"items": [_item(decision)]})},
            }
        ],
        "usage": {
            "prompt_tokens": 1500 if image_tokens else 330,
            "completion_tokens": 100,
            "total_tokens": 1600 if image_tokens else 430,
            "prompt_tokens_details": {
                "text_tokens": 330,
                "image_tokens": image_tokens,
            },
        },
        "estimated_cost": {"unit": 0.001, "irt": 0},
    }


class _Response:
    def __init__(self, root):
        self.status_code = 200
        self.headers = {"x-request-id": "019-test"}
        self._root = root

    def json(self):
        return self._root


def test_request_body_uses_advertised_chat_vision_shape():
    decision = _decision()
    body = v4._request_body(
        page_number=6,
        targets=[(decision, b"png")],
        model="gemini-3.6-flash",
    )
    assert body["model"] == "gemini-3.6-flash"
    assert body["response_format"] == {"type": "json_object"}
    assert body["extra_body"] == {
        "generationConfig": {
            "thinkingConfig": {"thinkingLevel": "minimal"},
        }
    }
    content = body["messages"][1]["content"]
    images = [part for part in content if part.get("type") == "image_url"]
    assert len(images) == 1
    assert images[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert images[0]["image_url"]["detail"] == "high"


def test_usage_reads_openai_compatible_image_tokens():
    usage = v4._usage(_root(_decision(), image_tokens=1120))
    assert usage["imageInputTokens"] == 1120
    assert usage["textInputTokens"] == 330
    assert usage["promptModalityDetailsPresent"] == 1


def test_chat_transport_rejects_text_only_success(monkeypatch):
    decision = _decision()
    monkeypatch.setattr(
        v4.base.requests,
        "post",
        lambda *args, **kwargs: _Response(_root(decision, image_tokens=0)),
    )
    monkeypatch.setattr(v4.base, "_api_key", lambda: "test")
    with pytest.raises(v4.PageBatchEnvelopeError) as exc:
        v4.transcribe_page_batch(page_number=6, targets=[(decision, b"png")])
    assert exc.value.reason_code == "image_modality_unproven:image_tokens_zero"


def test_chat_transport_accepts_only_image_grounded_item(monkeypatch):
    decision = _decision()
    monkeypatch.setattr(
        v4.base.requests,
        "post",
        lambda *args, **kwargs: _Response(_root(decision, image_tokens=1120)),
    )
    monkeypatch.setattr(v4.base, "_api_key", lambda: "test")
    result = v4.transcribe_page_batch(page_number=6, targets=[(decision, b"png")])
    assert result.usage["imageInputTokens"] == 1120
    assert [item.target_id for item in result.items] == [decision.target_id]
    assert result.missing_target_ids == ()
    assert result.invalid_target_ids == ()
