from __future__ import annotations

from dataclasses import replace
import re
import sys
import threading
import time
from types import SimpleNamespace

from PIL import Image
import pytest

from apps.classes.services import exam_prep_mistral_stage5 as stage5
from apps.classes.services.exam_prep_page_output import is_critical_page_issue
from apps.classes.services.exam_prep_mistral_region_transcriber import (
    RegionTranscriptionResult,
)
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _result(*, text: str = "صورت سؤال؟", issues=None, visuals=None) -> PageAssemblyResult:
    question = {
        "question_id": "default-q-1",
        "scope_key": "default",
        "section_key": "default",
        "source_question_number": "1",
        "question_text_markdown": text,
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "2",
        "teacher_solution_markdown": "پاسخ تشریحی",
        "final_answer_markdown": "گزینه 2",
        "confidence": 0.0,
        "issues": list(issues or ["native_pdf_answer_label_authority"]),
        "source_pages": [1],
        "source_regions": [
            {"pageNumber": 1, "kind": "question"},
            {"pageNumber": 1, "kind": "solution"},
        ],
        "visuals": list(visuals or []),
        "visualSourceContract": {
            "schemaVersion": 1,
            "requiredAssetIds": ["v1"] if visuals else [],
        },
    }
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "تست", "questions": [question]}},
        issues=[],
        question_count=1,
        questions_needing_review=0,
        matched_answer_count=1,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=True,
    )


def _decision(*, kind: str, suspicious: bool, hard_math: bool = False) -> RegionRiskDecision:
    candidate = (
        "صورت سؤال؟\n1) الف\n2) ب\n3) ج\n4) د"
        if kind == "question"
        else "پاسخ تشریحی"
    )
    return RegionRiskDecision(
        question_number=1,
        kind=kind,
        page_number=1,
        bbox=(0.1, 0.1, 0.9, 0.7),
        score=70 if suspicious else 7,
        suspicious=suspicious,
        hard_math=hard_math,
        signals=("source_corruption",) if suspicious else (),
        region_issues=(),
        candidate_text=candidate,
    )


def _transcript(
    *,
    kind: str,
    model: str,
    text: str | None = None,
    uncertain: bool = False,
    visual_required: bool = False,
    visual_type: str | None = None,
    target_number: int = 1,
    include_heading: bool = True,
) -> RegionTranscriptionResult:
    transcript_text = text or (
        "صورت سؤال؟\n1) الف\n2) ب\n3) ج\n4) د"
        if kind == "question"
        else "پاسخ تشریحی"
    )
    if include_heading and not re.match(r"^\s*[0-9۰-۹]+\s*[-–—ـ]", transcript_text):
        transcript_text = (
            f"{target_number}- {transcript_text}"
            if kind == "question"
            else f"{target_number}- گزینه 2\n{transcript_text}"
        )
    return RegionTranscriptionResult(
        kind=kind,
        question_number=1,
        page_number=1,
        model=model,
        transcript={
            "transcriptionMarkdown": transcript_text,
            "sourceVisualRequired": visual_required,
            "visualType": visual_type or ("diagram" if visual_required else "none"),
            "transcriptionUncertain": uncertain,
            "uncertainFragments": ["؟"] if uncertain else [],
        },
        response_id="resp",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        reasoning_tokens=0,
    )


def _fake_crops(_pdf_data, indexed_decisions, **_kwargs):
    return {index: b"png" for index, _decision in indexed_decisions}


