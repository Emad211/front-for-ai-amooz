"""Privacy-safe benchmark harness for the Exam Prep V4 Phase 2 exit gate.

The harness accepts local, non-committed PDF paths and emits aggregate structural
metrics only. Source paths, filenames, image bytes, native text, model payloads,
and storage object names are never included in the report.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from django.db.models import Sum
from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourceRole,
)
from apps.classes.services.exam_prep_v4_classification import (
    PersistedClassification,
    persist_classification_result,
)
from apps.classes.services.exam_prep_v4_fast_classifier import (
    PROMPT_VERSION,
    _input_fingerprint,
    _page_catalog,
    build_contact_sheets,
    classify_document_pages_fast,
)
from apps.classes.services.exam_prep_v4_pdf_source import (
    load_classification_page_inputs,
    prepare_pdf_source_from_path,
)
from apps.commons.models import LLMUsageLog


BenchmarkPattern = Literal[
    'cover_questions_solutions',
    'solutions_cover_questions',
    'cover_questions_solutions_overlap',
]
BenchmarkMode = Literal['fake_provider', 'live_provider']


class BenchmarkManifestError(ValueError):
    pass


class BenchmarkConfigurationError(RuntimeError):
    pass


class BenchmarkSegmentSpec(BaseModel):
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


class BenchmarkNumberRange(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    start: int = Field(alias='from', ge=1)
    end: int = Field(alias='to', ge=1)

    @model_validator(mode='after')
    def validate_range(self):
        if self.end < self.start:
            raise ValueError('to must be greater than or equal to from')
        return self


class BenchmarkFixtureSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True, str_strip_whitespace=True)

    fixture_id: str = Field(alias='fixtureId', min_length=1, max_length=64)
    pattern: BenchmarkPattern
    pdf_path: str = Field(alias='pdfPath', min_length=1)
    expected_page_count: int = Field(alias='expectedPageCount', ge=1)
    expected_segments: list[BenchmarkSegmentSpec] = Field(
        alias='expectedSegments',
        min_length=1,
    )
    expected_question_numbers: BenchmarkNumberRange | None = Field(
        alias='expectedQuestionNumbers',
        default=None,
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

        roles = [segment.role for segment in self.expected_segments]
        if self.pattern in {
            'cover_questions_solutions',
            'cover_questions_solutions_overlap',
        }:
            expected_roles = [
                ExamSourceRole.COVER,
                ExamSourceRole.QUESTIONS,
                ExamSourceRole.ANSWER_SOLUTIONS,
            ]
        else:
            expected_roles = [
                ExamSourceRole.ANSWER_SOLUTIONS,
                ExamSourceRole.COVER,
                ExamSourceRole.QUESTIONS,
            ]
        if roles != expected_roles:
            raise ValueError('expectedSegments do not match the declared pattern')
        return self


class BenchmarkManifestSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    manifest_version: Literal[1] = Field(alias='manifestVersion')
    fixtures: list[BenchmarkFixtureSpec] = Field(min_length=3, max_length=3)

    @model_validator(mode='after')
    def validate_fixture_ids(self):
        ids = [fixture.fixture_id for fixture in self.fixtures]
        if len(ids) != len(set(ids)):
            raise ValueError('fixtureId values must be unique')
        return self


@dataclass(frozen=True, slots=True)
class ResolvedBenchmarkFixture:
    fixture_id: str
    pattern: str
    pdf_path: Path
    expected_page_count: int
    expected_segments: tuple[BenchmarkSegmentSpec, ...]


@dataclass(frozen=True, slots=True)
class ResolvedBenchmarkManifest:
    fixtures: tuple[ResolvedBenchmarkFixture, ...]


def _safe_validation_fields(exc: ValidationError) -> str:
    fields = sorted(
        {
            '.'.join(str(part) for part in error.get('loc', ())) or 'manifest'
            for error in exc.errors(include_url=False, include_input=False)
        }
    )
    return ', '.join(fields[:12])


def _validate_pdf_file(*, fixture_id: str, path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise BenchmarkManifestError(
            f'Fixture {fixture_id}: private PDF is unavailable.'
        )
    try:
        with path.open('rb') as handle:
            header = handle.read(1024)
    except OSError as exc:
        raise BenchmarkManifestError(
            f'Fixture {fixture_id}: private PDF is unreadable.'
        ) from exc
    if b'%PDF' not in header:
        raise BenchmarkManifestError(
            f'Fixture {fixture_id}: source is not a valid PDF.'
        )


def load_benchmark_manifest(manifest_path: str | Path) -> ResolvedBenchmarkManifest:
    """Load and validate a local manifest without exposing source paths."""

    path = Path(manifest_path)
    try:
        if path.stat().st_size > 256 * 1024:
            raise BenchmarkManifestError('Benchmark manifest exceeds 256 KiB.')
        raw = json.loads(path.read_text(encoding='utf-8'))
    except BenchmarkManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkManifestError('Benchmark manifest is unavailable or invalid JSON.') from exc

    try:
        parsed = BenchmarkManifestSpec.model_validate(raw)
    except ValidationError as exc:
        fields = _safe_validation_fields(exc)
        detail = f' Fields: {fields}.' if fields else ''
        raise BenchmarkManifestError(f'Benchmark manifest validation failed.{detail}') from exc

    base_dir = path.parent
    fixtures: list[ResolvedBenchmarkFixture] = []
    for fixture in parsed.fixtures:
        candidate = Path(fixture.pdf_path)
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        candidate = candidate.resolve()
        _validate_pdf_file(fixture_id=fixture.fixture_id, path=candidate)
        fixtures.append(
            ResolvedBenchmarkFixture(
                fixture_id=fixture.fixture_id,
                pattern=fixture.pattern,
                pdf_path=candidate,
                expected_page_count=fixture.expected_page_count,
                expected_segments=tuple(fixture.expected_segments),
            )
        )
    return ResolvedBenchmarkManifest(fixtures=tuple(fixtures))


def _expected_role_map(fixture: ResolvedBenchmarkFixture) -> dict[int, str]:
    return {
        page_number: segment.role
        for segment in fixture.expected_segments
        for page_number in range(segment.start_page, segment.end_page + 1)
    }


def _safe_segments(segments) -> list[dict[str, Any]]:
    return [
        {
            'startPage': segment.start_page,
            'endPage': segment.end_page,
            'role': segment.role,
        }
        for segment in segments
    ]


def _expected_segments(fixture: ResolvedBenchmarkFixture) -> list[dict[str, Any]]:
    return [
        {
            'startPage': segment.start_page,
            'endPage': segment.end_page,
            'role': segment.role,
        }
        for segment in fixture.expected_segments
    ]


def _fake_raw_output(fixture: ResolvedBenchmarkFixture) -> dict[str, Any]:
    role_map = _expected_role_map(fixture)
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


def _usage_rows(document_id: int):
    return LLMUsageLog.objects.filter(
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        detail='exam_prep_v4_page_classification',
        context__source_document_id=document_id,
    )


def _usage_summary(document_id: int) -> dict[str, Any]:
    rows = _usage_rows(document_id)
    values = rows.aggregate(
        input_tokens=Sum('input_tokens'),
        output_tokens=Sum('output_tokens'),
        total_tokens=Sum('total_tokens'),
        duration_ms=Sum('duration_ms'),
        estimated_cost_usd=Sum('estimated_cost_usd'),
    )
    return {
        'calls': rows.count(),
        'inputTokens': int(values['input_tokens'] or 0),
        'outputTokens': int(values['output_tokens'] or 0),
        'totalTokens': int(values['total_tokens'] or 0),
        'providerDurationMs': int(values['duration_ms'] or 0),
        'estimatedCostUsd': float(values['estimated_cost_usd'] or Decimal('0')),
    }


def _usage_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        key: round(float(after[key]) - float(before[key]), 6)
        if key == 'estimatedCostUsd'
        else int(after[key]) - int(before[key])
        for key in before
    }


def _fake_classify(
    *,
    document: ExamSourceDocument,
    fixture: ResolvedBenchmarkFixture,
    sheets,
    native_text_samples: dict[int, str],
) -> PersistedClassification:
    catalog = _page_catalog(
        page_count=document.page_count,
        native_text_samples=native_text_samples,
    )
    fingerprint = _input_fingerprint(
        document=document,
        sheets=tuple(sheets),
        page_catalog=catalog,
        model='benchmark-fake-provider-v1',
    )
    return persist_classification_result(
        document_id=document.id,
        expected_revision=document.classification_revision,
        fingerprint=fingerprint,
        raw_output=_fake_raw_output(fixture),
    )


def _fake_warm_reuse(
    *,
    document: ExamSourceDocument,
    sheets,
    native_text_samples: dict[int, str],
) -> PersistedClassification:
    catalog = _page_catalog(
        page_count=document.page_count,
        native_text_samples=native_text_samples,
    )
    fingerprint = _input_fingerprint(
        document=document,
        sheets=tuple(sheets),
        page_catalog=catalog,
        model='benchmark-fake-provider-v1',
    )
    return persist_classification_result(
        document_id=document.id,
        expected_revision=document.classification_revision,
        fingerprint=fingerprint,
        raw_output={'pages': []},
    )


def _create_benchmark_scope(*, teacher, fixture_id: str) -> ExamSourceDocument:
    project = ExamProject.objects.create(
        teacher=teacher,
        title=f'V4 benchmark {fixture_id}',
        description='',
        status=ExamProject.Status.DRAFT,
        workflow_state={'stage': 'benchmark'},
    )
    return ExamSourceDocument.objects.create(
        project=project,
        original_name=f'{fixture_id}.pdf',
        mime_type='application/pdf',
        upload_order=0,
    )


def _preflight_live_provider(model: str | None) -> None:
    selected_model = (
        (model or '').strip()
        or (os.getenv('EXAM_PREP_V4_CLASSIFICATION_MODEL') or '').strip()
        or (os.getenv('PDF_VISION_MODEL') or '').strip()
    )
    if not selected_model:
        raise BenchmarkConfigurationError(
            'Live benchmark requires EXAM_PREP_V4_CLASSIFICATION_MODEL or PDF_VISION_MODEL.'
        )
    if not (os.getenv('AVALAI_API_KEY') or '').strip():
        raise BenchmarkConfigurationError(
            'Live benchmark requires AVALAI_API_KEY.'
        )


def _fixture_metrics(
    *,
    fixture: ResolvedBenchmarkFixture,
    classification: PersistedClassification,
    page_count: int,
    prepare_latency_ms: int,
    cold_latency_ms: int,
    warm_latency_ms: int,
    cold_usage: dict[str, Any],
    warm_usage: dict[str, Any],
    warm_reused: bool,
) -> dict[str, Any]:
    expected_roles = _expected_role_map(fixture)
    actual_roles = {page.page_number: page.role for page in classification.pages}
    correct_roles = sum(
        actual_roles.get(page_number) == expected_role
        for page_number, expected_role in expected_roles.items()
    )
    expected_segments = _expected_segments(fixture)
    actual_segments = _safe_segments(classification.segments)
    role_counts = Counter(actual_roles.values())
    page_role_accuracy = (
        round(correct_roles / fixture.expected_page_count, 6)
        if fixture.expected_page_count
        else 0.0
    )
    segment_map_exact = actual_segments == expected_segments
    passed = bool(
        page_count == fixture.expected_page_count
        and page_role_accuracy == 1.0
        and segment_map_exact
        and warm_reused
        and warm_usage['calls'] == 0
    )
    return {
        'fixtureId': fixture.fixture_id,
        'pattern': fixture.pattern,
        'status': 'passed' if passed else 'failed',
        'pageCount': page_count,
        'expectedPageCount': fixture.expected_page_count,
        'correctPageRoles': correct_roles,
        'pageRoleAccuracy': page_role_accuracy,
        'roleCounts': dict(sorted(role_counts.items())),
        'expectedSegments': expected_segments,
        'actualSegments': actual_segments,
        'segmentMapExact': segment_map_exact,
        'issueCount': len(classification.issues),
        'prepareLatencyMs': prepare_latency_ms,
        'coldClassificationLatencyMs': cold_latency_ms,
        'warmReuseLatencyMs': warm_latency_ms,
        'coldUsage': cold_usage,
        'warmUsage': warm_usage,
        'warmReused': warm_reused,
    }


def run_benchmark(
    *,
    manifest: ResolvedBenchmarkManifest,
    teacher,
    mode: BenchmarkMode,
    model: str | None = None,
    keep_projects: bool = False,
) -> dict[str, Any]:
    """Run classify-and-segment benchmark and return aggregate-only metrics."""

    if mode == 'live_provider':
        _preflight_live_provider(model)

    project_ids: list[int] = []
    fixture_reports: list[dict[str, Any]] = []
    try:
        for fixture in manifest.fixtures:
            document = _create_benchmark_scope(
                teacher=teacher,
                fixture_id=fixture.fixture_id,
            )
            project_ids.append(document.project_id)
            try:
                prepare_started = time.perf_counter()
                prepared = prepare_pdf_source_from_path(
                    document_id=document.id,
                    source_path=fixture.pdf_path,
                    original_name=f'{fixture.fixture_id}.pdf',
                    mime_type='application/pdf',
                )
                prepare_latency_ms = round(
                    (time.perf_counter() - prepare_started) * 1000
                )
                document.refresh_from_db()
                page_inputs = load_classification_page_inputs(document_id=document.id)
                sheets = build_contact_sheets(page_inputs)
                native_text_samples = {
                    page.page_number: page.native_text_sample
                    for page in page_inputs
                    if page.native_text_sample
                }

                usage_before = _usage_summary(document.id)
                cold_started = time.perf_counter()
                if mode == 'fake_provider':
                    cold = _fake_classify(
                        document=document,
                        fixture=fixture,
                        sheets=sheets,
                        native_text_samples=native_text_samples,
                    )
                    cold_usage = {
                        **usage_before,
                        'calls': 1,
                    }
                else:
                    cold_result = classify_document_pages_fast(
                        document_id=document.id,
                        expected_revision=document.classification_revision,
                        contact_sheets=sheets,
                        native_text_samples=native_text_samples,
                        model=model,
                    )
                    cold = cold_result.classification
                    cold_usage = _usage_delta(
                        _usage_summary(document.id),
                        usage_before,
                    )
                cold_latency_ms = round((time.perf_counter() - cold_started) * 1000)

                document.refresh_from_db()
                usage_after_cold = _usage_summary(document.id)
                warm_started = time.perf_counter()
                if mode == 'fake_provider':
                    warm = _fake_warm_reuse(
                        document=document,
                        sheets=sheets,
                        native_text_samples=native_text_samples,
                    )
                    warm_usage = {
                        'calls': 0,
                        'inputTokens': 0,
                        'outputTokens': 0,
                        'totalTokens': 0,
                        'providerDurationMs': 0,
                        'estimatedCostUsd': 0.0,
                    }
                else:
                    warm_result = classify_document_pages_fast(
                        document_id=document.id,
                        expected_revision=document.classification_revision,
                        contact_sheets=sheets,
                        native_text_samples=native_text_samples,
                        model=model,
                    )
                    warm = warm_result.classification
                    warm_usage = _usage_delta(
                        _usage_summary(document.id),
                        usage_after_cold,
                    )
                warm_latency_ms = round((time.perf_counter() - warm_started) * 1000)

                fixture_reports.append(
                    _fixture_metrics(
                        fixture=fixture,
                        classification=cold,
                        page_count=prepared.page_count,
                        prepare_latency_ms=prepare_latency_ms,
                        cold_latency_ms=cold_latency_ms,
                        warm_latency_ms=warm_latency_ms,
                        cold_usage=cold_usage,
                        warm_usage=warm_usage,
                        warm_reused=warm.reused,
                    )
                )
            except Exception as exc:
                fixture_reports.append(
                    {
                        'fixtureId': fixture.fixture_id,
                        'pattern': fixture.pattern,
                        'status': 'error',
                        'errorCode': type(exc).__name__,
                    }
                )

        passed = all(item.get('status') == 'passed' for item in fixture_reports)
        totals = {
            'fixtureCount': len(fixture_reports),
            'passedFixtures': sum(item.get('status') == 'passed' for item in fixture_reports),
            'failedFixtures': sum(item.get('status') != 'passed' for item in fixture_reports),
            'pageCount': sum(int(item.get('pageCount') or 0) for item in fixture_reports),
            'coldProviderCalls': sum(
                int((item.get('coldUsage') or {}).get('calls') or 0)
                for item in fixture_reports
            ),
            'warmProviderCalls': sum(
                int((item.get('warmUsage') or {}).get('calls') or 0)
                for item in fixture_reports
            ),
            'totalTokens': sum(
                int((item.get('coldUsage') or {}).get('totalTokens') or 0)
                + int((item.get('warmUsage') or {}).get('totalTokens') or 0)
                for item in fixture_reports
            ),
            'estimatedCostUsd': round(
                sum(
                    float((item.get('coldUsage') or {}).get('estimatedCostUsd') or 0)
                    + float((item.get('warmUsage') or {}).get('estimatedCostUsd') or 0)
                    for item in fixture_reports
                ),
                6,
            ),
            'independentProjectCount': len(set(project_ids)),
        }
        return {
            'schemaVersion': 1,
            'generatedAt': timezone.now().isoformat(),
            'mode': mode,
            'stage': 'classify_and_segment',
            'status': 'passed' if passed else 'failed',
            'fixtures': fixture_reports,
            'totals': totals,
            'privacy': {
                'containsSourcePaths': False,
                'containsSourceFilenames': False,
                'containsSourceText': False,
                'containsImageBytes': False,
                'containsModelPayloads': False,
                'containsStorageKeys': False,
            },
        }
    finally:
        if not keep_projects and project_ids:
            ExamProject.objects.filter(id__in=project_ids).delete()
