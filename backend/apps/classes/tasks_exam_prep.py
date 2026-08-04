"""Celery task for the non-versioned exam-preparation PDF pipeline."""
from __future__ import annotations

import json
import logging
import os

from celery import shared_task
from django.db import transaction

from apps.chatbot.services.llm_client import is_transient_llm_error
from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_pipeline import (
    ExamPrepPipelineCancelled,
    run_exam_prep_pdf_pipeline,
)
from apps.commons.token_tracker import set_current_user


logger = logging.getLogger('apps.classes.exam_prep')
PAGE_FIRST_ENGINE = 'page_first'
TASK_SOFT_LIMIT = int(os.getenv('EXAM_PREP_TASK_SOFT_LIMIT_SECONDS', '3300'))
TASK_HARD_LIMIT = int(os.getenv('EXAM_PREP_TASK_HARD_LIMIT_SECONDS', '3600'))
TASK_MAX_RETRIES = int(os.getenv('EXAM_PREP_TASK_MAX_RETRIES', '2'))


def _workflow_state(
    stage: str,
    *,
    message: str,
    progress: int,
    warnings: list[str] | None = None,
    ready: bool = False,
    failed_page_numbers: list[int] | None = None,
) -> dict:
    return {
        'engine': PAGE_FIRST_ENGINE,
        'stage': stage,
        'message': message,
        'progressPercent': max(0, min(100, int(progress))),
        'warnings': list(warnings or [])[:6],
        'readyForReview': bool(ready),
        'pendingExercises': [],
        'failedPageNumbers': sorted({int(value) for value in (failed_page_numbers or []) if int(value) > 0}),
    }


def _mark_cancelled(session_id: int) -> None:
    ClassCreationSession.objects.filter(id=session_id).update(
        status=ClassCreationSession.Status.CANCELLED,
        cancel_requested=True,
        celery_task_id='',
        error_detail='',
        workflow_state=_workflow_state(
            'cancelled',
            message='پردازش توسط شما متوقف شد.',
            progress=0,
        ),
    )


def _mark_failed(session_id: int, detail: str) -> None:
    ClassCreationSession.objects.filter(id=session_id).update(
        status=ClassCreationSession.Status.FAILED,
        celery_task_id='',
        error_detail=str(detail)[:2000],
        workflow_state=_workflow_state(
            'failed',
            message='پردازش PDF کامل نشد. دوباره تلاش کنید.',
            progress=0,
        ),
    )


