import io
from pathlib import Path

import pytest
from django.core.files.storage import FileSystemStorage
from model_bakery import baker
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from rest_framework.test import APIClient

from apps.classes.models_v4 import ExamProject, ExamSourceDocument, ExamSourcePage
from apps.classes.services.exam_prep_v4_pdf_source import (
    V4PdfSourceConflict,
    V4PdfSourceError,
    load_classification_page_inputs,
    prepare_pdf_source_from_bytes,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def private_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / 'private')
    for model, field_names in (
        (ExamSourceDocument, ('source_file',)),
        (ExamSourcePage, ('rendered_file', 'thumbnail_file')),
    ):
        for field_name in field_names:
            monkeypatch.setattr(model._meta.get_field(field_name), 'storage', storage)
    return storage


def _document(*, source_sha256=''):
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(teacher=teacher, title='آزمون')
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='source.pdf',
        source_sha256=source_sha256,
    )
    return project, document


def _raster_pdf(page_tones, *, labels=True):
    images = []
    for index, tone in enumerate(page_tones, start=1):
        image = Image.new('RGB', (480, 680), (tone, tone, tone))
        if labels:
            ImageDraw.Draw(image).text((30, 30), f'PAGE {index}', fill='black')
        images.append(image)
    output = io.BytesIO()
    images[0].save(
        output,
        format='PDF',
        save_all=True,
        append_images=images[1:],
        resolution=96,
    )
    return output.getvalue()


def _encrypted_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=480, height=680)
    writer.encrypt('secret')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _all_storage_files(root: Path):
    return sorted(path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file())


def test_prepare_pdf_saves_private_original_pages_and_thumbnails(private_storage):
    project, document = _document()
    data = _raster_pdf([245, 230, 215])

    result = prepare_pdf_source_from_bytes(
        document_id=document.id,
        data=data,
        original_name='teacher-source.pdf',
    )

    document.refresh_from_db()
    assert result.reused is False
    assert result.document_id == document.id
    assert result.page_count == 3
    assert len(result.pages) == 3
    assert document.project_id == project.id
    assert document.status == ExamSourceDocument.Status.UPLOADED
    assert document.original_name == 'teacher-source.pdf'
    assert document.mime_type == 'application/pdf'
    assert document.byte_size == len(data)
    assert len(document.source_sha256) == 64
    assert document.source_file.name.startswith('exam-prep-v4/source/documents/')
    assert document.pages.count() == 3

    for page in document.pages.order_by('page_number'):
        assert page.rendered_file.name.startswith('exam-prep-v4/source/pages/')
        assert page.thumbnail_file.name.startswith('exam-prep-v4/source/thumbnails/')
        assert page.width > 0 and page.height > 0
        assert page.byte_size > 0
        assert len(page.sha256) == 64
        with page.rendered_file.open('rb') as handle:
            rendered = Image.open(handle)
            rendered.verify()
            assert rendered.format == 'PNG'
        with page.thumbnail_file.open('rb') as handle:
            thumbnail = Image.open(handle)
            thumbnail.verify()
            assert thumbnail.format == 'JPEG'
            assert thumbnail.width <= 320

    assert private_storage.exists(document.source_file.name)


def test_same_pdf_retry_reuses_all_objects_without_new_files(private_storage):
    _, document = _document()
    data = _raster_pdf([240, 220])

    first = prepare_pdf_source_from_bytes(
        document_id=document.id,
        data=data,
        original_name='same.pdf',
    )
    files_before = _all_storage_files(Path(private_storage.location))
    second = prepare_pdf_source_from_bytes(
        document_id=document.id,
        data=data,
        original_name='same.pdf',
    )
    files_after = _all_storage_files(Path(private_storage.location))

    assert first.reused is False
    assert second.reused is True
    assert files_after == files_before
    assert document.pages.count() == 2


def test_different_pdf_bytes_cannot_replace_existing_document(private_storage):
    _, document = _document()
    prepare_pdf_source_from_bytes(
        document_id=document.id,
        data=_raster_pdf([240]),
        original_name='first.pdf',
    )

    with pytest.raises(V4PdfSourceConflict, match='different PDF bytes'):
        prepare_pdf_source_from_bytes(
            document_id=document.id,
            data=_raster_pdf([200]),
            original_name='second.pdf',
        )

    document.refresh_from_db()
    assert document.pages.count() == 1


