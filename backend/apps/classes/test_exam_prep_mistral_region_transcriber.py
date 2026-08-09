from __future__ import annotations

import json
from types import SimpleNamespace

from apps.classes.services import exam_prep_mistral_region_transcriber as transcriber


class _FakeCompletions:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.calls.append(kwargs)
        content = json.dumps(
            {
                "transcription_markdown": "1- متن سؤال\n1) الف\n2) ب\n3) ج\n4) د",
                "source_visual_required": False,
                "visual_type": "none",
                "transcription_uncertain": False,
                "uncertain_fragments": [],
            },
            ensure_ascii=False,
        )
        return SimpleNamespace(
            id="resp-1",
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                completion_tokens_details=SimpleNamespace(reasoning_tokens=0),
            ),
        )


class _FakeClient:
    def __init__(self):
        self.calls = []
        self.options = []
        self.chat = SimpleNamespace(completions=_FakeCompletions(self))

    def with_options(self, **kwargs):
        self.options.append(kwargs)
        return self


def test_gemini_call_is_one_image_source_only_minimal_and_no_retry(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(transcriber, "_get_gapgpt_client", lambda: client)
    monkeypatch.setattr(transcriber, "track_llm_usage", lambda **_kwargs: None)
    monkeypatch.setattr(transcriber, "track_llm_error", lambda **_kwargs: None)

    result = transcriber.transcribe_source_region(
        image=b"fake-image",
        kind="question",
        question_number=12,
        page_number=4,
        model="gemini-3-flash-preview",
        thinking_minimal=True,
    )

    assert result.model == "gemini-3-flash-preview"
    assert len(client.calls) == 1
    assert client.options == [{"max_retries": 0}]
    payload = client.calls[0]
    assert payload["extra_body"] == {
        "generationConfig": {"thinkingConfig": {"thinkingLevel": "minimal"}}
    }
    user_parts = payload["messages"][1]["content"]
    images = [part for part in user_parts if isinstance(part, dict) and part.get("type") == "image_url"]
    assert len(images) == 1
    serialized = json.dumps(payload["messages"], ensure_ascii=False)
    assert "CURRENT_ASSEMBLED_QUESTION" not in serialized
    assert "SECRET_MISTRAL_CANDIDATE" not in serialized
    assert "previous OCR candidate" in serialized


def test_secondary_call_has_no_gemini_thinking_body(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(transcriber, "_get_gapgpt_client", lambda: client)
    monkeypatch.setattr(transcriber, "track_llm_usage", lambda **_kwargs: None)
    monkeypatch.setattr(transcriber, "track_llm_error", lambda **_kwargs: None)

    transcriber.transcribe_source_region(
        image=b"fake-image",
        kind="solution",
        question_number=50,
        page_number=39,
        model="gpt-5.4-mini",
        thinking_minimal=False,
    )

    assert len(client.calls) == 1
    assert "extra_body" not in client.calls[0]
    assert client.options == [{"max_retries": 0}]
