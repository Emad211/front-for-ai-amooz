from __future__ import annotations

from decimal import Decimal

from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_stage4_page_batch as stage4


def test_total_pdf_budget_defaults_to_thirty_cents(monkeypatch):
    monkeypatch.delenv("EXAM_PREP_TOTAL_PDF_BUDGET_USD", raising=False)
    assert production._total_budget_usd() == Decimal("0.30")


def test_total_pdf_budget_can_be_lowered_but_not_negative(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_TOTAL_PDF_BUDGET_USD", "0.25")
    assert production._total_budget_usd() == Decimal("0.25")
    monkeypatch.setenv("EXAM_PREP_TOTAL_PDF_BUDGET_USD", "-1")
    assert production._total_budget_usd() == Decimal("0")


def test_stage4_budget_gate_stops_before_next_primary_call(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE4_PRIMARY_RESERVE_USD", "0.006")
    assert stage4._budget_allows(0.043, 0.05, "primary") is True
    assert stage4._budget_allows(0.045, 0.05, "primary") is False


def test_stage4_budget_gate_uses_larger_secondary_reserve(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE4_SECONDARY_RESERVE_USD", "0.012")
    assert stage4._budget_allows(0.037, 0.05, "secondary") is True
    assert stage4._budget_allows(0.039, 0.05, "secondary") is False
