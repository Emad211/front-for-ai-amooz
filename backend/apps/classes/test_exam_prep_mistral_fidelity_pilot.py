import pytest

from apps.classes.management.commands.probe_exam_prep_mistral_fidelity_pilot import (
    _PILOT_MODELS,
    _PILOT_TARGETS,
    _json_contract,
    _provider_content,
    _system_prompt,
)


def test_economical_fidelity_pilot_is_small_and_explicit():
    assert _PILOT_MODELS == ("gpt-5.4-mini", "gemini-3-flash-preview")
    assert _PILOT_TARGETS == (
        "question:65",
        "question:94",
        "question:120",
        "solution:50",
        "solution:57",
        "solution:133",
    )
    assert len(_PILOT_TARGETS) == 6


def test_direct_pilot_json_mode_prompt_explicitly_requests_json():
    prompt = f"{_system_prompt()} {_json_contract()}".lower()
    assert "json" in prompt
    assert "only one valid json object" in prompt


def test_direct_pilot_extracts_only_nonempty_first_choice_content():
    assert _provider_content(
        {"choices": [{"message": {"content": '{"items": []}'}}]}
    ) == '{"items": []}'

    with pytest.raises(ValueError, match="no first choice"):
        _provider_content({"choices": []})
    with pytest.raises(ValueError, match="empty or non-text"):
        _provider_content({"choices": [{"message": {"content": ""}}]})
