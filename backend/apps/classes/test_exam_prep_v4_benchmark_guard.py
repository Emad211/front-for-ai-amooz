from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.classes.models_v4 import ExamProject
from apps.classes.services import exam_prep_v4_full_benchmark as benchmark
from apps.classes.services.exam_prep_v4_benchmark_guard import (
    MAX_EXTERNAL_REQUESTS_PER_INVOCATION,
    LiveProviderCallBudget,
    calculate_required_external_request_ceiling,
    run_bounded_full_pipeline_benchmark,
)
from apps.classes.services.exam_prep_v4_full_benchmark import (
    FullBenchmarkFixture,
    FullBenchmarkManifest,
    FullBenchmarkNumberRange,
    FullBenchmarkSegmentSpec,
    load_full_benchmark_manifest,
)
from apps.classes.test_exam_prep_v4_full_benchmark import _manifest


def test_live_call_budget_reserves_structured_and_direct_requests():
    budget = LiveProviderCallBudget(limit=7, required_minimum=6)

    budget.reserve('page_classification')
    budget.reserve_external('ocr_document_annotation')
    assert budget.as_report() == {
        'limit': 7,
        'requiredMinimum': 6,
        'reservedUpperBound': 4,
        'remaining': 3,
        'pipelineInvocations': 1,
        'directExternalRequests': 1,
        'maxExternalRequestsPerInvocation': 3,
    }

    budget.reserve('block_detection')
    assert budget.remaining == 0
    with pytest.raises(benchmark.FullBenchmarkError, match='exhausted'):
        budget.reserve_external('ocr_bbox_annotation')


@pytest.mark.parametrize('invalid_limit', [True, 0, 1, 2, 3.5, '6'])
def test_live_call_budget_rejects_non_positive_or_unsafe_limits(invalid_limit):
    with pytest.raises(benchmark.FullBenchmarkError):
        LiveProviderCallBudget(limit=invalid_limit)


def test_manifest_ceiling_includes_ocr_retry_bbox_and_structured_fallbacks(
    tmp_path,
):
    manifest_path, _private_paths = _manifest(tmp_path)
    manifest = load_full_benchmark_manifest(manifest_path)

    no_ocr = calculate_required_external_request_ceiling(
        manifest=manifest,
    )
    with_ocr = calculate_required_external_request_ceiling(
        manifest=manifest,
        ocr_evidence_enabled=True,
        ocr_max_attempts=2,
        ocr_bbox_for_diagrams=True,
    )

    assert no_ocr == {
        'fixtureCount': 3,
        'classificationInvocations': 3,
        'blockFallbackInvocations': 6,
        'semanticBatchInvocations': 7,
        'structuredInvocationCount': 16,
        'structuredExternalUpperBound': 48,
        'ocrEligiblePageCount': 0,
        'ocrExternalUpperBound': 0,
        'requiredMinimum': 48,
    }
    assert with_ocr['ocrEligiblePageCount'] == 9
    assert with_ocr['ocrExternalUpperBound'] == 36
    assert with_ocr['requiredMinimum'] == 84


def test_recorded_three_private_fixture_ceiling_is_484():
    def fixture(
        fixture_id,
        page_count,
        segments,
        question_start,
        question_end,
        out_of_scope,
    ):
        return FullBenchmarkFixture(
            fixture_id=fixture_id,
            pattern='cover_questions_solutions',
            path=Path('/private/not-opened.pdf'),
            expected_page_count=page_count,
            expected_segments=tuple(
                FullBenchmarkSegmentSpec(
                    startPage=start,
                    endPage=end,
                    role=role,
                )
                for start, end, role in segments
            ),
            expected_question_numbers=(question_start, question_end),
            expected_out_of_scope_numbers=tuple(out_of_scope),
        )

    manifest = FullBenchmarkManifest(
        fixtures=(
            fixture(
                'fixture-a',
                16,
                ((1, 1, 'cover'), (2, 8, 'questions'), (9, 16, 'answer_solutions')),
                1,
                50,
                (51, 52, 53, 54),
            ),
            fixture(
                'fixture-b',
                27,
                ((1, 11, 'answer_solutions'), (12, 12, 'cover'), (13, 27, 'questions')),
                51,
                115,
                (49, 50, 116, 117),
            ),
            fixture(
                'fixture-c',
                15,
                ((1, 1, 'cover'), (2, 8, 'questions'), (9, 15, 'answer_solutions')),
                116,
                145,
                (114, 115, 146, 147),
            ),
        )
    )

    plan = calculate_required_external_request_ceiling(
        manifest=manifest,
        ocr_evidence_enabled=True,
        ocr_max_attempts=2,
        ocr_bbox_for_diagrams=True,
    )

    assert plan == {
        'fixtureCount': 3,
        'classificationInvocations': 3,
        'blockFallbackInvocations': 6,
        'semanticBatchInvocations': 79,
        'structuredInvocationCount': 88,
        'structuredExternalUpperBound': 264,
        'ocrEligiblePageCount': 55,
        'ocrExternalUpperBound': 220,
        'requiredMinimum': 484,
    }


