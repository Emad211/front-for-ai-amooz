"""Celery task for the production Mistral OCR exam-preparation pipeline."""
from __future__ import annotations

import json
import logging
import os
from time import monotonic
from typing import Any

from celery import shared_task
from django.db import transaction

from apps.chatbot.services.llm_client import is_transient_llm_error
from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_mistral_artifacts import (
    cleanup_session_private_artifacts,
    session_artifact_namespace,
)
from apps.classes.services.exam_prep_mistral_production import (
    PRODUCTION_ENGINE,
    run_exam_prep_mistral_pipeline,
)
from apps.classes.services.exam_prep_pipeline import ExamPrepPipelineCancelled
from apps.classes.services.exam_prep_mistral_stage5_runtime import stage5_task_deadline
from apps.commons.token_tracker import set_current_session_id, set_current_user


logger = logging.getLogger('apps.classes.exam_prep')
PIPELINE_ENGINE = PRODUCTION_ENGINE
TASK_SOFT_LIMIT = int(os.getenv('EXAM_PREP_TASK_SOFT_LIMIT_SECONDS', '3300'))
TASK_HARD_LIMIT = int(os.getenv('EXAM_PREP_TASK_HARD_LIMIT_SECONDS', '3600'))
TASK_MAX_RETRIES = int(os.getenv('EXAM_PREP_TASK_MAX_RETRIES', '2'))
TASK_FINALIZE_SAFETY_SECONDS = int(
    os.getenv('EXAM_PREP_TASK_FINALIZE_SAFETY_SECONDS', '300')
)

# Progress-bar bands (percent). The bar must track wall-clock share, not page
# count. OCR (Stage 1) is the fast phase — it finishes every page in the first
# ~2 of a ~8 minute run, so it may only fill the low "reading source" band; if
# it owned 20..90% it would read as ~90% two minutes in while the real work had
# not started. The per-question Stage-5 source re-read is the long tail (~6 of
# the ~8 minutes) and carries the bar up through the "extracting questions"
# band. The short deterministic Stages 2-4 fall in the seam at the OCR ceiling.
OCR_PROGRESS_FLOOR = 15
OCR_PROGRESS_CEILING = 40
STAGE5_PROGRESS_FLOOR = 40
STAGE5_PROGRESS_CEILING = 95


def _stage5_deadline_at(task_started_at: float) -> float:
    task_limit = min(TASK_SOFT_LIMIT, TASK_HARD_LIMIT)
    usable_seconds = max(0, task_limit - max(0, TASK_FINALIZE_SAFETY_SECONDS))
    return task_started_at + usable_seconds


def _band_progress(completed: int, total: int, *, floor: int, ceiling: int) -> int:
    """Map ``completed/total`` into the ``[floor, ceiling]`` percent band.

    Pure and provider-free so the progress mapping can be unit-tested without a
    live pipeline run. Clamps the fraction to ``[0, 1]`` so a caller can never
    push the bar past the band ceiling (e.g. OCR completion must not read 90%).
    """
    safe_total = max(1, int(total))
    fraction = min(1.0, max(0, int(completed)) / safe_total)
    return floor + int(fraction * (ceiling - floor))


