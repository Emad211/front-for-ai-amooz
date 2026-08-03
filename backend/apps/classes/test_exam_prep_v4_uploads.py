import io
import json
import uuid

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from PIL import Image

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services import exam_prep_v4_uploads as uploads_service
from apps.classes.services.exam_prep_v4_projects import (
    ExamPrepV4IdempotencyConflict,
    InvalidExamPrepV4Source,
)
from apps.classes.services.exam_prep_v4_uploads import (
    UploadMetadata,
    persist_uploaded_pdf_batch,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def private_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / 'private')
    monkeypatch.setattr(
        ExamSourceDocument._meta.get_field('source_file'),
        'storage',
        storage,
    )
    return storage


def _pdf(tone=240):
    image = Image.new('RGB', (320, 480), (tone, tone, tone))
    output = io.BytesIO()
    image.save(output, format='PDF', resolution=96)
    return output.getvalue()


def _upload(name, *, tone=240, content_type='application/pdf'):
    return SimpleUploadedFile(
        name,
        _pdf(tone),
        content_type=content_type,
    )


def _metadata(count):
    return tuple(
        UploadMetadata(
            client_request_id=uuid.uuid4(),
            client_document_id=uuid.uuid4(),
            title=f'آزمون {index + 1}',
        )
        for index in range(count)
    )


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _storage_files(storage):
    root = storage.location
    import os

    return sorted(
        os.path.relpath(os.path.join(dirpath, filename), root)
        for dirpath, _dirs, filenames in os.walk(root)
        for filename in filenames
    )


def test_three_equal_pdfs_create_three_projects_and_three_private_sources(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    metadata = _metadata(3)
    same_bytes = _pdf(235)
    source_files = [
        SimpleUploadedFile(
            f'exam-{index + 1}.pdf',
            same_bytes,
            content_type='application/pdf',
        )
        for index in range(3)
    ]

    result = persist_uploaded_pdf_batch(
        teacher=teacher,
        uploads=source_files,
        metadata=metadata,
    )

    assert len(result) == 3
    assert len({item.project_id for item in result}) == 3
    assert len({item.document_id for item in result}) == 3
    assert len({item.source_sha256 for item in result}) == 1
    assert ExamProject.objects.filter(teacher=teacher).count() == 3
    assert ExamSourceDocument.objects.filter(project__teacher=teacher).count() == 3
    assert all(item.project_status == ExamProject.Status.UPLOADING for item in result)
    assert all(
        item.document_status == ExamSourceDocument.Status.UPLOADED
        for item in result
    )
    assert all(item.reused_source is False for item in result)
    assert len(_storage_files(private_storage)) == 3


def test_batch_is_validated_before_any_database_or_blob_write(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    metadata = _metadata(2)
    invalid = SimpleUploadedFile(
        'bad.pdf',
        b'not a PDF',
        content_type='application/pdf',
    )

    with pytest.raises(InvalidExamPrepV4Source, match='not a valid PDF'):
        persist_uploaded_pdf_batch(
            teacher=teacher,
            uploads=[_upload('good.pdf'), invalid],
            metadata=metadata,
        )

    assert ExamProject.objects.count() == 0
    assert ExamSourceDocument.objects.count() == 0
    assert _storage_files(private_storage) == []


def test_metadata_count_and_duplicate_ids_are_rejected_before_writes(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()

    with pytest.raises(InvalidExamPrepV4Source, match='count must match'):
        persist_uploaded_pdf_batch(
            teacher=teacher,
            uploads=[_upload('one.pdf'), _upload('two.pdf')],
            metadata=_metadata(1),
        )

    shared = uuid.uuid4()
    metadata = (
        UploadMetadata(shared, uuid.uuid4()),
        UploadMetadata(shared, uuid.uuid4()),
    )
    with pytest.raises(InvalidExamPrepV4Source, match='distinct client request'):
        persist_uploaded_pdf_batch(
            teacher=teacher,
            uploads=[_upload('one.pdf'), _upload('two.pdf')],
            metadata=metadata,
        )

    assert ExamProject.objects.count() == 0
    assert _storage_files(private_storage) == []


def test_same_identifiers_and_bytes_reuse_project_document_and_blob(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    metadata = _metadata(1)

    first = persist_uploaded_pdf_batch(
        teacher=teacher,
        uploads=[_upload('retry.pdf', tone=230)],
        metadata=metadata,
    )[0]
    files_before = _storage_files(private_storage)
    second = persist_uploaded_pdf_batch(
        teacher=teacher,
        uploads=[_upload('retry.pdf', tone=230)],
        metadata=metadata,
    )[0]

    assert second.project_id == first.project_id
    assert second.document_id == first.document_id
    assert second.reused_source is True
    assert _storage_files(private_storage) == files_before
    assert ExamProject.objects.count() == 1
    assert ExamSourceDocument.objects.count() == 1


def test_same_request_with_different_pdf_bytes_is_conflict(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    metadata = _metadata(1)
    first = persist_uploaded_pdf_batch(
        teacher=teacher,
        uploads=[_upload('same.pdf', tone=240)],
        metadata=metadata,
    )[0]

    with pytest.raises(ExamPrepV4IdempotencyConflict):
        persist_uploaded_pdf_batch(
            teacher=teacher,
            uploads=[_upload('same.pdf', tone=180)],
            metadata=metadata,
        )

    document = ExamSourceDocument.objects.get(id=first.document_id)
    assert document.source_sha256 == first.source_sha256
    assert document.status == ExamSourceDocument.Status.UPLOADED
    assert len(_storage_files(private_storage)) == 1


def test_failure_after_blob_write_rolls_back_rows_and_deletes_new_blobs(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    original_mark_queued = uploads_service._mark_queued
    calls = []

    def fail_on_second(project, document):
        calls.append(document.id)
        if len(calls) == 2:
            raise RuntimeError('simulated persistence failure')
        original_mark_queued(project, document)

    monkeypatch.setattr(uploads_service, '_mark_queued', fail_on_second)
    monkeypatch.setattr(
        uploads_service,
        'delete_answer_source_file',
        lambda name: private_storage.delete(name) or True,
    )

    with pytest.raises(RuntimeError, match='simulated persistence failure'):
        persist_uploaded_pdf_batch(
            teacher=teacher,
            uploads=[_upload('one.pdf', tone=230), _upload('two.pdf', tone=210)],
            metadata=_metadata(2),
        )

    assert ExamProject.objects.count() == 0
    assert ExamSourceDocument.objects.count() == 0
    assert _storage_files(private_storage) == []


def test_existing_classification_keeps_reviewable_state_and_is_not_requeued(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    metadata = _metadata(1)
    first = persist_uploaded_pdf_batch(
        teacher=teacher,
        uploads=[_upload('ready.pdf')],
        metadata=metadata,
    )[0]
    project = ExamProject.objects.get(id=first.project_id)
    document = ExamSourceDocument.objects.get(id=first.document_id)
    project.status = ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    project.workflow_state = {'stage': 'awaiting_source_confirmation'}
    project.save(update_fields=['status', 'workflow_state', 'updated_at'])
    document.status = ExamSourceDocument.Status.AWAITING_CONFIRMATION
    document.classification_fingerprint = 'a' * 64
    document.save(
        update_fields=[
            'status',
            'classification_fingerprint',
            'updated_at',
        ]
    )

    retry = persist_uploaded_pdf_batch(
        teacher=teacher,
        uploads=[_upload('ready.pdf')],
        metadata=metadata,
    )[0]

    assert retry.reused_source is True
    assert retry.classification_already_available is True
    assert retry.project_status == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    assert retry.document_status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
