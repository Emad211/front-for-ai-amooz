import io
import json
from pathlib import Path

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker
from pypdf import PdfWriter

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
)
from apps.classes.services.exam_prep_v4_benchmark import (
    BenchmarkManifestError,
    load_benchmark_manifest,
    run_benchmark,
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


def _pdf_bytes(page_count=3):
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=480, height=680)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _write_pdf(path: Path, *, page_count=3):
    path.write_bytes(_pdf_bytes(page_count))
    return path


def _manifest_payload(paths):
    return {
        'manifestVersion': 1,
        'fixtures': [
            {
                'fixtureId': 'fixture-a',
                'pattern': 'cover_questions_solutions',
                'pdfPath': str(paths[0]),
                'expectedPageCount': 3,
                'expectedSegments': [
                    {'startPage': 1, 'endPage': 1, 'role': 'cover'},
                    {'startPage': 2, 'endPage': 2, 'role': 'questions'},
                    {'startPage': 3, 'endPage': 3, 'role': 'answer_solutions'},
                ],
                'expectedQuestionNumbers': {'from': 1, 'to': 50},
                'expectedOutOfScopeNumbers': [51],
            },
            {
                'fixtureId': 'fixture-b',
                'pattern': 'solutions_cover_questions',
                'pdfPath': str(paths[1]),
                'expectedPageCount': 3,
                'expectedSegments': [
                    {'startPage': 1, 'endPage': 1, 'role': 'answer_solutions'},
                    {'startPage': 2, 'endPage': 2, 'role': 'cover'},
                    {'startPage': 3, 'endPage': 3, 'role': 'questions'},
                ],
                'expectedQuestionNumbers': {'from': 51, 'to': 115},
                'expectedOutOfScopeNumbers': [50, 116],
            },
            {
                'fixtureId': 'fixture-c',
                'pattern': 'cover_questions_solutions_overlap',
                'pdfPath': str(paths[2]),
                'expectedPageCount': 3,
                'expectedSegments': [
                    {'startPage': 1, 'endPage': 1, 'role': 'cover'},
                    {'startPage': 2, 'endPage': 2, 'role': 'questions'},
                    {'startPage': 3, 'endPage': 3, 'role': 'answer_solutions'},
                ],
                'expectedQuestionNumbers': {'from': 116, 'to': 145},
                'expectedOutOfScopeNumbers': [115, 146],
            },
        ],
    }


def _manifest(tmp_path, *, same_pdf=False, mutate=None):
    if same_pdf:
        secret = _write_pdf(tmp_path / 'teacher-secret-source.pdf')
        paths = [secret, secret, secret]
    else:
        paths = [
            _write_pdf(tmp_path / 'teacher-secret-a.pdf'),
            _write_pdf(tmp_path / 'teacher-secret-b.pdf'),
            _write_pdf(tmp_path / 'teacher-secret-c.pdf'),
        ]
    payload = _manifest_payload(paths)
    if mutate:
        mutate(payload)
    path = tmp_path / 'private-benchmark-manifest.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path, paths


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _storage_files(storage):
    root = Path(storage.location)
    return sorted(path for path in root.rglob('*') if path.is_file())


def test_manifest_accepts_three_content_free_structural_patterns(tmp_path):
    manifest_path, _paths = _manifest(tmp_path)

    manifest = load_benchmark_manifest(manifest_path)

    assert [fixture.fixture_id for fixture in manifest.fixtures] == [
        'fixture-a',
        'fixture-b',
        'fixture-c',
    ]
    assert [fixture.pattern for fixture in manifest.fixtures] == [
        'cover_questions_solutions',
        'solutions_cover_questions',
        'cover_questions_solutions_overlap',
    ]


