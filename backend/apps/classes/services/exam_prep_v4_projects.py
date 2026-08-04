"""Project-boundary services for the source-aware Exam Prep engine.

Every uploaded PDF creates an independent exam project unless a future,
explicit grouping command is used. No classifier or extractor may infer
cross-document project membership.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.db import transaction

from apps.classes.models_v4 import ExamProject, ExamSourceDocument


class ExamPrepV4Disabled(RuntimeError):
    pass


class InvalidExamPrepV4Source(ValueError):
    pass


class ExamPrepV4IdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NewExamPdf:
    original_name: str
    mime_type: str = 'application/pdf'
    title: str = ''
    description: str = ''
    source_sha256: str = ''
    byte_size: int = 0
    page_count: int = 0
    client_request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    client_document_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def normalized_title(self) -> str:
        explicit = self.title.strip()
        if explicit:
            return explicit[:255]
        stem = Path(self.original_name.strip()).stem.strip()
        return (stem or 'آزمون جدید')[:255]


def exam_prep_v4_enabled() -> bool:
    """Return the rollout flag; enabled by default with explicit rollback support."""

    value = getattr(
        settings,
        'EXAM_PREP_V4_ENABLED',
        os.getenv('EXAM_PREP_V4_ENABLED', 'True'),
    )
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _validate_source(source: NewExamPdf) -> None:
    name = source.original_name.strip()
    content_type = source.mime_type.strip().lower()
    if not name:
        raise InvalidExamPrepV4Source('Source filename is required.')
    if content_type != 'application/pdf' and not name.lower().endswith('.pdf'):
        raise InvalidExamPrepV4Source('The exam-preparation engine currently accepts PDF sources only.')
    if source.byte_size < 0 or source.page_count < 0:
        raise InvalidExamPrepV4Source('Source sizes and page counts cannot be negative.')
    if source.source_sha256 and len(source.source_sha256) != 64:
        raise InvalidExamPrepV4Source('Source SHA-256 must contain 64 hexadecimal characters.')
    if source.source_sha256:
        try:
            int(source.source_sha256, 16)
        except ValueError as exc:
            raise InvalidExamPrepV4Source('Source SHA-256 is not hexadecimal.') from exc


def _existing_retry(
    *,
    teacher,
    source: NewExamPdf,
) -> ExamProject | None:
    project = (
        ExamProject.objects.select_for_update()
        .filter(
            teacher=teacher,
            client_request_id=source.client_request_id,
        )
        .first()
    )
    if project is None:
        return None

    document = project.source_documents.filter(
        client_document_id=source.client_document_id,
    ).first()
    if document is None:
        raise ExamPrepV4IdempotencyConflict(
            'The request id already belongs to another source document.'
        )
    if (
        document.original_name != source.original_name.strip()
        or document.mime_type != source.mime_type.strip().lower()
        or (
            source.source_sha256
            and document.source_sha256
            and document.source_sha256 != source.source_sha256.lower()
        )
    ):
        raise ExamPrepV4IdempotencyConflict(
            'The request id was retried with different source metadata.'
        )
    return project


@transaction.atomic
def create_independent_exam_projects(
    *,
    teacher,
    sources: Iterable[NewExamPdf],
    organization=None,
    study_group=None,
) -> list[ExamProject]:
    """Create one independent project for every supplied PDF.

    The whole operation is atomic and retry-safe. Supplying three PDFs creates
    three projects even when their page numbers, hashes, or layouts overlap.
    """

    if not exam_prep_v4_enabled():
        raise ExamPrepV4Disabled('The source-aware exam-preparation engine is disabled.')

    source_list = list(sources)
    if not source_list:
        raise InvalidExamPrepV4Source('At least one PDF source is required.')

    projects: list[ExamProject] = []
    for source in source_list:
        _validate_source(source)
        existing = _existing_retry(teacher=teacher, source=source)
        if existing is not None:
            projects.append(existing)
            continue

        project = ExamProject.objects.create(
            teacher=teacher,
            organization=organization,
            study_group=study_group,
            client_request_id=source.client_request_id,
            title=source.normalized_title(),
            description=source.description.strip(),
            status=ExamProject.Status.DRAFT,
            workflow_state={
                'stage': 'draft',
                'message': 'منبع آزمون آماده بارگذاری است.',
                'progressPercent': 0,
            },
        )
        ExamSourceDocument.objects.create(
            project=project,
            client_document_id=source.client_document_id,
            upload_order=0,
            original_name=source.original_name.strip(),
            mime_type=source.mime_type.strip().lower(),
            source_sha256=source.source_sha256.lower(),
            byte_size=source.byte_size,
            page_count=source.page_count,
            status=ExamSourceDocument.Status.PENDING_UPLOAD,
        )
        projects.append(project)

    return projects


def teacher_exam_projects(teacher):
    """Owner-scoped base queryset for teacher endpoints."""

    return ExamProject.objects.filter(teacher=teacher)
