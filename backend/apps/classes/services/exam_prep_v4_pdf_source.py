"""Private, bounded-memory PDF preparation for Exam Prep V4.

This stage validates and stores one source PDF, renders classification-quality
page images serially, creates small thumbnails, and captures bounded native-text
samples. It performs no LLM OCR and no question extraction.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from django.conf import settings
from django.core.files import File
from django.db import transaction
from PIL import Image

from apps.classes.models_v4 import ExamSourceDocument, ExamSourcePage
from apps.classes.services.exam_prep_v4_fast_classifier import RenderedPageInput

logger = logging.getLogger(__name__)


class V4PdfSourceError(RuntimeError):
    pass


class V4PdfSourceConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedPage:
    page_number: int
    sha256: str
    rendered_name: str
    thumbnail_name: str
    width: int
    height: int
    native_text_length: int
    duplicate_of_id: int | None


@dataclass(frozen=True, slots=True)
class PreparedDocument:
    document_id: int
    source_sha256: str
    page_count: int
    pages: tuple[PreparedPage, ...]
    reused: bool


def _setting_int(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    raw = getattr(settings, name, os.getenv(name, default))
    try:
        value = max(minimum, int(raw))
    except (TypeError, ValueError):
        value = default
    return min(value, maximum) if maximum is not None else value


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_size(path: Path) -> int:
    try:
        byte_size = path.stat().st_size
    except OSError as exc:
        raise V4PdfSourceError('Source PDF is unavailable.') from exc
    max_bytes = int(getattr(settings, 'PDF_MAX_UPLOAD_BYTES', 100 * 1024 * 1024))
    if byte_size <= 0:
        raise V4PdfSourceError('Source PDF is empty.')
    if byte_size > max_bytes:
        raise V4PdfSourceError(
            f'Source PDF exceeds the configured {max_bytes // (1024 * 1024)} MB limit.'
        )
    return byte_size


def _validate_header(path: Path) -> None:
    try:
        with path.open('rb') as handle:
            header = handle.read(1024)
    except OSError as exc:
        raise V4PdfSourceError('Source PDF could not be read.') from exc
    if b'%PDF' not in header:
        raise V4PdfSourceError('Source file is not a valid PDF.')


def _open_pdf(path: Path):
    import pypdfium2 as pdfium
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                if reader.decrypt('') == 0:
                    raise V4PdfSourceError('Encrypted PDFs require an unprotected copy.')
            except V4PdfSourceError:
                raise
            except Exception as exc:
                raise V4PdfSourceError(
                    'Encrypted PDFs require an unprotected copy.'
                ) from exc
        page_count = len(reader.pages)
        pdf = pdfium.PdfDocument(str(path))
    except V4PdfSourceError:
        raise
    except (PdfReadError, Exception) as exc:
        raise V4PdfSourceError(f'PDF validation failed: {exc}') from exc

    if page_count < 1:
        pdf.close()
        raise V4PdfSourceError('Source PDF contains no pages.')
    max_pages = _setting_int('PDF_MAX_PAGES', 200)
    if page_count > max_pages:
        pdf.close()
        raise V4PdfSourceError(
            f'PDF page count {page_count} exceeds the configured limit {max_pages}.'
        )
    return reader, pdf, page_count


def _encode_png(image: Image.Image, *, max_bytes: int) -> bytes:
    current = image.convert('RGB')
    encoded = b''
    for _ in range(5):
        output = io.BytesIO()
        current.save(output, format='PNG', optimize=True)
        encoded = output.getvalue()
        if len(encoded) <= max_bytes or min(current.size) <= 320:
            return encoded
        width, height = current.size
        current = current.resize(
            (max(320, int(width * 0.78)), max(320, int(height * 0.78))),
            Image.Resampling.LANCZOS,
        )
    return encoded


def _encode_thumbnail(image: Image.Image, *, width: int) -> bytes:
    thumbnail = image.convert('RGB')
    if thumbnail.width > width:
        height = max(1, round(thumbnail.height * width / thumbnail.width))
        thumbnail = thumbnail.resize((width, height), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    thumbnail.save(output, format='JPEG', quality=70, optimize=True)
    return output.getvalue()


def _native_text(reader, index: int) -> tuple[str, int]:
    try:
        text = (reader.pages[index].extract_text() or '').strip()
    except Exception:
        text = ''
    sample_chars = _setting_int(
        'EXAM_PREP_V4_NATIVE_TEXT_STORED_CHARS',
        4000,
        maximum=20_000,
    )
    return text[:sample_chars], len(text)


def _render_page(pdf, index: int, *, scale: float) -> Image.Image:
    try:
        return pdf[index].render(scale=scale).to_pil().convert('RGB')
    except Exception as exc:
        raise V4PdfSourceError(f'Unable to render PDF page {index + 1}.') from exc


def _is_complete(document: ExamSourceDocument, *, page_count: int) -> bool:
    if not document.source_file or document.page_count != page_count:
        return False
    pages = list(
        document.pages.order_by('page_number').values_list(
            'page_number', 'rendered_file', 'thumbnail_file', 'sha256'
        )
    )
    return (
        len(pages) == page_count
        and [row[0] for row in pages] == list(range(1, page_count + 1))
        and all(row[1] and row[2] and row[3] for row in pages)
    )


def _prepared_result(document: ExamSourceDocument, *, reused: bool) -> PreparedDocument:
    return PreparedDocument(
        document_id=document.id,
        source_sha256=document.source_sha256,
        page_count=document.page_count,
        pages=tuple(
            PreparedPage(
                page_number=page.page_number,
                sha256=page.sha256,
                rendered_name=page.rendered_file.name,
                thumbnail_name=page.thumbnail_file.name,
                width=page.width,
                height=page.height,
                native_text_length=page.native_text_length,
                duplicate_of_id=page.duplicate_of_id,
            )
            for page in document.pages.order_by('page_number')
        ),
        reused=reused,
    )


def _save_raw_source(
    *,
    document: ExamSourceDocument,
    source_path: Path,
    source_sha256: str,
) -> None:
    if document.source_file:
        return
    suffix = '.pdf'
    object_name = (
        f'{document.project_id}/{document.id}/'
        f'{source_sha256}{suffix}'
    )
    with source_path.open('rb') as handle:
        document.source_file.save(object_name, File(handle), save=False)


def _find_duplicate_page(
    *,
    document: ExamSourceDocument,
    page_sha256: str,
    current_page_number: int,
) -> ExamSourcePage | None:
    return (
        ExamSourcePage.objects.filter(
            document__project_id=document.project_id,
            sha256=page_sha256,
        )
        .exclude(document=document, page_number=current_page_number)
        .order_by('document_id', 'page_number', 'id')
        .first()
    )


def prepare_pdf_source_from_path(
    *,
    document_id: int,
    source_path: str | Path,
    original_name: str | None = None,
    mime_type: str = 'application/pdf',
) -> PreparedDocument:
    """Prepare one PDF serially and persist private source/page artifacts."""

    path = Path(source_path)
    byte_size = _validate_size(path)
    _validate_header(path)
    source_sha256 = _sha256_path(path)
    reader, pdf, page_count = _open_pdf(path)

    try:
        with transaction.atomic():
            document = (
                ExamSourceDocument.objects.select_for_update()
                .select_related('project')
                .get(id=document_id)
            )
            if document.classification_fingerprint:
                raise V4PdfSourceConflict(
                    'Accepted classification must be revised before replacing source pages.'
                )
            if document.source_sha256 and document.source_sha256 != source_sha256:
                raise V4PdfSourceConflict(
                    'This source document already belongs to different PDF bytes.'
                )
            if _is_complete(document, page_count=page_count):
                return _prepared_result(document, reused=True)

            document.status = ExamSourceDocument.Status.RENDERING
            document.source_sha256 = source_sha256
            document.byte_size = byte_size
            document.page_count = page_count
            document.mime_type = (mime_type or 'application/pdf').strip().lower()
            if original_name:
                document.original_name = str(original_name).strip()[:255]
            _save_raw_source(
                document=document,
                source_path=path,
                source_sha256=source_sha256,
            )
            document.save()

        render_dpi = _setting_int(
            'EXAM_PREP_V4_CLASSIFICATION_RENDER_DPI',
            110,
            minimum=72,
            maximum=180,
        )
        scale = render_dpi / 72.0
        max_page_bytes = _setting_int(
            'EXAM_PREP_V4_CLASSIFICATION_MAX_PAGE_IMAGE_MB',
            2,
            maximum=8,
        ) * 1024 * 1024
        thumbnail_width = _setting_int(
            'EXAM_PREP_V4_CLASSIFICATION_THUMBNAIL_WIDTH',
            320,
            minimum=160,
            maximum=640,
        )

        for index in range(page_count):
            page_number = index + 1
            image = _render_page(pdf, index, scale=scale)
            rendered = _encode_png(image, max_bytes=max_page_bytes)
            thumbnail = _encode_thumbnail(image, width=thumbnail_width)
            page_sha256 = hashlib.sha256(rendered).hexdigest()
            text_sample, text_length = _native_text(reader, index)

            with transaction.atomic():
                document = (
                    ExamSourceDocument.objects.select_for_update()
                    .select_related('project')
                    .get(id=document_id)
                )
                if document.source_sha256 != source_sha256:
                    raise V4PdfSourceConflict('Source changed while pages were rendering.')
                page, _created = ExamSourcePage.objects.select_for_update().get_or_create(
                    document=document,
                    page_number=page_number,
                )
                if page.sha256 == page_sha256 and page.rendered_file and page.thumbnail_file:
                    continue

                old_names = [
                    field.name
                    for field in (page.rendered_file, page.thumbnail_file)
                    if field and field.name
                ]
                page.rendered_file.save(
                    f'{document.project_id}/{document.id}/page-{page_number}-{page_sha256}.png',
                    File(io.BytesIO(rendered)),
                    save=False,
                )
                thumbnail_sha = hashlib.sha256(thumbnail).hexdigest()
                page.thumbnail_file.save(
                    f'{document.project_id}/{document.id}/page-{page_number}-{thumbnail_sha}.jpg',
                    File(io.BytesIO(thumbnail)),
                    save=False,
                )
                page.content_type = 'image/png'
                page.byte_size = len(rendered)
                page.width = image.width
                page.height = image.height
                page.sha256 = page_sha256
                page.native_text_sample = text_sample
                page.native_text_length = text_length
                page.duplicate_of = _find_duplicate_page(
                    document=document,
                    page_sha256=page_sha256,
                    current_page_number=page_number,
                )
                page.save()

                for old_name in old_names:
                    if old_name not in {
                        page.rendered_file.name,
                        page.thumbnail_file.name,
                    }:
                        transaction.on_commit(
                            lambda name=old_name, storage=page.rendered_file.storage: storage.delete(name)
                        )

        with transaction.atomic():
            document = ExamSourceDocument.objects.select_for_update().get(id=document_id)
            document.status = ExamSourceDocument.Status.UPLOADED
            document.error_code = ''
            document.error_detail = ''
            document.save(
                update_fields=['status', 'error_code', 'error_detail', 'updated_at']
            )
            return _prepared_result(document, reused=False)
    except Exception as exc:
        ExamSourceDocument.objects.filter(id=document_id).update(
            status=ExamSourceDocument.Status.FAILED,
            error_code=type(exc).__name__[:64],
            error_detail=str(exc)[:2000],
        )
        raise
    finally:
        pdf.close()


def prepare_pdf_source_from_bytes(
    *,
    document_id: int,
    data: bytes,
    original_name: str,
    mime_type: str = 'application/pdf',
) -> PreparedDocument:
    """Test/convenience wrapper; production upload paths should stay streamed."""

    if not data:
        raise V4PdfSourceError('Source PDF is empty.')
    with tempfile.NamedTemporaryFile(suffix='.pdf') as handle:
        handle.write(data)
        handle.flush()
        return prepare_pdf_source_from_path(
            document_id=document_id,
            source_path=handle.name,
            original_name=original_name,
            mime_type=mime_type,
        )


def load_classification_page_inputs(
    *,
    document_id: int,
) -> tuple[RenderedPageInput, ...]:
    """Load private thumbnails and native samples for the fast classifier."""

    document = ExamSourceDocument.objects.get(id=document_id)
    pages = list(document.pages.order_by('page_number'))
    if len(pages) != document.page_count:
        raise V4PdfSourceError('Source pages are incomplete.')

    inputs: list[RenderedPageInput] = []
    for expected, page in enumerate(pages, start=1):
        if page.page_number != expected or not page.thumbnail_file:
            raise V4PdfSourceError('Source page map is incomplete.')
        with page.thumbnail_file.open('rb') as handle:
            thumbnail = handle.read()
        inputs.append(
            RenderedPageInput(
                page_number=page.page_number,
                image=thumbnail,
                mime_type='image/jpeg',
                native_text_sample=page.native_text_sample,
            )
        )
    return tuple(inputs)
