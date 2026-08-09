from __future__ import annotations

import json

from apps.classes.services import exam_prep_mistral_page_batch_transcriber as batch
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision


def _decision(number: int, *, kind: str = "solution", page: int = 40):
    return RegionRiskDecision(
        question_number=number,
        kind=kind,
        page_number=page,
        bbox=(0.1, 0.1, 0.8, 0.5),
        score=80,
        suspicious=True,
        hard_math=kind == "solution",
        signals=("source_corruption",),
        region_issues=(),
        candidate_text="SECRET_MISTRAL_CANDIDATE",
    )


def _item(number: int):
    return {
        "target_id": f"s-{number:03d}-p040",
        "kind": "solution",
        "question_number": number,
        "question_text_markdown": "",
        "options": [],
        "correct_option_label": "3",
        "teacher_solution_markdown": f"راه حل {number}",
        "source_visual_required": False,
        "visual_type": "none",
        "transcription_uncertain": False,
        "uncertain_spans": [],
        "uncertain_fragments": [],
    }


class _Response:
    status_code = 200
    headers = {"x-request-id": "req-1"}

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_one_page_with_multiple_crops_makes_one_native_structured_request(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        result = {"items": [_item(52), _item(53)]}
        return _Response(
            {
                "candidates": [{"content": {"parts": [{"text": json.dumps(result, ensure_ascii=False)}]}}],
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 50,
                    "thoughtsTokenCount": 20,
                    "totalTokenCount": 170,
                },
                "estimated_cost": {"unit": 0.001, "irt": 120.0},
            }
        )

    monkeypatch.setattr(batch.requests, "post", fake_post)
    monkeypatch.setenv("AVALAI_API_KEY", "test-key")
    monkeypatch.setenv("AVALAI_BASE_URL", "https://api.avalai.ir/v1")

    result = batch.transcribe_page_batch(
        page_number=40,
        targets=[(_decision(52), b"png-52"), (_decision(53), b"png-53")],
    )

    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url.endswith("/v1beta/models/gemini-3-flash-preview:generateContent")
    body = kwargs["json"]
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    schema = body["generationConfig"]["responseSchema"]
    assert schema["properties"]["items"]["type"] == "array"
    assert "uncertain_spans" in schema["properties"]["items"]["items"]["properties"]
    inline_images = [
        part
        for part in body["contents"][0]["parts"]
        if isinstance(part, dict) and "inlineData" in part
    ]
    assert len(inline_images) == 2
    serialized = json.dumps(body, ensure_ascii=False)
    assert "SECRET_MISTRAL_CANDIDATE" not in serialized
    assert [item.target_id for item in result.items] == ["s-052-p040", "s-053-p040"]
    assert result.missing_target_ids == ()
    assert result.invalid_target_ids == ()
    assert result.usage["reasoningTokens"] == 20
    assert result.estimated_cost["irt"] == 120.0


def test_missing_target_preserves_valid_sibling_without_retry(monkeypatch):
    calls = []

    def fake_post(_url, **_kwargs):
        calls.append(1)
        return _Response(
            {"candidates": [{"content": {"parts": [{"text": json.dumps({"items": [_item(52)]})}]}}]}
        )

    monkeypatch.setattr(batch.requests, "post", fake_post)
    monkeypatch.setenv("AVALAI_API_KEY", "test-key")

    result = batch.transcribe_page_batch(
        page_number=40,
        targets=[(_decision(52), b"a"), (_decision(53), b"b")],
    )
    assert len(calls) == 1
    assert [item.target_id for item in result.items] == ["s-052-p040"]
    assert result.missing_target_ids == ("s-053-p040",)
    assert result.invalid_target_ids == ()
    assert result.safe_dict()["partial"] is True


def test_invalid_one_item_does_not_poison_valid_sibling(monkeypatch):
    calls = []

    def fake_post(_url, **_kwargs):
        calls.append(1)
        bad = _item(53)
        bad["kind"] = "question"
        return _Response(
            {"candidates": [{"content": {"parts": [{"text": json.dumps({"items": [_item(52), bad]})}]}}]}
        )

    monkeypatch.setattr(batch.requests, "post", fake_post)
    monkeypatch.setenv("AVALAI_API_KEY", "test-key")

    result = batch.transcribe_page_batch(
        page_number=40,
        targets=[(_decision(52), b"a"), (_decision(53), b"b")],
    )
    assert len(calls) == 1
    assert [item.target_id for item in result.items] == ["s-052-p040"]
    assert result.invalid_target_ids == ("s-053-p040",)
