"""Celery tasks for Exam Prep V4.

Every source document is dispatched independently. A batch upload never becomes
one extraction task and no task can inspect another exam project's records.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import Iterable

from celery import group, shared_task
from django.core.cache import cache

from apps.chatbot.services.llm_client import is_transient_llm_error
from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services.exam_prep_v4_source_pipeline import (
    prepare_and_classify_pdf_source,
)
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled


TASK_SOFT_LIMIT = int(os.getenv('EXAM_PREP_V4_TASK_SOFT_LIMIT_SECONDS', '3300'))
TASK_HARD_LIMIT = int(os.getenv('EXAM_PREP_V4_TASK_HARD_LIMIT_SECONDS', '3600'))


def _mark_source_file_missing(document: ExamSourceDocument) -> None:
    document.status = ExamSourceDocument.Status.FAILED
    document.error_code = 'source_file_missing'
    document.error_detail = 'Private source file is missing.'
    document.save(
        update_fields=['status', 'error_code', 'error_detail', 'updated_at']
    )
    ExamProject.objects.filter(id=document.project_id).update(
        status=ExamProject.Status.FAILED,
        error_code='source_file_missing',
        error_detail='Private source file is missing.',
        workflow_state={
            'stage': 'failed',
            'message': 'فایل خصوصی منبع در دسترس نیست؛ فایل را دوباره بارگذاری کنید.',
            'progressPercent': 0,
        },
    )


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=TASK_SOFT_LIMIT,
    time_limit=TASK_HARD_LIMIT,
    queue='pipeline',
)
def process_exam_prep_v4_source(self, document_id: int) -> dict:
    """Prepare and classify one private source document."""

    if not exam_prep_v4_enabled():
        return {
            'status': 'skipped',
            'document_id': document_id,
            'reason': 'v4_disabled',
        }

    lock_key = f'exam-prep-v4-source:{document_id}'
    if not cache.add(lock_key, '1', timeout=TASK_HARD_LIMIT + 300):
        return {
            'status': 'skipped',
            'document_id': document_id,
            'reason': 'already_processing',
        }

    try:
        document = (
            ExamSourceDocument.objects.select_related('project')
            .filter(id=document_id)
            .first()
        )
        if document is None:
            return {
                'status': 'skipped',
                'document_id': document_id,
                'reason': 'document_not_found',
            }
        if not document.source_file:
            _mark_source_file_missing(document)
            return {
                'status': 'failed',
                'document_id': document_id,
                'reason': 'source_file_missing',
            }

        with tempfile.NamedTemporaryFile(suffix='.pdf') as handle:
            with document.source_file.open('rb') as source:
                shutil.copyfileobj(source, handle, length=1024 * 1024)
            handle.flush()
            result = prepare_and_classify_pdf_source(
                document_id=document.id,
                source_path=handle.name,
                original_name=document.original_name,
                mime_type=document.mime_type,
            )
        return {
            'status': 'ready_for_source_confirmation',
            'project_id': document.project_id,
            'document_id': document.id,
            'page_count': result.prepared.page_count,
            'segment_count': len(result.classified.classification.segments),
            'issue_count': len(result.classified.classification.issues),
            'reused_source': result.prepared.reused,
            'reused_classification': result.classified.classification.reused,
        }
    except Exception as exc:
        if is_transient_llm_error(exc) and self.request.retries < self.max_retries:
            countdown = min(300, 30 * (2 ** self.request.retries))
            raise self.retry(exc=exc, countdown=countdown)
        return {
            'status': 'failed',
            'document_id': document_id,
            'reason': str(exc)[:500],
            'error_code': type(exc).__name__,
        }
    finally:
        cache.delete(lock_key)


def dispatch_exam_prep_v4_sources(document_ids: Iterable[int]) -> str:
    """Publish one pipeline task per document in a single Celery group."""

    ids = [int(document_id) for document_id in document_ids]
    if not ids:
        raise ValueError('At least one document id is required for dispatch.')
    result = group(
        process_exam_prep_v4_source.s(document_id)
        for document_id in ids
    ).apply_async()
    return str(result.id)
