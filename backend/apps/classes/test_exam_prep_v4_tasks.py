import io
from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import override_settings
from model_bakery import baker
from PIL import Image

from apps.classes import tasks_v4
from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services.exam_prep_v4_classification import PersistedClassification
from apps.classes.services.exam_prep_v4_fast_classifier import FastClassifierResult
from apps.classes.services.exam_prep_v4_pdf_source import PreparedDocument
from apps.classes.services.exam_prep_v4_source_pipeline import SourcePipelineResult


pytestmark = pytest.mark.django_db


def _pdf() -> bytes:
    image = Image.new('RGB', (320, 480), 'white')
    output = io.BytesIO()
    image.save(output, format='PDF', resolution=96)
    return output.getvalue()


@pytest.fixture
def private_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / 'private')
    monkeypatch.setattr(
        ExamSourceDocument._meta.get_field('source_file'),
        'storage',
        storage,
    )
    return storage


def _document(*, with_source=True):
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(teacher=teacher, title='آزمون')
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='source.pdf',
        mime_type='application/pdf',
    )
    if with_source:
        document.source_file.save('source.pdf', ContentFile(_pdf()), save=True)
    return project, document


def _pipeline_result(document_id):
    return SourcePipelineResult(
        prepared=PreparedDocument(
            document_id=document_id,
            source_sha256='a' * 64,
            page_count=2,
            pages=(),
            reused=False,
        ),
        classified=FastClassifierResult(
            model='fast-model',
            prompt_version='v1',
            input_fingerprint='b' * 64,
            classification=PersistedClassification(
                document_id=document_id,
                revision=1,
                fingerprint='b' * 64,
                pages=(),
                segments=(SimpleNamespace(), SimpleNamespace(), SimpleNamespace()),
                issues=(SimpleNamespace(),),
                reused=False,
            ),
        ),
    )


@override_settings(EXAM_PREP_V4_ENABLED=False)
def test_task_skips_without_feature_flag(private_storage):
    _project, document = _document()

    result = tasks_v4.process_exam_prep_v4_source.run(document.id)

    assert result == {
        'status': 'skipped',
        'document_id': document.id,
        'reason': 'v4_disabled',
    }


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_task_skips_missing_document():
    result = tasks_v4.process_exam_prep_v4_source.run(999999)

    assert result['status'] == 'skipped'
    assert result['reason'] == 'document_not_found'


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_task_lock_prevents_duplicate_processing(private_storage, monkeypatch):
    _project, document = _document()
    monkeypatch.setattr(tasks_v4.cache, 'add', lambda *_args, **_kwargs: False)

    result = tasks_v4.process_exam_prep_v4_source.run(document.id)

    assert result['status'] == 'skipped'
    assert result['reason'] == 'already_processing'


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_missing_source_file_marks_document_and_project_failed():
    project, document = _document(with_source=False)

    result = tasks_v4.process_exam_prep_v4_source.run(document.id)

    document.refresh_from_db()
    project.refresh_from_db()
    assert result['status'] == 'failed'
    assert result['reason'] == 'source_file_missing'
    assert document.status == ExamSourceDocument.Status.FAILED
    assert document.error_code == 'source_file_missing'
    assert project.status == ExamProject.Status.FAILED
    assert project.error_code == 'source_file_missing'


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_task_copies_only_its_private_source_to_temp_and_runs_coordinator(
    private_storage,
    monkeypatch,
):
    project, document = _document()
    captured = {}

    def fake_pipeline(**kwargs):
        captured.update(kwargs)
        with open(kwargs['source_path'], 'rb') as handle:
            assert handle.read().startswith(b'%PDF')
        return _pipeline_result(document.id)

    monkeypatch.setattr(tasks_v4, 'prepare_and_classify_pdf_source', fake_pipeline)

    result = tasks_v4.process_exam_prep_v4_source.run(document.id)

    assert result == {
        'status': 'ready_for_source_confirmation',
        'project_id': project.id,
        'document_id': document.id,
        'page_count': 2,
        'segment_count': 3,
        'issue_count': 1,
        'reused_source': False,
        'reused_classification': False,
    }
    assert captured['document_id'] == document.id
    assert captured['original_name'] == 'source.pdf'
    assert captured['mime_type'] == 'application/pdf'


def test_dispatch_publishes_one_signature_per_document(monkeypatch):
    captured = {}

    class FakeGroupResult:
        id = 'group-123'

    class FakeGroup:
        def apply_async(self):
            captured['applied'] = True
            return FakeGroupResult()

    def fake_group(signatures):
        captured['signatures'] = list(signatures)
        return FakeGroup()

    monkeypatch.setattr(tasks_v4, 'group', fake_group)

    result = tasks_v4.dispatch_exam_prep_v4_sources([11, 22, 33])

    assert result == 'group-123'
    assert captured['applied'] is True
    assert [signature.args for signature in captured['signatures']] == [
        (11,),
        (22,),
        (33,),
    ]
    assert all(
        signature.task == tasks_v4.process_exam_prep_v4_source.name
        for signature in captured['signatures']
    )


def test_dispatch_rejects_empty_batch():
    with pytest.raises(ValueError, match='At least one document'):
        tasks_v4.dispatch_exam_prep_v4_sources([])
