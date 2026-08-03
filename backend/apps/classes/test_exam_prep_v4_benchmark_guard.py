from __future__ import annotations

from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.classes.models_v4 import ExamProject
from apps.classes.services import exam_prep_v4_full_benchmark as benchmark
from apps.classes.services.exam_prep_v4_benchmark_guard import (
    MAX_EXTERNAL_REQUESTS_PER_INVOCATION,
    LiveProviderCallBudget,
    run_bounded_full_pipeline_benchmark,
)
from apps.classes.test_exam_prep_v4_full_benchmark import _manifest


def test_live_call_budget_reserves_worst_case_external_requests():
    budget = LiveProviderCallBudget(limit=6)

    budget.reserve('page_classification')
    assert budget.as_report() == {
        'limit': 6,
        'reservedUpperBound': 3,
        'remaining': 3,
        'pipelineInvocations': 1,
        'maxExternalRequestsPerInvocation': 3,
    }

    budget.reserve('block_detection')
    assert budget.remaining == 0
    with pytest.raises(benchmark.FullBenchmarkError, match='exhausted'):
        budget.reserve('question_extraction')


@pytest.mark.parametrize('invalid_limit', [True, 0, 1, 2, 3.5, '6'])
def test_live_call_budget_rejects_non_positive_or_unsafe_limits(invalid_limit):
    with pytest.raises(benchmark.FullBenchmarkError):
        LiveProviderCallBudget(limit=invalid_limit)


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

    monkeypatch.setattr(
        benchmark,
        'classify_document_pages_fast',
        original_classifier,
    )
    monkeypatch.setattr(
        benchmark,
        'StructuredLLMExamPrepV4Provider',
        original_provider,
    )
    monkeypatch.setattr(
        benchmark,
        'run_full_pipeline_benchmark',
        fake_runner,
    )
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
        'reservedUpperBound': 9,
        'remaining': 0,
        'pipelineInvocations': 3,
        'maxExternalRequestsPerInvocation': (
            MAX_EXTERNAL_REQUESTS_PER_INVOCATION
        ),
    }
    assert benchmark.classify_document_pages_fast is original_classifier
    assert benchmark.StructuredLLMExamPrepV4Provider is original_provider


def test_bounded_runner_fails_before_call_beyond_limit_and_restores_symbols(
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
