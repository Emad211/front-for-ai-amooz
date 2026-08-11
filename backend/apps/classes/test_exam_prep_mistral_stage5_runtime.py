from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import inspect

from apps.classes import tasks_exam_prep
from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_stage5 as stage5
from apps.classes.services import exam_prep_mistral_stage5_runtime as runtime
from apps.classes.services.exam_prep_mistral_region_transcriber import (
    RegionTranscriptionResult,
)
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _decision(number: int = 1) -> RegionRiskDecision:
    return RegionRiskDecision(
        question_number=number,
        kind="question",
        page_number=1,
        bbox=(0.1, 0.1, 0.9, 0.8),
        score=1,
        suspicious=False,
        hard_math=False,
        signals=(),
        region_issues=(),
        candidate_text="صورت سؤال؟",
    )


def _transcript(number: int = 1) -> RegionTranscriptionResult:
    return RegionTranscriptionResult(
        kind="question",
        question_number=number,
        page_number=1,
        model="gpt-5.4-mini",
        transcript={
            "transcriptionMarkdown": f"{number}- صورت سؤال؟",
            "sourceVisualRequired": False,
            "visualType": "none",
            "transcriptionUncertain": False,
            "uncertainFragments": [],
        },
        response_id="response",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        reasoning_tokens=0,
    )


def _result() -> PageAssemblyResult:
    return PageAssemblyResult(
        projection={
            "exam_prep": {
                "title": "test",
                "questions": [
                    {
                        "question_id": "q-1",
                        "source_question_number": "1",
                        "question_text_markdown": "صورت سؤال؟",
                        "options": [],
                        "teacher_solution_markdown": "",
                        "issues": [],
                        "source_regions": [
                            {"pageNumber": 1, "kind": "question"}
                        ],
                    }
                ],
            }
        },
        issues=[],
        question_count=1,
        questions_needing_review=0,
        publication_ready=True,
    )