def _install_fake_live_runner(monkeypatch, calls: list[str]):
    def fake_classifier(*args, **kwargs):
        calls.append('page_classification')
        return object()

    class FakeProvider:
        def __init__(self, *args, **kwargs):
            self.provider_calls = 0

        def detect_segment_blocks(self, **kwargs):
            calls.append('block_detection')
            self.provider_calls += 1
            return {'blocks': []}

        def extract_questions_batch(self, **kwargs):
            calls.append('question_extraction')
            self.provider_calls += 1
            return {'questions': []}

        def extract_answer_solutions_batch(self, **kwargs):
            calls.append('answer_solution_extraction')
            self.provider_calls += 1
            return {'answers': []}

        def extract_question(self, **kwargs):
            raise AssertionError('single-block path was not expected')

        def extract_answer_solution(self, **kwargs):
            raise AssertionError('single-block path was not expected')

    original_classifier = fake_classifier
    original_provider = FakeProvider

    def fake_runner(**kwargs):
        benchmark.classify_document_pages_fast()
        provider = benchmark.StructuredLLMExamPrepV4Provider()
        provider.detect_segment_blocks()
        provider.extract_questions_batch()
        return benchmark.FullBenchmarkRunResult(
            report={'acceptance': {'passed': True}},
            project_ids=(),
        )

    monkeypatch.setattr(benchmark, 'classify_document_pages_fast', original_classifier)
    monkeypatch.setattr(benchmark, 'StructuredLLMExamPrepV4Provider', original_provider)
    monkeypatch.setattr(benchmark, 'run_full_pipeline_benchmark', fake_runner)
    return original_classifier, original_provider


def test_bounded_runner_reports_reservation_and_restores_provider_symbols(
    monkeypatch,
):
    calls: list[str] = []
    original_classifier, original_provider = _install_fake_live_runner(
        monkeypatch,
        calls,
    )

    result = run_bounded_full_pipeline_benchmark(
        manifest=object(),
        mode='live_provider',
        classifier_model='classifier',
        block_model='block',
        question_model='question',
        answer_model='answer',
        max_provider_calls=9,
    )

    assert calls == [
        'page_classification',
        'block_detection',
        'question_extraction',
    ]
    assert result.report['providerCallBudget'] == {
        'limit': 9,
        'requiredMinimum': 3,
        'reservedUpperBound': 9,
        'remaining': 0,
        'pipelineInvocations': 3,
        'directExternalRequests': 0,
        'maxExternalRequestsPerInvocation': (
            MAX_EXTERNAL_REQUESTS_PER_INVOCATION
        ),
    }
    assert result.report['ocrEvidence']['enabled'] is False
    assert benchmark.classify_document_pages_fast is original_classifier
    assert benchmark.StructuredLLMExamPrepV4Provider is original_provider


def test_bounded_runner_fails_before_call_beyond_runtime_limit_and_restores(
    monkeypatch,
):
    calls: list[str] = []
    original_classifier, original_provider = _install_fake_live_runner(
        monkeypatch,
        calls,
    )

    with pytest.raises(benchmark.FullBenchmarkError, match='exhausted'):
        run_bounded_full_pipeline_benchmark(
            manifest=object(),
            mode='live_provider',
            classifier_model='classifier',
            block_model='block',
            question_model='question',
            answer_model='answer',
            max_provider_calls=6,
        )

    assert calls == ['page_classification', 'block_detection']
    assert benchmark.classify_document_pages_fast is original_classifier
    assert benchmark.StructuredLLMExamPrepV4Provider is original_provider


def test_fake_mode_does_not_require_or_emit_live_call_budget(monkeypatch):
    expected = benchmark.FullBenchmarkRunResult(
        report={'acceptance': {'passed': True}},
        project_ids=(),
    )
    calls: list[str] = []

    def fake_runner(**kwargs):
        calls.append(kwargs['mode'])
        return expected

    monkeypatch.setattr(benchmark, 'run_full_pipeline_benchmark', fake_runner)
    result = run_bounded_full_pipeline_benchmark(
        manifest=object(),
        mode='fake_provider',
    )

    assert result is expected
    assert calls == ['fake_provider']
    assert 'providerCallBudget' not in result.report


@pytest.mark.django_db
def test_show_required_ceiling_exits_before_project_or_provider(
    tmp_path,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, _private_paths = _manifest(tmp_path)
    report_path = Path(tmp_path) / 'must-not-exist.json'
    stdout = io.StringIO()

    call_command(
        'benchmark_exam_prep_v4_full_pipeline',
        manifest=str(manifest_path),
        mode='live_provider',
        model='vision-model',
        ocr_evidence=True,
        ocr_bbox_for_diagrams=True,
        show_required_ceiling=True,
        report=str(report_path),
        stdout=stdout,
    )

    plan = json.loads(stdout.getvalue())
    assert plan['requiredMinimum'] == 84
    assert not report_path.exists()
    assert ExamProject.objects.count() == 0


@pytest.mark.django_db
def test_live_command_requires_call_ceiling_before_project_or_report_write(
    tmp_path,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, _private_paths = _manifest(tmp_path)
    report_path = Path(tmp_path) / 'must-not-exist.json'

    with pytest.raises(CommandError, match='max_provider_calls'):
        call_command(
            'benchmark_exam_prep_v4_full_pipeline',
            manifest=str(manifest_path),
            mode='live_provider',
            model='vision-model',
            report=str(report_path),
        )

    assert not report_path.exists()
    assert ExamProject.objects.count() == 0


@pytest.mark.django_db
def test_live_command_rejects_ceiling_below_manifest_plan_before_projects(
    tmp_path,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, _private_paths = _manifest(tmp_path)
    report_path = Path(tmp_path) / 'must-not-exist.json'

    with pytest.raises(CommandError, match='required minimum'):
        call_command(
            'benchmark_exam_prep_v4_full_pipeline',
            manifest=str(manifest_path),
            mode='live_provider',
            model='vision-model',
            ocr_evidence=True,
            ocr_bbox_for_diagrams=True,
            max_provider_calls=83,
            report=str(report_path),
        )

    assert not report_path.exists()
    assert ExamProject.objects.count() == 0
