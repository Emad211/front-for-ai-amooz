import io
import uuid

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from PIL import Image

from apps.classes.models_v4 import ExamSourceDocument
from apps.classes.services.exam_prep_v4_uploads import (
    UploadMetadata,
    persist_uploaded_pdf_batch,
)


pytestmark = pytest.mark.django_db


def _pdf() -> bytes:
    image = Image.new('RGB', (320, 480), 'white')
    output = io.BytesIO()
    image.save(output, format='PDF', resolution=96)
    return output.getvalue()


def _upload(data: bytes):
    return SimpleUploadedFile('recover.pdf', data, content_type='application/pdf')


def test_idempotent_retry_recreates_named_but_missing_private_blob(
    tmp_path,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    storage = FileSystemStorage(location=tmp_path / 'private')
    monkeypatch.setattr(
        ExamSourceDocument._meta.get_field('source_file'),
        'storage',
        storage,
    )
    teacher = baker.make('accounts.User', role='TEACHER')
    metadata = (
        UploadMetadata(
            client_request_id=uuid.uuid4(),
            client_document_id=uuid.uuid4(),
        ),
    )
    data = _pdf()

    first = persist_uploaded_pdf_batch(
        teacher=teacher,
        uploads=[_upload(data)],
        metadata=metadata,
    )[0]
    document = ExamSourceDocument.objects.get(id=first.document_id)
    missing_name = document.source_file.name
    storage.delete(missing_name)
    assert not storage.exists(missing_name)

    retry = persist_uploaded_pdf_batch(
        teacher=teacher,
        uploads=[_upload(data)],
        metadata=metadata,
    )[0]

    document.refresh_from_db()
    assert retry.project_id == first.project_id
    assert retry.document_id == first.document_id
    assert retry.reused_source is False
    assert storage.exists(document.source_file.name)
    assert document.status == ExamSourceDocument.Status.UPLOADED
