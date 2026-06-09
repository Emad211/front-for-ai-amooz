import pytest


@pytest.mark.unit
def test_chatbot_llm_client_uses_gapgpt_gateway(monkeypatch):
    """The chatbot LLM client routes through the single OpenAI-compatible GapGPT
    gateway.

    The old Gemini/Avalai dual `_get_clients` selection was refactored away — the
    client now always goes through `_get_gapgpt_client()` and tags the result with
    provider='gapgpt'. Verify generate_text() exercises that seam without hitting
    the network or the DB-backed usage tracker.
    """
    from apps.chatbot.services import llm_client

    class _FakeCompletions:
        @staticmethod
        def create(**_kwargs):
            msg = type('M', (), {'content': 'OK'})()
            choice = type('C', (), {'message': msg})()
            return type('R', (), {'choices': [choice]})()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr(llm_client, '_get_gapgpt_client', lambda: _FakeClient())
    # Pure unit test: skip the DB-backed usage tracking.
    monkeypatch.setattr(llm_client, 'track_llm_usage', lambda **_kwargs: None)

    res = llm_client.generate_text(contents='hi')
    assert res.provider == 'gapgpt'
    assert res.text == 'OK'
