"""Internal coordinator for the Exam Prep V4 source-preparation stage."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services.exam_prep_v4_classification import (
    ClassificationFingerprintConflict,
    StaleClassificationRevision,
)
from apps.classes.services.exam_prep_v4_fast_classifier import (
    FastClassifierResult,
    build_contact_sheets,
    classify_document_pages_fast,
)
from apps.classes.services.exam_prep_v4_pdf_source import (
    PreparedDocument,
    V4PdfSourceConflict,
    load_classification_page_inputs,
    prepare_pdf_source_from_path,
)
from apps.classes.services.exam_prep_v4_projects import (
    ExamPrepV4Disabled,
    exam_prep_v4_enabled,
)


_CONTROLLED_CONFLICTS = (
    V4PdfSourceConflict,
    ClassificationFingerprintConflict,
    StaleClassificationRevision,
)


@dataclass(frozen=True, slots=True)
class SourcePipelineResult:
    prepared: PreparedDocument
    classified: FastClassifierResult


def _mark_classifying(document_id: int) -> tuple[int, int]:
    with transaction.atomic():
        document = (
            ExamSourceDocument.objects.select_for_update()
            .select_related('project')
            .get(id=document_id)
        )
        project = ExamProject.objects.select_for_update().get(id=document.project_id)
        document.status = ExamSourceDocument.Status.CLASSIFYING
        document.error_code = ''
        document.error_detail = ''
        document.save(
            update_fields=['status', 'error_code', 'error_detail', 'updated_at']
        )
        project.status = ExamProject.Status.CLASSIFYING
        project.error_code = ''
        project.error_detail = ''
        project.workflow_state = {
            'stage': 'classifying',
            'message': 'ساختار صفحات در حال تشخیص است.',
            'progressPercent': 10,
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
        return project.id, document.classification_revision


def _active_revision_without_status_regression(document_id: int) -> int:
    document = ExamSourceDocument.objects.only(
        'classification_revision',
    ).get(id=document_id)
    return document.classification_revision


def _mark_failed(*, document_id: int, exc: Exception) -> None:
    error_code = type(exc).__name__[:64]
    error_detail = str(exc)[:2000]
    with transaction.atomic():
        document = (
            ExamSourceDocument.objects.select_for_update()
            .select_related('project')
            .filter(id=document_id)
            .first()
        )
        if document is None:
            return
        document.status = ExamSourceDocument.Status.FAILED
        document.error_code = error_code
        document.error_detail = error_detail
        document.save(
            update_fields=['status', 'error_code', 'error_detail', 'updated_at']
        )
        ExamProject.objects.filter(id=document.project_id).update(
            status=ExamProject.Status.FAILED,
            error_code=error_code,
            error_detail=error_detail,
            workflow_state={
                'stage': 'failed',
                'message': 'آماده‌سازی یا تشخیص ساختار PDF کامل نشد.',
                'progressPercent': 0,
            },
        )


def prepare_and_classify_pdf_source(
    *,
    document_id: int,
    source_path: str | Path,
    original_name: str | None = None,
    mime_type: str = 'application/pdf',
    model: str | None = None,
) -> SourcePipelineResult:
    """Prepare one PDF and produce persisted source-segment proposals."""

    if not exam_prep_v4_enabled():
        raise ExamPrepV4Disabled('Exam Prep V4 is not enabled.')

    try:
        prepared = prepare_pdf_source_from_path(
            document_id=document_id,
            source_path=source_path,
            original_name=original_name,
            mime_type=mime_type,
        )
        document = ExamSourceDocument.objects.only(
            'classification_fingerprint',
            'classification_revision',
        ).get(id=document_id)
        revision = (
            _active_revision_without_status_regression(document_id)
            if document.classification_fingerprint
            else _mark_classifying(document_id)[1]
        )
        page_inputs = load_classification_page_inputs(document_id=document_id)
        sheets = build_contact_sheets(page_inputs)
        native_text_samples = {
            page.page_number: page.native_text_sample
            for page in page_inputs
            if page.native_text_sample
        }
        classified = classify_document_pages_fast(
            document_id=document_id,
            expected_revision=revision,
            contact_sheets=sheets,
            native_text_samples=native_text_samples,
            model=model,
        )
        return SourcePipelineResult(prepared=prepared, classified=classified)
    except _CONTROLLED_CONFLICTS:
        # A stale retry or changed source/model must fail closed without turning
        # a valid stored source or reviewed result into a failed workflow.
        raise
    except Exception as exc:
        _mark_failed(document_id=document_id, exc=exc)
        raise
