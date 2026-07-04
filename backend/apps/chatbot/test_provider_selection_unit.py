import pytest


@pytest.mark.unit
def test_preferred_provider_respects_mode_avalai(monkeypatch):
    """`MODE=avalai` (legacy alias for LLM_PROVIDER) selects the avalai provider.

    The old dual-client Gemini-vs-avalai routing (`llm_client._get_clients`) was
    removed when the client became a single OpenAI-compatible path; provider
    selection now lives in `apps.commons.llm_provider.preferred_provider()`.
    """
    from apps.commons.llm_provider import preferred_provider

    monkeypatch.delenv('LLM_PROVIDER', raising=False)
    monkeypatch.setenv('MODE', 'avalai')
    assert preferred_provider() == 'avalai'


@pytest.mark.unit
def test_preferred_provider_prefers_llm_provider_over_legacy_mode(monkeypatch):
    from apps.commons.llm_provider import preferred_provider

    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('MODE', 'avalai')
    assert preferred_provider() == 'gemini'


@pytest.mark.unit
def test_preferred_provider_defaults_to_auto(monkeypatch):
    from apps.commons.llm_provider import preferred_provider

    monkeypatch.delenv('LLM_PROVIDER', raising=False)
    monkeypatch.delenv('MODE', raising=False)
    assert preferred_provider() == 'auto'
