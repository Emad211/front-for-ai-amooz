from __future__ import annotations

from apps.classes.services import exam_prep_mistral_stage4_page_batch_runtime as runtime
from apps.classes.services.exam_prep_mistral_page_batch_transcriber import PageBatchEnvelopeError
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision


def _decision(number: int):
    return RegionRiskDecision(
        question_number=number,
        kind="solution",
        page_number=40,
        bbox=(0.1, 0.1, 0.8, 0.5),
        score=80,
        suspicious=True,
        hard_math=True,
        signals=("source_corruption",),
        region_issues=(),
        candidate_text="candidate",
    )


def test_network_or_http_failure_never_splits(monkeypatch):
    calls = []

    def fail(**kwargs):
        calls.append(len(kwargs["targets"]))
        return None, RuntimeError("gemini_page_batch_http_503"), kwargs["spent"]

    monkeypatch.setattr(runtime._impl, "_call_primary", fail)
    rendered = [(_decision(1), b"a"), (_decision(2), b"b")]
    _results, failed, audits, _spent, primary_calls, split_calls = (
        runtime._page_results_with_structured_split_only(
            page_number=40,
            rendered=rendered,
            spent=0.0,
            budget=0.20,
        )
    )
    assert calls == [2]
    assert failed == {"s-001-p040", "s-002-p040"}
    assert primary_calls == 1
    assert split_calls == 0
    assert audits[0]["status"] == "provider_failed_no_retry"


def test_stop_with_malformed_structured_json_never_splits(monkeypatch):
    calls = []

    def fail(**kwargs):
        calls.append(len(kwargs["targets"]))
        return (
            None,
            PageBatchEnvelopeError(
                "structured_json_invalid",
                finish_reason="STOP",
            ),
            kwargs["spent"],
        )

    monkeypatch.setattr(runtime._impl, "_call_primary", fail)
    rendered = [(_decision(1), b"a"), (_decision(2), b"b")]
    _results, failed, audits, _spent, primary_calls, split_calls = (
        runtime._page_results_with_structured_split_only(
            page_number=40,
            rendered=rendered,
            spent=0.0,
            budget=0.20,
        )
    )
    assert calls == [2]
    assert failed == {"s-001-p040", "s-002-p040"}
    assert primary_calls == 1
    assert split_calls == 0
    assert audits[0]["status"] == "provider_failed_no_retry"
    assert audits[0]["finishReason"] == "STOP"


def test_explicit_output_truncation_may_split_exactly_once(monkeypatch):
    calls = []

    def fail(**kwargs):
        calls.append(len(kwargs["targets"]))
        if len(kwargs["targets"]) == 2:
            return (
                None,
                PageBatchEnvelopeError(
                    "structured_json_invalid",
                    finish_reason="MAX_TOKENS",
                ),
                kwargs["spent"],
            )
        return None, RuntimeError("child_failure"), kwargs["spent"]

    monkeypatch.setattr(runtime._impl, "_call_primary", fail)
    rendered = [(_decision(1), b"a"), (_decision(2), b"b")]
    _results, failed, audits, _spent, primary_calls, split_calls = (
        runtime._page_results_with_structured_split_only(
            page_number=40,
            rendered=rendered,
            spent=0.0,
            budget=0.20,
        )
    )
    assert calls == [2, 1, 1]
    assert failed == {"s-001-p040", "s-002-p040"}
    assert primary_calls == 3
    assert split_calls == 2
    assert audits[0]["status"] == "truncated_envelope_split"


def test_two_consecutive_image_provenance_failures_open_per_run_circuit(monkeypatch):
    calls = []

    def unproven(**kwargs):
        calls.append(kwargs["page_number"])
        return (
            None,
            PageBatchEnvelopeError(
                "image_modality_unproven:image_tokens_zero",
                finish_reason="STOP",
            ),
            kwargs["spent"],
        )

    monkeypatch.setattr(runtime._impl, "_call_primary", unproven)
    state = {"consecutiveFailures": 0, "circuitOpen": False, "blockedPages": 0}
    token = runtime._PROVENANCE_STATE.set(state)
    try:
        for page_number in (40, 41):
            runtime._page_results_with_structured_split_only(
                page_number=page_number,
                rendered=[(_decision(page_number), b"a")],
                spent=0.0,
                budget=0.20,
            )
        _results, failed, audits, _spent, primary_calls, split_calls = (
            runtime._page_results_with_structured_split_only(
                page_number=42,
                rendered=[(_decision(42), b"a")],
                spent=0.0,
                budget=0.20,
            )
        )
    finally:
        runtime._PROVENANCE_STATE.reset(token)

    assert calls == [40, 41]
    assert state["circuitOpen"] is True
    assert state["blockedPages"] == 1
    assert primary_calls == 0
    assert split_calls == 0
    assert failed == {"s-042-p040"}
    assert audits[0]["status"] == "primary_circuit_open"
