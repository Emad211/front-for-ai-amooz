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

import json
import logging
import os
import tempfile
import time

from celery import shared_task
from celery.exceptions import Retry as CeleryRetry

logger = logging.getLogger(__name__)


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


def _run_pipeline_step(
    step_fn,
    step_label: str,
    session_id: int,
    session,
    *,
    max_attempts: int = 4,
    base_delay: int = 30,
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

        except (CeleryRetry, Exception) as exc:
            is_last = attempt >= max_attempts
            exc_msg = str(exc)[:300]

            if is_last:
                logger.error(
                    'Pipeline step %s failed after %d attempts for session %s: %s',
                    step_label, max_attempts, session_id, exc_msg,
                )
                session.refresh_from_db()
                if session.status != session.Status.FAILED:
                    session.status = session.Status.FAILED
                    session.error_detail = f'{step_label}: {exc_msg}'
                    session.save(update_fields=['status', 'error_detail', 'updated_at'])
                return False

            delay = min(base_delay * (2 ** (attempt - 1)), 300)
            logger.warning(
                'Pipeline step %s attempt %d/%d failed for session %s: %s — retrying in %ds',
                step_label, attempt, max_attempts, session_id, exc_msg, delay,
            )
            time.sleep(delay)
            session.refresh_from_db()
            if session.status == session.Status.FAILED:
                # Something else marked it failed — abort.
                return False

    return False  # pragma: no cover


# ---------------------------------------------------------------------------
# CLASS pipeline tasks (steps 1-5 + full pipeline)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def process_class_step1_transcription(self, session_id: int) -> dict:
    """Transcribe uploaded media for a class creation session."""
    from .models import ClassCreationSession
    from .services.transcription import transcribe_media_bytes

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.TRANSCRIBING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}

    tmp_path: str | None = None
    try:
        tmp_path = _read_session_file_to_disk(session)
        data = _read_file_bytes(tmp_path)

        transcript, provider, model_name = transcribe_media_bytes(
            data=data,
            mime_type=session.source_mime_type or 'application/octet-stream',
        )
        session.transcript_markdown = transcript
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.TRANSCRIBED
        session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'status', 'updated_at'])

        # Delete the uploaded source file to free disk space.
        # Only the transcript text is needed from this point on.
        _cleanup_source_file(session)

        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            tmp_path = None
        # Mark failed only on final retry.
        if self.request.retries >= self.max_retries:
            session.refresh_from_db()
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
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
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز متن درس آماده نیست.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
        return {'status': 'failed', 'error': session.error_detail}

    try:
        structure_obj, provider, model_name = structure_transcript_markdown(
            transcript_markdown=session.transcript_markdown,
        )
        session.structure_json = json.dumps(structure_obj, ensure_ascii=False)
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.STRUCTURED
        session.save(update_fields=['structure_json', 'llm_provider', 'llm_model', 'status', 'updated_at'])
        sync_structure_from_session(session=session)
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            session.refresh_from_db()
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def process_class_step3_prerequisites(self, session_id: int) -> dict:
    """Extract prerequisites from transcript."""
    from .models import ClassCreationSession, ClassPrerequisite
    from .services.prerequisites import extract_prerequisites

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.PREREQ_EXTRACTING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز متن درس آماده نیست.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
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
        session.save(update_fields=['llm_provider', 'llm_model', 'status', 'updated_at'])
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            session.refresh_from_db()
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def process_class_step4_prereq_teaching(self, session_id: int, prerequisite_name: str | None = None) -> dict:
    """Generate teaching notes for prerequisites."""
    from .models import ClassCreationSession, ClassPrerequisite
    from .services.prerequisites import generate_prerequisite_teaching

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.PREREQ_TEACHING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}

    qs = ClassPrerequisite.objects.filter(session=session).order_by('order')
    if prerequisite_name:
        qs = qs.filter(name=prerequisite_name)
    if not qs.exists():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'پیش نیازها یافت نشدند. ابتدا مرحله پیش نیازها را اجرا کنید.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
        return {'status': 'failed', 'error': session.error_detail}

    try:
        provider = model_name = ''
        for prereq in qs:
            teaching, provider, model_name = generate_prerequisite_teaching(prerequisite_name=prereq.name)
            prereq.teaching_text = teaching
            prereq.save(update_fields=['teaching_text'])

        if provider:
            session.llm_provider = provider
        if model_name:
            session.llm_model = model_name
        session.status = ClassCreationSession.Status.PREREQ_TAUGHT
        session.save(update_fields=['llm_provider', 'llm_model', 'status', 'updated_at'])
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            session.refresh_from_db()
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def process_class_step5_recap(self, session_id: int) -> dict:
    """Generate recap markdown from structured content."""
    from .models import ClassCreationSession
    from .services.recap import generate_recap_from_structure, recap_json_to_markdown

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.RECAPPING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}
    if not (session.structure_json or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز ساختار مرحله ۲ آماده نیست.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
        return {'status': 'failed', 'error': session.error_detail}

    try:
        recap_obj, provider, model_name = generate_recap_from_structure(structure_json=session.structure_json)
        session.recap_markdown = recap_json_to_markdown(recap_obj)
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.RECAPPED
        session.save(update_fields=['recap_markdown', 'llm_provider', 'llm_model', 'status', 'updated_at'])
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            session.refresh_from_db()
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=0, acks_late=True)
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

    # Step 1
    if session.status == ClassCreationSession.Status.TRANSCRIBING:
        if not _run_pipeline_step(process_class_step1_transcription, 'step1_transcription', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step1'}

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step1'}

    # Step 2
    if session.status == ClassCreationSession.Status.TRANSCRIBED:
        session.status = ClassCreationSession.Status.STRUCTURING
        session.save(update_fields=['status', 'updated_at'])
        if not _run_pipeline_step(process_class_step2_structure, 'step2_structure', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step2'}

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step2'}

    # Step 3
    if session.status == ClassCreationSession.Status.STRUCTURED:
        session.status = ClassCreationSession.Status.PREREQ_EXTRACTING
        session.save(update_fields=['status', 'updated_at'])
        if not _run_pipeline_step(process_class_step3_prerequisites, 'step3_prerequisites', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step3'}

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step3'}

    # Step 4
    if session.status == ClassCreationSession.Status.PREREQ_EXTRACTED:
        session.status = ClassCreationSession.Status.PREREQ_TEACHING
        session.save(update_fields=['status', 'updated_at'])
        if not _run_pipeline_step(process_class_step4_prereq_teaching, 'step4_prereq_teaching', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step4'}

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step4'}

    # Step 5
    if session.status == ClassCreationSession.Status.PREREQ_TAUGHT:
        session.status = ClassCreationSession.Status.RECAPPING
        session.save(update_fields=['status', 'updated_at'])
        if not _run_pipeline_step(process_class_step5_recap, 'step5_recap', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step5'}

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step5'}

    logger.info('Full pipeline completed for session %s', session_id)
    return {'status': 'success', 'session_id': session_id}


# ---------------------------------------------------------------------------
# EXAM PREP pipeline tasks (steps 1-2 + full pipeline)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def process_exam_prep_step1_transcription(self, session_id: int) -> dict:
    """Transcribe uploaded media for exam prep pipeline."""
    from .models import ClassCreationSession
    from .services.transcription import transcribe_media_bytes

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}
    if session.status != ClassCreationSession.Status.EXAM_TRANSCRIBING:
        return {'status': 'skipped', 'reason': f'unexpected status {session.status}'}

    tmp_path: str | None = None
    try:
        tmp_path = _read_session_file_to_disk(session)
        data = _read_file_bytes(tmp_path)

        transcript, provider, model_name = transcribe_media_bytes(
            data=data,
            mime_type=session.source_mime_type or 'application/octet-stream',
        )
        session.transcript_markdown = transcript
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.EXAM_TRANSCRIBED
        session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'status', 'updated_at'])

        # Delete the uploaded source file to free disk space.
        _cleanup_source_file(session)

        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            tmp_path = None
        if self.request.retries >= self.max_retries:
            session.refresh_from_db()
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
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
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز ترنسکریپت مرحله ۱ آماده نیست.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
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
        session.save(update_fields=['exam_prep_json', 'llm_provider', 'llm_model', 'status', 'updated_at'])
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            session.refresh_from_db()
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return {'status': 'failed', 'error': str(exc)}
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=0, acks_late=True)
def process_exam_prep_full_pipeline(self, session_id: int) -> dict:
    """Run exam prep steps 1-2 sequentially with inline retry logic."""
    from .models import ClassCreationSession

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return {'status': 'skipped', 'reason': 'session not found'}

    # Step 1
    if session.status == ClassCreationSession.Status.EXAM_TRANSCRIBING:
        if not _run_pipeline_step(process_exam_prep_step1_transcription, 'step1_transcription', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step1'}

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step1'}

    # Step 2
    if session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED:
        session.status = ClassCreationSession.Status.EXAM_STRUCTURING
        session.save(update_fields=['status', 'updated_at'])
        if not _run_pipeline_step(process_exam_prep_step2_structure, 'step2_structure', session_id, session):
            return {'status': 'failed', 'stopped_at': 'step2'}

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return {'status': 'failed', 'stopped_at': 'step2'}

    logger.info('Exam-prep pipeline completed for session %s', session_id)
    return {'status': 'success', 'session_id': session_id}


# ---------------------------------------------------------------------------
# Lightweight tasks (SMS, notifications, etc.)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=5, acks_late=True)
def send_publish_sms_task(self, session_id: int) -> dict:
    """Send publish SMS notifications to invited students.

    Uses exponential back-off: 30 s → 60 s → 120 s → 240 s → 480 s.
    """
    from .services.mediana_sms import send_publish_sms_for_session

    try:
        send_publish_sms_for_session(session_id)
        return {'status': 'success', 'session_id': session_id}
    except Exception as exc:
        logger.error('SMS send failed for session %s (attempt %s/%s): %s',
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

    try:
        send_invite_sms_for_ids(session_id, invite_ids)
        return {'status': 'success', 'session_id': session_id, 'invite_count': len(invite_ids)}
    except Exception as exc:
        logger.error('New-invite SMS failed for session %s (attempt %s/%s): %s',
                     session_id, self.request.retries + 1, self.max_retries + 1,
                     str(exc)[:200])
        if self.request.retries >= self.max_retries:
            return {'status': 'failed', 'error': str(exc)[:500]}
        backoff = 30 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)
