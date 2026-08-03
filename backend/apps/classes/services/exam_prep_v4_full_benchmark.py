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
from typing import Any, Literal, Mapping, Sequence

from django.contrib.auth import get_user_model
from django.db.models import Sum
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourceRole,
)
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamMatchDecision,
    ExamQuestionRecord,
)
from apps.classes.services.exam_prep_v4_classification import (
    PersistedClassification,
    persist_classification_result,
)
from apps.classes.services.exam_prep_v4_fast_classifier import (
    build_contact_sheets,
    classify_document_pages_fast,
)
from apps.classes.services.exam_prep_v4_live_pipeline import (
    ExamPrepV4ExtractionProvider,
    StructuredLLMExamPrepV4Provider,
    run_document_extraction_pipeline,
)
from apps.classes.services.exam_prep_v4_pdf_source import (
    load_classification_page_inputs,
    prepare_pdf_source_from_path,
)
from apps.classes.services.exam_prep_v4_source_map_mutation import (
    confirm_teacher_source_map,
)
from apps.commons.models import LLMUsageLog


FULL_BENCHMARK_SCHEMA_VERSION = 1
FullBenchmarkMode = Literal['fake_provider', 'live_provider']


class FullBenchmarkError(RuntimeError):
    pass


class FullBenchmarkManifestError(ValueError):
    pass


class FullBenchmarkSegmentSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    start_page: int = Field(alias='startPage', ge=1)
    end_page: int = Field(alias='endPage', ge=1)
    role: str

    @model_validator(mode='after')
    def validate_segment(self):
        if self.end_page < self.start_page:
            raise ValueError('endPage must be greater than or equal to startPage')
        if self.role not in ExamSourceRole.values:
            raise ValueError('unsupported source role')
        return self


