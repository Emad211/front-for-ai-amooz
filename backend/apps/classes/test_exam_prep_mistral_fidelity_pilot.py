from apps.classes.management.commands.probe_exam_prep_mistral_fidelity_pilot import (
    _PILOT_MODELS,
    _PILOT_TARGETS,
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