def test_predeclared_matching_sha_is_accepted(private_storage):
    data = _raster_pdf([235])
    import hashlib

    digest = hashlib.sha256(data).hexdigest()
    _, document = _document(source_sha256=digest)

    result = prepare_pdf_source_from_bytes(
        document_id=document.id,
        data=data,
        original_name='predeclared.pdf',
    )

    assert result.source_sha256 == digest
    assert result.page_count == 1


def test_encrypted_pdf_is_rejected_before_rendering(private_storage):
    _, document = _document()

    with pytest.raises(V4PdfSourceError, match='Encrypted PDFs'):
        prepare_pdf_source_from_bytes(
            document_id=document.id,
            data=_encrypted_pdf(),
            original_name='encrypted.pdf',
        )

    assert document.pages.count() == 0


def test_non_pdf_bytes_are_rejected(private_storage):
    _, document = _document()

    with pytest.raises(V4PdfSourceError, match='not a valid PDF'):
        prepare_pdf_source_from_bytes(
            document_id=document.id,
            data=b'plain text, not a PDF',
            original_name='fake.pdf',
        )

    assert document.pages.count() == 0


def test_page_limit_is_enforced(private_storage, settings):
    settings.PDF_MAX_PAGES = 1
    _, document = _document()

    with pytest.raises(V4PdfSourceError, match='exceeds the configured limit'):
        prepare_pdf_source_from_bytes(
            document_id=document.id,
            data=_raster_pdf([240, 230]),
            original_name='too-many.pdf',
        )

    assert document.pages.count() == 0


def test_identical_pages_are_deduplicated_only_inside_project(private_storage):
    first_project, first_document = _document()
    # No labels keeps both rendered pages byte-identical.
    prepare_pdf_source_from_bytes(
        document_id=first_document.id,
        data=_raster_pdf([220, 220], labels=False),
        original_name='duplicates.pdf',
    )
    first_pages = list(first_document.pages.order_by('page_number'))
    assert first_pages[0].duplicate_of_id is None
    assert first_pages[1].duplicate_of_id == first_pages[0].id

    teacher = baker.make('accounts.User', role='TEACHER')
    second_project = ExamProject.objects.create(teacher=teacher, title='آزمون دیگر')
    second_document = ExamSourceDocument.objects.create(
        project=second_project,
        original_name='separate.pdf',
    )
    prepare_pdf_source_from_bytes(
        document_id=second_document.id,
        data=_raster_pdf([220], labels=False),
        original_name='separate.pdf',
    )
    second_page = second_document.pages.get()

    assert first_project.id != second_project.id
    assert second_page.sha256 == first_pages[0].sha256
    assert second_page.duplicate_of_id is None


def test_load_classification_inputs_reads_private_thumbnails(private_storage):
    _, document = _document()
    prepare_pdf_source_from_bytes(
        document_id=document.id,
        data=_raster_pdf([240, 225]),
        original_name='input.pdf',
    )

    inputs = load_classification_page_inputs(document_id=document.id)

    assert [item.page_number for item in inputs] == [1, 2]
    assert all(item.mime_type == 'image/jpeg' for item in inputs)
    assert all(item.image.startswith(b'\xff\xd8') for item in inputs)


def test_generic_media_route_denies_all_v4_source_prefixes(monkeypatch):
    opened = []

    def fail_if_opened(name, mode='rb'):
        opened.append((name, mode))
        raise AssertionError('Private V4 media must not reach generic storage.')

    monkeypatch.setattr(
        'django.core.files.storage.default_storage.open',
        fail_if_opened,
    )

    for path in (
        '/media/exam-prep-v4/source/documents/private.pdf',
        '/media/exam-prep-v4/source/pages/page.png',
        '/media/exam-prep-v4/source/thumbnails/page.jpg',
    ):
        assert APIClient().get(path).status_code == 404

    assert opened == []