@pytest.fixture(autouse=True)
def _single_worker_by_default(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAX_CONCURRENCY", "1")


def test_stage5_defaults_to_cheap_primary_and_gemini_36_main(monkeypatch):
    monkeypatch.delenv("EXAM_PREP_STAGE5_PRIMARY_MODEL", raising=False)
    monkeypatch.delenv("EXAM_PREP_STAGE5_MAIN_MODEL", raising=False)
    monkeypatch.delenv("EXAM_PREP_STAGE5_TIEBREAKER_MODEL", raising=False)

    assert stage5.primary_model() == "gpt-5.4-mini"
    assert stage5.main_model() == "gemini-3.6-flash"
    assert stage5.tiebreaker_model() == ""
    assert stage5._main_cap() == 40


def test_stage5_targeted_eval_uses_exact_production_policy_without_missing_siblings(
    monkeypatch,
):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append((kwargs["model"], kwargs["kind"]))
        return _transcript(kind=kwargs["kind"], model=kwargs["model"])

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[_decision(kind="solution", suspicious=True)],
        required_targets={(1, "solution")},
    )

    assert calls == [("gpt-5.4-mini", "solution")]
    assert audit["stats"]["regions"] == 1
    assert audit["stats"]["missingRegions"] == 0
    assert audit["stats"]["blocked"] == 0
    assert audit["policy"]["targetedEvaluation"] is True
    question = updated.projection["exam_prep"]["questions"][0]
    assert "stage5_finalization_blocked" not in question["issues"]
    assert [row["kind"] for row in question["stage5_finalization"]["regions"]] == [
        "solution"
    ]


def test_stage5_renders_one_page_once_for_multiple_region_crops(monkeypatch):
    class FakeDocument:
        def __len__(self):
            return 1

        def close(self):
            return None

    monkeypatch.setitem(
        sys.modules,
        "pypdfium2",
        SimpleNamespace(PdfDocument=lambda _data: FakeDocument()),
    )
    render_calls: list[int] = []

    def render_page(_document, page_number):
        render_calls.append(page_number)
        return Image.new("RGB", (100, 100), "white")

    monkeypatch.setattr(stage5, "_render_page_image", render_page)
    indexed = [
        (0, _decision(kind="question", suspicious=False)),
        (1, _decision(kind="solution", suspicious=False)),
    ]

    crops = stage5._render_crops(b"%PDF-fake", indexed)

    assert render_calls == [1]
    assert set(crops) == {0, 1}
    assert all(isinstance(crops[index], bytes) for index in crops)


def test_stage5_transcribes_with_bounded_parallelism_and_stable_results(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAX_CONCURRENCY", "2")
    lock = threading.Lock()
    active = 0
    max_active = 0

    def transcribe(*, decision, crop, model):
        nonlocal active, max_active
        assert crop in {b"q", b"s"}
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return _transcript(kind=decision.kind, model=model)

    monkeypatch.setattr(stage5, "_transcribe", transcribe)
    items = [
        (0, _decision(kind="question", suspicious=False), b"q"),
        (1, _decision(kind="solution", suspicious=False), b"s"),
    ]

    outcomes = stage5._transcribe_many(items, model="gpt-5.4-mini")

    assert list(outcomes) == [0, 1]
    assert all(isinstance(value, RegionTranscriptionResult) for value in outcomes.values())
    assert max_active == 2


def test_stage5_missing_region_coverage_is_a_critical_fail_closed_gate(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)
    monkeypatch.setattr(
        stage5,
        "transcribe_source_region",
        lambda **kwargs: calls.append(kwargs),
    )

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[],
    )

    question = updated.projection["exam_prep"]["questions"][0]
    assert calls == []
    assert updated.publication_ready is False
    assert "stage5_finalization_blocked" in question["issues"]
    assert is_critical_page_issue("stage5_finalization_blocked") is True
    assert audit["stats"]["missingRegions"] == 2
    assert {row["kind"] for row in audit["regions"]} == {"question", "solution"}
    assert all(row["status"] == "blocked_missing_region" for row in audit["regions"])


def test_stage5_visual_requirement_without_stage3_asset_blocks(monkeypatch):
    decisions = [
        _decision(kind="question", suspicious=False),
        _decision(kind="solution", suspicious=False),
    ]
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        return _transcript(
            kind=kwargs["kind"],
            model=kwargs["model"],
            visual_required=kwargs["kind"] == "question",
        )

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=decisions,
    )

    question = updated.projection["exam_prep"]["questions"][0]
    assert updated.publication_ready is False
    assert "stage5_finalization_blocked" in question["issues"]
    assert audit["regions"][0]["status"] == "blocked_visual_evidence_missing"


