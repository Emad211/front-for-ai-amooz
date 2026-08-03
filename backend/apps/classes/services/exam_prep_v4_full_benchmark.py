"""Aggregate-only cold/warm full-pipeline benchmark for private V4 fixtures."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from django.contrib.auth import get_user_model
from django.db.models import Sum

from apps.classes.models_v4 import ExamSourceRole
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamMatchDecision,
    ExamQuestionRecord,
)
from apps.classes.services.exam_prep_v4_benchmark import (
    BenchmarkFixture,
    BenchmarkManifest,
    BenchmarkMode,
    ResolvedBenchmarkFixture,
    _FakeClassifier,
    _validate_segment_map,
    resolve_benchmark_manifest,
)
from apps.classes.services.exam_prep_v4_fast_classifier import (
    classify_document_source_map,
)
from apps.classes.services.exam_prep_v4_live_pipeline import (
    ExamPrepV4ExtractionProvider,
    PreparedVisionImage,
    StructuredLLMExamPrepV4Provider,
    run_document_extraction_pipeline,
)
from apps.classes.services.exam_prep_v4_pdf_source import prepare_pdf_source_from_path
from apps.classes.services.exam_prep_v4_projects import (
    NewExamPdf,
    create_independent_exam_projects,
)
from apps.classes.services.exam_prep_v4_source_map_mutation import (
    confirm_teacher_source_map,
)
from apps.commons.models import LLMUsageLog


FULL_BENCHMARK_SCHEMA_VERSION = 1


class FullBenchmarkError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FullBenchmarkRunResult:
    report: dict[str, Any]
    project_ids: tuple[int, ...]


class ManifestFakeExtractionProvider:
    """Deterministic fake provider that still uses the real persistence runner."""

    def __init__(self, fixture: BenchmarkFixture):
        self.fixture = fixture
        self.provider_calls = 0
        start, end = fixture.expected_question_numbers
        self.question_numbers = tuple(str(value) for value in range(start, end + 1))
        self.answer_numbers = self.question_numbers + tuple(
            str(value) for value in fixture.expected_out_of_scope_numbers
        )

    @staticmethod
    def _boxes(numbers: Sequence[str], pages) -> list[dict[str, Any]]:
        if not pages:
            return []
        assignments: dict[int, list[str]] = defaultdict(list)
        for index, number in enumerate(numbers):
            assignments[index % len(pages)].append(number)
        result: list[dict[str, Any]] = []
        order = 0
        for page_index, page in enumerate(pages):
            page_numbers = assignments.get(page_index, [])
            count = max(1, len(page_numbers))
            for local_index, number in enumerate(page_numbers):
                top = Decimal('0.03') + (Decimal('0.94') * local_index / count)
                bottom = Decimal('0.03') + (Decimal('0.94') * (local_index + 1) / count)
                result.append(
                    {
                        'order': order,
                        'printedNumber': number,
                        'confidence': 0.99,
                        'fragments': [
                            {
                                'order': 0,
                                'pageNumber': page.page_number,
                                'x0': 0.02,
                                'y0': float(top),
                                'x1': 0.98,
                                'y1': float(bottom),
                                'columnIndex': 0,
                                'isContinuation': False,
                            }
                        ],
                    }
                )
                order += 1
        return result

    def detect_segment_blocks(self, *, document, segment, pages, images):
        self.provider_calls += 1
        if segment.role == ExamSourceRole.QUESTIONS:
            return {
                'blocks': [
                    {**item, 'kind': 'question'}
                    for item in self._boxes(self.question_numbers, pages)
                ]
            }
        if segment.role == ExamSourceRole.ANSWER_SOLUTIONS:
            return {
                'blocks': [
                    {**item, 'kind': 'answer_solution'}
                    for item in self._boxes(self.answer_numbers, pages)
                ]
            }
        if segment.role == ExamSourceRole.ANSWER_KEY:
            return {
                'blocks': [
                    {**item, 'kind': 'answer_key'}
                    for item in self._boxes(self.answer_numbers, pages)
                ]
            }
        return {'blocks': []}

    def extract_question(self, *, document, block, images):
        self.provider_calls += 1
        return {
            'questions': [
                {
                    'blockId': block.id,
                    'printedNumber': block.printed_number,
                    'sectionKey': block.segment.section_key,
                    'questionText': f'SYNTHETIC_QUESTION_{block.printed_number}',
                    'options': [
                        {'label': '1', 'text': 'SYNTHETIC_OPTION_1'},
                        {'label': '2', 'text': 'SYNTHETIC_OPTION_2'},
                        {'label': '3', 'text': 'SYNTHETIC_OPTION_3'},
                        {'label': '4', 'text': 'SYNTHETIC_OPTION_4'},
                    ],
                    'confidence': 0.99,
                    'warnings': [],
                }
            ]
        }

    def extract_answer_solution(
        self,
        *,
        document,
        block,
        evidence_blocks,
        images,
    ):
        self.provider_calls += 1
        return {
            'answers': [
                {
                    'blockId': block.id,
                    'printedNumber': block.printed_number,
                    'sectionKey': block.segment.section_key,
                    'correctOption': '1',
                    'finalAnswer': 'SYNTHETIC_FINAL_ANSWER',
                    'solutionText': f'SYNTHETIC_SOLUTION_{block.printed_number}',
                    'confidence': 0.99,
                    'warnings': [],
                }
            ]
        }


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _benchmark_user():
    User = get_user_model()
    user, _created = User.objects.get_or_create(
        username='exam-prep-v4-full-benchmark',
        defaults={
            'email': 'exam-prep-v4-full-benchmark@example.invalid',
            'role': 'TEACHER',
            'is_active': False,
        },
    )
    changed = False
    if getattr(user, 'role', None) != 'TEACHER':
        user.role = 'TEACHER'
        changed = True
    if getattr(user, 'is_active', True):
        user.is_active = False
        changed = True
    if changed:
        user.save(update_fields=['role', 'is_active'])
    return user


def _classify_and_confirm(
    *,
    teacher,
    fixture: ResolvedBenchmarkFixture,
    document,
    mode: str,
    classifier_model: str | None,
):
    classifier = None
    if mode == BenchmarkMode.FAKE_PROVIDER:
        classifier = _FakeClassifier(fixture.expected_segments)
    classification = classify_document_source_map(
        document_id=document.id,
        classifier=classifier,
        model=classifier_model,
    )
    document.refresh_from_db()
    actual_segments = tuple(
        document.segments.filter(
            revision=document.classification_revision,
        ).order_by('order')
    )
    structure = _validate_segment_map(
        expected=fixture.expected_segments,
        actual=actual_segments,
        page_count=document.page_count,
    )
    if structure['mismatchCount']:
        raise FullBenchmarkError(
            f'Fixture {fixture.fixture_id} source map has '
            f'{structure["mismatchCount"]} structural mismatches.'
        )
    confirm_teacher_source_map(
        teacher=teacher,
        project_id=document.project_id,
        document_id=document.id,
        expected_revision=document.classification_revision,
        expected_fingerprint=document.source_map_fingerprint,
    )
    document.refresh_from_db()
    return classification, structure


def _record_metrics(project, fixture: BenchmarkFixture) -> dict[str, Any]:
    questions = tuple(
        ExamQuestionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
            source_block__status='accepted',
        ).order_by('document__upload_order', 'order')
    )
    answers = tuple(
        ExamAnswerSolutionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
            source_block__status='accepted',
        ).order_by('document__upload_order', 'order')
    )
    decisions = tuple(
        ExamMatchDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).order_by('order')
    )
    expected_start, expected_end = fixture.expected_question_numbers
    expected_questions = {str(value) for value in range(expected_start, expected_end + 1)}
    expected_out_of_scope = {
        str(value) for value in fixture.expected_out_of_scope_numbers
    }
    actual_questions = {record.printed_number for record in questions}
    counts: dict[str, int] = defaultdict(int)
    for decision in decisions:
        counts[decision.decision] += 1
    actual_out_of_scope_numbers = {
        decision.normalized_number
        for decision in decisions
        if decision.decision == ExamMatchDecision.Decision.OUT_OF_SCOPE
    }
    return {
        'questionCount': len(questions),
        'answerSolutionCount': len(answers),
        'decisionCount': len(decisions),
        'matchedCount': counts[ExamMatchDecision.Decision.MATCHED],
        'outOfScopeCount': counts[ExamMatchDecision.Decision.OUT_OF_SCOPE],
        'unresolvedCount': counts[ExamMatchDecision.Decision.UNRESOLVED],
        'ambiguousCount': counts[ExamMatchDecision.Decision.AMBIGUOUS],
        'conflictCount': counts[ExamMatchDecision.Decision.CONFLICT],
        'missingQuestionCount': len(expected_questions - actual_questions),
        'unexpectedQuestionCount': len(actual_questions - expected_questions),
        'missingExpectedOutOfScopeCount': len(
            expected_out_of_scope - actual_out_of_scope_numbers
        ),
        'unexpectedOutOfScopeCount': len(
            actual_out_of_scope_numbers - expected_out_of_scope
        ),
    }


def _usage_metrics(document_id: int, started_at: datetime) -> dict[str, Any]:
    rows = LLMUsageLog.objects.filter(
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        context__source_document_id=document_id,
        created_at__gte=started_at,
    )
    totals = rows.aggregate(
        inputTokens=Sum('input_tokens'),
        outputTokens=Sum('output_tokens'),
        totalTokens=Sum('total_tokens'),
        estimatedCostUsd=Sum('estimated_cost_usd'),
    )
    by_detail: dict[str, dict[str, Any]] = {}
    for detail in (
        'exam_prep_v4_page_classification',
        'exam_prep_v4_block_detection',
        'exam_prep_v4_question_extraction',
        'exam_prep_v4_answer_solution_extraction',
    ):
        detail_rows = rows.filter(detail=detail)
        values = detail_rows.aggregate(
            inputTokens=Sum('input_tokens'),
            outputTokens=Sum('output_tokens'),
            totalTokens=Sum('total_tokens'),
            estimatedCostUsd=Sum('estimated_cost_usd'),
        )
        by_detail[detail] = {
            'requestCount': detail_rows.count(),
            'inputTokens': int(values['inputTokens'] or 0),
            'outputTokens': int(values['outputTokens'] or 0),
            'totalTokens': int(values['totalTokens'] or 0),
            'estimatedCostUsd': str(values['estimatedCostUsd'] or Decimal('0')),
        }
    return {
        'requestCount': rows.count(),
        'inputTokens': int(totals['inputTokens'] or 0),
        'outputTokens': int(totals['outputTokens'] or 0),
        'totalTokens': int(totals['totalTokens'] or 0),
        'estimatedCostUsd': str(totals['estimatedCostUsd'] or Decimal('0')),
        'byStage': by_detail,
    }


def _acceptance(metrics: Mapping[str, Any], warm_provider_calls: int) -> dict[str, Any]:
    checks = {
        'questionInventoryExact': (
            metrics['missingQuestionCount'] == 0
            and metrics['unexpectedQuestionCount'] == 0
        ),
        'expectedOutOfScopeExact': (
            metrics['missingExpectedOutOfScopeCount'] == 0
            and metrics['unexpectedOutOfScopeCount'] == 0
        ),
        'automaticMatchesHaveNoAmbiguity': (
            metrics['unresolvedCount'] == 0
            and metrics['ambiguousCount'] == 0
            and metrics['conflictCount'] == 0
        ),
        'warmRerunProviderCallsZero': warm_provider_calls == 0,
    }
    return {
        **checks,
        'passed': all(checks.values()),
    }


def _assert_aggregate_report(report: Mapping[str, Any]) -> None:
    rendered = json.dumps(report, ensure_ascii=False, default=str)
    forbidden_keys = {
        'path',
        'originalName',
        'questionText',
        'solutionText',
        'finalAnswer',
        'options',
        'rawPayload',
        'nativeText',
        'sourceFile',
        'renderedFile',
        'thumbnailFile',
        'metadata',
        'fingerprint',
    }

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            assert not (set(value) & forbidden_keys)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(report)
    if '%PDF' in rendered or 'SYNTHETIC_QUESTION_' in rendered:
        raise FullBenchmarkError('Aggregate report contains private or synthetic content.')


def _live_preflight(
    *,
    classifier_model: str | None,
    block_model: str | None,
    question_model: str | None,
    answer_model: str | None,
) -> None:
    missing: list[str] = []
    if not (os.getenv('AVALAI_API_KEY') or '').strip():
        missing.append('AVALAI_API_KEY')
    for name, value in (
        ('classifier_model', classifier_model),
        ('block_model', block_model),
        ('question_model', question_model),
        ('answer_model', answer_model),
    ):
        if not (value or '').strip():
            missing.append(name)
    if missing:
        raise FullBenchmarkError(
            'Live full-pipeline benchmark preflight failed: ' + ', '.join(missing)
        )


def run_full_pipeline_benchmark(
    *,
    manifest: BenchmarkManifest,
    mode: str,
    classifier_model: str | None = None,
    block_model: str | None = None,
    question_model: str | None = None,
    answer_model: str | None = None,
    keep_projects: bool = False,
) -> FullBenchmarkRunResult:
    resolved = resolve_benchmark_manifest(manifest)
    if mode == BenchmarkMode.LIVE_PROVIDER:
        _live_preflight(
            classifier_model=classifier_model,
            block_model=block_model,
            question_model=question_model,
            answer_model=answer_model,
        )
    elif mode != BenchmarkMode.FAKE_PROVIDER:
        raise FullBenchmarkError('Unsupported full benchmark mode.')

    teacher = _benchmark_user()
    project_ids: list[int] = []
    fixture_reports: list[dict[str, Any]] = []
    benchmark_started = datetime.now(timezone.utc)
    total_started = time.monotonic()

    try:
        for fixture_index, resolved_fixture in enumerate(resolved):
            fixture = manifest.fixtures[fixture_index]
            source_sha256 = _sha256_path(resolved_fixture.path)
            source = NewExamPdf(
                original_name=resolved_fixture.path.name,
                title=f'V4 full benchmark {resolved_fixture.fixture_id}',
                source_sha256=source_sha256,
                byte_size=resolved_fixture.path.stat().st_size,
            )
            project = create_independent_exam_projects(
                teacher=teacher,
                sources=[source],
            )[0]
            project_ids.append(project.id)
            document = project.source_documents.get()

            cold_started = time.monotonic()
            prepared = prepare_pdf_source_from_path(
                document_id=document.id,
                source_path=resolved_fixture.path,
                original_name=resolved_fixture.path.name,
            )
            document.refresh_from_db()
            _classification, structure = _classify_and_confirm(
                teacher=teacher,
                fixture=resolved_fixture,
                document=document,
                mode=mode,
                classifier_model=classifier_model,
            )
            provider: ExamPrepV4ExtractionProvider
            if mode == BenchmarkMode.FAKE_PROVIDER:
                provider = ManifestFakeExtractionProvider(fixture)
            else:
                provider = StructuredLLMExamPrepV4Provider(
                    block_model=block_model,
                    question_model=question_model,
                    answer_model=answer_model,
                )
            cold = run_document_extraction_pipeline(
                document_id=document.id,
                provider=provider,
            )
            cold_latency_ms = round((time.monotonic() - cold_started) * 1000, 2)

            warm_provider: ExamPrepV4ExtractionProvider
            if mode == BenchmarkMode.FAKE_PROVIDER:
                warm_provider = ManifestFakeExtractionProvider(fixture)
            else:
                warm_provider = StructuredLLMExamPrepV4Provider(
                    block_model=block_model,
                    question_model=question_model,
                    answer_model=answer_model,
                )
            warm_started = time.monotonic()
            warm = run_document_extraction_pipeline(
                document_id=document.id,
                provider=warm_provider,
            )
            warm_latency_ms = round((time.monotonic() - warm_started) * 1000, 2)
            metrics = _record_metrics(project, fixture)
            acceptance = _acceptance(metrics, warm.provider_calls)
            fixture_reports.append(
                {
                    'fixtureId': resolved_fixture.fixture_id,
                    'pageCount': prepared.page_count,
                    'structuralMismatchCount': structure['mismatchCount'],
                    'blockCount': cold.block_set.block_count,
                    'fragmentCount': cold.block_set.fragment_count,
                    'coldProviderCalls': cold.provider_calls,
                    'warmProviderCalls': warm.provider_calls,
                    'coldLatencyMs': cold_latency_ms,
                    'warmLatencyMs': warm_latency_ms,
                    'issueCount': len(cold.issues),
                    **metrics,
                    'usage': _usage_metrics(document.id, benchmark_started),
                    'acceptance': acceptance,
                }
            )

        totals: dict[str, Any] = defaultdict(int)
        numeric_keys = (
            'pageCount',
            'structuralMismatchCount',
            'blockCount',
            'fragmentCount',
            'coldProviderCalls',
            'warmProviderCalls',
            'issueCount',
            'questionCount',
            'answerSolutionCount',
            'decisionCount',
            'matchedCount',
            'outOfScopeCount',
            'unresolvedCount',
            'ambiguousCount',
            'conflictCount',
            'missingQuestionCount',
            'unexpectedQuestionCount',
            'missingExpectedOutOfScopeCount',
            'unexpectedOutOfScopeCount',
        )
        for fixture_report in fixture_reports:
            for key in numeric_keys:
                totals[key] += int(fixture_report[key])
        report = {
            'schemaVersion': FULL_BENCHMARK_SCHEMA_VERSION,
            'mode': mode,
            'fixtureCount': len(fixture_reports),
            'projectCount': len(project_ids),
            'independentProjectCount': len(set(project_ids)),
            'models': {
                'classifier': classifier_model if mode == BenchmarkMode.LIVE_PROVIDER else 'fake-provider',
                'block': block_model if mode == BenchmarkMode.LIVE_PROVIDER else 'fake-provider',
                'question': question_model if mode == BenchmarkMode.LIVE_PROVIDER else 'fake-provider',
                'answer': answer_model if mode == BenchmarkMode.LIVE_PROVIDER else 'fake-provider',
            },
            'totalLatencyMs': round((time.monotonic() - total_started) * 1000, 2),
            'fixtures': fixture_reports,
            'totals': dict(totals),
            'acceptance': {
                'allFixturesPassed': all(
                    item['acceptance']['passed'] for item in fixture_reports
                ),
                'allProjectsIndependent': len(set(project_ids)) == len(project_ids),
                'warmRerunProviderCallsZero': totals['warmProviderCalls'] == 0,
            },
        }
        report['acceptance']['passed'] = all(report['acceptance'].values())
        _assert_aggregate_report(report)
        return FullBenchmarkRunResult(
            report=report,
            project_ids=tuple(project_ids),
        )
    finally:
        if not keep_projects:
            ExamProject.objects.filter(id__in=project_ids).delete()
