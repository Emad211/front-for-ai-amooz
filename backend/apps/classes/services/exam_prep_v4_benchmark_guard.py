"""Hard provider-call guard for the explicit private Exam Prep V4 benchmark.

The full benchmark runner intentionally shares the production classifier and
semantic providers. This module adds a command-scoped call ceiling without
changing production request behavior or persisting credentials/budget state.

The guard is process-local and is intended only for the single-process Django
management command. It temporarily wraps the provider symbols imported by the
benchmark module, restores them in ``finally``, and fails before the next
external call when the approved ceiling has been consumed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.classes.services import exam_prep_v4_full_benchmark as benchmark


@dataclass(slots=True)
class LiveProviderCallBudget:
    """A strict, monotonic ceiling consumed immediately before provider calls."""

    limit: int
    used: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.limit, bool) or int(self.limit) < 1:
            raise benchmark.FullBenchmarkError(
                'Live benchmark requires max_provider_calls >= 1.'
            )
        self.limit = int(self.limit)

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def consume(self, stage: str) -> None:
        stage_name = str(stage or 'unknown')[:100]
        if self.used >= self.limit:
            raise benchmark.FullBenchmarkError(
                'Live provider-call budget exhausted before '
                f'{stage_name}; used={self.used}, limit={self.limit}.'
            )
        self.used += 1

    def as_report(self) -> dict[str, int]:
        return {
            'limit': self.limit,
            'used': self.used,
            'remaining': self.remaining,
        }


class _BudgetedExtractionProvider:
    """Delegate production provider methods through one shared call budget."""

    def __init__(self, delegate: Any, budget: LiveProviderCallBudget) -> None:
        self._delegate = delegate
        self._budget = budget

    @property
    def provider_calls(self) -> int:
        return int(self._delegate.provider_calls)

    def detect_segment_blocks(self, **kwargs):
        self._budget.consume('block_detection')
        return self._delegate.detect_segment_blocks(**kwargs)

    def extract_questions_batch(self, **kwargs):
        self._budget.consume('question_extraction')
        return self._delegate.extract_questions_batch(**kwargs)

    def extract_answer_solutions_batch(self, **kwargs):
        self._budget.consume('answer_solution_extraction')
        return self._delegate.extract_answer_solutions_batch(**kwargs)

    def extract_question(self, **kwargs):
        self._budget.consume('question_extraction')
        return self._delegate.extract_question(**kwargs)

    def extract_answer_solution(self, **kwargs):
        self._budget.consume('answer_solution_extraction')
        return self._delegate.extract_answer_solution(**kwargs)


def run_bounded_full_pipeline_benchmark(
    *,
    manifest: benchmark.FullBenchmarkManifest,
    mode: benchmark.FullBenchmarkMode,
    classifier_model: str | None = None,
    block_model: str | None = None,
    question_model: str | None = None,
    answer_model: str | None = None,
    keep_projects: bool = False,
    max_provider_calls: int | None = None,
) -> benchmark.FullBenchmarkRunResult:
    """Run the existing benchmark with a mandatory hard ceiling in live mode."""

    if mode != 'live_provider':
        return benchmark.run_full_pipeline_benchmark(
            manifest=manifest,
            mode=mode,
            classifier_model=classifier_model,
            block_model=block_model,
            question_model=question_model,
            answer_model=answer_model,
            keep_projects=keep_projects,
        )

    if max_provider_calls is None:
        raise benchmark.FullBenchmarkError(
            'Live benchmark requires an explicit max_provider_calls ceiling.'
        )
    budget = LiveProviderCallBudget(max_provider_calls)

    original_classifier = benchmark.classify_document_pages_fast
    original_provider_class = benchmark.StructuredLLMExamPrepV4Provider

    def budgeted_classifier(*args, **kwargs):
        budget.consume('page_classification')
        return original_classifier(*args, **kwargs)

    def budgeted_provider_factory(*args, **kwargs):
        delegate = original_provider_class(*args, **kwargs)
        return _BudgetedExtractionProvider(delegate, budget)

    benchmark.classify_document_pages_fast = budgeted_classifier
    benchmark.StructuredLLMExamPrepV4Provider = budgeted_provider_factory
    try:
        result = benchmark.run_full_pipeline_benchmark(
            manifest=manifest,
            mode=mode,
            classifier_model=classifier_model,
            block_model=block_model,
            question_model=question_model,
            answer_model=answer_model,
            keep_projects=keep_projects,
        )
    finally:
        benchmark.classify_document_pages_fast = original_classifier
        benchmark.StructuredLLMExamPrepV4Provider = original_provider_class

    report = dict(result.report)
    report['providerCallBudget'] = budget.as_report()
    benchmark._assert_aggregate_report(report)
    return benchmark.FullBenchmarkRunResult(
        report=report,
        project_ids=result.project_ids,
    )