def test_stage5_ignores_inconsistent_visual_required_none_signal(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs["model"])
        return _transcript(
            kind=kwargs["kind"],
            model=kwargs["model"],
            visual_required=kwargs["kind"] == "question",
            visual_type="none",
        )

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[
            _decision(kind="question", suspicious=False),
            _decision(kind="solution", suspicious=False),
        ],
    )

    assert calls == ["gpt-5.4-mini", "gpt-5.4-mini"]
    assert updated.publication_ready is True
    assert audit["stats"]["blocked"] == 0


def test_stage5_visual_only_options_are_verified_by_stem_and_grouped_source_asset(
    monkeypatch,
):
    visual = {
        "id": "v1",
        "role": "question",
        "visualMode": "grouped_options",
        "groupedOptionLabels": ["1", "2", "3", "4"],
        "reviewOnly": False,
        "sanity": {"status": "passed", "issues": []},
    }
    original = _result(visuals=[visual])
    question = original.projection["exam_prep"]["questions"][0]
    question["options"] = [
        {"label": str(index), "text_markdown": ""}
        for index in range(1, 5)
    ]
    question["issues"] = [
        "native_pdf_answer_label_authority",
        "missing_option_text",
    ]
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        if kwargs["kind"] == "question":
            return _transcript(
                kind="question",
                model=kwargs["model"],
                text="صورت سؤال؟",
                visual_required=True,
                visual_type="diagram",
            )
        return _transcript(kind="solution", model=kwargs["model"])

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        original,
        pdf_data=b"%PDF-fake",
        decisions=[
            _decision(kind="question", suspicious=False),
            _decision(kind="solution", suspicious=False),
        ],
    )

    output = updated.projection["exam_prep"]["questions"][0]
    question_row = next(row for row in audit["regions"] if row["kind"] == "question")
    assert question_row["status"] == "verified_visual_source"
    assert "stage5_finalization_blocked" not in output["issues"]
    assert "missing_option_text" not in output["issues"]


def test_stage5_visual_only_options_can_be_verified_by_main_after_primary_failure(monkeypatch):
    visual = {
        "id": "v1", "role": "question", "visualMode": "grouped_options",
        "groupedOptionLabels": ["1", "2", "3", "4"], "reviewOnly": False,
        "sanity": {"status": "passed"},
    }
    original = _result(visuals=[visual])
    question = original.projection["exam_prep"]["questions"][0]
    question["options"] = [{"label": str(index), "text_markdown": ""} for index in range(1, 5)]
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        if kwargs["kind"] == "question" and kwargs["model"] == "gpt-5.4-mini":
            raise RuntimeError("primary failed")
        if kwargs["kind"] == "question":
            return _transcript(
                kind="question", model=kwargs["model"], text="صورت سؤال؟",
                visual_required=True, visual_type="diagram",
            )
        return _transcript(kind="solution", model=kwargs["model"])

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)
    updated, audit = stage5.finalize_stage5_regions(
        original, pdf_data=b"%PDF-fake",
        decisions=[_decision(kind="question", suspicious=False), _decision(kind="solution", suspicious=False)],
    )

    row = next(item for item in audit["regions"] if item["kind"] == "question")
    assert row["status"] == "verified_visual_source_main"
    assert updated.publication_ready is True


def test_stage5_consensus_cannot_override_native_answer_label(monkeypatch):
    decisions = [
        _decision(kind="question", suspicious=False),
        _decision(kind="solution", suspicious=False),
    ]
    calls: list[str] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs["model"])
        text = (
            "1- گزینه «3»\nپاسخ تشریحی"
            if kwargs["kind"] == "solution"
            else None
        )
        return _transcript(kind=kwargs["kind"], model=kwargs["model"], text=text)

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=decisions,
    )

    question = updated.projection["exam_prep"]["questions"][0]
    assert calls == ["gpt-5.4-mini", "gpt-5.4-mini", "gemini-3.6-flash"]
    assert question["correct_option_label"] == "2"
    assert question["final_answer_markdown"] == "گزینه 2"
    assert "stage5_finalization_blocked" in question["issues"]
    solution_row = next(row for row in audit["regions"] if row["kind"] == "solution")
    assert solution_row["status"] == "blocked_answer_label_conflict"