@shared_task(
    bind=True,
    max_retries=TASK_MAX_RETRIES,
    default_retry_delay=45,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=TASK_SOFT_LIMIT,
    time_limit=TASK_HARD_LIMIT,
    queue='pipeline',
)
def process_exam_prep_pdf_session(self, session_id: int) -> dict:
    """Write one PDF directly into the existing ``exam_prep_json`` field."""

    session = (
        ClassCreationSession.objects.select_related('teacher')
        .filter(id=session_id)
        .first()
    )
    if session is None:
        return {'status': 'skipped', 'reason': 'session_not_found'}
    if session.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP:
        return {'status': 'skipped', 'reason': 'not_exam_prep'}
    if session.status == ClassCreationSession.Status.EXAM_STRUCTURED:
        return {'status': 'reused', 'session_id': session.id}
    if session.status != ClassCreationSession.Status.EXAM_TRANSCRIBING:
        return {'status': 'skipped', 'reason': f'status:{session.status}'}
    if session.cancel_requested:
        _mark_cancelled(session.id)
        return {'status': 'cancelled', 'session_id': session.id}
    if session.source_type != ClassCreationSession.SourceType.PDF or not session.source_file:
        detail = 'A valid PDF source file is required.'
        _mark_failed(session.id, detail)
        raise RuntimeError(detail)

    set_current_user(session.teacher)
    logger.info(
        'exam_prep.pipeline.started sessionId=%s taskId=%s attempt=%s',
        session.id,
        str(self.request.id or ''),
        int(self.request.retries or 0) + 1,
    )

    try:
        ClassCreationSession.objects.filter(id=session.id).update(
            workflow_state=_workflow_state(
                'reading_source',
                message='PDF دریافت شد و صفحات آن در حال آماده‌سازی است.',
                progress=15,
            ),
            error_detail='',
        )
        session.source_file.open('rb')
        try:
            data = session.source_file.read()
        finally:
            session.source_file.close()

        def should_cancel() -> bool:
            return ClassCreationSession.objects.filter(
                id=session.id,
                cancel_requested=True,
            ).exists()

        def on_page_complete(completed: int, total: int) -> None:
            progress = 20 + int((completed / max(1, total)) * 70)
            ClassCreationSession.objects.filter(
                id=session.id,
                cancel_requested=False,
                status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
            ).update(
                workflow_state=_workflow_state(
                    'extracting_questions',
                    message=f'صفحه {completed} از {total} پردازش شد.',
                    progress=progress,
                )
            )

        result = run_exam_prep_pdf_pipeline(
            data=data,
            title=session.title,
            scope_hint='default',
            on_page_complete=on_page_complete,
            should_cancel=should_cancel,
        )
        if should_cancel():
            raise ExamPrepPipelineCancelled('Cancellation requested after extraction.')

        warnings = []
        if result.questions_needing_review:
            warnings.append(
                f'{result.questions_needing_review} سؤال نیازمند بازبینی است.'
            )
        if result.failed_page_numbers:
            page_list = '، '.join(str(value) for value in result.failed_page_numbers[:12])
            suffix = ' و چند صفحهٔ دیگر' if len(result.failed_page_numbers) > 12 else ''
            warnings.append(
                f'استخراج صفحه‌های {page_list}{suffix} کامل نشد؛ محتوای نهایی را بازبینی کنید.'
            )

        with transaction.atomic():
            locked = (
                ClassCreationSession.objects.select_for_update()
                .filter(id=session.id)
                .first()
            )
            if locked is None:
                return {'status': 'skipped', 'reason': 'session_deleted'}
            if locked.cancel_requested:
                locked.status = ClassCreationSession.Status.CANCELLED
                locked.celery_task_id = ''
                locked.error_detail = ''
                locked.workflow_state = _workflow_state(
                    'cancelled',
                    message='پردازش توسط شما متوقف شد.',
                    progress=0,
                )
                locked.save(
                    update_fields=[
                        'status',
                        'celery_task_id',
                        'error_detail',
                        'workflow_state',
                        'updated_at',
                    ]
                )
                return {'status': 'cancelled', 'session_id': locked.id}

            locked.exam_prep_json = json.dumps(
                result.projection,
                ensure_ascii=False,
            )
            locked.source_page_count = result.page_count
            locked.llm_model = result.model
            locked.status = ClassCreationSession.Status.EXAM_STRUCTURED
            locked.celery_task_id = ''
            locked.error_detail = ''
            locked.workflow_state = _workflow_state(
                'ready_for_review',
                message='سؤال‌ها و پاسخ‌ها آمادهٔ بازبینی هستند.',
                progress=100,
                warnings=warnings,
                ready=True,
                failed_page_numbers=result.failed_page_numbers,
            )
            locked.save(
                update_fields=[
                    'exam_prep_json',
                    'source_page_count',
                    'llm_model',
                    'status',
                    'celery_task_id',
                    'error_detail',
                    'workflow_state',
                    'updated_at',
                ]
            )

        logger.info(
            'exam_prep.pipeline.completed sessionId=%s pageCount=%s questionCount=%s reviewCount=%s failedPageCount=%s',
            session.id,
            result.page_count,
            result.question_count,
            result.questions_needing_review,
            len(result.failed_page_numbers),
        )
        return {
            'status': 'ready_for_review',
            'session_id': session.id,
            'page_count': result.page_count,
            'question_count': result.question_count,
            'questions_needing_review': result.questions_needing_review,
            'failed_page_numbers': result.failed_page_numbers,
        }
    except ExamPrepPipelineCancelled:
        _mark_cancelled(session.id)
        logger.info('exam_prep.pipeline.cancelled sessionId=%s', session.id)
        return {'status': 'cancelled', 'session_id': session.id}
    except Exception as exc:
        if is_transient_llm_error(exc) and self.request.retries < self.max_retries:
            countdown = min(300, 45 * (2 ** int(self.request.retries or 0)))
            ClassCreationSession.objects.filter(id=session.id).update(
                workflow_state=_workflow_state(
                    'extracting_questions',
                    message='خطای موقت رخ داد؛ پردازش دوباره تلاش می‌شود.',
                    progress=20,
                )
            )
            logger.warning(
                'exam_prep.pipeline.retry sessionId=%s countdown=%s errorCode=%s',
                session.id,
                countdown,
                type(exc).__name__,
            )
            raise self.retry(exc=exc, countdown=countdown)

        _mark_failed(session.id, str(exc))
        logger.exception(
            'exam_prep.pipeline.failed sessionId=%s errorCode=%s',
            session.id,
            type(exc).__name__,
        )
        raise