class FullBenchmarkNumberRange(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    start: int = Field(alias='from', ge=1)
    end: int = Field(alias='to', ge=1)

    @model_validator(mode='after')
    def validate_range(self):
        if self.end < self.start:
            raise ValueError('to must be greater than or equal to from')
        return self


class FullBenchmarkFixtureSpec(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    fixture_id: str = Field(alias='fixtureId', min_length=1, max_length=64)
    pattern: Literal[
        'cover_questions_solutions',
        'solutions_cover_questions',
        'cover_questions_solutions_overlap',
    ]
    pdf_path: str = Field(alias='pdfPath', min_length=1)
    expected_page_count: int = Field(alias='expectedPageCount', ge=1)
    expected_segments: list[FullBenchmarkSegmentSpec] = Field(
        alias='expectedSegments',
        min_length=1,
    )
    expected_question_numbers: FullBenchmarkNumberRange = Field(
        alias='expectedQuestionNumbers'
    )
    expected_out_of_scope_numbers: list[int] = Field(
        alias='expectedOutOfScopeNumbers',
        default_factory=list,
    )

    @model_validator(mode='after')
    def validate_structure(self):
        expected_start = 1
        for segment in self.expected_segments:
            if segment.start_page != expected_start:
                raise ValueError('expectedSegments must be contiguous and one-based')
            expected_start = segment.end_page + 1
        if expected_start - 1 != self.expected_page_count:
            raise ValueError('expectedSegments must cover expectedPageCount exactly')
        if len(self.expected_out_of_scope_numbers) != len(
            set(self.expected_out_of_scope_numbers)
        ):
            raise ValueError('expectedOutOfScopeNumbers must be unique')
        return self


class FullBenchmarkManifestSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    manifest_version: Literal[1] = Field(alias='manifestVersion')
    fixtures: list[FullBenchmarkFixtureSpec] = Field(min_length=3, max_length=3)

    @model_validator(mode='after')
    def validate_fixture_ids(self):
        ids = [fixture.fixture_id for fixture in self.fixtures]
        if len(ids) != len(set(ids)):
            raise ValueError('fixtureId values must be unique')
        return self


@dataclass(frozen=True, slots=True)
class FullBenchmarkFixture:
    fixture_id: str
    pattern: str
    path: Path
    expected_page_count: int
    expected_segments: tuple[FullBenchmarkSegmentSpec, ...]
    expected_question_numbers: tuple[int, int]
    expected_out_of_scope_numbers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FullBenchmarkManifest:
    fixtures: tuple[FullBenchmarkFixture, ...]


@dataclass(frozen=True, slots=True)
class FullBenchmarkRunResult:
    report: dict[str, Any]
    project_ids: tuple[int, ...]


def load_full_benchmark_manifest(path: str | Path) -> FullBenchmarkManifest:
    manifest_path = Path(path).expanduser().resolve()
    try:
        if manifest_path.stat().st_size > 256 * 1024:
            raise FullBenchmarkManifestError('Benchmark manifest exceeds 256 KiB.')
        raw = json.loads(manifest_path.read_text(encoding='utf-8'))
    except FullBenchmarkManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FullBenchmarkManifestError(
            'Benchmark manifest is unavailable or invalid JSON.'
        ) from exc
    try:
        parsed = FullBenchmarkManifestSpec.model_validate(raw)
    except ValidationError as exc:
        fields = sorted(
            {
                '.'.join(str(part) for part in error.get('loc', ())) or 'manifest'
                for error in exc.errors(include_url=False, include_input=False)
            }
        )
        detail = ', '.join(fields[:12])
        raise FullBenchmarkManifestError(
            'Benchmark manifest validation failed.'
            + (f' Fields: {detail}.' if detail else '')
        ) from exc

    fixtures: list[FullBenchmarkFixture] = []
    for item in parsed.fixtures:
        candidate = Path(item.pdf_path)
        if not candidate.is_absolute():
            candidate = manifest_path.parent / candidate
        candidate = candidate.resolve()
        try:
            with candidate.open('rb') as handle:
                header = handle.read(1024)
        except OSError as exc:
            raise FullBenchmarkManifestError(
                f'Fixture {item.fixture_id}: private PDF is unavailable.'
            ) from exc
        if b'%PDF' not in header:
            raise FullBenchmarkManifestError(
                f'Fixture {item.fixture_id}: source is not a valid PDF.'
            )
        fixtures.append(
            FullBenchmarkFixture(
                fixture_id=item.fixture_id,
                pattern=item.pattern,
                path=candidate,
                expected_page_count=item.expected_page_count,
                expected_segments=tuple(item.expected_segments),
                expected_question_numbers=(
                    item.expected_question_numbers.start,
                    item.expected_question_numbers.end,
                ),
                expected_out_of_scope_numbers=tuple(
                    item.expected_out_of_scope_numbers
                ),
            )
        )
    return FullBenchmarkManifest(fixtures=tuple(fixtures))


class ManifestFakeExtractionProvider:
    """Deterministic fake provider that still uses the real persistence runner."""

    def __init__(self, fixture: FullBenchmarkFixture):
        self.fixture = fixture
        self.provider_calls = 0
        start, end = fixture.expected_question_numbers
        self.question_numbers = tuple(str(value) for value in range(start, end + 1))
        self.answer_numbers = self.question_numbers + tuple(
            str(value) for value in fixture.expected_out_of_scope_numbers
        )

    @staticmethod
    def _boxes(numbers: Sequence[str], pages) -> list[dict[str, Any]]:
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
                bottom = Decimal('0.03') + (
                    Decimal('0.94') * (local_index + 1) / count
                )
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
            kind = 'question'
            numbers = self.question_numbers
        elif segment.role == ExamSourceRole.ANSWER_SOLUTIONS:
            kind = 'answer_solution'
            numbers = self.answer_numbers
        elif segment.role == ExamSourceRole.ANSWER_KEY:
            kind = 'answer_key'
            numbers = self.answer_numbers
        else:
            return {'blocks': []}
        return {
            'blocks': [
                {**item, 'kind': kind}
                for item in self._boxes(numbers, pages)
            ]
        }

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


def _create_scope(teacher, fixture: FullBenchmarkFixture) -> ExamSourceDocument:
    project = ExamProject.objects.create(
        teacher=teacher,
        title=f'V4 full benchmark {fixture.fixture_id}',
        description='',
        status=ExamProject.Status.DRAFT,
        workflow_state={'stage': 'full_benchmark'},
    )
    return ExamSourceDocument.objects.create(
        project=project,
        original_name=f'{fixture.fixture_id}.pdf',
        mime_type='application/pdf',
        source_sha256=_sha256_path(fixture.path),
        byte_size=fixture.path.stat().st_size,
        upload_order=0,
    )


def _expected_raw_classification(fixture: FullBenchmarkFixture) -> dict[str, Any]:
    role_map = {
        page_number: segment.role
        for segment in fixture.expected_segments
        for page_number in range(segment.start_page, segment.end_page + 1)
    }
    return {
        'pages': [
            {
                'page_number': page_number,
                'role': role_map[page_number],
                'confidence': 0.999,
                'printed_numbers': [],
                'reason': '',
            }
            for page_number in range(1, fixture.expected_page_count + 1)
        ]
    }


def _fake_classify(
    document: ExamSourceDocument,
    fixture: FullBenchmarkFixture,
) -> PersistedClassification:
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                'sourceSha256': document.source_sha256,
                'pageCount': document.page_count,
                'revision': document.classification_revision,
                'fixtureId': fixture.fixture_id,
                'segments': [
                    {
                        'start': item.start_page,
                        'end': item.end_page,
                        'role': item.role,
                    }
                    for item in fixture.expected_segments
                ],
                'model': 'full-benchmark-fake-classifier-v1',
            },
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    ).hexdigest()
    return persist_classification_result(
        document_id=document.id,
        expected_revision=document.classification_revision,
        fingerprint=fingerprint,
        raw_output=_expected_raw_classification(fixture),
    )