def test_stage5_sanitizes_source_urls_without_another_model_call(monkeypatch):
    stem = "صورت سؤال؟ https://example.invalid/source"
    question_decision = replace(
        _decision(kind="question", suspicious=False),
        candidate_text=stem + "\n1) الف\n2) ب\n3) ج\n4) د",
    )
    calls: list[str] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs["model"])
        return _transcript(
            kind=kwargs["kind"],
            model=kwargs["model"],
            text=(
                stem + "\n1) الف\n2) ب\n3) ج\n4) د"
                if kwargs["kind"] == "question"
                else None
            ),
        )

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(text=stem),
        pdf_data=b"%PDF-fake",
        decisions=[question_decision, _decision(kind="solution", suspicious=False)],
    )

    question = updated.projection["exam_prep"]["questions"][0]
    assert calls == ["gpt-5.4-mini", "gpt-5.4-mini"]
    assert question["question_text_markdown"] == "صورت سؤال؟"
    assert audit["stats"]["finalSanitizerQuestionCount"] == 1
    assert audit["policy"]["globalFinalSanitizer"] is True


def test_stage5_primary_reads_every_region_one_crop_per_call(monkeypatch):
    decisions = [
        _decision(kind="question", suspicious=False),
        _decision(kind="solution", suspicious=True),
    ]
    calls: list[dict] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs)
        return _transcript(kind=kwargs["kind"], model=kwargs["model"])

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    _updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=decisions,
    )

    assert [call["model"] for call in calls] == [
        "gpt-5.4-mini",
        "gpt-5.4-mini",
    ]
    assert [call["image"] for call in calls] == [b"png", b"png"]
    assert all(call["thinking_minimal"] is False for call in calls)
    assert all(call["max_output_tokens"] == 2500 for call in calls)
    assert all(call["timeout"] == 60.0 for call in calls)
    assert audit["stats"] == {
        "regions": 2,
        "missingRegions": 0,
        "primaryCalls": 2,
        "mainCalls": 0,
        "primaryFormatRetries": 0,
        "mainFormatRetries": 0,
        "formatRetries": 0,
        "primaryDegradedRechecks": 0,
        "mainDisagreementRechecks": 0,
        "tiebreakerCalls": 0,
        "verified": 2,
        "repaired": 0,
        "blocked": 0,
        "successfulInputTokens": 200,
        "successfulOutputTokens": 40,
        "successfulTotalTokens": 240,
        "finalSanitizerQuestionCount": 0,
    }
    assert audit["policy"]["oneRegionOneImageOneCall"] is False
    assert audit["policy"]["oneRegionOneImagePerAttempt"] is True
    assert audit["policy"]["maxFormatRetriesPerRegion"] == 1
    assert audit["policy"]["maxPrimaryDegradedRechecksPerRegion"] == 1
    assert audit["policy"]["maxMainDisagreementRechecksPerRegion"] == 1
    assert audit["policy"]["allRegionsReceivePrimary"] is True


def test_stage5_primary_cap_fails_closed_before_any_paid_call(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAX_PRIMARY_CALLS", "1")
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)
    monkeypatch.setattr(
        stage5,
        "transcribe_source_region",
        lambda **kwargs: calls.append(kwargs),
    )

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[
            _decision(kind="question", suspicious=False),
            _decision(kind="solution", suspicious=False),
        ],
    )

    assert calls == []
    assert updated.publication_ready is False
    assert audit["stats"]["primaryCalls"] == 0
    assert audit["stats"]["blocked"] == 2
    assert audit["budget"]["primaryCap"] == 1
    assert audit["budget"]["preflightExceeded"] is True
    assert all(
        row["status"] == "blocked_primary_cost_cap" for row in audit["regions"]
    )


