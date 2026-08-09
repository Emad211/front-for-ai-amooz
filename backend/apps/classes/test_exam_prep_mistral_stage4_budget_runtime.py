from __future__ import annotations

from apps.classes.services import exam_prep_mistral_stage4_page_batch_runtime as runtime


def test_primary_budget_reserve_grows_with_batch_target_count(monkeypatch):
    monkeypatch.delenv("EXAM_PREP_STAGE4_PRIMARY_RESERVE_BASE_USD", raising=False)
    monkeypatch.delenv("EXAM_PREP_STAGE4_PRIMARY_RESERVE_PER_EXTRA_TARGET_USD", raising=False)
    one = runtime._primary_reserve(1)
    three = runtime._primary_reserve(3)
    seven = runtime._primary_reserve(7)
    assert one == 0.0028
    assert three > one
    assert seven > three
    assert seven >= 0.015


def test_secondary_default_reserve_is_bounded_near_prior_observed_max(monkeypatch):
    monkeypatch.delenv("EXAM_PREP_STAGE4_SECONDARY_RESERVE_USD", raising=False)
    assert runtime._budget_reserve("secondary") == 0.0045


def test_primary_call_stops_before_budget_when_reserve_does_not_fit(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE4_PRIMARY_RESERVE_BASE_USD", "0.0028")
    monkeypatch.setenv("EXAM_PREP_STAGE4_PRIMARY_RESERVE_PER_EXTRA_TARGET_USD", "0.00205")
    called = []
    monkeypatch.setattr(
        runtime._impl,
        "transcribe_page_batch",
        lambda **_kwargs: called.append(1),
    )
    result, error, spent = runtime._call_primary_budgeted(
        page_number=40,
        targets=[(object(), b"a")] * 3,
        spent=0.044,
        budget=0.05,
    )
    assert result is None
    assert str(error) == "stage4_cost_budget"
    assert spent == 0.044
    assert called == []
