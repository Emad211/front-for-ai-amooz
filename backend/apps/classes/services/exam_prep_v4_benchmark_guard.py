"""Hard external-request guard for the private Exam Prep V4 benchmark.

The guard is command-scoped and process-local. It keeps production provider
behavior unchanged while reserving a conservative upper bound before every
structured invocation and exactly one slot before every direct OCR HTTP call.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import os
from typing import Any

import requests

from apps.classes.services import exam_prep_v4_full_benchmark as benchmark
from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRTransportError,
    OCRHTTPResponse,
)
from apps.classes.services.exam_prep_v4_ocr_evidence import (
    AvalAIOCREvidenceAdapter,
    OCREvidenceAdapterConfig,
)


# Every structured invocation may issue JSON-mode, one response-format fallback,
# and one repair request. Reserve all three before entering the provider.
MAX_EXTERNAL_REQUESTS_PER_INVOCATION = 3


def _positive_batch_size() -> int:
    try:
        return max(
            1,
            int(os.getenv('EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BLOCKS', '4')),
        )
    except (TypeError, ValueError):
        return 4


def calculate_required_external_request_ceiling(
    *,
    manifest: Any,
    ocr_evidence_enabled: bool = False,
    ocr_max_attempts: int = 2,
    ocr_bbox_for_diagrams: bool = True,
) -> dict[str, int]:
    """Calculate a deterministic manifest/config upper bound before execution.

    The bound assumes one expected question block per in-scope question and one
    answer block per in-scope/out-of-scope answer. It reserves block-detector
    fallback for every non-cover segment, even when OCR is enabled. The runtime
    guard still fails closed if a provider returns more work than the manifest.
    """

    fixtures = tuple(getattr(manifest, 'fixtures', ()) or ())
    if not fixtures:
        return {
            'fixtureCount': 0,
            'classificationInvocations': 0,
            'blockFallbackInvocations': 0,
            'semanticBatchInvocations': 0,
            'structuredInvocationCount': 1,
            'structuredExternalUpperBound': (
                MAX_EXTERNAL_REQUESTS_PER_INVOCATION
            ),
            'ocrEligiblePageCount': 0,
            'ocrExternalUpperBound': 0,
            'requiredMinimum': MAX_EXTERNAL_REQUESTS_PER_INVOCATION,
        }

    if isinstance(ocr_max_attempts, bool) or ocr_max_attempts < 1:
        raise benchmark.FullBenchmarkError(
            'OCR max attempts must be a positive integer.'
        )

    batch_size = _positive_batch_size()
    classification_invocations = len(fixtures)
    block_invocations = 0
    semantic_invocations = 0
    ocr_pages = 0

    for fixture in fixtures:
        expected_start, expected_end = fixture.expected_question_numbers
        question_count = expected_end - expected_start + 1
        answer_count = question_count + len(fixture.expected_out_of_scope_numbers)
        semantic_invocations += math.ceil(question_count / batch_size)
        semantic_invocations += math.ceil(answer_count / batch_size)

        for segment in fixture.expected_segments:
            role = str(segment.role)
            if role in {'cover', 'ignored'}:
                continue
            block_invocations += 1
            ocr_pages += segment.end_page - segment.start_page + 1

    structured_invocations = (
        classification_invocations
        + block_invocations
        + semantic_invocations
    )
    structured_external = (
        structured_invocations * MAX_EXTERNAL_REQUESTS_PER_INVOCATION
    )
    ocr_external = 0
    if ocr_evidence_enabled:
        modes_per_page = 1 + int(bool(ocr_bbox_for_diagrams))
        ocr_external = ocr_pages * ocr_max_attempts * modes_per_page

    return {
        'fixtureCount': len(fixtures),
        'classificationInvocations': classification_invocations,
        'blockFallbackInvocations': block_invocations,
        'semanticBatchInvocations': semantic_invocations,
        'structuredInvocationCount': structured_invocations,
        'structuredExternalUpperBound': structured_external,
        'ocrEligiblePageCount': ocr_pages if ocr_evidence_enabled else 0,
        'ocrExternalUpperBound': ocr_external,
        'requiredMinimum': structured_external + ocr_external,
    }


@dataclass(slots=True)
class LiveProviderCallBudget:
    """Reserve hard upper bounds before structured and direct external calls."""

    limit: int
    required_minimum: int = MAX_EXTERNAL_REQUESTS_PER_INVOCATION
    reserved: int = 0
    pipeline_invocations: int = 0
    direct_external_requests: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.limit, bool) or not isinstance(self.limit, int):
            raise benchmark.FullBenchmarkError(
                'Live benchmark max_provider_calls must be a positive integer.'
            )
        if self.limit < self.required_minimum:
            raise benchmark.FullBenchmarkError(
                'Live benchmark max_provider_calls is below the calculated '
                f'required minimum; supplied={self.limit}, '
                f'required={self.required_minimum}.'
            )

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.reserved)

    def _reserve_count(self, *, stage: str, requested: int) -> None:
        stage_name = str(stage or 'unknown')[:100]
        if requested < 1:
            raise benchmark.FullBenchmarkError('Reserved call count must be positive.')
        if self.reserved + requested > self.limit:
            raise benchmark.FullBenchmarkError(
                'Live provider-call budget exhausted before '
                f'{stage_name}; reserved={self.reserved}, '
                f'required={requested}, limit={self.limit}.'
            )
        self.reserved += requested

    def reserve(self, stage: str) -> None:
        self._reserve_count(
            stage=stage,
            requested=MAX_EXTERNAL_REQUESTS_PER_INVOCATION,
        )
        self.pipeline_invocations += 1

    def reserve_external(self, stage: str) -> None:
        self._reserve_count(stage=stage, requested=1)
        self.direct_external_requests += 1

    def as_report(self) -> dict[str, int]:
        return {
            'limit': self.limit,
            'requiredMinimum': self.required_minimum,
            'reservedUpperBound': self.reserved,
            'remaining': self.remaining,
            'pipelineInvocations': self.pipeline_invocations,
            'directExternalRequests': self.direct_external_requests,
            'maxExternalRequestsPerInvocation': (
                MAX_EXTERNAL_REQUESTS_PER_INVOCATION
            ),
        }


class _BudgetedExtractionProvider:
    """Delegate existing structured provider methods through one budget."""

    def __init__(self, delegate: Any, budget: LiveProviderCallBudget) -> None:
        self._delegate = delegate
        self._budget = budget

    @property
    def provider_calls(self) -> int:
        return int(self._delegate.provider_calls)

    def detect_segment_blocks(self, **kwargs):
        self._budget.reserve('block_detection')
        return self._delegate.detect_segment_blocks(**kwargs)

    def extract_questions_batch(self, **kwargs):
        self._budget.reserve('question_extraction')
        return self._delegate.extract_questions_batch(**kwargs)

    def extract_answer_solutions_batch(self, **kwargs):
        self._budget.reserve('answer_solution_extraction')
        return self._delegate.extract_answer_solutions_batch(**kwargs)

    def extract_question(self, **kwargs):
        self._budget.reserve('question_extraction')
        return self._delegate.extract_question(**kwargs)

    def extract_answer_solution(self, **kwargs):
        self._budget.reserve('answer_solution_extraction')
        return self._delegate.extract_answer_solution(**kwargs)


def _aggregate_ocr_adapters(
    adapters: list[AvalAIOCREvidenceAdapter],
    *,
    enabled: bool,
    requested_model: str,
) -> dict[str, Any]:
    fallback_reasons: Counter[str] = Counter()
    resolved_models: set[str] = set()
    totals = {
        'ocrCalls': 0,
        'primarySuccesses': 0,
        'bboxCalls': 0,
        'retries': 0,
        'fallbackCount': 0,
    }
    for adapter in adapters:
        stats = adapter.stats
        totals['ocrCalls'] += stats.ocr_calls
        totals['primarySuccesses'] += stats.primary_successes
        totals['bboxCalls'] += stats.bbox_calls
        totals['retries'] += stats.retries
        totals['fallbackCount'] += stats.fallback_count
        fallback_reasons.update(stats.fallback_reasons)
        resolved_models.update(stats.resolved_models)
    return {
        'enabled': bool(enabled),
        'requestedModel': requested_model if enabled else None,
        **totals,
        'fallbackReasons': dict(sorted(fallback_reasons.items())),
        'resolvedModels': sorted(resolved_models),
    }


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
    ocr_evidence_enabled: bool = False,
    ocr_model: str = AVALAI_OCR_PINNED_MODEL,
    ocr_max_attempts: int = 2,
    ocr_bbox_for_diagrams: bool = True,
) -> benchmark.FullBenchmarkRunResult:
    """Run the benchmark with mandatory live ceilings and optional OCR evidence."""

    if mode != 'live_provider':
        if ocr_evidence_enabled:
            raise benchmark.FullBenchmarkError(
                'OCR evidence is available only in live_provider mode.'
            )
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
    ceiling_plan = calculate_required_external_request_ceiling(
        manifest=manifest,
        ocr_evidence_enabled=ocr_evidence_enabled,
        ocr_max_attempts=ocr_max_attempts,
        ocr_bbox_for_diagrams=ocr_bbox_for_diagrams,
    )
    budget = LiveProviderCallBudget(
        max_provider_calls,
        required_minimum=ceiling_plan['requiredMinimum'],
    )

    original_classifier = benchmark.classify_document_pages_fast
    original_provider_class = benchmark.StructuredLLMExamPrepV4Provider
    adapters: list[AvalAIOCREvidenceAdapter] = []

    def budgeted_classifier(*args, **kwargs):
        budget.reserve('page_classification')
        return original_classifier(*args, **kwargs)

    def budgeted_ocr_transport(url, headers, payload, timeout):
        stage = (
            'ocr_bbox_annotation'
            if 'bbox_annotation_format' in payload
            else 'ocr_document_annotation'
        )
        budget.reserve_external(stage)
        try:
            response = requests.post(
                url,
                headers=dict(headers),
                json=dict(payload),
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise AvalAIOCRTransportError('AvalAI OCR request failed.') from exc
        return OCRHTTPResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    def budgeted_provider_factory(*args, **kwargs):
        delegate = original_provider_class(*args, **kwargs)
        budgeted: Any = _BudgetedExtractionProvider(delegate, budget)
        if not ocr_evidence_enabled:
            return budgeted
        adapter = AvalAIOCREvidenceAdapter(
            fallback=budgeted,
            config=OCREvidenceAdapterConfig(
                enabled=True,
                model=ocr_model,
                max_attempts=ocr_max_attempts,
                request_bbox_for_diagrams=ocr_bbox_for_diagrams,
            ),
            transport=budgeted_ocr_transport,
        )
        adapters.append(adapter)
        return adapter

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
    report['providerCallCeilingPlan'] = ceiling_plan
    report['providerCallBudget'] = budget.as_report()
    report['ocrEvidence'] = _aggregate_ocr_adapters(
        adapters,
        enabled=ocr_evidence_enabled,
        requested_model=ocr_model,
    )
    benchmark._assert_aggregate_report(report)
    return benchmark.FullBenchmarkRunResult(
        report=report,
        project_ids=result.project_ids,
    )