def test_stage5_primary_failure_is_counted_and_main_can_verify_candidate(monkeypatch):
    decisions = [
        _decision(kind="question", suspicious=False),
        _decision(kind="solution", suspicious=False),
    ]
    calls: list[str] = []
    failed_once = False
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        nonlocal failed_once
        calls.append(kwargs["model"])
        if kwargs["kind"] == "question" and not failed_once:
            failed_once = True
            raise TimeoutError("primary timeout")
        return _transcript(kind=kwargs["kind"], model=kwargs["model"])

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=decisions,
    )

    assert calls == ["gpt-5.4-mini", "gpt-5.4-mini", "gemini-3.6-flash"]
    assert updated.publication_ready is True
    assert audit["stats"]["primaryCalls"] == 2
    assert audit["stats"]["mainCalls"] == 1
    assert audit["stats"]["successfulTotalTokens"] == 240
    assert audit["stats"]["blocked"] == 0
    question_row = next(row for row in audit["regions"] if row["kind"] == "question")
    assert question_row["primaryFailure"] == "TimeoutError"
    assert question_row["status"] == "verified_source_main"


def test_stage5_rejects_same_primary_and_main_model_before_calls(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setenv("EXAM_PREP_STAGE5_PRIMARY_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAIN_MODEL", "gemini-3.6-flash")
    monkeypatch.setattr(
        stage5,
        "transcribe_source_region",
        lambda **kwargs: calls.append(kwargs),
    )

    try:
        stage5.finalize_stage5_regions(
            _result(),
            pdf_data=b"%PDF-fake",
            decisions=[
                _decision(kind="question", suspicious=False),
                _decision(kind="solution", suspicious=False),
            ],
        )
    except ValueError as exc:
        assert "distinct" in str(exc)
    else:  # pragma: no cover - keeps the assertion dependency-free
        raise AssertionError("same-model Stage 5 configuration must fail")
    assert calls == []


def test_stage5_high_similarity_word_error_requires_main_consensus(monkeypatch):
    candidate_stem = "کدام عبارت درباره تعداد الکترون های تایپوندی مولکول درست است؟"
    source_stem = "کدام عبارت درباره تعداد الکترون های ناپیوندی مولکول درست است؟"
    question_decision = replace(
        _decision(kind="question", suspicious=False),
        candidate_text=candidate_stem + "\n1) الف\n2) ب\n3) ج\n4) د",
    )
    visual = {"id": "v1", "role": "question", "sanity": {"status": "passed"}}
    original = _result(text=candidate_stem, visuals=[visual])
    original_question = original.projection["exam_prep"]["questions"][0]
    calls: list[str] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["kind"] == "solution":
            return _transcript(kind="solution", model=kwargs["model"])
        return _transcript(
            kind="question",
            model=kwargs["model"],
            text=source_stem + "\n1) الف\n2) ب\n3) ج\n4) د",
        )

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        original,
        pdf_data=b"%PDF-fake",
        decisions=[question_decision, _decision(kind="solution", suspicious=False)],
    )

    assert calls == ["gpt-5.4-mini", "gpt-5.4-mini", "gemini-3.6-flash"]
    question = updated.projection["exam_prep"]["questions"][0]
    assert question["question_text_markdown"] == source_stem
    assert question["correct_option_label"] == original_question["correct_option_label"]
    assert question["final_answer_markdown"] == original_question["final_answer_markdown"]
    assert question["visuals"] == original_question["visuals"]
    assert question["visualSourceContract"] == original_question["visualSourceContract"]
    assert question["source_regions"] == original_question["source_regions"]
    assert audit["stats"]["mainCalls"] == 1
    assert audit["stats"]["repaired"] == 1
    assert audit["stats"]["blocked"] == 0


