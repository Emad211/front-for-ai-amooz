import io
import json
from pathlib import Path

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from pypdf import PdfWriter

from apps.classes.models_v4 import ExamProject, ExamSourceDocument, ExamSourcePage
from apps.classes.services.exam_prep_v4_full_benchmark import (
    FullBenchmarkError,
    load_full_benchmark_manifest,
    run_full_pipeline_benchmark,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def private_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / 'private')
    for model, fields in (
        (ExamSourceDocument, ('source_file',)),
        (ExamSourcePage, ('rendered_file', 'thumbnail_file')),
    ):
        for field_name in fields:
            monkeypatch.setattr(model._meta.get_field(field_name), 'storage', storage)
    monkeypatch.setattr(
        'apps.classes.signals.delete_answer_source_file',
        lambda name: storage.delete(name) or True,
    )
    return storage


def _write_pdf(path: Path, page_count=4):
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=480, height=680)
    with path.open('wb') as handle:
        writer.write(handle)
    return path


def _manifest(tmp_path):
    paths = [
        _write_pdf(tmp_path / 'PRIVATE_FIXTURE_A.pdf'),
        _write_pdf(tmp_path / 'PRIVATE_FIXTURE_B.pdf'),
        _write_pdf(tmp_path / 'PRIVATE_FIXTURE_C.pdf'),
    ]
    payload = {
        'manifestVersion': 1,
        'fixtures': [
            {
                'fixtureId': 'fixture-a',
                'pattern': 'cover_questions_solutions',
                'pdfPath': str(paths[0]),
                'expectedPageCount': 4,
                'expectedSegments': [
                    {'startPage': 1, 'endPage': 1, 'role': 'cover'},
                    {'startPage': 2, 'endPage': 2, 'role': 'questions'},
                    {'startPage': 3, 'endPage': 4, 'role': 'answer_solutions'},
                ],
                'expectedQuestionNumbers': {'from': 1, 'to': 2},
                'expectedOutOfScopeNumbers': [3],
            },
            {
                'fixtureId': 'fixture-b',
                'pattern': 'solutions_cover_questions',
                'pdfPath': str(paths[1]),
                'expectedPageCount': 4,
                'expectedSegments': [
                    {'startPage': 1, 'endPage': 2, 'role': 'answer_solutions'},
                    {'startPage': 3, 'endPage': 3, 'role': 'cover'},
                    {'startPage': 4, 'endPage': 4, 'role': 'questions'},
                ],
                'expectedQuestionNumbers': {'from': 4, 'to': 5},
                'expectedOutOfScopeNumbers': [3, 6],
            },
            {
                'fixtureId': 'fixture-c',
                'pattern': 'cover_questions_solutions_overlap',
                'pdfPath': str(paths[2]),
                'expectedPageCount': 4,
                'expectedSegments': [
                    {'startPage': 1, 'endPage': 1, 'role': 'cover'},
                    {'startPage': 2, 'endPage': 3, 'role': 'questions'},
                    {'startPage': 4, 'endPage': 4, 'role': 'answer_solutions'},
                ],
                'expectedQuestionNumbers': {'from': 6, 'to': 8},
                'expectedOutOfScopeNumbers': [5, 9],
            },
        ],
    }
    manifest_path = tmp_path / 'PRIVATE_FULL_MANIFEST.json'
    manifest_path.write_text(json.dumps(payload), encoding='utf-8')
    return manifest_path, paths


def _storage_files(storage):
    root = Path(storage.location)
    return sorted(path for path in root.rglob('*') if path.is_file())


def test_fake_full_benchmark_runs_three_independent_cold_and_warm_pipelines(
    tmp_path,
    private_storage,
    settings,
    django_capture_on_commit_callbacks,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, private_paths = _manifest(tmp_path)
    manifest = load_full_benchmark_manifest(manifest_path)

    with django_capture_on_commit_callbacks(execute=True):
        result = run_full_pipeline_benchmark(
            manifest=manifest,
            mode='fake_provider',
        )

    report = result.report
    rendered = json.dumps(report, ensure_ascii=False)
    assert report['fixtureCount'] == 3
    assert report['projectCount'] == 3
    assert report['independentProjectCount'] == 3
    assert report['acceptance'] == {
        'allFixturesPassed': True,
        'allProjectsIndependent': True,
        'warmRerunProviderCallsZero': True,
        'passed': True,
    }
    assert report['totals']['questionCount'] == 7
    assert report['totals']['matchedCount'] == 7
    assert report['totals']['outOfScopeCount'] == 5
    assert report['totals']['warmProviderCalls'] == 0
    assert report['totals']['unresolvedCount'] == 0
    assert report['totals']['ambiguousCount'] == 0
    assert report['totals']['conflictCount'] == 0
    assert all(item['acceptance']['passed'] for item in report['fixtures'])
    assert all(item['missingQuestionCount'] == 0 for item in report['fixtures'])
    assert all(item['unexpectedQuestionCount'] == 0 for item in report['fixtures'])
    assert all(item['warmProviderCalls'] == 0 for item in report['fixtures'])
    for private_path in [manifest_path, *private_paths]:
        assert str(private_path) not in rendered
        assert private_path.name not in rendered
    assert 'SYNTHETIC_QUESTION_' not in rendered
    assert 'SYNTHETIC_SOLUTION_' not in rendered
    assert ExamProject.objects.count() == 0
    assert _storage_files(private_storage) == []


def test_full_benchmark_command_writes_only_aggregate_report(
    tmp_path,
    private_storage,
    settings,
    django_capture_on_commit_callbacks,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, private_paths = _manifest(tmp_path)
    report_path = tmp_path / 'aggregate-full-report.json'
    stdout = io.StringIO()

    with django_capture_on_commit_callbacks(execute=True):
        call_command(
            'benchmark_exam_prep_v4_full_pipeline',
            manifest=str(manifest_path),
            mode='fake_provider',
            report=str(report_path),
            stdout=stdout,
        )

    report = json.loads(report_path.read_text(encoding='utf-8'))
    terminal = stdout.getvalue()
    assert report['acceptance']['passed'] is True
    assert 'passed=True' in terminal
    for private_path in [manifest_path, *private_paths]:
        assert str(private_path) not in terminal
        assert private_path.name not in terminal
        assert str(private_path) not in json.dumps(report, ensure_ascii=False)
        assert private_path.name not in json.dumps(report, ensure_ascii=False)
    assert ExamProject.objects.count() == 0
    assert _storage_files(private_storage) == []


def test_live_full_benchmark_fails_preflight_before_project_or_storage_writes(
    tmp_path,
    private_storage,
    settings,
    monkeypatch,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, _private_paths = _manifest(tmp_path)
    manifest = load_full_benchmark_manifest(manifest_path)
    monkeypatch.delenv('AVALAI_API_KEY', raising=False)

    with pytest.raises(FullBenchmarkError, match='AVALAI_API_KEY'):
        run_full_pipeline_benchmark(
            manifest=manifest,
            mode='live_provider',
            classifier_model='vision-model',
            block_model='vision-model',
            question_model='vision-model',
            answer_model='vision-model',
        )

    assert ExamProject.objects.count() == 0
    assert _storage_files(private_storage) == []


def test_command_requires_explicit_mode_and_live_models(tmp_path, settings):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, _private_paths = _manifest(tmp_path)
    report_path = tmp_path / 'report.json'

    with pytest.raises(CommandError):
        call_command(
            'benchmark_exam_prep_v4_full_pipeline',
            manifest=str(manifest_path),
            report=str(report_path),
        )