def test_rolling_ledger_releases_success_reservation_for_next_call(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE5_RESERVED_INPUT_TOKENS", "1000")
    ledger = runtime.Stage5BudgetLedger(
        max_cost_usd=Decimal("0.006"),
        max_output_tokens=1000,
    )

    first = ledger.reserve("gpt-5.4-mini")
    assert first is not None
    ledger.settle(first, _transcript())
    second = ledger.reserve("gpt-5.4-mini")

    assert second is not None
    assert ledger.safe_dict()["chargedCostUsd"] == "0.000165"


def test_failed_call_keeps_reservation_and_blocks_next_call(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE5_RESERVED_INPUT_TOKENS", "1000")
    ledger = runtime.Stage5BudgetLedger(
        max_cost_usd=Decimal("0.006"),
        max_output_tokens=1000,
    )

    first = ledger.reserve("gpt-5.4-mini")
    assert first is not None
    ledger.settle(first, ValueError("invalid provider response"))
    assert ledger.reserve("gpt-5.4-mini") is None
    ledger.record_blocked(1)

    audit = ledger.safe_dict()
    assert audit["failedCallReservedCostUsd"] == "0.00525"
    assert audit["chargedCostUsd"] == "0.00525"
    assert audit["failedCallsChargedAtReservation"] == 1
    assert audit["costCapExceeded"] is True


def test_success_without_usage_keeps_reservation_charge(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE5_RESERVED_INPUT_TOKENS", "1000")
    ledger = runtime.Stage5BudgetLedger(
        max_cost_usd=Decimal("0.006"),
        max_output_tokens=1000,
    )

    reservation = ledger.reserve("gpt-5.4-mini")
    assert reservation is not None
    missing_usage = replace(
        _transcript(),
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
    )
    ledger.settle(reservation, missing_usage)

    audit = ledger.safe_dict()
    assert audit["chargedCostUsd"] == "0.00525"
    assert audit["successfulCallEstimatedCostUsd"] == "0.00525"
    assert audit["successfulCallsChargedAtReservation"] == 1
    assert audit["costEstimateComplete"] is False
    assert ledger.reserve("gpt-5.4-mini") is None


def test_successful_call_cost_marks_missing_usage_incomplete():
    audit = {
        "regions": [
            {
                "primary": {
                    "model": "gpt-5.4-mini",
                    "inputTokens": 0,
                    "outputTokens": 0,
                }
            }
        ]
    }

    cost, complete = runtime.successful_call_cost_usd(audit)

    assert cost == Decimal("0")
    assert complete is False


def test_unknown_priced_model_fails_closed():
    ledger = runtime.Stage5BudgetLedger(
        max_cost_usd=Decimal("1.00"),
        max_output_tokens=1000,
    )

    assert ledger.reserve("unknown-model") is None
    assert ledger.safe_dict()["costEstimateComplete"] is False


def test_stage5_failure_is_charged_and_main_is_blocked_before_call(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE5_RESERVED_INPUT_TOKENS", "1000")
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAX_OUTPUT_TOKENS", "1000")
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAX_CONCURRENCY", "1")
    monkeypatch.setattr(
        stage5,
        "_render_crops",
        lambda _pdf, indexed, **_kwargs: {index: b"png" for index, _item in indexed},
    )
    calls: list[str] = []

    def fail(**kwargs):
        calls.append(kwargs["model"])
        raise ValueError("invalid provider response")

    monkeypatch.setattr(stage5, "transcribe_source_region", fail)
    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[_decision()],
        max_cost_usd=Decimal("0.006"),
    )

    assert calls == ["gpt-5.4-mini"]
    assert updated.publication_ready is False
    assert audit["regions"][0]["status"] == "blocked_stage5_cost_budget"
    assert audit["stats"]["primaryCalls"] == 1
    assert audit["stats"]["mainCalls"] == 0
    assert audit["budget"]["chargedCostUsd"] == "0.00525"


def test_reservation_underestimate_blocks_publication_fail_closed(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE5_RESERVED_INPUT_TOKENS", "1000")
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAX_OUTPUT_TOKENS", "1000")
    monkeypatch.setattr(
        stage5,
        "_render_crops",
        lambda _pdf, indexed, **_kwargs: {index: b"png" for index, _item in indexed},
    )
    expensive = replace(_transcript(), input_tokens=10_000, total_tokens=10_020)
    monkeypatch.setattr(
        stage5,
        "transcribe_source_region",
        lambda **_kwargs: expensive,
    )
    monkeypatch.setattr(stage5, "_candidate_corroborated", lambda *_args: True)
    monkeypatch.setattr(
        stage5,
        "_proposal",
        lambda *_args: {"question_text_markdown": "صورت سؤال؟", "options": []},
    )

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[_decision()],
        max_cost_usd=Decimal("0.006"),
    )

    assert updated.publication_ready is False
    assert audit["regions"][0]["status"] == "blocked_stage5_cost_budget"
    assert audit["budget"]["costCapExceeded"] is True
    assert audit["budget"]["costEstimateComplete"] is False


def test_task_deadline_is_clamped_inside_stage5_before_a_new_call(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        stage5,
        "_render_crops",
        lambda _pdf, indexed, **_kwargs: {index: b"png" for index, _item in indexed},
    )
    monkeypatch.setattr(
        stage5,
        "transcribe_source_region",
        lambda **kwargs: calls.append(kwargs),
    )

    with runtime.stage5_task_deadline(0.0):
        updated, audit = stage5.finalize_stage5_regions(
            _result(),
            pdf_data=b"%PDF-fake",
            decisions=[_decision()],
        )

    assert calls == []
    assert updated.publication_ready is False
    assert audit["budget"]["taskDeadlineApplied"] is True
    assert audit["budget"]["deadlineExceeded"] is True


def test_task_deadline_leaves_cleanup_window_before_celery_soft_limit(monkeypatch):
    monkeypatch.setattr(tasks_exam_prep, "TASK_SOFT_LIMIT", 3300)
    monkeypatch.setattr(tasks_exam_prep, "TASK_HARD_LIMIT", 3600)
    monkeypatch.setattr(tasks_exam_prep, "TASK_FINALIZE_SAFETY_SECONDS", 300)

    assert tasks_exam_prep._stage5_deadline_at(100.0) == 3100.0


def test_production_keeps_public_signature_and_passes_remaining_budget_directly():
    source = inspect.getsource(production.run_exam_prep_mistral_pipeline)
    signature = inspect.signature(production.run_exam_prep_mistral_pipeline)

    assert "finalize_stage5_regions(" in source
    assert "max_cost_usd=remaining_stage5_budget" in source
    assert list(signature.parameters) == [
        "data",
        "title",
        "model",
        "scope_hint",
        "on_page_complete",
        "should_cancel",
        "asset_namespace",
    ]
