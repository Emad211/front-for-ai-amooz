"""Fail-closed storage and metadata persistence for V4 PDF upload batches."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from django.conf import settings
from django.db import transaction

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services.exam_prep_v4_projects import (
    ExamPrepV4IdempotencyConflict,
    InvalidExamPrepV4Source,
    NewExamPdf,
    create_independent_exam_projects,
)
from core.storage_backends import delete_answer_source_file


@dataclass(frozen=True, slots=True)
class UploadMetadata:
    client_request_id: uuid.UUID
    client_document_id: uuid.UUID
    title: str = ''
    description: str = ''


@dataclass(frozen=True, slots=True)
class UploadedExamProject:
    project_id: int
    document_id: int
    client_request_id: uuid.UUID
    client_document_id: uuid.UUID
    title: str
    original_name: str
    source_sha256: str
    byte_size: int
    project_status: str
    document_status: str
    reused_source: bool
    classification_already_available: bool


@dataclass(frozen=True, slots=True)
class _InspectedUpload:
    upload: Any
    metadata: UploadMetadata
    original_name: str
    mime_type: str
    source_sha256: str
    byte_size: int


def _rewind(upload: Any) -> None:
    try:
        upload.seek(0)
    except (AttributeError, OSError) as exc:
        raise InvalidExamPrepV4Source('Uploaded PDF is not seekable.') from exc


def _inspect_upload(upload: Any, metadata: UploadMetadata) -> _InspectedUpload:
    original_name = str(getattr(upload, 'name', '') or '').strip()
    mime_type = str(getattr(upload, 'content_type', '') or '').strip().lower()
    if not original_name:
        raise InvalidExamPrepV4Source('Uploaded PDF filename is required.')
    if mime_type != 'application/pdf' and not original_name.lower().endswith('.pdf'):
        raise InvalidExamPrepV4Source('Exam Prep V4 currently accepts PDF files only.')

    max_bytes = int(getattr(settings, 'PDF_MAX_UPLOAD_BYTES', 100 * 1024 * 1024))
    digest = hashlib.sha256()
    total = 0
    header = b''
    _rewind(upload)
    try:
        for chunk in upload.chunks():
            if not chunk:
                continue
            if len(header) < 1024:
                header += bytes(chunk[: 1024 - len(header)])
            total += len(chunk)
            if total > max_bytes:
                raise InvalidExamPrepV4Source(
                    f'PDF exceeds the configured {max_bytes // (1024 * 1024)} MB limit.'
                )
            digest.update(chunk)
    finally:
        _rewind(upload)

    if total <= 0:
        raise InvalidExamPrepV4Source('Uploaded PDF is empty.')
    if b'%PDF' not in header:
        raise InvalidExamPrepV4Source('Uploaded file is not a valid PDF.')

    return _InspectedUpload(
        upload=upload,
        metadata=metadata,
        original_name=original_name,
        mime_type='application/pdf',
        source_sha256=digest.hexdigest(),
        byte_size=total,
    )


def _project_source_name(
    *,
    project_id: int,
    document_id: int,
    source_sha256: str,
) -> str:
    return f'{project_id}/{document_id}/{source_sha256}.pdf'


def _source_blob_exists(document: ExamSourceDocument) -> bool:
    if not document.source_file or not document.source_file.name:
        return False
    try:
        return document.source_file.storage.exists(document.source_file.name)
    except Exception:
        # Storage availability failures must fail the whole atomic intake rather
        # than silently treating an unknown blob state as reusable.
        raise


def _mark_queued(project: ExamProject, document: ExamSourceDocument) -> None:
    if document.classification_fingerprint:
        return
    if document.status not in {
        ExamSourceDocument.Status.PENDING_UPLOAD,
        ExamSourceDocument.Status.UPLOADED,
        ExamSourceDocument.Status.FAILED,
    }:
        return
    document.status = ExamSourceDocument.Status.UPLOADED
    document.error_code = ''
    document.error_detail = ''
    document.save(
        update_fields=['status', 'error_code', 'error_detail', 'updated_at']
    )
    project.status = ExamProject.Status.UPLOADING
    project.error_code = ''
    project.error_detail = ''
    project.workflow_state = {
        'stage': 'queued',
        'message': 'فایل دریافت شد و برای تشخیص ساختار در صف قرار گرفت.',
        'progressPercent': 5,
    }
    project.save(
        update_fields=[
            'status',
            'error_code',
            'error_detail',
            'workflow_state',
            'updated_at',
        ]
    )


def persist_uploaded_pdf_batch(
    *,
    teacher,
    uploads: Iterable[Any],
    metadata: Iterable[UploadMetadata],
    organization=None,
    study_group=None,
) -> tuple[UploadedExamProject, ...]:
    """Persist a validated batch while keeping every PDF in its own project."""

    upload_list = list(uploads)
    metadata_list = list(metadata)
    if not upload_list:
        raise InvalidExamPrepV4Source('At least one PDF is required.')
    if len(upload_list) != len(metadata_list):
        raise InvalidExamPrepV4Source(
            'Upload metadata count must match the number of PDF files.'
        )

    inspected = [
        _inspect_upload(upload, item_metadata)
        for upload, item_metadata in zip(upload_list, metadata_list, strict=True)
    ]
    request_ids = [item.metadata.client_request_id for item in inspected]
    if len(request_ids) != len(set(request_ids)):
        raise InvalidExamPrepV4Source(
            'Each PDF in one batch requires a distinct client request id.'
        )
    document_ids = [item.metadata.client_document_id for item in inspected]
    if len(document_ids) != len(set(document_ids)):
        raise InvalidExamPrepV4Source(
            'Each PDF in one batch requires a distinct client document id.'
        )

    sources = [
        NewExamPdf(
            original_name=item.original_name,
            mime_type=item.mime_type,
            title=item.metadata.title,
            description=item.metadata.description,
            source_sha256=item.source_sha256,
            byte_size=item.byte_size,
            page_count=0,
            client_request_id=item.metadata.client_request_id,
            client_document_id=item.metadata.client_document_id,
        )
        for item in inspected
    ]

    saved_names: list[str] = []
    try:
        with transaction.atomic():
            projects = create_independent_exam_projects(
                teacher=teacher,
                sources=sources,
                organization=organization,
                study_group=study_group,
            )
            results: list[UploadedExamProject] = []
            for item, project in zip(inspected, projects, strict=True):
                document = (
                    ExamSourceDocument.objects.select_for_update()
                    .get(
                        project=project,
                        client_document_id=item.metadata.client_document_id,
                    )
                )
                if document.source_sha256 and document.source_sha256 != item.source_sha256:
                    raise ExamPrepV4IdempotencyConflict(
                        'The upload retry contains different PDF bytes.'
                    )

                reused_source = _source_blob_exists(document)
                if not reused_source:
                    _rewind(item.upload)
                    document.source_file.save(
                        _project_source_name(
                            project_id=project.id,
                            document_id=document.id,
                            source_sha256=item.source_sha256,
                        ),
                        item.upload,
                        save=False,
                    )
                    saved_names.append(document.source_file.name)

                document.source_sha256 = item.source_sha256
                document.byte_size = item.byte_size
                document.original_name = item.original_name
                document.mime_type = item.mime_type
                if not reused_source:
                    document.status = ExamSourceDocument.Status.UPLOADED
                document.save()
                _mark_queued(project, document)

                results.append(
                    UploadedExamProject(
                        project_id=project.id,
                        document_id=document.id,
                        client_request_id=item.metadata.client_request_id,
                        client_document_id=item.metadata.client_document_id,
                        title=project.title,
                        original_name=document.original_name,
                        source_sha256=document.source_sha256,
                        byte_size=document.byte_size,
                        project_status=project.status,
                        document_status=document.status,
                        reused_source=reused_source,
                        classification_already_available=bool(
                            document.classification_fingerprint
                        ),
                    )
                )
            return tuple(results)
    except Exception:
        for name in saved_names:
            delete_answer_source_file(name)
        raise