@pytest.mark.parametrize(
    'mutate, expected_fragment',
    [
        (
            lambda payload: payload.update({'unexpected': True}),
            'validation failed',
        ),
        (
            lambda payload: payload['fixtures'][1].update(
                {'fixtureId': payload['fixtures'][0]['fixtureId']}
            ),
            'validation failed',
        ),
        (
            lambda payload: payload['fixtures'][0]['expectedSegments'][1].update(
                {'startPage': 3}
            ),
            'validation failed',
        ),
        (
            lambda payload: payload['fixtures'][0].update(
                {'pattern': 'solutions_cover_questions'}
            ),
            'validation failed',
        ),
    ],
)
def test_manifest_rejects_invalid_contract_without_echoing_paths(
    tmp_path,
    mutate,
    expected_fragment,
):
    manifest_path, paths = _manifest(tmp_path, mutate=mutate)

    with pytest.raises(BenchmarkManifestError) as caught:
        load_benchmark_manifest(manifest_path)

    message = str(caught.value)
    assert expected_fragment in message.lower()
    assert all(str(path) not in message for path in paths)
    assert all(path.name not in message for path in paths)


def test_manifest_rejects_missing_or_non_pdf_source_without_path_leak(tmp_path):
    manifest_path, paths = _manifest(tmp_path)
    paths[0].unlink()

    with pytest.raises(BenchmarkManifestError) as missing:
        load_benchmark_manifest(manifest_path)

    assert 'fixture-a' in str(missing.value)
    assert str(paths[0]) not in str(missing.value)
    assert paths[0].name not in str(missing.value)

    paths[0].write_text('not a PDF', encoding='utf-8')
    with pytest.raises(BenchmarkManifestError) as invalid:
        load_benchmark_manifest(manifest_path)
    assert 'fixture-a' in str(invalid.value)
    assert paths[0].name not in str(invalid.value)