def _workflow_state(
    stage: str,
    *,
    message: str,
    progress: int,
    warnings: list[str] | None = None,
    ready: bool = False,
    failed_page_numbers: list[int] | None = None,
    extraction_audit: dict[str, Any] | None = None,
    publication_blocked: bool = False,
) -> dict:
    return {
        'engine': PIPELINE_ENGINE,
        'stage': stage,
        'message': message,
        'progressPercent': max(0, min(100, int(progress))),
        'warnings': list(warnings or [])[:8],
        'readyForReview': bool(ready),
        'pendingExercises': [],
        'failedPageNumbers': sorted(
            {int(value) for value in (failed_page_numbers or []) if int(value) > 0}
        ),
        'extractionAudit': dict(extraction_audit or {}),
        'publicationBlocked': bool(publication_blocked),
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


def _session_cancel_requested(session_id: int) -> bool:
    """A deleted session is also terminal; never keep spending after deletion."""

    return not ClassCreationSession.objects.filter(
        id=session_id,
        cancel_requested=False,
    ).exists()


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

    task_started_at = monotonic()
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
        cleanup_session_private_artifacts(
            session.id,
            include_visuals=False,
            include_checkpoints=True,
        )
        return {'status': 'reused', 'session_id': session.id}
    if session.status != ClassCreationSession.Status.EXAM_TRANSCRIBING:
        if session.status in {
            ClassCreationSession.Status.CANCELLED,
            ClassCreationSession.Status.FAILED,
        }:
            cleanup_session_private_artifacts(
                session.id,
                include_visuals=True,
                include_checkpoints=True,
            )
        return {'status': 'skipped', 'reason': f'status:{session.status}'}
    if session.cancel_requested:
        cleanup_session_private_artifacts(
            session.id,
            include_visuals=True,
            include_checkpoints=True,
        )
        _mark_cancelled(session.id)
        return {'status': 'cancelled', 'session_id': session.id}
    if session.source_type != ClassCreationSession.SourceType.PDF or not session.source_file:
        detail = 'A valid PDF source file is required.'
        cleanup_session_private_artifacts(
            session.id,
            include_visuals=True,
            include_checkpoints=True,
        )
        _mark_failed(session.id, detail)
        raise RuntimeError(detail)

    set_current_user(session.teacher)
    set_current_session_id(session.id)
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
            return _session_cancel_requested(session.id)

        def on_page_complete(completed: int, total: int) -> None:
            # OCR is the fast phase: keep it inside the low "reading source"
            # band so finishing all pages (~2 min in) never reads as near-done.
            progress = _band_progress(
                completed,
                total,
                floor=OCR_PROGRESS_FLOOR,
                ceiling=OCR_PROGRESS_CEILING,
            )
            ClassCreationSession.objects.filter(
                id=session.id,
                cancel_requested=False,
                status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
            ).update(
                workflow_state=_workflow_state(
                    'reading_source',
                    message=f'صفحه {completed} از {total} خوانده شد.',
                    progress=progress,
                )
            )

        def on_region_complete(completed: int, total: int) -> None:
            # Stage-5 per-question source re-read is the long tail (~6 min); it
            # carries the bar through the "extracting questions" band so the UI
            # keeps advancing during the phase that actually dominates runtime.
            progress = _band_progress(
                completed,
                total,
                floor=STAGE5_PROGRESS_FLOOR,
                ceiling=STAGE5_PROGRESS_CEILING,
            )
            ClassCreationSession.objects.filter(
                id=session.id,
                cancel_requested=False,
                status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
            ).update(
                workflow_state=_workflow_state(
                    'extracting_questions',
                    message=f'تحلیل سؤال {completed} از {total}.',
                    progress=progress,
                )
            )

        with stage5_task_deadline(_stage5_deadline_at(task_started_at)):
            result = run_exam_prep_mistral_pipeline(
                data=data,
                title=session.title,
                scope_hint='default',
                on_page_complete=on_page_complete,
                on_region_complete=on_region_complete,
                should_cancel=should_cancel,
                asset_namespace=session_artifact_namespace(session.id),
            )
        if should_cancel():
            raise ExamPrepPipelineCancelled('Cancellation requested after extraction.')

        warnings: list[str] = []
        if result.questions_needing_review:
            warnings.append(
                f'{result.questions_needing_review} سؤال نیازمند بازبینی است.'
            )
        if result.failed_page_numbers:
            page_list = '، '.join(str(value) for value in result.failed_page_numbers[:12])
            suffix = ' و چند صفحهٔ دیگر' if len(result.failed_page_numbers) > 12 else ''
            warnings.append(
                f'استخراج صفحه‌های {page_list}{suffix} کامل نشد؛ انتشار مسدود است.'
            )
        if result.question_number_gaps:
            gap_count = sum(len(values) for values in result.question_number_gaps.values())
            warnings.append(
                f'{gap_count} شماره سؤال در توالی سؤال‌های استخراج‌شده وجود ندارد.'
            )
        if result.orphan_answer_count:
            warnings.append(
                f'{result.orphan_answer_count} پاسخ بدون صورت سؤال کنار گذاشته شد و سؤال جدید نساخت.'
            )

        publishable = bool(result.publication_ready)
        final_status = (
            ClassCreationSession.Status.EXAM_STRUCTURED
            if publishable
            else ClassCreationSession.Status.EXAM_TRANSCRIBED
        )
        final_message = (
            'سؤال‌ها و پاسخ‌ها آمادهٔ بازبینی و انتشار هستند.'
            if publishable
            else 'استخراج انجام شد، اما تا رفع موارد بحرانی قابل انتشار نیست.'
        )

        with transaction.atomic():
            locked = (
                ClassCreationSession.objects.select_for_update()
                .filter(id=session.id)
                .first()
            )
            if locked is None:
                cleanup_session_private_artifacts(
                    session.id,
                    include_visuals=True,
                    include_checkpoints=True,
                )
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
                cleanup_session_private_artifacts(
                    session.id,
                    include_visuals=True,
                    include_checkpoints=True,
                )
                return {'status': 'cancelled', 'session_id': locked.id}

            locked.exam_prep_json = json.dumps(
                result.projection,
                ensure_ascii=False,
            )
            locked.transcript_markdown = result.transcript_markdown
            locked.source_page_count = result.page_count
            locked.llm_model = result.model
            locked.status = final_status
            locked.celery_task_id = ''
            locked.error_detail = ''
            locked.workflow_state = _workflow_state(
                'ready_for_review',
                message=final_message,
                progress=100,
                warnings=warnings,
                ready=True,
                failed_page_numbers=result.failed_page_numbers,
                extraction_audit=result.extraction_audit,
                publication_blocked=not publishable,
            )
            locked.save(
                update_fields=[
                    'exam_prep_json',
                    'transcript_markdown',
                    'source_page_count',
                    'llm_model',
                    'status',
                    'celery_task_id',
                    'error_detail',
                    'workflow_state',
                    'updated_at',
                ]
            )

        if not cleanup_session_private_artifacts(
            session.id,
            include_visuals=False,
            include_checkpoints=True,
        ):
            logger.warning(
                'exam_prep.pipeline.checkpoint_cleanup_pending sessionId=%s',
                session.id,
            )

        logger.info(
            'exam_prep.pipeline.completed sessionId=%s pageCount=%s questionCount=%s matchedAnswerCount=%s orphanAnswerCount=%s reviewCount=%s criticalIssueCount=%s failedPageCount=%s publicationReady=%s',
            session.id,
            result.page_count,
            result.question_count,
            result.matched_answer_count,
            result.orphan_answer_count,
            result.questions_needing_review,
            int(result.extraction_audit.get('criticalIssueCount') or 0),
            len(result.failed_page_numbers),
            publishable,
        )
        return {
            'status': 'ready_for_review',
            'session_id': session.id,
            'page_count': result.page_count,
            'question_count': result.question_count,
            'matched_answer_count': result.matched_answer_count,
            'orphan_answer_count': result.orphan_answer_count,
            'questions_needing_review': result.questions_needing_review,
            'failed_page_numbers': result.failed_page_numbers,
            'publication_ready': publishable,
        }
    except ExamPrepPipelineCancelled:
        cleanup_session_private_artifacts(
            session.id,
            include_visuals=True,
            include_checkpoints=True,
        )
        _mark_cancelled(session.id)
        logger.info('exam_prep.pipeline.cancelled sessionId=%s', session.id)
        return {'status': 'cancelled', 'session_id': session.id}
    except Exception as exc:
        if is_transient_llm_error(exc) and self.request.retries < self.max_retries:
            countdown = min(300, 45 * (2 ** int(self.request.retries or 0)))
            ClassCreationSession.objects.filter(id=session.id).update(
                workflow_state=_workflow_state(
                    'reading_source',
                    message='خطای موقت رخ داد؛ پردازش دوباره تلاش می‌شود.',
                    progress=OCR_PROGRESS_FLOOR,
                )
            )
            logger.warning(
                'exam_prep.pipeline.retry sessionId=%s countdown=%s errorCode=%s',
                session.id,
                countdown,
                type(exc).__name__,
            )
            raise self.retry(exc=exc, countdown=countdown)

        cleanup_session_private_artifacts(
            session.id,
            include_visuals=True,
            include_checkpoints=True,
        )
        _mark_failed(session.id, str(exc))
        logger.exception(
            'exam_prep.pipeline.failed sessionId=%s errorCode=%s',
            session.id,
            type(exc).__name__,
        )
        raise
