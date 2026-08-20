from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
from django.core.management.base import CommandError
from pypdf import PdfWriter

from apps.classes.management.commands import replay_exam_prep_mistral_stage5 as replay
from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_stage5 as stage5
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _pdf(path: Path, *, pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as stream:
        writer.write(stream)
    return path.read_bytes()


def _bundle(
    path: Path,
    *,
    pdf_sha256: str,
    page_count: int = 1,
) -> Path:
    root = {
        "model": "mistral-ocr-4-0",
        "pages": [
            {"index": index, "markdown": "", "blocks": []}
            for index in range(page_count)
        ],
    }
    manifest = {
        "sourcePdfSha256": pdf_sha256,
        "originalPdfPageCount": page_count,
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("response.raw.json", json.dumps(root))
        archive.writestr("manifest.json", json.dumps(manifest))
    return path


def _assembly() -> PageAssemblyResult:
    return PageAssemblyResult(
        projection={
            "exam_prep": {
                "title": "target replay",
                "questions": [
                    {
                        "question_id": "q-65",
                        "source_question_number": 65,
                        "question_text_markdown": "Q65",
                        "options": [],
                        "issues": [],
                    },
                    {
                        "question_id": "q-66",
                        "source_question_number": 66,
                        "question_text_markdown": "Q66",
                        "options": [],
                        "issues": [],
                    },
                ],
            }
        },
        issues=[],
        question_count=2,
        questions_needing_review=0,
    )


def test_parse_targets_accepts_exact_region_keys_and_deduplicates():
    assert replay._parse_targets("question:65, solution:57;question:65") == frozenset(
        {(65, "question"), (57, "solution")}
    )


@pytest.mark.parametrize(
    "raw",
    ["", "question", "page:65", "question:0", "solution:not-a-number"],
)
def test_parse_targets_rejects_invalid_region_keys(raw):
    with pytest.raises(CommandError, match="target"):
        replay._parse_targets(raw)


def test_cached_input_rejects_pdf_bundle_sha_mismatch(tmp_path):
    pdf_path = tmp_path / "exam.pdf"
    _pdf(pdf_path)
    bundle_path = _bundle(
        tmp_path / "ocr.zip",
        pdf_sha256="0" * 64,
    )

    with pytest.raises(CommandError, match="SHA-256"):
        replay._load_cached_input(pdf_path=pdf_path, bundle_path=bundle_path)


def test_cached_input_rejects_pdf_bundle_page_count_mismatch(tmp_path):
    pdf_path = tmp_path / "exam.pdf"
    pdf_data = _pdf(pdf_path, pages=2)
    bundle_path = _bundle(
        tmp_path / "ocr.zip",
        pdf_sha256=sha256(pdf_data).hexdigest(),
        page_count=1,
    )

    with pytest.raises(CommandError, match="page count mismatch"):
        replay._load_cached_input(pdf_path=pdf_path, bundle_path=bundle_path)


def test_cached_runner_uses_only_cached_ocr_filters_targets_and_restores_patches(
    monkeypatch,
    tmp_path,
):
    cached_result = object()
    targets = frozenset({(65, "question")})
    assembly = _assembly()
    decision_65 = SimpleNamespace(question_number=65, kind="question")
    decision_66 = SimpleNamespace(question_number=66, kind="solution")
    calls: dict[str, object] = {}
    evidence: list[dict[str, object]] = []
    monkeypatch.setenv(replay._USAGE_LOG_ENV, "sentinel")

    def live_ocr(*args, **kwargs):
        raise AssertionError("live OCR must never run during cached replay")

    def live_targeted_recovery(*args, **kwargs):
        raise AssertionError("targeted OCR must never run during cached replay")

    def real_reconcile(result, **kwargs):
        questions = result.projection["exam_prep"]["questions"]
        calls["visualQuestionNumbers"] = [
            item["source_question_number"] for item in questions
        ]
        calls["visualStore"] = kwargs.get("store")
        assert "storage_namespace" not in kwargs
        assert "should_cancel" not in kwargs
        return result, {}, {}

    def real_score(**kwargs):
        return [decision_65, decision_66]

    def real_finalize(result, **kwargs):
        calls["requiredTargets"] = kwargs.get("required_targets")
        return result, {"stats": {}}

    monkeypatch.setattr(production, "fetch_ocr4_document", live_ocr)
    monkeypatch.setattr(production, "_targeted_recovery", live_targeted_recovery)
    monkeypatch.setattr(production, "reconcile_mistral_source_visuals", real_reconcile)
    monkeypatch.setattr(production, "score_region_risks", real_score)
    monkeypatch.setattr(production, "finalize_stage5_regions", real_finalize)
    transcribe_result = SimpleNamespace(
        response_id="response-1",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        reasoning_tokens=0,
        transcript={
            "transcriptionMarkdown": "source text",
            "sourceVisualRequired": False,
        },
    )

    def real_transcribe(*args, **kwargs):
        return transcribe_result

    monkeypatch.setattr(stage5, "_transcribe", real_transcribe)
    originals = {
        "fetch": production.fetch_ocr4_document,
        "targeted": production._targeted_recovery,
        "visual": production.reconcile_mistral_source_visuals,
        "risk": production.score_region_risks,
        "stage5": production.finalize_stage5_regions,
        "transcribe": stage5._transcribe,
    }

    def fake_runner(**kwargs):
        assert os.environ[replay._USAGE_LOG_ENV] == "0"
        assert production.fetch_ocr4_document(b"ignored") is cached_result
        assert production._targeted_recovery(b"ignored") == ({}, None)
        updated, _stats, _audit = production.reconcile_mistral_source_visuals(
            assembly,
            pdf_data=b"pdf",
            ocr_pages=(),
            layout={},
            source_sha256="a" * 64,
            storage_namespace="session/1",
            should_cancel=lambda: False,
        )
        decisions = production.score_region_risks(projection={}, layout={})
        assert decisions == [decision_65]
        production.finalize_stage5_regions(
            updated,
            pdf_data=b"pdf",
            decisions=decisions,
        )
        assert (
            stage5._transcribe(
                decision=SimpleNamespace(
                    question_number=65,
                    kind="question",
                    page_number=13,
                ),
                crop=b"png",
                model="gpt-5.4-mini",
            )
            is transcribe_result
        )
        raise RuntimeError("prove restoration on failure")

    monkeypatch.setattr(production, "run_exam_prep_mistral_pipeline", fake_runner)
    with pytest.raises(RuntimeError, match="prove restoration"):
        replay._run_cached_pipeline(
            pdf_data=b"pdf",
            cached_result=cached_result,
            title="target replay",
            targets=targets,
            visual_store=replay._DiagnosticStore(tmp_path / "visuals"),
            evidence_sink=evidence,
        )

    assert calls["visualQuestionNumbers"] == [65]
    assert isinstance(calls["visualStore"], replay._DiagnosticStore)
    assert calls["requiredTargets"] == targets
    assert production.fetch_ocr4_document is originals["fetch"]
    assert production._targeted_recovery is originals["targeted"]
    assert production.reconcile_mistral_source_visuals is originals["visual"]
    assert production.score_region_risks is originals["risk"]
    assert production.finalize_stage5_regions is originals["stage5"]
    assert stage5._transcribe is originals["transcribe"]
    assert production.run_exam_prep_mistral_pipeline is fake_runner
    assert os.environ[replay._USAGE_LOG_ENV] == "sentinel"
    assert evidence == [
        {
            "questionNumber": 65,
            "kind": "question",
            "pageNumber": 13,
            "model": "gpt-5.4-mini",
            "status": "succeeded",
            "responseId": "response-1",
            "inputTokens": 10,
            "outputTokens": 20,
            "totalTokens": 30,
            "reasoningTokens": 0,
            "transcript": {
                "transcriptionMarkdown": "source text",
                "sourceVisualRequired": False,
            },
        }
    ]


def test_manifest_separates_replay_spend_from_projected_production_total():
    result = SimpleNamespace(
        extraction_audit={
            "totalProviderCalls": 9,
            "stage5SuccessfulCallEstimatedCostUsd": "0.120000",
            "stage5ChargedCostUsd": "0.130000",
            "stage5CostEstimateComplete": False,
            "totalEstimatedCostUsd": "0.600000",
            "totalPdfBudgetUsd": "1.500000",
            "budgetWithinLimit": True,
            "riskEngine": {
                "stats": {
                    "primaryCalls": 2,
                    "mainCalls": 1,
                    "blocked": 0,
                    "verified": 3,
                    "repaired": 1,
                },
                "regions": [
                    {"status": "verified_source"},
                    {"status": "verified_source_main"},
                    {"status": "repaired_source"},
                ],
            },
        }
    )
    cached_result = SimpleNamespace(source_sha256="a" * 64, page_count=55)

    manifest = replay._build_manifest(
        result=result,
        cached_result=cached_result,
        bundle_name="cached.zip",
        targets=frozenset({(65, "question"), (57, "solution")}),
    )

    assert manifest["schemaVersion"] == 3
    assert manifest["callStats"]["ocrProviderCallsThisReplay"] == 0
    assert manifest["callStats"]["totalProviderCallsThisReplay"] == 3
    assert manifest["callStats"]["projectedProductionTotalProviderCalls"] == 9
    assert manifest["costStats"]["replayChargedCostUsd"] == "0.130000"
    assert manifest["costStats"]["replaySuccessfulUsageCostUsd"] == "0.120000"
    assert manifest["costStats"]["replayCostEstimateComplete"] is False
    assert (
        manifest["costStats"]["projectedProductionTotalEstimatedCostUsd"]
        == "0.600000"
    )
