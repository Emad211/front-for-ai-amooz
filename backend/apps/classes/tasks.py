"""Celery tasks for the classes app.

Every function that used to run inside ``run_in_background`` (daemon thread)
is now a proper Celery task so it survives worker restarts, can be monitored,
and does **not** block the Gunicorn sync worker.

Design principles
-----------------
* Media files are stored in S3-compatible object storage (MinIO in
  production).  Django's ``FileField`` reads/writes through ``boto3``,
  so **every pod** (Gunicorn, Celery worker) can access the same files
  without sharing a filesystem volume.
* Each task streams file data to a local temp file before processing so
  RAM stays low even for 500 MB uploads.
* Retry with exponential back-off (max 3 retries, delay starts at 60 s).
* ``time_limit`` / ``soft_time_limit`` inherited from settings by default;
  individual tasks can override if needed.
* Full-pipeline tasks run steps **inline** with their own retry logic.
  Celery's ``self.retry()`` raises ``Retry``; the pipeline catches this
  and retries locally with exponential back-off instead.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from celery.exceptions import Retry as CeleryRetry
from billiard.exceptions import SoftTimeLimitExceeded
from django.core.files.base import File
from django.utils import timezone

from apps.chatbot.services.llm_client import is_transient_llm_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time budget for the heavy pipeline tasks.
#
# The global settings limits (hard 2 h / soft 100 min) are sized for ordinary
# tasks. Chunked transcription deliberately ACCEPTS media up to
# TRANSCRIPTION_MAX_DURATION_SECONDS (default 4 h of *content*), and the
# full-pipeline tasks additionally run steps 2-5 inline — so the four
# media-ingesting tasks get their own, larger envelope. Keep these >= the
# worst case implied by the duration cap, or long lectures get SIGKILLed
# mid-run.
# ---------------------------------------------------------------------------
PIPELINE_TASK_SOFT_TIME_LIMIT = int(os.getenv('PIPELINE_TASK_SOFT_TIME_LIMIT', str(int(3.5 * 3600))))
PIPELINE_TASK_TIME_LIMIT = int(os.getenv('PIPELINE_TASK_TIME_LIMIT', str(4 * 3600)))

_PIPELINE_TIMEOUT_FA = (
    'پردازش از سقف زمانی مجاز فراتر رفت. لطفاً فایل را به جلسات کوتاه‌تر تقسیم کنید و دوباره تلاش کنید.'
)


def _current_task_id(task) -> str:
    return getattr(getattr(task, 'request', None), 'id', '') or ''


def _retry_countdown(task, *, base: int = 60, cap: int = 5 * 60) -> int:
    retries = getattr(getattr(task, 'request', None), 'retries', 0) or 0
    return min(base * (2 ** int(retries)), cap)


def _exercise_extract_cancelled(exercise) -> bool:
    """Cooperative cancellation checkpoint for exercise extraction.

    Re-delivered / retried tasks must stop as soon as the teacher has cancelled
    the current extraction, even if the original worker child ignored or missed
    the hard revoke.
    """
    exercise.refresh_from_db(fields=['status', 'cancel_requested', 'workflow_state', 'updated_at'])
    if not getattr(exercise, 'cancel_requested', False) and exercise.status != exercise.Status.CANCELLED:
        return False

    from .services.exercise_workflow import build_workflow_state

    exercise.status = exercise.Status.CANCELLED
    exercise.workflow_state = build_workflow_state(
        'cancelled',
        message='استخراج تمرین توسط شما متوقف شد.',
        ready_for_review=False,
    )
    exercise.save(update_fields=['status', 'workflow_state', 'updated_at'])
    return True


def _session_workflow_stage_for_status(status_value: str) -> str:
    mapping = {
        'transcribing': 'transcribing',
        'transcribed': 'transcribing',
        'structuring': 'structuring',
        'structured': 'structuring',
        'prereq_extracting': 'extracting_prerequisites',
        'prereq_extracted': 'extracting_prerequisites',
        'prereq_teaching': 'teaching_prerequisites',
        'prereq_taught': 'teaching_prerequisites',
        'recapping': 'building_recap',
        'recapped': 'ready_for_review',
        'exam_transcribing': 'transcribing',
        'exam_transcribed': 'transcribing',
        'exam_structuring': 'extracting_questions',
        'exam_structured': 'ready_for_review',
        'failed': 'failed',
        'cancelled': 'cancelled',
    }
    return mapping.get(status_value, 'queued')


def _sync_session_workflow_to_status(session, *, message: str | None = None, warnings: list[str] | None = None) -> None:
    from .services.session_workflow import build_session_workflow_state

    current = getattr(session, 'workflow_state', None)
    pending = []
    if isinstance(current, dict) and isinstance(current.get('pendingExercises'), list):
        pending = current.get('pendingExercises') or []
    session.workflow_state = build_session_workflow_state(
        _session_workflow_stage_for_status(session.status),
        message=message,
        warnings=warnings,
        ready_for_review=session.status in {'recapped', 'exam_structured'},
        pending_exercises=pending,
    )


def _session_cancelled(session) -> bool:
    from .services.session_workflow import build_session_workflow_state

    session.refresh_from_db(fields=['status', 'cancel_requested', 'workflow_state', 'pending_exercises', 'updated_at'])
    if not getattr(session, 'cancel_requested', False) and session.status != session.Status.CANCELLED:
        return False
    pending = []
    current = getattr(session, 'workflow_state', None)
    if isinstance(current, dict) and isinstance(current.get('pendingExercises'), list):
        pending = current.get('pendingExercises') or []
    session.status = session.Status.CANCELLED
    session.workflow_state = build_session_workflow_state(
        'cancelled',
        message='پردازش توسط شما متوقف شد.',
        ready_for_review=False,
        pending_exercises=pending,
    )
    session.save(update_fields=['status', 'workflow_state', 'updated_at'])
    return True


def _session_pending_exercises(session) -> list[dict]:
    raw = getattr(session, 'pending_exercises', None)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _save_session_pending_exercises(session, pending: list[dict], *, stage: str | None = None, warnings: list[str] | None = None) -> None:
    current = getattr(session, 'workflow_state', None)
    current_warnings = []
    if isinstance(current, dict) and isinstance(current.get('warnings'), list):
        current_warnings = current.get('warnings') or []
    merged_warnings = warnings if warnings is not None else current_warnings
    next_stage = stage or _session_workflow_stage_for_status(session.status)
    session.pending_exercises = pending
    _sync_session_workflow_to_status(session, warnings=merged_warnings)
    session.workflow_state['stage'] = next_stage
    session.workflow_state['pendingExercises'] = pending
    session.save(update_fields=['pending_exercises', 'workflow_state', 'updated_at'])


def _queue_session_review_ready_sms(session_id: int) -> None:
    try:
        send_session_review_ready_sms_task.delay(session_id)
    except Exception:
        logger.exception('Failed to queue session-ready SMS for %s', session_id)


def _materialize_pending_exercises(session) -> list[str]:
    """Create queued exercise drafts for any embedded exercise snapshots.

    Idempotent on ``clientExerciseKey``/``exerciseId`` persisted in
    ``session.pending_exercises``. Errors are recorded back onto the snapshot
    rows and returned as user-facing warnings without failing the class session.
    """
    from django.db import transaction
    from .models import ClassExercise, ClassExerciseAsset
    from .services.exercise_workflow import build_workflow_state

    pending = _session_pending_exercises(session)
    if not pending:
        return []

    warnings: list[str] = []
    changed = False
    for item in pending:
        if item.get('exerciseId'):
            continue
        title = str(item.get('title') or '').strip() or 'تمرین بدون عنوان'
        no_deadline = bool(item.get('noDeadline')) or not item.get('deadline')
        allow_late = bool(item.get('allowLate')) and not no_deadline
        try:
            with transaction.atomic():
                exercise = ClassExercise.objects.create(
                    session=session,
                    title=title,
                    description=str(item.get('teacherNote') or '').strip(),
                    deadline=item.get('deadline'),
                    allow_late=allow_late,
                    assistant_enabled=bool(item.get('assistantEnabled', True)),
                    workflow_state=build_workflow_state('queued'),
                    intake_config={
                        'v': 1,
                        'mode': 'embedded_class_create',
                        'autoExtract': True,
                        'noDeadline': no_deadline,
                        'deadline': item.get('deadline').isoformat() if getattr(item.get('deadline'), 'isoformat', None) else item.get('deadline'),
                        'allowLate': allow_late,
                        'assistantEnabled': bool(item.get('assistantEnabled', True)),
                        'teacherNote': str(item.get('teacherNote') or '').strip(),
                        'sources': item.get('sources') if isinstance(item.get('sources'), list) else [],
                    },
                )
                for source in item.get('sources') or []:
                    if not isinstance(source, dict):
                        continue
                    storage_path = str(source.get('storagePath') or '').strip()
                    if not storage_path:
                        continue
                    ClassExerciseAsset.objects.create(
                        exercise=exercise,
                        kind=str(source.get('assetKind') or ClassExerciseAsset.Kind.PDF),
                        file=storage_path,
                        order=int(source.get('assetOrder') or 0),
                    )
                transaction.on_commit(lambda eid=exercise.id: extract_exercise_content.delay(eid))
        except Exception:
            logger.exception('Failed to create embedded exercise for session %s title=%s', session.id, title)
            item['status'] = 'failed'
            item['message'] = 'پیش‌نویس این تمرین ساخته نشد و نیاز به بررسی دوباره دارد.'
            warnings.append(f'ساخت تمرین «{title}» کامل نشد و باید دوباره بررسی شود.')
            changed = True
            continue

        item['exerciseId'] = exercise.id
        item['status'] = 'queued'
        item['message'] = 'در صف ساخت پیش‌نویس تمرین قرار گرفت.'
        changed = True

    if changed:
        _save_session_pending_exercises(session, pending)
    return warnings


def _mark_session_ready_for_review(session) -> None:
    warnings = []
    if session.pipeline_type == session.PipelineType.CLASS:
        warnings.extend(_materialize_pending_exercises(session))

    _sync_session_workflow_to_status(session, warnings=warnings)
    session.status = session.status
    session.save(update_fields=['workflow_state', 'updated_at'])

    notified_now = (
        session.__class__.objects.filter(
            id=session.id,
            review_ready_notified_at__isnull=True,
        ).update(review_ready_notified_at=timezone.now()) > 0
    )
    if notified_now:
        session.refresh_from_db(fields=['review_ready_notified_at'])
    if notified_now:
        _queue_session_review_ready_sms(session.id)


# ---------------------------------------------------------------------------
# LLM usage attribution
# ---------------------------------------------------------------------------

def _attribute_llm_usage_to_teacher(task_fn):
    """Attribute all LLM usage inside a pipeline task to the session teacher.

    Celery workers run outside the HTTP request cycle, so the request-scoped
    ``LLMTrackingMiddleware`` never sets the current user — pipeline LLM calls
    would otherwise be logged with ``user=NULL``.  This decorator looks up the
    session's teacher and binds it (plus the session id) into the token
    tracker's thread-local context for the duration of the task.

    Applied *inside* ``@shared_task`` (i.e. listed below it) so Celery still
    sees the original task name.  The first positional argument of every
    wrapped task is ``session_id``.
    """

    @functools.wraps(task_fn)
    def _wrapper(self, session_id, *args, **kwargs):
        from .models import ClassCreationSession
        from apps.commons.token_tracker import llm_tracking_context

        session = (
            ClassCreationSession.objects
            .filter(id=session_id)
            .select_related('teacher')
            .first()
        )
        teacher_user = session.teacher if session else None
        with llm_tracking_context(user=teacher_user, session_id=session_id):
            return task_fn(self, session_id, *args, **kwargs)

    return _wrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_session_file_to_disk(session) -> str:
    """Stream the uploaded file (from S3 or local FS) to a temp file.

    Django's ``FileField.open()`` uses whichever storage backend is
    configured — ``S3Boto3Storage`` in production, ``FileSystemStorage``
    in local dev.  Both are transparent to this function.

    Raises ``FileNotFoundError`` if the session has no source file.
    Raises ``RuntimeError`` if the storage backend appears misconfigured
    (e.g. S3 env vars missing on the Celery worker pod).
    """
    if not session.source_file:
        raise FileNotFoundError(
            f'فایل منبع برای جلسه {session.id} وجود ندارد. '
            'ممکن است قبلاً حذف شده باشد.'
        )

    # Detect storage misconfiguration: if the backend saved to S3 but this
    # worker uses FileSystemStorage, the file won't exist on disk.  Give a
    # clear error instead of a confusing "No such file or directory".
    from django.core.files.storage import default_storage
    storage_cls = type(default_storage).__name__
    logger.info(
        'Reading source file for session %s via %s storage (name=%s)',
        session.id, storage_cls, session.source_file.name,
    )
    if storage_cls == 'FileSystemStorage' and os.getenv('AWS_STORAGE_BUCKET_NAME'):
        raise RuntimeError(
            f'Storage misconfiguration: AWS_STORAGE_BUCKET_NAME is set but '
            f'default_storage is FileSystemStorage. Ensure S3 env vars are '
            f'set on this pod/container (celery worker).'
        )

    suffix = os.path.splitext(session.source_original_name or '')[-1] or '.bin'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        session.source_file.open('rb')
        try:
            for chunk in session.source_file.chunks(chunk_size=2 * 1024 * 1024):
                tmp.write(chunk)
        finally:
            session.source_file.close()
    except FileNotFoundError:
        tmp.close()
        os.unlink(tmp.name)
        logger.error(
            'File not found for session %s. Storage backend: %s. '
            'If this is a Celery worker, ensure ALL S3 env vars '
            '(AWS_STORAGE_BUCKET_NAME, AWS_ACCESS_KEY_ID, '
            'AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT_URL) are set.',
            session.id, storage_cls,
        )
        raise
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise
    tmp.close()
    return tmp.name


def _read_file_bytes(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()


def _cleanup_source_file(session) -> None:
    """Delete the uploaded source file from disk and clear the DB field.

    Called after successful transcription — only the transcript text is
    needed from that point on.  This avoids accumulating large media
    files on the server.
    """
    try:
        if session.source_file:
            session.source_file.delete(save=False)
            session.source_file = None
            session.save(update_fields=['source_file', 'updated_at'])
    except Exception:
        logger.warning('Failed to cleanup source file for session %s', session.id, exc_info=True)


def _safe_refresh(session) -> bool:
    """Refresh session from DB, returning ``False`` if the row was deleted.

    Every ``session.refresh_from_db()`` call in pipeline code should go
    through this helper so that a user-initiated deletion does not crash
    the worker with ``DoesNotExist``.
    """
    try:
        session.refresh_from_db()
        return True
    except Exception:
        logger.info('Session %s no longer exists — aborting.', session.id)
        return False


def _safe_mark_failed(session, error_detail: str) -> None:
    """Best-effort update of session status to FAILED.

    If the session was already deleted (e.g. user removed it while the
    pipeline was running), this silently does nothing.
    """
    try:
        session.refresh_from_db()
        if session.status != session.Status.FAILED:
            session.status = session.Status.FAILED
            session.error_detail = (error_detail or '')[:2000]
            _sync_session_workflow_to_status(
                session,
                message='پردازش کامل نشد. دوباره تلاش کنید یا منبع را بازبینی کنید.',
                warnings=['پردازش کامل نشد. دوباره تلاش کنید یا منبع را بازبینی کنید.'],
            )
            session.save(update_fields=['status', 'error_detail', 'workflow_state', 'updated_at'])
    except Exception:
        logger.info(
            'Could not mark session %s as FAILED (likely deleted).',
            session.id,
        )


def _safe_mark_cancelled(session) -> None:
    """Best-effort transition of a session to the terminal CANCELLED state.

    Idempotent: if the session was already cancelled (or deleted) this does
    nothing. Used by the cooperative-cancellation checkpoints so a revoked /
    re-queued pipeline settles on a consistent terminal status.
    """
    try:
        session.refresh_from_db()
        if session.status != session.Status.CANCELLED:
            session.status = session.Status.CANCELLED
            _sync_session_workflow_to_status(
                session,
                message='پردازش توسط شما متوقف شد.',
            )
            session.save(update_fields=['status', 'workflow_state', 'updated_at'])
    except Exception:
        logger.info(
            'Could not mark session %s as CANCELLED (likely deleted).',
            session.id,
        )


def _pipeline_cancelled(session) -> bool:
    """Cooperative-cancellation checkpoint (call right after ``_safe_refresh``).

    Returns ``True`` if the teacher requested cancellation — either the
    ``cancel_requested`` flag is set or the row is already in the terminal
    CANCELLED state — and settles the row on CANCELLED. The full-pipeline
    tasks call this at every step boundary so an in-flight pipeline stops
    promptly even if ``app.control.revoke`` could not kill the worker.
    """
    if _session_cancelled(session):
        _safe_mark_cancelled(session)
        return True
    return False


def _safe_save(session, update_fields: list[str]) -> bool:
    """Save session with ``update_fields``, returning ``False`` on error.

    Handles the ``DatabaseError("Save with update_fields did not affect
    any rows")`` that Django raises when the row was deleted between a
    ``refresh_from_db()`` and a ``save()``.
    """
    try:
        session.save(update_fields=update_fields)
        return True
    except Exception:
        logger.info(
            'Could not save session %s (may have been deleted).',
            session.id,
        )
        return False


def _run_pipeline_step(
    step_fn,
    step_label: str,
    session_id: int,
    session,
    *,
    max_attempts: int = 4,
    base_delay: int = 15,
) -> bool:
    """Run a pipeline step inline with retry logic.

    Individual step tasks call ``self.retry()`` on failure which raises
    ``celery.exceptions.Retry``.  When called directly from a full-pipeline
    task, the Retry is caught here and retried inline with exponential
    back-off instead of re-queuing a separate Celery task.

    Returns ``True`` on success, ``False`` on failure (session marked FAILED).
    """
    for attempt in range(1, max_attempts + 1):
        try:
            result = step_fn(session_id)
            # Step returned normally — check if it flagged failure internally.
            if isinstance(result, dict) and result.get('status') == 'failed':
                return False
            return True

        except SoftTimeLimitExceeded:
            # The task's wall-time budget is gone. The signal fires ONCE —
            # retrying the step inline would run blind into the hard-limit
            # SIGKILL. Settle the session and stop immediately.
            logger.error(
                'Pipeline step %s hit the soft time limit for session %s — failing fast.',
                step_label, session_id,
            )
            _safe_mark_failed(session, _PIPELINE_TIMEOUT_FA)
            return False

        except (CeleryRetry, Exception) as exc:
            is_last = attempt >= max_attempts
            exc_msg = str(exc)[:300]

            if is_last:
                logger.error(
                    'Pipeline step %s failed after %d attempts for session %s: %s',
                    step_label, max_attempts, session_id, exc_msg,
                )
                _safe_mark_failed(session, f'{step_label}: {exc_msg}')
                return False

            delay = min(base_delay * (2 ** (attempt - 1)), 120)
            logger.warning(
                'Pipeline step %s attempt %d/%d failed for session %s: %s — retrying in %ds',
                step_label, attempt, max_attempts, session_id, exc_msg, delay,
            )
            time.sleep(delay)
            if not _safe_refresh(session):
                return False
            if session.status == session.Status.FAILED:
                # Something else marked it failed — abort.
                return False

    return False  # pragma: no cover


# ---------------------------------------------------------------------------
# Step-1 ingestion dispatch (media transcription OR PDF extraction)
# ---------------------------------------------------------------------------

def _make_step1_heartbeat(session_id: int):
    """Progress hook for long (chunked) transcriptions.

    Called by ``transcribe_media_file`` after every audio chunk. Does two jobs:

    * **Stale-session protection** — bumps ``updated_at`` so a legitimately
      running multi-hour transcription is never force-FAILED by
      ``cleanup_stale_sessions`` (which reaps sessions idle in an *ING status
      for >2 h).
    * **Mid-step cancellation** — returns ``False`` (→ the service raises
      ``TranscriptionAborted``) when the teacher set ``cancel_requested`` or
      deleted the session, so a 2-hour lecture stops within one chunk instead
      of only at the next step boundary.
    """
    from .models import ClassCreationSession

    def _heartbeat(done: int, total: int):
        session = ClassCreationSession.objects.filter(id=session_id).first()
        if session is None:
            logger.info('STEP1 heartbeat: session %s deleted — aborting transcription.', session_id)
            return False
        if session.cancel_requested:
            logger.info('STEP1 heartbeat: session %s cancel requested — aborting transcription.', session_id)
            return False
        _sync_session_workflow_to_status(session)
        if total > 1 and isinstance(session.workflow_state, dict):
            bounded_done = max(0, min(done, total))
            chunk_progress = int(30 + (15 * bounded_done / max(total, 1)))
            session.workflow_state['progressPercent'] = max(
                session.workflow_state.get('progressPercent') or 0,
                min(chunk_progress, 45),
            )
            session.workflow_state['message'] = f'در حال تبدیل فایل به متن هستیم ({bounded_done} از {total}).'
        session.save(update_fields=['workflow_state', 'updated_at'])
        if total > 1:
            logger.info('STEP1 progress: session=%s chunk %d/%d transcribed', session_id, done, total)
        return True

    return _heartbeat


def _ingest_source_to_markdown(session, tmp_path: str, progress_cb=None):
    """Branch step-1 ingestion on ``source_type``, operating on an on-disk file.

    Takes the temp FILE PATH already streamed to disk by
    ``_read_session_file_to_disk`` — NOT the full bytes — so a large lecture
    video is never re-materialized in worker RAM (the cause of the pipeline
    OOM-kill during frame extraction). PDFs are small, so the PDF branch still
    reads bytes; media streams from the file through ffmpeg.

    ``progress_cb`` is forwarded to the (possibly chunked) media transcription
    for heartbeat + mid-step cancellation; the PDF engine has its own paging.

    Returns ``(markdown, provider, model, page_count)``.
    """
    from .models import ClassCreationSession
    from .services.transcription import transcribe_media_file
    from .services.pdf_extraction import extract_pdf_to_markdown

    mime = session.source_mime_type or ''
    if session.source_type == ClassCreationSession.SourceType.PDF:
        return extract_pdf_to_markdown(
            data=_read_file_bytes(tmp_path), mime_type=mime or 'application/pdf',
            asset_prefix=f'class_creation/extracted/{session.id}',
        )
    markdown, provider, model_name = transcribe_media_file(
        path=tmp_path, mime_type=mime or 'application/octet-stream',
        progress_cb=progress_cb,
    )
    return markdown, provider, model_name, 0


# ---------------------------------------------------------------------------
# CLASS pipeline tasks (steps 1-5 + full pipeline)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True, max_retries=3, default_retry_delay=60, acks_late=True,
    soft_time_limit=PIPELINE_TASK_SOFT_TIME_LIMIT, time_limit=PIPELINE_TASK_TIME_LIMIT,
)
@_attribute_llm_usage_to_teacher
def process_class_step1_transcription(self, session_id: int) -> dict:
    """Transcribe uploaded media (or extract a PDF) for a class creation session."""
    from .models import ClassCreationSession
    from .services.transcription import TranscriptionAborted

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.TRANSCRIBING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    _sync_session_workflow_to_status(session, message='فایل جلسه دریافت شد و در حال تبدیل به متن هستیم.')
    session.save(update_fields=['workflow_state', 'updated_at'])

    tmp_path: str | None = None
    try:
        tmp_path = _read_session_file_to_disk(session)
        logger.info(
            "STEP1 task: session=%s source_type=%s file=%r",
            session.id, session.source_type, session.source_file.name if session.source_file else None,
        )

        # Pass the on-disk temp path (NOT the full bytes) so media is streamed
        # through ffmpeg and never resident in RAM — prevents the worker OOM.
        transcript, provider, model_name, page_count = _ingest_source_to_markdown(
            session, tmp_path, progress_cb=_make_step1_heartbeat(session.id),
        )
        logger.info(
            "STEP1 task done: session=%s transcript_chars=%d pages=%s provider=%s",
            session.id, len(transcript or ""), page_count, provider,
        )
        session.transcript_markdown = transcript
        session.llm_provider = provider
        session.llm_model = model_name
        session.source_page_count = page_count
        session.status = ClassCreationSession.Status.TRANSCRIBED
        _sync_session_workflow_to_status(session, message='متن جلسه آماده شد و در صف ساختاردهی قرار گرفت.')
        session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'source_page_count', 'status', 'workflow_state', 'updated_at'])

        # Delete the uploaded source file to free disk space.
        # Only the transcript text is needed from this point on.
        _cleanup_source_file(session)

        return {'status': 'success', 'session_id': session_id}
    except TranscriptionAborted:
        # Teacher cancelled (or deleted the session) mid-transcription. This is
        # a terminal outcome, NOT a transient failure — never retry it.
        logger.info('STEP1 task: session=%s transcription aborted (cancelled).', session_id)
        _safe_mark_cancelled(session)
        return {'status': 'cancelled', 'session_id': session_id}
    except SoftTimeLimitExceeded:
        # Wall-time budget exhausted. The signal fires once — retrying would
        # run blind into the hard-limit SIGKILL. Fail fast with a clear error.
        logger.error('STEP1 task: session=%s hit the soft time limit — failing fast.', session_id)
        _safe_mark_failed(session, _PIPELINE_TIMEOUT_FA)
        return {'status': 'failed', 'error': 'soft time limit exceeded'}
    except Exception as exc:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            tmp_path = None
        # Mark failed only on final retry.
        if self.request.retries >= self.max_retries:
            _safe_mark_failed(session, str(exc))
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
@_attribute_llm_usage_to_teacher
def process_class_step2_structure(self, session_id: int) -> dict:
    """Structure transcript into outline/units."""
    from .models import ClassCreationSession
    from .services.structure import structure_transcript_markdown
    from .services.sync_structure import sync_structure_from_session

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.STRUCTURING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    _sync_session_workflow_to_status(session)
    session.save(update_fields=['workflow_state', 'updated_at'])
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز متن درس آماده نیست.'
        _sync_session_workflow_to_status(session, warnings=[session.error_detail])
        session.save(update_fields=['status', 'error_detail', 'workflow_state', 'updated_at'])
        return {'status': 'failed', 'error': session.error_detail}

    try:
        structure_obj, provider, model_name = structure_transcript_markdown(
            transcript_markdown=session.transcript_markdown,
        )
        session.structure_json = json.dumps(structure_obj, ensure_ascii=False)
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.STRUCTURED
        _sync_session_workflow_to_status(session, message='ساختار جلسه آماده شد و حالا پیش‌نیازها را استخراج می‌کنیم.')
        session.save(update_fields=['structure_json', 'llm_provider', 'llm_model', 'status', 'workflow_state', 'updated_at'])
        sync_structure_from_session(session=session)
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _safe_mark_failed(session, str(exc))
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
@_attribute_llm_usage_to_teacher
def process_class_step3_prerequisites(self, session_id: int) -> dict:
    """Extract prerequisites from transcript."""
    from .models import ClassCreationSession, ClassPrerequisite
    from .services.prerequisites import extract_prerequisites

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.PREREQ_EXTRACTING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    _sync_session_workflow_to_status(session)
    session.save(update_fields=['workflow_state', 'updated_at'])
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز متن درس آماده نیست.'
        _sync_session_workflow_to_status(session, warnings=[session.error_detail])
        session.save(update_fields=['status', 'error_detail', 'workflow_state', 'updated_at'])
        return {'status': 'failed', 'error': session.error_detail}

    try:
        prereq_obj, provider, model_name = extract_prerequisites(
            transcript_markdown=session.transcript_markdown,
        )
        raw_list = prereq_obj.get('prerequisites') if isinstance(prereq_obj, dict) else None
        prereqs = [str(x).strip() for x in (raw_list or []) if str(x).strip()]

        # Upsert prerequisites
        keep_ids: list[int] = []
        for idx, name in enumerate(prereqs):
            obj, _ = ClassPrerequisite.objects.update_or_create(
                session=session, order=idx + 1, defaults={'name': name},
            )
            keep_ids.append(obj.id)
        ClassPrerequisite.objects.filter(session=session).exclude(id__in=keep_ids).delete()

        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.PREREQ_EXTRACTED
        _sync_session_workflow_to_status(session, message='پیش‌نیازها آماده شد و حالا توضیح هر مورد ساخته می‌شود.')
        session.save(update_fields=['llm_provider', 'llm_model', 'status', 'workflow_state', 'updated_at'])
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _safe_mark_failed(session, str(exc))
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
@_attribute_llm_usage_to_teacher
def process_class_step4_prereq_teaching(self, session_id: int, prerequisite_name: str | None = None) -> dict:
    """Generate teaching notes for prerequisites."""
    from .models import ClassCreationSession, ClassPrerequisite
    from .services.prerequisites import generate_prerequisite_teaching

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.PREREQ_TEACHING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    _sync_session_workflow_to_status(session)
    session.save(update_fields=['workflow_state', 'updated_at'])

    qs = ClassPrerequisite.objects.filter(session=session).order_by('order')
    if prerequisite_name:
        qs = qs.filter(name=prerequisite_name)
    if not qs.exists():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'پیش نیازها یافت نشدند. ابتدا مرحله پیش نیازها را اجرا کنید.'
        _sync_session_workflow_to_status(session, warnings=[session.error_detail])
        session.save(update_fields=['status', 'error_detail', 'workflow_state', 'updated_at'])
        return {'status': 'failed', 'error': session.error_detail}

    try:
        provider = model_name = ''
        for prereq in qs:
            teaching, provider, model_name = generate_prerequisite_teaching(
                prerequisite_name=prereq.name,
                source_markdown=session.transcript_markdown,
            )
            prereq.teaching_text = teaching
            prereq.save(update_fields=['teaching_text'])

        if provider:
            session.llm_provider = provider
        if model_name:
            session.llm_model = model_name
        session.status = ClassCreationSession.Status.PREREQ_TAUGHT
        _sync_session_workflow_to_status(session, message='آموزش پیش‌نیازها آماده شد و حالا جمع‌بندی ساخته می‌شود.')
        session.save(update_fields=['llm_provider', 'llm_model', 'status', 'workflow_state', 'updated_at'])
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _safe_mark_failed(session, str(exc))
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
@_attribute_llm_usage_to_teacher
def process_class_step5_recap(self, session_id: int) -> dict:
    """Generate recap markdown from structured content."""
    from .models import ClassCreationSession
    from .services.recap import generate_recap_from_structure, recap_json_to_markdown

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.RECAPPING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    _sync_session_workflow_to_status(session)
    session.save(update_fields=['workflow_state', 'updated_at'])
    if not (session.structure_json or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز ساختار مرحله ۲ آماده نیست.'
        _sync_session_workflow_to_status(session, warnings=[session.error_detail])
        session.save(update_fields=['status', 'error_detail', 'workflow_state', 'updated_at'])
        return {'status': 'failed', 'error': session.error_detail}

    try:
        recap_obj, provider, model_name = generate_recap_from_structure(structure_json=session.structure_json)
        session.recap_markdown = recap_json_to_markdown(recap_obj)
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.RECAPPED
        _sync_session_workflow_to_status(session)
        session.save(update_fields=['recap_markdown', 'llm_provider', 'llm_model', 'status', 'workflow_state', 'updated_at'])
        _mark_session_ready_for_review(session)
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _safe_mark_failed(session, str(exc))
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(
    bind=True, max_retries=0, acks_late=True,
    soft_time_limit=PIPELINE_TASK_SOFT_TIME_LIMIT, time_limit=PIPELINE_TASK_TIME_LIMIT,
)
@_attribute_llm_usage_to_teacher
def process_class_full_pipeline(self, session_id: int) -> dict:
    """Run class creation steps 1-5 sequentially (one-click pipeline).

    Each step is called **inline** (not as a sub-task) so that ordering
    is always guaranteed.  Failures are retried up to 4 times with
    exponential back-off per step before the pipeline gives up.
    """
    from .models import ClassCreationSession

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'start'}

    # Step 1
    if session.status == ClassCreationSession.Status.TRANSCRIBING:
        if not _run_pipeline_step(process_class_step1_transcription, 'step1_transcription', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step1'}

    if not _safe_refresh(session):
        return {'status': 'aborted', 'reason': 'session deleted'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'step1'}
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step1'}

    # Step 2
    if session.status == ClassCreationSession.Status.TRANSCRIBED:
        session.status = ClassCreationSession.Status.STRUCTURING
        _sync_session_workflow_to_status(session)
        if not _safe_save(session, ['status', 'workflow_state', 'updated_at']):
            return {'status': 'aborted', 'reason': 'session deleted'}
        if not _run_pipeline_step(process_class_step2_structure, 'step2_structure', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step2'}

    if not _safe_refresh(session):
        return {'status': 'aborted', 'reason': 'session deleted'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'step2'}
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step2'}

    # Step 3
    if session.status == ClassCreationSession.Status.STRUCTURED:
        session.status = ClassCreationSession.Status.PREREQ_EXTRACTING
        _sync_session_workflow_to_status(session)
        if not _safe_save(session, ['status', 'workflow_state', 'updated_at']):
            return {'status': 'aborted', 'reason': 'session deleted'}
        if not _run_pipeline_step(process_class_step3_prerequisites, 'step3_prerequisites', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step3'}

    if not _safe_refresh(session):
        return {'status': 'aborted', 'reason': 'session deleted'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'step3'}
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step3'}

    # Step 4
    if session.status == ClassCreationSession.Status.PREREQ_EXTRACTED:
        session.status = ClassCreationSession.Status.PREREQ_TEACHING
        _sync_session_workflow_to_status(session)
        if not _safe_save(session, ['status', 'workflow_state', 'updated_at']):
            return {'status': 'aborted', 'reason': 'session deleted'}
        if not _run_pipeline_step(process_class_step4_prereq_teaching, 'step4_prereq_teaching', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step4'}

    if not _safe_refresh(session):
        return {'status': 'aborted', 'reason': 'session deleted'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'step4'}
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step4'}

    # Step 5
    if session.status == ClassCreationSession.Status.PREREQ_TAUGHT:
        session.status = ClassCreationSession.Status.RECAPPING
        _sync_session_workflow_to_status(session)
        if not _safe_save(session, ['status', 'workflow_state', 'updated_at']):
            return {'status': 'aborted', 'reason': 'session deleted'}
        if not _run_pipeline_step(process_class_step5_recap, 'step5_recap', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step5'}

    if not _safe_refresh(session):
        return {'status': 'aborted', 'reason': 'session deleted'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'step5'}
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step5'}

    logger.info('Full pipeline completed for session %s', session_id)
    return {'status': 'success', 'session_id': session_id}


# ---------------------------------------------------------------------------
# EXAM PREP pipeline tasks (steps 1-2 + full pipeline)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True, max_retries=3, default_retry_delay=60, acks_late=True,
    soft_time_limit=PIPELINE_TASK_SOFT_TIME_LIMIT, time_limit=PIPELINE_TASK_TIME_LIMIT,
)
@_attribute_llm_usage_to_teacher
def process_exam_prep_step1_transcription(self, session_id: int) -> dict:
    """Transcribe uploaded media (or extract a PDF) for exam prep pipeline."""
    from .models import ClassCreationSession
    from .services.transcription import TranscriptionAborted

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.EXAM_TRANSCRIBING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    _sync_session_workflow_to_status(session, message='منبع آمادگی آزمون دریافت شد و در حال تبدیل به متن هستیم.')
    session.save(update_fields=['workflow_state', 'updated_at'])

    tmp_path: str | None = None
    try:
        tmp_path = _read_session_file_to_disk(session)
        logger.info(
            "STEP1 task: session=%s source_type=%s file=%r",
            session.id, session.source_type, session.source_file.name if session.source_file else None,
        )

        # Pass the on-disk temp path (NOT the full bytes) so media is streamed
        # through ffmpeg and never resident in RAM — prevents the worker OOM.
        transcript, provider, model_name, page_count = _ingest_source_to_markdown(
            session, tmp_path, progress_cb=_make_step1_heartbeat(session.id),
        )
        logger.info(
            "STEP1 task done: session=%s transcript_chars=%d pages=%s provider=%s",
            session.id, len(transcript or ""), page_count, provider,
        )
        session.transcript_markdown = transcript
        session.llm_provider = provider
        session.llm_model = model_name
        session.source_page_count = page_count
        session.status = ClassCreationSession.Status.EXAM_TRANSCRIBED
        _sync_session_workflow_to_status(session, message='متن آمادگی آزمون آماده شد و حالا سوال‌ها را استخراج می‌کنیم.')
        session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'source_page_count', 'status', 'workflow_state', 'updated_at'])

        # Delete the uploaded source file to free disk space.
        _cleanup_source_file(session)

        return {'status': 'success', 'session_id': session_id}
    except TranscriptionAborted:
        # Teacher cancelled (or deleted the session) mid-transcription — a
        # terminal outcome, NOT a transient failure; never retry it.
        logger.info('STEP1 task: session=%s transcription aborted (cancelled).', session_id)
        _safe_mark_cancelled(session)
        return {'status': 'cancelled', 'session_id': session_id}
    except SoftTimeLimitExceeded:
        # Wall-time budget exhausted — fail fast instead of retrying into the
        # hard-limit SIGKILL (the signal only fires once).
        logger.error('STEP1 task: session=%s hit the soft time limit — failing fast.', session_id)
        _safe_mark_failed(session, _PIPELINE_TIMEOUT_FA)
        return {'status': 'failed', 'error': 'soft time limit exceeded'}
    except Exception as exc:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            tmp_path = None
        if self.request.retries >= self.max_retries:
            _safe_mark_failed(session, str(exc))
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
@_attribute_llm_usage_to_teacher
def process_exam_prep_step2_structure(self, session_id: int) -> dict:
    """Extract Q&A structure from exam prep transcript."""
    import json as _json
    from .models import ClassCreationSession
    from .services.exam_prep_structure import extract_exam_prep_structure
    from .services.exam_prep_utils import normalize_exam_prep_questions

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.EXAM_STRUCTURING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    _sync_session_workflow_to_status(session)
    session.save(update_fields=['workflow_state', 'updated_at'])
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز ترنسکریپت مرحله ۱ آماده نیست.'
        _sync_session_workflow_to_status(session, warnings=[session.error_detail])
        session.save(update_fields=['status', 'error_detail', 'workflow_state', 'updated_at'])
        return {'status': 'failed', 'error': session.error_detail}

    try:
        exam_prep_obj, provider, model_name = extract_exam_prep_structure(
            transcript_markdown=session.transcript_markdown,
        )
        normalized, _changed = normalize_exam_prep_questions(exam_prep_obj)
        session.exam_prep_json = _json.dumps(normalized, ensure_ascii=False)
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.EXAM_STRUCTURED
        _sync_session_workflow_to_status(session)
        session.save(update_fields=['exam_prep_json', 'llm_provider', 'llm_model', 'status', 'workflow_state', 'updated_at'])
        _mark_session_ready_for_review(session)
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _safe_mark_failed(session, str(exc))
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(
    bind=True, max_retries=0, acks_late=True,
    soft_time_limit=PIPELINE_TASK_SOFT_TIME_LIMIT, time_limit=PIPELINE_TASK_TIME_LIMIT,
)
@_attribute_llm_usage_to_teacher
def process_exam_prep_full_pipeline(self, session_id: int) -> dict:
    """Run exam prep steps 1-2 sequentially with inline retry logic."""
    from .models import ClassCreationSession

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'start'}

    # Step 1
    if session.status == ClassCreationSession.Status.EXAM_TRANSCRIBING:
        if not _run_pipeline_step(process_exam_prep_step1_transcription, 'step1_transcription', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step1'}

    if not _safe_refresh(session):
        return {'status': 'aborted', 'reason': 'session deleted'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'step1'}
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step1'}

    # Step 2
    if session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED:
        session.status = ClassCreationSession.Status.EXAM_STRUCTURING
        _sync_session_workflow_to_status(session)
        if not _safe_save(session, ['status', 'workflow_state', 'updated_at']):
            return {'status': 'aborted', 'reason': 'session deleted'}
        if not _run_pipeline_step(process_exam_prep_step2_structure, 'step2_structure', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step2'}

    if not _safe_refresh(session):
        return {'status': 'aborted', 'reason': 'session deleted'}
    if _pipeline_cancelled(session):
        return {'status': 'cancelled', 'stopped_at': 'step2'}
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step2'}

    logger.info('Exam-prep pipeline completed for session %s', session_id)
    return {'status': 'success', 'session_id': session_id}


@shared_task(bind=True, max_retries=2, default_retry_delay=120, acks_late=True)
def pregenerate_student_assessments(self, session_id: int, student_id: int) -> dict:
    """Pre-build every chapter quiz + the final exam for a student in the
    background, so the FIRST time they open a quiz it is already there instead
    of waiting on on-demand generation.

    Idempotent and best-effort: anything already generated is skipped, and one
    section/exam failing never aborts the rest (on-demand generation remains the
    fallback for anything this misses).
    """
    from django.contrib.auth import get_user_model
    from .models import ClassCreationSession, ClassSectionQuiz, ClassFinalExam
    from .services.quizzes import generate_section_quiz_questions, generate_final_exam_pool

    User = get_user_model()
    session = (
        ClassCreationSession.objects
        .filter(id=session_id, is_published=True)
        .prefetch_related('sections__units')
        .first()
    )
    student = User.objects.filter(id=student_id).first()
    if session is None or student is None:
        return {'status': 'skipped', 'reason': 'session or student missing'}

    quizzes_created = 0
    for section in session.sections.order_by('order'):
        existing = ClassSectionQuiz.objects.filter(session=session, section=section, student=student).first()
        if existing is not None and isinstance(existing.questions, dict) and existing.questions.get('questions'):
            continue
        units = list(section.units.order_by('order'))
        combined = "\n\n".join(
            [
                (u.content_markdown or u.source_markdown or '').strip()
                for u in units
                if (u.content_markdown or u.source_markdown or '').strip()
            ]
        ).strip()[:8000]
        if not combined:
            continue
        try:
            quiz_obj, _provider, _model = generate_section_quiz_questions(section_content=combined, count=5)
            ClassSectionQuiz.objects.update_or_create(
                session=session, section=section, student=student,
                defaults={'questions': quiz_obj},
            )
            quizzes_created += 1
        except Exception:
            logger.exception('pregenerate: section quiz failed session=%s section=%s', session_id, section.id)

    final_exam_created = False
    existing_exam = ClassFinalExam.objects.filter(session=session, student=student).first()
    if existing_exam is None or not (isinstance(existing_exam.exam, dict) and existing_exam.exam.get('questions')):
        parts: list[str] = []
        for section in session.sections.order_by('order'):
            parts.append(str(section.title or '').strip())
            for unit in section.units.order_by('order'):
                txt = (unit.content_markdown or unit.source_markdown or '').strip()
                if txt:
                    parts.append(txt)
        combined = "\n\n".join([p for p in parts if p]).strip()[:12000]
        if combined:
            try:
                exam_obj, _provider, _model = generate_final_exam_pool(combined_content=combined, pool_size=12)
                ClassFinalExam.objects.update_or_create(
                    session=session, student=student, defaults={'exam': exam_obj},
                )
                final_exam_created = True
            except Exception:
                logger.exception('pregenerate: final exam failed session=%s', session_id)

    logger.info(
        'pregenerate done session=%s student=%s quizzes=%d final_exam=%s',
        session_id, student_id, quizzes_created, final_exam_created,
    )
    return {
        'status': 'success',
        'quizzes_created': quizzes_created,
        'final_exam_created': final_exam_created,
    }


# ---------------------------------------------------------------------------
# Lightweight tasks (SMS, notifications, etc.)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=5, acks_late=True)
def send_publish_sms_task(self, session_id: int) -> dict:
    """Send publish SMS notifications to invited students.

    Uses exponential back-off: 30 s → 60 s → 120 s → 240 s → 480 s.
    """
    from .services.mediana_sms import send_publish_sms_for_session

    logger.info(
        '[SMS] send_publish_sms_task STARTED session=%s attempt=%s/%s',
        session_id, self.request.retries + 1, self.max_retries + 1,
    )
    try:
        send_publish_sms_for_session(session_id)
        logger.info('[SMS] send_publish_sms_task SUCCESS session=%s', session_id)
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        logger.error('[SMS] send_publish_sms_task FAILED session=%s (attempt %s/%s): %s',
                     session_id, self.request.retries + 1, self.max_retries + 1,
                     str(exc)[:200])
        if self.request.retries >= self.max_retries:
            return {'status': 'failed', 'error': str(exc)[:500]}
        backoff = 30 * (2 ** self.request.retries)  # 30, 60, 120, 240, 480
        raise self.retry(exc=exc, countdown=backoff)


@shared_task(bind=True, max_retries=5, acks_late=True)
def send_new_invites_sms_task(self, session_id: int, invite_ids: list[int]) -> dict:
    """Send SMS to specific newly-added invitations (post-publish).

    Uses exponential back-off: 30 s → 60 s → 120 s → 240 s → 480 s.
    """
    from .services.mediana_sms import send_invite_sms_for_ids

    logger.info(
        '[SMS] send_new_invites_sms_task STARTED session=%s invites=%d attempt=%s/%s',
        session_id, len(invite_ids), self.request.retries + 1, self.max_retries + 1,
    )
    try:
        send_invite_sms_for_ids(session_id, invite_ids)
        logger.info('[SMS] send_new_invites_sms_task SUCCESS session=%s invites=%d', session_id, len(invite_ids))
        return {'status': 'success', 'session_id': session_id, 'invite_count': len(invite_ids)}
    except Exception as exc:
        logger.error('New-invite SMS failed for session %s (attempt %s/%s): %s',
                     session_id, self.request.retries + 1, self.max_retries + 1,
                     str(exc)[:200])
        if self.request.retries >= self.max_retries:
            return {'status': 'failed', 'error': str(exc)[:500]}
        backoff = 30 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)


# ---------------------------------------------------------------------------
# Periodic maintenance tasks
# ---------------------------------------------------------------------------

# In-progress statuses that indicate a pipeline step is actively running.
# Sessions stuck in these statuses for too long are considered stale.
_IN_PROGRESS_STATUSES: list[str] = []  # populated lazily


def _get_in_progress_statuses() -> list[str]:
    global _IN_PROGRESS_STATUSES
    if not _IN_PROGRESS_STATUSES:
        from .models import ClassCreationSession
        _IN_PROGRESS_STATUSES = [
            ClassCreationSession.Status.TRANSCRIBING,
            ClassCreationSession.Status.STRUCTURING,
            ClassCreationSession.Status.PREREQ_EXTRACTING,
            ClassCreationSession.Status.PREREQ_TEACHING,
            ClassCreationSession.Status.RECAPPING,
            ClassCreationSession.Status.EXAM_TRANSCRIBING,
            ClassCreationSession.Status.EXAM_STRUCTURING,
        ]
    return _IN_PROGRESS_STATUSES


@shared_task(bind=True, max_retries=5, acks_late=True)
def send_teacher_message_sms_task(self, notification_id: int) -> dict:
    """Send a teacher broadcast message to its recipients via SMS.

    Uses exponential back-off: 30 s → 60 s → 120 s → 240 s → 480 s.
    """
    from .services.mediana_sms import send_teacher_message_sms

    logger.info(
        '[SMS] send_teacher_message_sms_task STARTED notif=%s attempt=%s/%s',
        notification_id, self.request.retries + 1, self.max_retries + 1,
    )
    try:
        send_teacher_message_sms(notification_id)
        logger.info('[SMS] send_teacher_message_sms_task SUCCESS notif=%s', notification_id)
        return {'status': 'success', 'notification_id': notification_id}
    except Exception as exc:
        logger.error('Teacher message SMS failed for notif %s (attempt %s/%s): %s',
                     notification_id, self.request.retries + 1, self.max_retries + 1,
                     str(exc)[:200])
        if self.request.retries >= self.max_retries:
            return {'status': 'failed', 'error': str(exc)[:500]}
        backoff = 30 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)


@shared_task(bind=True, max_retries=5, acks_late=True)
def send_exercise_review_ready_sms_task(self, exercise_id: int) -> dict:
    """Send the ready-for-review SMS to the owning teacher."""
    from .services.mediana_sms import send_exercise_review_ready_sms

    logger.info(
        '[SMS] send_exercise_review_ready_sms_task STARTED exercise=%s attempt=%s/%s',
        exercise_id, self.request.retries + 1, self.max_retries + 1,
    )
    try:
        send_exercise_review_ready_sms(exercise_id)
        logger.info('[SMS] send_exercise_review_ready_sms_task SUCCESS exercise=%s', exercise_id)
        return {'status': 'success', 'exercise_id': exercise_id}
    except Exception as exc:
        logger.error(
            'Exercise-ready SMS failed for exercise %s (attempt %s/%s): %s',
            exercise_id, self.request.retries + 1, self.max_retries + 1, str(exc)[:200],
        )
        if self.request.retries >= self.max_retries:
            return {'status': 'failed', 'error': str(exc)[:500]}
        backoff = 30 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)


@shared_task(bind=True, max_retries=5, acks_late=True)
def send_session_review_ready_sms_task(self, session_id: int) -> dict:
    """Send the ready-for-review SMS for a class or exam-prep session."""
    from .services.mediana_sms import send_session_review_ready_sms

    logger.info(
        '[SMS] send_session_review_ready_sms_task STARTED session=%s attempt=%s/%s',
        session_id, self.request.retries + 1, self.max_retries + 1,
    )
    try:
        send_session_review_ready_sms(session_id)
        logger.info('[SMS] send_session_review_ready_sms_task SUCCESS session=%s', session_id)
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        logger.error(
            'Session-ready SMS failed for session %s (attempt %s/%s): %s',
            session_id, self.request.retries + 1, self.max_retries + 1, str(exc)[:200],
        )
        if self.request.retries >= self.max_retries:
            return {'status': 'failed', 'error': str(exc)[:500]}
        backoff = 30 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)


@shared_task(bind=True, max_retries=0)
def cleanup_stale_sessions(self) -> dict:
    """Mark sessions stuck in *ING statuses for >2 hours as FAILED.

    Should be scheduled as a periodic task (celery beat) every 30 minutes.
    Can also be called manually via Django management shell.
    """
    from django.utils import timezone as _tz
    from .models import ClassCreationSession

    cutoff = _tz.now() - timedelta(hours=2)
    stale_statuses = _get_in_progress_statuses()

    stale_qs = ClassCreationSession.objects.filter(
        status__in=stale_statuses,
        updated_at__lt=cutoff,
    )
    count = stale_qs.count()
    if count > 0:
        stale_qs.update(
            status=ClassCreationSession.Status.FAILED,
            error_detail='پایپ لاین بیش از ۲ ساعت بدون پاسخ ماند و به طور خودکار متوقف شد.',
        )
        logger.warning('Marked %d stale sessions as FAILED (stuck >2h).', count)

    return {'status': 'success', 'stale_count': count}


# ---------------------------------------------------------------------------
# Exercise Hub — async extraction (ingest OCR -> structure -> section/question
# rows). Runs on the `pipeline` queue. Design: docs/features/exercise-hub.md.
# ---------------------------------------------------------------------------


def _exercise_source_hint(intake_config: dict | None) -> str:
    from .services.exercise_workflow import source_entries

    rows = source_entries(intake_config)
    if not rows:
        return ''
    lines = [
        'TEACHER_INTAKE_HINTS:',
        'Use these teacher-provided source hints as guidance only:',
    ]
    for row in rows:
        lines.append(
            f"- {row.get('assetName') or 'source'} | role={row.get('role') or 'auto'}"
            f" | writing={row.get('writingMode') or 'auto'}"
            f" | answer_layout={row.get('answerLayout') or 'auto'}"
        )
    return '\n'.join(lines)


def _reference_mode_hint(intake_config: dict | None) -> str:
    from .services.exercise_workflow import source_entries

    rows = source_entries(intake_config)
    if not rows:
        return 'auto'
    layouts = {str(row.get('answerLayout') or 'auto') for row in rows}
    roles = {str(row.get('role') or 'auto') for row in rows}
    if 'question_and_answer' in roles and 'inline' in layouts:
        return 'full_qa'
    if 'answer_only' in roles and layouts & {'end', 'separate'}:
        return 'numbered_answers'
    return 'auto'

@shared_task(
    bind=True, max_retries=3, default_retry_delay=60, acks_late=True,
    soft_time_limit=PIPELINE_TASK_SOFT_TIME_LIMIT, time_limit=PIPELINE_TASK_TIME_LIMIT,
)
def extract_exercise_content(self, exercise_id: int) -> dict:
    """OCR the exercise's source assets, extract its structure, and persist rows.

    State machine: {DRAFT, FAILED} --(run)--> EXTRACTING --(ok)--> EXTRACTED
    (or --(error)--> FAILED). Idempotent: a status guard skips anything not in a
    runnable state, and a `cache.add` lock rejects a concurrent second dispatch.
    """
    from django.core.cache import cache
    from django.utils import timezone
    from .models import ClassExercise
    from .services.exercise_ingest import (
        apply_reference_preview_items,
        build_reference_ingest_preview,
        compact_existing_questions,
        ingest_reference_answers_markdown,
        ocr_assets_to_markdown,
        persist_exercise_structure,
        structure_exercise_markdown,
    )
    from .services.exercise_workflow import (
        SOURCE_ROLE_ANSWER_ONLY,
        SOURCE_ROLE_AUTO,
        SOURCE_ROLE_QUESTION_AND_ANSWER,
        SOURCE_ROLE_QUESTION_ONLY,
        build_workflow_state,
        source_entries,
        source_orders_for_roles,
        update_workflow_state,
    )

    exercise = ClassExercise.objects.filter(id=exercise_id).first()
    if exercise is None:
        return {'status': 'skipped', 'reason': 'exercise not found'}

    task_id = _current_task_id(self)
    if exercise.status == ClassExercise.Status.CANCELLED and exercise.cancel_requested:
        return {'status': 'cancelled', 'exercise_id': exercise_id, 'stopped_at': 'pre_start'}
    runnable = {
        ClassExercise.Status.DRAFT,
        ClassExercise.Status.FAILED,
        ClassExercise.Status.CANCELLED,
        ClassExercise.Status.EXTRACTED,
    }
    is_same_retry = (
        exercise.status == ClassExercise.Status.EXTRACTING
        and exercise.extract_task_id
        and exercise.extract_task_id == task_id
    )
    if exercise.status not in runnable and not is_same_retry:
        return {'status': 'skipped', 'reason': f'status={exercise.status}'}

    lock_key = f'exercise-extract:{exercise_id}'
    if not cache.add(lock_key, '1', timeout=PIPELINE_TASK_TIME_LIMIT):
        return {'status': 'skipped', 'reason': 'already dispatched'}

    try:
        if not is_same_retry:
            exercise.status = ClassExercise.Status.EXTRACTING
            exercise.extract_task_id = task_id
            exercise.cancel_requested = False
            exercise.workflow_state = build_workflow_state('reading_sources')
            exercise.save(update_fields=['status', 'extract_task_id', 'cancel_requested', 'workflow_state', 'updated_at'])

        if _exercise_extract_cancelled(exercise):
            return {'status': 'cancelled', 'exercise_id': exercise_id, 'stopped_at': 'start'}

        intake_config = exercise.intake_config if isinstance(exercise.intake_config, dict) else {}
        has_source_entries = bool(source_entries(intake_config))
        warnings: list[str] = []
        question_orders = source_orders_for_roles(
            intake_config,
            {SOURCE_ROLE_AUTO, SOURCE_ROLE_QUESTION_ONLY, SOURCE_ROLE_QUESTION_AND_ANSWER},
        )
        answer_orders = source_orders_for_roles(
            intake_config,
            {SOURCE_ROLE_QUESTION_AND_ANSWER, SOURCE_ROLE_ANSWER_ONLY},
        )
        if not question_orders and has_source_entries:
            raise RuntimeError('هیچ منبعی برای استخراج سوال‌های تمرین پیدا نشد.')

        update_workflow_state(exercise, 'ocr_and_transcription')
        markdown = ocr_assets_to_markdown(
            exercise,
            asset_orders=question_orders or None,
            preamble=_exercise_source_hint(intake_config),
        )
        if _exercise_extract_cancelled(exercise):
            return {'status': 'cancelled', 'exercise_id': exercise_id, 'stopped_at': 'ocr'}
        if not (markdown or '').strip():
            raise RuntimeError('از منابع سوال، متن قابل استفاده‌ای استخراج نشد.')

        update_workflow_state(exercise, 'extracting_questions')
        structure, _provider, _model = structure_exercise_markdown(ingest_markdown=markdown)
        if _exercise_extract_cancelled(exercise):
            return {'status': 'cancelled', 'exercise_id': exercise_id, 'stopped_at': 'structure'}
        n_sections, n_questions = persist_exercise_structure(exercise, structure)
        if _exercise_extract_cancelled(exercise):
            return {'status': 'cancelled', 'exercise_id': exercise_id, 'stopped_at': 'persist'}

        if answer_orders:
            update_workflow_state(exercise, 'matching_reference_answers')
            try:
                answer_markdown = ocr_assets_to_markdown(
                    exercise,
                    asset_orders=answer_orders or None,
                    preamble=_exercise_source_hint(intake_config),
                )
                if (answer_markdown or '').strip():
                    extracted, _p2, _m2 = ingest_reference_answers_markdown(
                        source_markdown=answer_markdown,
                        existing_questions=compact_existing_questions(exercise),
                        mode_hint=_reference_mode_hint(intake_config),
                    )
                    if _exercise_extract_cancelled(exercise):
                        return {'status': 'cancelled', 'exercise_id': exercise_id, 'stopped_at': 'answer_ingest'}
                    preview = build_reference_ingest_preview(
                        exercise=exercise,
                        extracted=extracted,
                    )
                    warnings.extend(str(w).strip() for w in preview.get('warnings') or [] if str(w).strip())
                    counts = preview.get('counts') or {}
                    auto_items = [
                        item for item in preview.get('items') or []
                        if isinstance(item, dict)
                        and item.get('matchStatus') == 'matched'
                        and str(item.get('referenceAnswerMarkdown') or '').strip()
                    ]
                    apply_result = apply_reference_preview_items(
                        exercise=exercise,
                        preview_items=auto_items,
                        replace_existing=False,
                    )
                    ambiguous = int(counts.get('ambiguous') or 0)
                    unmatched = int(counts.get('unmatched') or 0)
                    if ambiguous:
                        warnings.append(f'{ambiguous} پاسخ مرجع نیاز به بازبینی دستی دارد.')
                    if unmatched:
                        warnings.append(f'{unmatched} مورد پاسخ‌نامه به سوالی تطبیق داده نشد.')
                    if apply_result['appliedCount'] == 0:
                        warnings.append('پاسخ‌های مرجع این تمرین خودکار اعمال نشد و نیاز به بازبینی دارد.')
                else:
                    warnings.append('از منابع پاسخ‌نامه متن قابل استفاده‌ای استخراج نشد.')
            except Exception:
                logger.exception('Exercise reference ingest fallback warning for %s', exercise_id)
                warnings.append(
                    'پاسخ‌های مرجع این تمرین خودکار اعمال نشد و برای انتشار باید بازبینی شود.'
                )
        else:
            warnings.append('برای این تمرین پاسخ‌نامه‌ای تشخیص داده نشد؛ پیش از انتشار پاسخ‌های مرجع را بازبینی کنید.')

        update_workflow_state(exercise, 'building_review_draft', warnings=warnings)
        if _exercise_extract_cancelled(exercise):
            return {'status': 'cancelled', 'exercise_id': exercise_id, 'stopped_at': 'draft'}
        exercise.status = ClassExercise.Status.EXTRACTED
        exercise.workflow_state = build_workflow_state(
            'ready_for_review',
            warnings=warnings,
            ready_for_review=True,
        )
        exercise.cancel_requested = False
        exercise.save(update_fields=['status', 'cancel_requested', 'workflow_state', 'updated_at'])

        notified_now = (
            ClassExercise.objects.filter(
                id=exercise_id,
                review_ready_notified_at__isnull=True,
            )
            .update(review_ready_notified_at=timezone.now())
            > 0
        )
        if notified_now:
            try:
                send_exercise_review_ready_sms_task.delay(exercise.id)
            except Exception:
                logger.exception('Failed to queue exercise-ready SMS for %s', exercise.id)
        return {
            'status': 'extracted', 'exercise_id': exercise_id,
            'sections': n_sections, 'questions': n_questions,
            'warnings': warnings,
        }
    except Exception as exc:
        if is_transient_llm_error(exc) and self.request.retries < self.max_retries:
            countdown = _retry_countdown(self)
            logger.warning(
                'Exercise extraction transient failure for %s; retrying in %ss '
                '(attempt %s/%s): %s',
                exercise_id, countdown, self.request.retries + 1, self.max_retries + 1,
                str(exc)[:300],
            )
            raise self.retry(exc=exc, countdown=countdown)

        logger.exception('Exercise extraction failed for %s', exercise_id)
        ClassExercise.objects.filter(id=exercise_id).update(
            status=ClassExercise.Status.FAILED,
            workflow_state=build_workflow_state(
                'failed',
                warnings=['ساخت پیش‌نویس تمرین کامل نشد. دوباره تلاش کنید یا منابع را بازبینی کنید.'],
                ready_for_review=False,
            ),
        )
        return {'status': 'failed', 'exercise_id': exercise_id, 'reason': str(exc)}
    finally:
        cache.delete(lock_key)


# ---------------------------------------------------------------------------
# Student answer OCR preview. Runs on the dedicated interactive queue.
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=15, acks_late=True,
             soft_time_limit=20 * 60, time_limit=25 * 60)
def process_student_answer_source(self, source_id: int, revision: int) -> dict:
    """OCR one immutable source revision and discard stale task results."""
    from apps.commons.token_tracker import llm_tracking_context
    from .models import StudentExerciseAnswerSource
    from .services.exercise_answer_ocr import (
        StaleAnswerSource, mark_failed, process_source,
    )

    source = StudentExerciseAnswerSource.objects.select_related(
        'submission__exercise__session', 'submission__student',
    ).filter(id=source_id, revision=revision).first()
    if source is None:
        return {'status': 'stale', 'source_id': source_id, 'revision': revision}
    task_id = _current_task_id(self)
    StudentExerciseAnswerSource.objects.filter(id=source_id, revision=revision).update(
        processing_task_id=task_id,
    )
    try:
        with llm_tracking_context(
            user=source.submission.student,
            session_id=source.submission.exercise.session_id,
        ):
            result = process_source(source_id, revision)
    except StaleAnswerSource:
        return {'status': 'stale', 'source_id': source_id, 'revision': revision}
    except Exception as exc:
        if is_transient_llm_error(exc) and self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=_retry_countdown(self, base=15, cap=120))
        logger.exception('Student answer OCR failed for source %s revision %s', source_id, revision)
        mark_failed(source_id, revision)
        result = {'status': 'failed', 'source_id': source_id, 'revision': revision}

    # A submission may have been finalized while OCR was running. Wake grading
    # only after this frozen source reaches a terminal state; task guards keep
    # redelivery idempotent.
    source = StudentExerciseAnswerSource.objects.select_related('submission').filter(
        id=source_id, revision=revision,
    ).first()
    if source and source.submission.current_attempt_id:
        attempt = source.submission.current_attempt
        if attempt and attempt.status == attempt.Status.SUBMITTED:
            grade_exercise_submission.delay(source.submission_id, attempt.id)
    return result


# ---------------------------------------------------------------------------
# Exercise Hub — async grading (SUBMITTED -> GRADING -> GRADED / GRADING_FAILED).
# Runs on the `pipeline` queue. Design: docs/features/exercise-hub.md.
# ---------------------------------------------------------------------------

@shared_task(
    bind=True, max_retries=3, default_retry_delay=60, acks_late=True,
    soft_time_limit=PIPELINE_TASK_SOFT_TIME_LIMIT, time_limit=PIPELINE_TASK_TIME_LIMIT,
)
def grade_exercise_submission(self, submission_id: int, attempt_id: int | None = None) -> dict:
    """Grade one exercise submission with the LLM (+ deterministic MCQ/fill-blank).

    Guarded per attempt. Partial OCR/grading progress is persisted, and a retry
    resumes only unfinished questions. Old queued calls that only carry a
    submission id remain supported during the coordinated rollout.
    """
    from django.core.cache import cache
    from django.db import transaction
    from apps.commons.token_tracker import llm_tracking_context
    from .models import StudentExerciseAttempt, StudentExerciseSubmission
    from .services.exercise_grading import (
        grade_attempt, apply_grading_result, build_question_snapshot, grading_enabled,
    )
    from .services.exercise_answer_ocr import (
        AnswerSourceFailed, AnswerSourcePending, prepare_attempt_ocr,
    )

    submission = StudentExerciseSubmission.objects.filter(id=submission_id).first()
    if submission is None:
        return {'status': 'skipped', 'reason': 'submission not found'}

    with transaction.atomic():
        submission = StudentExerciseSubmission.objects.select_for_update().get(id=submission_id)
        attempt = None
        if attempt_id is not None:
            attempt = StudentExerciseAttempt.objects.filter(
                id=attempt_id, submission=submission,
            ).first()
        elif submission.current_attempt_id:
            attempt = StudentExerciseAttempt.objects.filter(
                id=submission.current_attempt_id, submission=submission,
            ).first()
        elif submission.status in {
            StudentExerciseSubmission.Status.SUBMITTED,
            StudentExerciseSubmission.Status.GRADING,
        }:
            latest = submission.attempts.order_by('-attempt_number').first()
            attempt = StudentExerciseAttempt.objects.create(
                submission=submission,
                attempt_number=(latest.attempt_number + 1) if latest else 1,
                status=(
                    StudentExerciseAttempt.Status.GRADING
                    if submission.status == StudentExerciseSubmission.Status.GRADING
                    else StudentExerciseAttempt.Status.SUBMITTED
                ),
                answers=submission.answers,
                question_snapshot=build_question_snapshot(submission.exercise),
                is_late=submission.is_late,
                grading_task_id=submission.grading_task_id,
            )
            submission.current_attempt = attempt
            submission.save(update_fields=['current_attempt', 'updated_at'])
    if attempt is None:
        return {'status': 'skipped', 'reason': 'attempt not found'}

    task_id = _current_task_id(self)
    is_same_retry = (
        attempt.status == StudentExerciseAttempt.Status.GRADING
        and attempt.grading_task_id
        and attempt.grading_task_id == task_id
    )
    if attempt.status != StudentExerciseAttempt.Status.SUBMITTED and not is_same_retry:
        return {'status': 'skipped', 'reason': f'status={attempt.status}'}
    if not grading_enabled():
        return {'status': 'skipped', 'reason': 'grading disabled'}

    lock_key = f'exercise-grade-attempt:{attempt.id}'
    if not cache.add(lock_key, '1', timeout=PIPELINE_TASK_TIME_LIMIT):
        return {'status': 'skipped', 'reason': 'already dispatched'}

    try:
        try:
            prepare_attempt_ocr(attempt)
        except AnswerSourcePending:
            return {
                'status': 'waiting_for_ocr', 'submission_id': submission_id,
                'attempt_id': attempt.id,
            }
        except AnswerSourceFailed:
            StudentExerciseAttempt.objects.filter(id=attempt.id).update(
                status=StudentExerciseAttempt.Status.GRADING_FAILED,
            )
            StudentExerciseSubmission.objects.filter(
                id=submission_id, current_attempt_id=attempt.id,
            ).update(status=StudentExerciseSubmission.Status.GRADING_FAILED)
            return {
                'status': 'failed', 'reason': 'answer_ocr_failed',
                'submission_id': submission_id, 'attempt_id': attempt.id,
            }

        if not is_same_retry:
            attempt.status = StudentExerciseAttempt.Status.GRADING
            attempt.grading_task_id = task_id
            attempt.save(update_fields=['status', 'grading_task_id', 'updated_at'])
            StudentExerciseSubmission.objects.filter(
                id=submission_id, current_attempt_id=attempt.id,
            ).update(
                status=StudentExerciseSubmission.Status.GRADING,
                grading_task_id=task_id,
            )

        with llm_tracking_context(
            user=submission.exercise.session.teacher,
            session_id=submission.exercise.session_id,
        ):
            result = grade_attempt(attempt)
        with transaction.atomic():
            locked_submission = StudentExerciseSubmission.objects.select_for_update().get(
                id=submission_id,
            )
            locked_attempt = StudentExerciseAttempt.objects.select_for_update().get(
                id=attempt.id,
                submission_id=submission_id,
            )
            if locked_attempt.status == StudentExerciseAttempt.Status.GRADED:
                # A duplicate redelivery finished after this worker started.
                # Keep any teacher override committed after that completion.
                attempt = locked_attempt
                projection_result = {
                    'per_question': locked_attempt.result.get('per_question', []),
                    'score_points': locked_attempt.score_points,
                    'max_points': locked_attempt.max_points,
                }
            elif (
                locked_attempt.status == StudentExerciseAttempt.Status.GRADING
                and locked_attempt.grading_task_id == task_id
            ):
                apply_grading_result(locked_attempt, result)
                locked_attempt.status = StudentExerciseAttempt.Status.GRADED
                locked_attempt.save(update_fields=[
                    'status', 'result', 'score_points', 'max_points', 'graded_at',
                    'updated_at',
                ])
                attempt = locked_attempt
                projection_result = result
            else:
                return {
                    'status': 'skipped',
                    'reason': f'status={locked_attempt.status}',
                    'submission_id': submission_id,
                    'attempt_id': locked_attempt.id,
                }

            if (
                locked_submission.current_attempt_id == attempt.id
                and locked_submission.status == StudentExerciseSubmission.Status.GRADING
            ):
                apply_grading_result(locked_submission, projection_result)
                locked_submission.status = StudentExerciseSubmission.Status.GRADED
                locked_submission.grading_task_id = attempt.grading_task_id
                locked_submission.overridden_at = attempt.overridden_at
                locked_submission.save(update_fields=[
                    'status', 'result', 'score_points', 'max_points', 'graded_at',
                    'grading_task_id', 'overridden_at', 'updated_at',
                ])
        return {
            'status': 'graded', 'submission_id': submission_id, 'attempt_id': attempt.id,
            'score_points': str(attempt.score_points),
        }
    except Exception as exc:
        if is_transient_llm_error(exc) and self.request.retries < self.max_retries:
            countdown = _retry_countdown(self)
            logger.warning(
                'Exercise grading transient failure for %s; retrying in %ss '
                '(attempt %s/%s): %s',
                submission_id, countdown, self.request.retries + 1, self.max_retries + 1,
                str(exc)[:300],
            )
            raise self.retry(exc=exc, countdown=countdown)

        logger.exception('Exercise grading failed for %s', submission_id)
        StudentExerciseAttempt.objects.filter(id=attempt.id).update(
            status=StudentExerciseAttempt.Status.GRADING_FAILED,
        )
        StudentExerciseSubmission.objects.filter(
            id=submission_id, current_attempt_id=attempt.id,
        ).update(
            status=StudentExerciseSubmission.Status.GRADING_FAILED,
        )
        return {
            'status': 'failed', 'submission_id': submission_id,
            'attempt_id': attempt.id, 'reason': str(exc),
        }
    finally:
        cache.delete(lock_key)
