import pytest


@pytest.mark.unit
def test_generate_json_repairs_invalid_json_without_format_keyerror(monkeypatch):
    from apps.chatbot.services import llm_client

    calls = {"n": 0, "repair_prompt": ""}

    def _fake_generate_text(*, contents, model=None):
        calls["n"] += 1
        # First call returns invalid JSON, forcing repair path.
        if calls["n"] == 1:
            return type("R", (), {"text": "NOT JSON"})()
        # Second call is the repair LLM. Capture prompt and return fixed JSON.
        calls["repair_prompt"] = str(contents)
        return type("R", (), {"text": '{"ok": true}'})()

    monkeypatch.setattr(llm_client, "generate_text", _fake_generate_text)

    obj = llm_client.generate_json(feature="chat_intent", contents="whatever")
    assert obj == {"ok": True}
    # Ensure placeholders were filled (no leftover tokens).
    assert "{schema_hint}" not in calls["repair_prompt"]
    assert "{raw_text}" not in calls["repair_prompt"]
    assert "Feature: chat_intent" in calls["repair_prompt"]
    assert "NOT JSON" in calls["repair_prompt"]
