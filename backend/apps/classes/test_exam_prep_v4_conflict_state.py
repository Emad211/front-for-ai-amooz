import io

import pytest
from django.core.files.storage import FileSystemStorage
from model_bakery import baker
from PIL import Image

from apps.classes.models_v4 import ExamProject, ExamSourceDocument, ExamSourcePage
from apps.classes.services.exam_prep_v4_pdf_source import (
    V4PdfSourceConflict,
    prepare_pdf_source_from_bytes,
)


pytestmark = pytest.mark.django_db


def _pdf(tone: int) -> bytes:
    image = Image.new('RGB', (320, 480), (tone, tone, tone))
    output = io.BytesIO()
    image.save(output, format='PDF', resolution=96)
    return output.getvalue()


def test_replacement_conflict_preserves_valid_document_and_private_blobs(
    tmp_path,
    monkeypatch,
):
    storage = FileSystemStorage(location=tmp_path / 'private')
    for model, field_names in (
        (ExamSourceDocument, ('source_file',)),
        (ExamSourcePage, ('rendered_file', 'thumbnail_file')),
    ):
        for field_name in field_names:
            monkeypatch.setattr(model._meta.get_field(field_name), 'storage', storage)

    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(teacher=teacher, title='آزمون')
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='first.pdf',
    )
    prepare_pdf_source_from_bytes(
        document_id=document.id,
        data=_pdf(240),
        original_name='first.pdf',
    )
    document.refresh_from_db()
    page = document.pages.get()
    original_state = {
        'status': document.status,
        'sha256': document.source_sha256,
        'source_name': document.source_file.name,
        'rendered_name': page.rendered_file.name,
        'thumbnail_name': page.thumbnail_file.name,
        'error_code': document.error_code,
        'error_detail': document.error_detail,
    }
    assert original_state['status'] == ExamSourceDocument.Status.UPLOADED
    assert all(
        storage.exists(original_state[key])
        for key in ('source_name', 'rendered_name', 'thumbnail_name')
    )

    with pytest.raises(V4PdfSourceConflict, match='different PDF bytes'):
        prepare_pdf_source_from_bytes(
            document_id=document.id,
            data=_pdf(190),
            original_name='replacement.pdf',
        )

    document.refresh_from_db()
    page.refresh_from_db()
    assert document.status == original_state['status']
    assert document.source_sha256 == original_state['sha256']
    assert document.source_file.name == original_state['source_name']
    assert page.rendered_file.name == original_state['rendered_name']
    assert page.thumbnail_file.name == original_state['thumbnail_name']
    assert document.error_code == original_state['error_code'] == ''
    assert document.error_detail == original_state['error_detail'] == ''
    assert document.pages.count() == 1
    assert all(
        storage.exists(original_state[key])
        for key in ('source_name', 'rendered_name', 'thumbnail_name')
    )