def _live_classify(
    document: ExamSourceDocument,
    model: str,
) -> PersistedClassification:
    page_inputs = load_classification_page_inputs(document_id=document.id)
    sheets = build_contact_sheets(page_inputs)
    native_text_samples = {
        page.page_number: page.native_text_sample
        for page in page_inputs
        if page.native_text_sample
    }
    return classify_document_pages_fast(
        document_id=document.id,
        expected_revision=document.classification_revision,
        contact_sheets=sheets,
        native_text_samples=native_text_samples,
        model=model,
    ).classification


def _validate_segments(
    fixture: FullBenchmarkFixture,
    classification: PersistedClassification,
) -> int:
    expected = [
        (item.start_page, item.end_page, item.role)
        for item in fixture.expected_segments
    ]
    actual = [
        (item.start_page, item.end_page, item.role)
        for item in classification.segments
    ]
    return 0 if expected == actual else max(len(expected), len(actual), 1)


def _classify_and_confirm(
    *,
    teacher,
    fixture: FullBenchmarkFixture,
    document: ExamSourceDocument,
    mode: FullBenchmarkMode,
    classifier_model: str | None,
) -> tuple[PersistedClassification, int]:
    if mode == 'fake_provider':
        classification = _fake_classify(document, fixture)
    else:
        if not classifier_model:
            raise FullBenchmarkError('Live benchmark requires classifier model.')
        classification = _live_classify(document, classifier_model)
    document.refresh_from_db()
    mismatch_count = _validate_segments(fixture, classification)
    if mismatch_count:
        raise FullBenchmarkError(
            f'Fixture {fixture.fixture_id} source map has structural mismatches.'
        )
    confirm_teacher_source_map(
        teacher=teacher,
        project_id=document.project_id,
        document_id=document.id,
        expected_revision=document.classification_revision,
        expected_fingerprint=document.source_map_fingerprint,
    )
    document.refresh_from_db()
    return classification, mismatch_count


def _record_metrics(project, fixture: FullBenchmarkFixture) -> dict[str, Any]:
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
    return {**checks, 'passed': all(checks.values())}


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
            if set(value) & forbidden_keys:
                raise FullBenchmarkError('Aggregate report contains a private key.')
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(report)
    if (
        '%PDF' in rendered
        or 'SYNTHETIC_QUESTION_' in rendered
        or 'SYNTHETIC_SOLUTION_' in rendered
    ):
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
    manifest: FullBenchmarkManifest,
    mode: FullBenchmarkMode,
    classifier_model: str | None = None,
    block_model: str | None = None,
    question_model: str | None = None,
    answer_model: str | None = None,
    keep_projects: bool = False,
) -> FullBenchmarkRunResult:
    if mode == 'live_provider':
        _live_preflight(
            classifier_model=classifier_model,
            block_model=block_model,
            question_model=question_model,
            answer_model=answer_model,
        )
    elif mode != 'fake_provider':
        raise FullBenchmarkError('Unsupported full benchmark mode.')

    teacher = _benchmark_user()
    project_ids: list[int] = []
    fixture_reports: list[dict[str, Any]] = []
    benchmark_started = datetime.now(timezone.utc)
    total_started = time.monotonic()

    try:
        for fixture in manifest.fixtures:
            document = _create_scope(teacher, fixture)
            project_ids.append(document.project_id)
            cold_started = time.monotonic()
            prepared = prepare_pdf_source_from_path(
                document_id=document.id,
                source_path=fixture.path,
                original_name=f'{fixture.fixture_id}.pdf',
            )
            document.refresh_from_db()
            _classification, mismatch_count = _classify_and_confirm(
                teacher=teacher,
                fixture=fixture,
                document=document,
                mode=mode,
                classifier_model=classifier_model,
            )
            provider: ExamPrepV4ExtractionProvider
            if mode == 'fake_provider':
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

            if mode == 'fake_provider':
                warm_provider: ExamPrepV4ExtractionProvider = (
                    ManifestFakeExtractionProvider(fixture)
                )
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
            metrics = _record_metrics(document.project, fixture)
            acceptance = _acceptance(metrics, warm.provider_calls)
            fixture_reports.append(
                {
                    'fixtureId': fixture.fixture_id,
                    'pageCount': prepared.page_count,
                    'structuralMismatchCount': mismatch_count,
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

        totals: dict[str, int] = defaultdict(int)
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
                'classifier': classifier_model if mode == 'live_provider' else 'fake-provider',
                'block': block_model if mode == 'live_provider' else 'fake-provider',
                'question': question_model if mode == 'live_provider' else 'fake-provider',
                'answer': answer_model if mode == 'live_provider' else 'fake-provider',
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
        if not keep_projects and project_ids:
            ExamProject.objects.filter(id__in=project_ids).delete()
