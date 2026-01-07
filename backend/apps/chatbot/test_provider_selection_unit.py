import pytest


@pytest.mark.unit
def test_chatbot_llm_client_respects_mode_avalai(monkeypatch):
    from apps.chatbot.services import llm_client

    monkeypatch.setenv('MODE', 'avalai')

    class _Bomb:
        class models:
            @staticmethod
            def generate_content(*args, **kwargs):  # pragma: no cover
                raise AssertionError('Gemini should not be called when MODE=avalai')

    class _Ok:
        class models:
            @staticmethod
            def generate_content(*args, **kwargs):
                return type('R', (), {'text': 'OK'})()

    monkeypatch.setattr(llm_client, '_get_clients', lambda: (_Bomb(), _Ok()))

    res = llm_client.generate_text(contents='hi')
    assert res.provider == 'avalai'
    assert res.text == 'OK'