def test_stage5_accepts_safe_nonexact_primary_corroboration_without_main(monkeypatch):
    candidate = "این عبارت درباره ساختار یاخته و عملکرد آن درست است؟"
    source = "این عبارت دربارهٔ ساختار یاخته و عملکرد آن درست است؟"
    question_decision = replace(
        _decision(kind="question", suspicious=False),
        candidate_text=candidate + "\n1) الف\n2) ب\n3) ج\n4) د",
    )
    calls: list[str] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs["model"])
        return _transcript(
            kind=kwargs["kind"],
            model=kwargs["model"],
            text=(
                source + "\n1) الف\n2) ب\n3) ج\n4) د"
                if kwargs["kind"] == "question"
                else None
            ),
        )

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(text=candidate),
        pdf_data=b"%PDF-fake",
        decisions=[question_decision, _decision(kind="solution", suspicious=False)],
    )

    assert calls == ["gpt-5.4-mini", "gpt-5.4-mini"]
    assert updated.publication_ready is True
    question_row = next(row for row in audit["regions"] if row["kind"] == "question")
    assert question_row["status"] == "verified_source"
    assert question_row["candidateSimilarity"] < 1.0


def test_stage5_combines_field_level_corroboration_without_mutating_candidate(
    monkeypatch,
):
    original = _result(text="صورت اصلی سؤال؟")
    question = original.projection["exam_prep"]["questions"][0]
    question["options"][0]["text_markdown"] = "گزینه اصلی و دقیق شماره یک"
    question_decision = replace(
        _decision(kind="question", suspicious=False),
        candidate_text=(
            "صورت اصلی سؤال؟\n"
            "1) گزینه اصلی و دقیق شماره یک\n2) ب\n3) ج\n4) د"
        ),
    )
    calls: list[str] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["kind"] == "solution":
            return _transcript(kind="solution", model=kwargs["model"])
        if kwargs["model"] == "gpt-5.4-mini":
            text = (
                "صورت متفاوت سؤال؟\n"
                "1) گزینه اصلی و دقیق شماره یک\n2) ب\n3) ج\n4) د"
            )
        else:
            text = (
                "صورت اصلی سؤال؟\n"
                "1) گزینه کاملاً متفاوت\n2) ب\n3) ج\n4) د"
            )
        return _transcript(kind="question", model=kwargs["model"], text=text)

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        original,
        pdf_data=b"%PDF-fake",
        decisions=[question_decision, _decision(kind="solution", suspicious=False)],
    )

    output = updated.projection["exam_prep"]["questions"][0]
    question_row = next(row for row in audit["regions"] if row["kind"] == "question")
    assert calls == ["gpt-5.4-mini", "gpt-5.4-mini", "gemini-3.6-flash"]
    assert question_row["status"] == "verified_source_consensus"
    assert output["question_text_markdown"] == "صورت اصلی سؤال؟"
    assert output["options"][0]["text_markdown"] == "گزینه اصلی و دقیق شماره یک"


@pytest.mark.parametrize("kind", ["question", "solution"])
def test_stage5_rejects_transcript_bound_to_wrong_target_heading(monkeypatch, kind):
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        return _transcript(
            kind=kwargs["kind"],
            model=kwargs["model"],
            target_number=2,
        )

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[_decision(kind=kind, suspicious=False)],
        required_targets={(1, kind)},
    )

    row = audit["regions"][0]
    assert row["status"] == "blocked_main_failed"
    assert row["primaryTargetConfirmed"] is False
    assert row["mainTargetConfirmed"] is False
    assert "stage5_finalization_blocked" in updated.projection["exam_prep"]["questions"][0]["issues"]


def test_stage5_uncertain_primary_uses_main_but_never_guesses(monkeypatch):
    solution_decision = _decision(kind="solution", suspicious=False)
    calls: list[str] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["kind"] == "question":
            return _transcript(kind="question", model=kwargs["model"])
        return _transcript(
            kind="solution",
            model=kwargs["model"],
            uncertain=True,
            text="ناخوانا",
        )

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[_decision(kind="question", suspicious=False), solution_decision],
    )

    assert calls == ["gpt-5.4-mini", "gpt-5.4-mini", "gemini-3.6-flash"]
    question = updated.projection["exam_prep"]["questions"][0]
    assert question["teacher_solution_markdown"] == "پاسخ تشریحی"
    assert "stage5_finalization_blocked" in question["issues"]
    assert audit["stats"]["mainCalls"] == 1
    assert audit["stats"]["blocked"] == 1


