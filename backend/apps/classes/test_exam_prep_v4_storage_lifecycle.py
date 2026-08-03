import io

import pytest
from django.core.files.storage import FileSystemStorage
from model_bakery import baker
from PIL import Image

from apps.classes.models_v4 import ExamProject, ExamSourceDocument, ExamSourcePage
from apps.classes.services.exam_prep_v4_pdf_source import prepare_pdf_source_from_bytes


pytestmark = pytest.mark.django_db


def _one_page_pdf():
    image = Image.new('RGB', (480, 680), 'white')
    output = io.BytesIO()
    image.save(output, format='PDF', resolution=96)
    return output.getvalue()


def test_deleting_v4_project_deletes_all_private_source_blobs(
    tmp_path,
    monkeypatch,
    django_capture_on_commit_callbacks,
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
        original_name='source.pdf',
    )
    prepare_pdf_source_from_bytes(
        document_id=document.id,
        data=_one_page_pdf(),
        original_name='source.pdf',
    )
    document.refresh_from_db()
    page = document.pages.get()
    names = {
        document.source_file.name,
        page.rendered_file.name,
        page.thumbnail_file.name,
    }
    assert all(storage.exists(name) for name in names)

    deleted = []

    def delete_private(name):
        deleted.append(name)
        storage.delete(name)
        return True

    monkeypatch.setattr(
        'apps.classes.signals.delete_answer_source_file',
        delete_private,
    )

    with django_capture_on_commit_callbacks(execute=True):
        project.delete()

    assert set(deleted) == names
    assert all(not storage.exists(name) for name in names)
    assert not ExamProject.objects.filter(id=project.id).exists()