def test_fake_benchmark_reports_aggregate_metrics_and_cleans_everything(
    tmp_path,
    private_storage,
    settings,
    django_capture_on_commit_callbacks,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, secret_paths = _manifest(tmp_path)
    manifest = load_benchmark_manifest(manifest_path)
    teacher = _teacher()

    with django_capture_on_commit_callbacks(execute=True):
        report = run_benchmark(
            manifest=manifest,
            teacher=teacher,
            mode='fake_provider',
        )

    serialized = json.dumps(report, ensure_ascii=False)
    assert report['status'] == 'passed'
    assert report['mode'] == 'fake_provider'
    assert report['totals'] == {
        'fixtureCount': 3,
        'passedFixtures': 3,
        'failedFixtures': 0,
        'pageCount': 9,
        'coldProviderCalls': 3,
        'warmProviderCalls': 0,
        'totalTokens': 0,
        'estimatedCostUsd': 0.0,
        'independentProjectCount': 3,
    }
    assert all(item['segmentMapExact'] for item in report['fixtures'])
    assert all(item['pageRoleAccuracy'] == 1.0 for item in report['fixtures'])
    assert all(item['warmReused'] for item in report['fixtures'])
    assert all(item['warmUsage']['calls'] == 0 for item in report['fixtures'])
    assert all(value is False for value in report['privacy'].values())
    assert all(str(path) not in serialized for path in secret_paths)
    assert all(path.name not in serialized for path in secret_paths)
    assert str(manifest_path) not in serialized
    assert manifest_path.name not in serialized
    assert ExamProject.objects.filter(teacher=teacher).count() == 0
    assert ExamSourceDocument.objects.filter(project__teacher=teacher).count() == 0
    assert _storage_files(private_storage) == []


def test_equal_pdf_bytes_still_create_three_independent_benchmark_projects(
    tmp_path,
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, _paths = _manifest(tmp_path, same_pdf=True)
    manifest = load_benchmark_manifest(manifest_path)
    teacher = _teacher()

    report = run_benchmark(
        manifest=manifest,
        teacher=teacher,
        mode='fake_provider',
        keep_projects=True,
    )

    projects = ExamProject.objects.filter(teacher=teacher)
    documents = ExamSourceDocument.objects.filter(project__teacher=teacher)
    assert report['status'] == 'passed'
    assert report['totals']['independentProjectCount'] == 3
    assert projects.count() == 3
    assert documents.count() == 3
    assert len(set(documents.values_list('source_sha256', flat=True))) == 1

    projects.delete()


def test_mismatched_real_page_count_never_produces_false_pass(
    tmp_path,
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, paths = _manifest(tmp_path)
    _write_pdf(paths[0], page_count=4)
    manifest = load_benchmark_manifest(manifest_path)

    report = run_benchmark(
        manifest=manifest,
        teacher=_teacher(),
        mode='fake_provider',
    )

    assert report['status'] == 'failed'
    assert report['totals']['failedFixtures'] >= 1
    fixture_a = next(item for item in report['fixtures'] if item['fixtureId'] == 'fixture-a')
    assert fixture_a['status'] != 'passed'


def test_live_mode_fails_closed_without_model_or_credentials_before_writes(
    tmp_path,
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, _paths = _manifest(tmp_path)
    manifest = load_benchmark_manifest(manifest_path)
    monkeypatch.delenv('EXAM_PREP_V4_CLASSIFICATION_MODEL', raising=False)
    monkeypatch.delenv('PDF_VISION_MODEL', raising=False)
    monkeypatch.delenv('AVALAI_API_KEY', raising=False)

    from apps.classes.services.exam_prep_v4_benchmark import BenchmarkConfigurationError

    with pytest.raises(BenchmarkConfigurationError, match='CLASSIFICATION_MODEL'):
        run_benchmark(
            manifest=manifest,
            teacher=_teacher(),
            mode='live_provider',
        )

    assert ExamProject.objects.count() == 0
    assert _storage_files(private_storage) == []


def test_management_command_output_and_report_never_reveal_private_paths(
    tmp_path,
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, secret_paths = _manifest(tmp_path)
    output_path = tmp_path / 'aggregate-report.json'
    stdout = io.StringIO()

    call_command(
        'benchmark_exam_prep_v4',
        manifest=str(manifest_path),
        fake_provider=True,
        output=str(output_path),
        stdout=stdout,
    )

    terminal = stdout.getvalue()
    written = output_path.read_text(encoding='utf-8')
    assert json.loads(terminal)['status'] == 'passed'
    assert json.loads(written)['status'] == 'passed'
    for private_path in [manifest_path, *secret_paths]:
        assert str(private_path) not in terminal
        assert private_path.name not in terminal
        assert str(private_path) not in written
        assert private_path.name not in written
    assert ExamProject.objects.count() == 0
    assert not get_benchmark_users().exists()


def get_benchmark_users():
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(username__startswith='v4-benchmark-')


def test_command_requires_explicit_mode_and_keep_requires_real_teacher(
    tmp_path,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, _paths = _manifest(tmp_path)

    with pytest.raises(CommandError):
        call_command('benchmark_exam_prep_v4', manifest=str(manifest_path))
    with pytest.raises(CommandError, match='requires --teacher-id'):
        call_command(
            'benchmark_exam_prep_v4',
            manifest=str(manifest_path),
            fake_provider=True,
            keep_projects=True,
        )


def test_command_prints_failed_aggregate_then_returns_nonzero(
    tmp_path,
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    manifest_path, paths = _manifest(tmp_path)
    _write_pdf(paths[0], page_count=4)
    stdout = io.StringIO()

    with pytest.raises(CommandError, match='aggregate status is failed'):
        call_command(
            'benchmark_exam_prep_v4',
            manifest=str(manifest_path),
            fake_provider=True,
            stdout=stdout,
        )

    payload = json.loads(stdout.getvalue())
    assert payload['status'] == 'failed'
    assert payload['totals']['failedFixtures'] >= 1
    assert ExamProject.objects.count() == 0
    assert not get_benchmark_users().exists()