def test_stage5_hard_math_disagreement_blocks_without_a_slow_third_model(monkeypatch):
    question_decision = replace(
        _decision(kind="question", suspicious=False, hard_math=True),
        candidate_text="مقدار؟\n1) 10\n2) 20\n3) 30\n4) 40",
    )
    calls: list[str] = []
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)

    def transcribe(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["kind"] == "solution":
            return _transcript(kind="solution", model=kwargs["model"])
        first = "12" if kwargs["model"] == "gemini-3.6-flash" else "11"
        return _transcript(
            kind="question",
            model=kwargs["model"],
            text=f"مقدار؟\n1) {first}\n2) 20\n3) 30\n4) 40",
        )

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    updated, audit = stage5.finalize_stage5_regions(
        _result(text="مقدار؟"),
        pdf_data=b"%PDF-fake",
        decisions=[question_decision, _decision(kind="solution", suspicious=False)],
    )

    assert calls == [
        "gpt-5.4-mini",
        "gpt-5.4-mini",
        "gemini-3.6-flash",
        "gemini-3.6-flash",
    ]
    question = updated.projection["exam_prep"]["questions"][0]
    assert question["options"][0]["text_markdown"] == "الف"
    assert "stage5_finalization_blocked" in question["issues"]
    assert audit["stats"]["tiebreakerCalls"] == 0
    assert audit["stats"]["mainDisagreementRechecks"] == 1
    assert audit["stats"]["repaired"] == 0
    assert audit["stats"]["blocked"] == 1
    question_row = next(row for row in audit["regions"] if row["kind"] == "question")
    assert question_row["mainDisagreementRecheck"] is True
    assert question_row["mainDisagreementRecheckFailure"] == "still_disagrees"


def test_stage5_main_cap_is_selected_in_input_order_after_parallel_primary(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("EXAM_PREP_STAGE5_MAX_MAIN_CALLS", "1")
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)
    calls: list[tuple[str, str]] = []

    def transcribe(**kwargs):
        model = kwargs["model"]
        kind = kwargs["kind"]
        calls.append((model, kind))
        if model == "gpt-5.4-mini":
            time.sleep(0.05 if kind == "question" else 0.001)
            text = (
                "صورت متفاوت؟\n1) یک\n2) دو\n3) سه\n4) چهار"
                if kind == "question"
                else "پاسخ متفاوت"
            )
            return _transcript(kind=kind, model=model, text=text)
        return _transcript(kind=kind, model=model)

    monkeypatch.setattr(stage5, "transcribe_source_region", transcribe)

    _updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[
            _decision(kind="question", suspicious=False),
            _decision(kind="solution", suspicious=False),
        ],
    )

    assert ("gemini-3.6-flash", "question") in calls
    assert ("gemini-3.6-flash", "solution") not in calls
    rows = {row["kind"]: row for row in audit["regions"]}
    assert rows["question"]["status"] == "verified_source_main"
    assert rows["solution"]["status"] == "blocked_main_cost_cap"
    assert audit["stats"]["mainCalls"] == 1


def test_stage5_deadline_stops_new_calls_and_fails_closed(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(stage5, "_max_wall_seconds", lambda: 0)
    monkeypatch.setattr(stage5, "_render_crops", _fake_crops)
    monkeypatch.setattr(
        stage5,
        "transcribe_source_region",
        lambda **kwargs: calls.append(kwargs),
    )

    updated, audit = stage5.finalize_stage5_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        decisions=[
            _decision(kind="question", suspicious=False),
            _decision(kind="solution", suspicious=False),
        ],
    )

    assert calls == []
    assert updated.publication_ready is False
    assert audit["stats"]["primaryCalls"] == 0
    assert audit["stats"]["mainCalls"] == 0
    assert audit["stats"]["blocked"] == 2
    assert audit["budget"]["deadlineExceeded"] is True
    assert all(
        row["status"] == "blocked_stage5_deadline"
        for row in audit["regions"]
    )