from __future__ import annotations

from types import SimpleNamespace

from apps.classes.services import exam_prep_mistral_targeted_recovery_policy as policy


def test_missing_heading_alone_never_buys_targeted_ocr(monkeypatch):
    monkeypatch.setattr(
        policy,
        "_ORIGINAL_TARGETED_RECOVERY",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not call OCR")),
    )
    recovered, result = policy.targeted_recovery_with_usable_solution_context(
        b"pdf",
        accepted=[SimpleNamespace(question_number=5)],
        missing=[4],
        invalid=[],
        config=object(),
        should_cancel=None,
    )
    assert recovered == {}
    assert result is None


def test_invalid_label_on_accepted_solution_remains_eligible(monkeypatch):
    calls = []

    def fake(data, **kwargs):
        calls.append((data, kwargs))
        return {5: ("3", 40, "right")}, "result"

    monkeypatch.setattr(policy, "_ORIGINAL_TARGETED_RECOVERY", fake)
    recovered, result = policy.targeted_recovery_with_usable_solution_context(
        b"pdf",
        accepted=[SimpleNamespace(question_number=5)],
        missing=[4],
        invalid=[5, 6],
        config="config",
        should_cancel=None,
    )
    assert recovered == {5: ("3", 40, "right")}
    assert result == "result"
    assert len(calls) == 1
    assert calls[0][1]["missing"] == ()
    assert calls[0][1]["invalid"] == [5]
