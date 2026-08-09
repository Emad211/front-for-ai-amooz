from __future__ import annotations

from decimal import Decimal

from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_stage4_page_batch_runtime as runtime


def test_total_pdf_budget_defaults_to_thirty_cents(monkeypatch):
    monkeypatch.delenv("EXAM_PREP_TOTAL_PDF_BUDGET_USD", raising=False)
    assert production._total_budget_usd() == Decimal("0.30")


def test_total_pdf_budget_can_be_lowered_but_not_negative(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_TOTAL_PDF_BUDGET_USD", "0.25")
    assert production._total_budget_usd() == Decimal("0.25")
    monkeypatch.setenv("EXAM_PREP_TOTAL_PDF_BUDGET_USD", "-1")
    assert production._total_budget_usd() == Decimal("0")


def test_targeted_ocr_recovery_is_allowed_only_when_it_leaves_stage4_reserve(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_TARGETED_OCR_RESERVE_PER_PAGE_USD", "0.0065")
    monkeypatch.setenv("EXAM_PREP_STAGE4_MINIMUM_RESERVE_USD", "0.0065")
    monkeypatch.setattr(production, "_target_crop_specs", lambda accepted, targets: [(1, "left")] * 2)

    allowed = production._targeted_recovery_budget_plan(
        accepted=[],
        missing=[4, 5],
        invalid=[],
        ocr_cost_usd=Decimal("0.232"),
        total_budget_usd=Decimal("0.30"),
    )
    assert allowed["allowed"] is True
    assert allowed["reserveUsd"] == Decimal("0.0130")

    blocked = production._targeted_recovery_budget_plan(
        accepted=[],
        missing=[4, 5],
        invalid=[],
        ocr_cost_usd=Decimal("0.285"),
        total_budget_usd=Decimal("0.30"),
    )
    assert blocked["allowed"] is False


def test_targeted_ocr_recovery_has_no_reserve_when_no_crop_is_needed(monkeypatch):
    monkeypatch.setattr(production, "_target_crop_specs", lambda accepted, targets: [])
    plan = production._targeted_recovery_budget_plan(
        accepted=[],
        missing=[],
        invalid=[],
        ocr_cost_usd=Decimal("0.232"),
        total_budget_usd=Decimal("0.30"),
    )
    assert plan["allowed"] is False
    assert plan["reserveUsd"] == Decimal("0")
    assert plan["minimumStage4ReserveUsd"] == Decimal("0")


def test_secondary_budget_gate_uses_runtime_reserve(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE4_SECONDARY_RESERVE_USD", "0.0045")
    assert runtime._impl._budget_allows(0.045, 0.05, "secondary") is True
    assert runtime._impl._budget_allows(0.046, 0.05, "secondary") is False
