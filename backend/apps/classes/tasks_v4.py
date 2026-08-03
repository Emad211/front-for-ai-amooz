"""Celery orchestration for Exam Prep V4.

Every source document is dispatched independently. Source preparation and
semantic extraction use separate idempotent tasks on the pipeline queue.
Production extraction emits content-free correlated events through
``exam_prep_v4_observability``.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import shutil
import tempfile
import uuid
from typing import Iterable

from celery import group, shared_task
from django.core.cache import cache
from django.utils import timezone

from apps.chatbot.services.llm_client import is_transient_llm_error
from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services.exam_prep_v4_live_pipeline import (
    StructuredLLMExamPrepV4Provider,
    run_document_extraction_pipeline,
)
from apps.classes.services.exam_prep_v4_observability import (
    ExtractionRunContext,
    ObservedExamPrepV4Provider,
    emit_v4_event,
    merge_project_workflow_state,
    new_extraction_run_id,
)
from apps.classes.services.exam_prep_v4_ocr_evidence import (
    wrap_with_optional_ocr_evidence,
)
from apps.classes.services.exam_prep_v4_source_pipeline import (
    prepare_and_classify_pdf_source,
)
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled


LOGGER = logging.getLogger('apps.classes.exam_prep_v4')
TASK_SOFT_LIMIT = int(os.getenv('EXAM_PREP_V4_TASK_SOFT_LIMIT_SECONDS', '3300'))
TASK_HARD_LIMIT = int(os.getenv('EXAM_PREP_V4_TASK_HARD_LIMIT_SECONDS', '3600'))
EXTRACTION_MAX_RETRIES = int(os.getenv('EXAM_PREP_V4_EXTRACTION_MAX_RETRIES', '2'))


@dataclass(frozen=True, slots=True)
class ExtractionDispatchResult:
    run_id: str
    task_id: str
    queued: bool
    reused: bool


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


def _is_exact_confirmed(document: ExamSourceDocument) -> bool:
    return bool(
        document.status == ExamSourceDocument.Status.CONFIRMED
        and document.teacher_confirmed_at is not None
        and document.teacher_confirmed_revision == document.classification_revision
        and document.teacher_confirmed_fingerprint
        and document.teacher_confirmed_fingerprint == document.source_map_fingerprint
    )


def _dispatch_key(document: ExamSourceDocument) -> str:
    return (
        f'exam-prep-v4-extraction-dispatch:{document.id}:'
        f'{document.classification_revision}:{document.source_map_fingerprint}'
    )


def _run_lock_key(document: ExamSourceDocument) -> str:
    return (
        f'exam-prep-v4-extraction-run:{document.id}:'
        f'{document.classification_revision}:{document.source_map_fingerprint}'
    )


def _existing_dispatch(project: ExamProject, document: ExamSourceDocument) -> ExtractionDispatchResult | None:
    state = project.workflow_state if isinstance(project.workflow_state, dict) else {}
    run_id = str(state.get('runId') or '').strip()
    task_id = str(state.get('taskId') or '').strip()
    same_revision = int(state.get('sourceMapRevision') or 0) == document.classification_revision
    same_fingerprint = (
        str(state.get('sourceMapFingerprintPrefix') or '')
        == str(document.source_map_fingerprint or '')[:12]
    )
    if not (run_id and task_id and same_revision and same_fingerprint):
        return None
    active = project.status in {
        ExamProject.Status.SEGMENTING,
        ExamProject.Status.EXTRACTING_QUESTIONS,
        ExamProject.Status.EXTRACTING_ANSWERS,
        ExamProject.Status.MATCHING,
    }
    completed = project.status in {
        ExamProject.Status.AWAITING_REVIEW,
        ExamProject.Status.READY_TO_PUBLISH,
        ExamProject.Status.PUBLISHED,
    }
    if not (active or completed):
        return None
    return ExtractionDispatchResult(
        run_id=run_id,
        task_id=task_id,
        queued=active,
        reused=True,
    )


def dispatch_exam_prep_v4_extraction(
    document_id: int,
    *,
    force: bool = False,
    run_id: str | None = None,
) -> ExtractionDispatchResult:
    """Queue one exact confirmed document revision, refusing duplicate active work."""

    document = (
        ExamSourceDocument.objects.select_related('project')
        .filter(id=document_id)
        .first()
    )
    if document is None:
        raise ExamSourceDocument.DoesNotExist
    project = document.project
    if not _is_exact_confirmed(document):
        raise ValueError('The current source map must be confirmed before extraction.')

    existing = _existing_dispatch(project, document)
    if existing is not None and (existing.queued or not force):
        context = ExtractionRunContext(
            run_id=existing.run_id,
            task_id=existing.task_id,
            project_id=project.id,
            document_id=document.id,
            source_map_revision=document.classification_revision,
            source_map_fingerprint=document.source_map_fingerprint,
        )
        emit_v4_event(
            'exam_prep_v4.extraction.dispatch_reused',
            context=context,
            status=project.status,
        )
        return existing

    selected_run_id = str(run_id or new_extraction_run_id())
    selected_task_id = str(uuid.uuid4())
    context = ExtractionRunContext(
        run_id=selected_run_id,
        task_id=selected_task_id,
        project_id=project.id,
        document_id=document.id,
        source_map_revision=document.classification_revision,
        source_map_fingerprint=document.source_map_fingerprint,
    )
    key = _dispatch_key(document)
    if not cache.add(key, selected_task_id, timeout=10 * 60):
        project.refresh_from_db()
        existing = _existing_dispatch(project, document)
        if existing is not None:
            emit_v4_event(
                'exam_prep_v4.extraction.dispatch_reused',
                context=ExtractionRunContext(
                    run_id=existing.run_id,
                    task_id=existing.task_id,
                    project_id=project.id,
                    document_id=document.id,
                    source_map_revision=document.classification_revision,
                    source_map_fingerprint=document.source_map_fingerprint,
                ),
                status=project.status,
            )
            return existing
        raise RuntimeError('Extraction dispatch is already being created.')

    emit_v4_event(
        'exam_prep_v4.extraction.dispatch_requested',
        context=context,
        force=force,
    )
    merge_project_workflow_state(
        project_id=project.id,
        context=context,
        stage='extraction_queued',
        progress_percent=32,
        status=ExamProject.Status.SEGMENTING,
        warning_count=0,
        message='استخراج سؤال و پاسخ در صف پردازش قرار گرفت.',
    )
    try:
        process_exam_prep_v4_extraction.apply_async(
            args=[document.id, selected_run_id],
            task_id=selected_task_id,
            queue='pipeline',
        )
    except Exception:
        cache.delete(key)
        ExamProject.objects.filter(id=project.id).update(
            status=ExamProject.Status.FAILED,
            error_code='extraction_dispatch_failed',
            error_detail='Extraction task could not be queued.',
            workflow_state={
                **(
                    project.workflow_state
                    if isinstance(project.workflow_state, dict)
                    else {}
                ),
                'stage': 'extraction_dispatch_failed',
                'progressPercent': 32,
                'runId': selected_run_id,
                'taskId': selected_task_id,
                'sourceMapRevision': document.classification_revision,
                'sourceMapFingerprintPrefix': document.source_map_fingerprint[:12],
                'lastEventAt': timezone.now().isoformat(),
            },
        )
        emit_v4_event(
            'exam_prep_v4.extraction.task_failed',
            context=context,
            level=logging.ERROR,
            stage='dispatch',
            errorCode='extraction_dispatch_failed',
        )
        raise

    return ExtractionDispatchResult(
        run_id=selected_run_id,
        task_id=selected_task_id,
        queued=True,
        reused=False,
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


@shared_task(
    bind=True,
    max_retries=EXTRACTION_MAX_RETRIES,
    default_retry_delay=45,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=TASK_SOFT_LIMIT,
    time_limit=TASK_HARD_LIMIT,
    queue='pipeline',
)
def process_exam_prep_v4_extraction(
    self,
    document_id: int,
    run_id: str,
) -> dict:
    """Run the current confirmed V4 block/record/matching pipeline."""

    task_id = str(self.request.id or '')
    attempt = int(self.request.retries or 0) + 1
    document = (
        ExamSourceDocument.objects.select_related('project')
        .filter(id=document_id)
        .first()
    )
    if document is None:
        emit_v4_event(
            'exam_prep_v4.extraction.task_skipped',
            runId=run_id,
            taskId=task_id,
            documentId=document_id,
            reasonCode='document_not_found',
        )
        return {'status': 'skipped', 'reason': 'document_not_found'}

    context = ExtractionRunContext(
        run_id=str(run_id),
        task_id=task_id,
        project_id=document.project_id,
        document_id=document.id,
        source_map_revision=document.classification_revision,
        source_map_fingerprint=document.source_map_fingerprint,
        attempt=attempt,
    )
    lock_key = _run_lock_key(document)
    if not cache.add(lock_key, task_id, timeout=TASK_HARD_LIMIT + 300):
        emit_v4_event(
            'exam_prep_v4.extraction.task_skipped',
            context=context,
            reasonCode='already_processing',
        )
        return {'status': 'skipped', 'reason': 'already_processing', 'run_id': run_id}

    started = timezone.now()
    provider: ObservedExamPrepV4Provider | None = None
    try:
        if not exam_prep_v4_enabled():
            emit_v4_event(
                'exam_prep_v4.extraction.task_skipped',
                context=context,
                reasonCode='v4_disabled',
            )
            return {'status': 'skipped', 'reason': 'v4_disabled', 'run_id': run_id}
        if document.project.cancel_requested:
            emit_v4_event(
                'exam_prep_v4.extraction.task_skipped',
                context=context,
                reasonCode='cancel_requested',
            )
            return {'status': 'skipped', 'reason': 'cancel_requested', 'run_id': run_id}
        if not _is_exact_confirmed(document):
            emit_v4_event(
                'exam_prep_v4.extraction.task_skipped',
                context=context,
                reasonCode='source_map_not_currently_confirmed',
            )
            return {
                'status': 'skipped',
                'reason': 'source_map_not_currently_confirmed',
                'run_id': run_id,
            }

        emit_v4_event(
            'exam_prep_v4.extraction.task_started',
            context=context,
            pageCount=document.page_count,
        )
        merge_project_workflow_state(
            project_id=document.project_id,
            context=context,
            stage='extraction_started',
            progress_percent=34,
            status=ExamProject.Status.SEGMENTING,
            warning_count=0,
            message='استخراج ساختاریافته آغاز شد.',
            counters={'pageCount': document.page_count},
        )

        structured = StructuredLLMExamPrepV4Provider()
        selected = wrap_with_optional_ocr_evidence(structured)
        provider = ObservedExamPrepV4Provider(delegate=selected, context=context)
        result = run_document_extraction_pipeline(
            document_id=document.id,
            provider=provider,
        )

        warning_count = (
            len(result.issues)
            + result.matches.unresolved_count
            + result.matches.ambiguous_count
            + result.matches.conflict_count
        )
        counters = {
            'blockCount': result.block_set.block_count,
            'fragmentCount': result.block_set.fragment_count,
            'questionCount': result.question_set.record_count,
            'answerSolutionCount': result.answer_set.record_count,
            'matchedCount': result.matches.matched_count,
            'outOfScopeCount': result.matches.out_of_scope_count,
            'unresolvedCount': result.matches.unresolved_count,
            'ambiguousCount': result.matches.ambiguous_count,
            'conflictCount': result.matches.conflict_count,
            'issueCount': len(result.issues),
            **provider.safe_provider_metrics(),
        }
        merge_project_workflow_state(
            project_id=document.project_id,
            context=context,
            stage='awaiting_review',
            progress_percent=80,
            status=ExamProject.Status.AWAITING_REVIEW,
            warning_count=warning_count,
            message='استخراج و اتصال رکوردها کامل شد و آمادهٔ بازبینی است.',
            counters=counters,
        )
        elapsed_ms = round((timezone.now() - started).total_seconds() * 1000, 2)
        emit_v4_event(
            'exam_prep_v4.extraction.task_completed',
            context=context,
            elapsedMs=elapsed_ms,
            warningCount=warning_count,
            **counters,
        )
        return {
            'status': 'awaiting_review',
            'run_id': context.run_id,
            'task_id': context.task_id,
            'project_id': context.project_id,
            'document_id': context.document_id,
            **counters,
        }
    except Exception as exc:
        transient = is_transient_llm_error(exc)
        if transient and self.request.retries < self.max_retries:
            countdown = min(300, 45 * (2 ** self.request.retries))
            merge_project_workflow_state(
                project_id=document.project_id,
                context=context,
                stage='extraction_retrying',
                progress_percent=34,
                status=ExamProject.Status.SEGMENTING,
                message='خطای موقت سرویس رخ داد و پردازش دوباره تلاش می‌شود.',
                counters={
                    'providerCalls': provider.provider_calls if provider else 0,
                    'retryCountdownSeconds': countdown,
                },
            )
            emit_v4_event(
                'exam_prep_v4.extraction.task_retried',
                context=context,
                level=logging.WARNING,
                errorCode=type(exc).__name__,
                countdownSeconds=countdown,
                providerCalls=provider.provider_calls if provider else 0,
            )
            raise self.retry(exc=exc, countdown=countdown)

        state = (
            dict(document.project.workflow_state)
            if isinstance(document.project.workflow_state, dict)
            else {}
        )
        state.update(
            {
                'stage': 'extraction_failed',
                'progressPercent': max(34, int(state.get('progressPercent') or 0)),
                'runId': context.run_id,
                'taskId': context.task_id,
                'attempt': context.attempt,
                'sourceMapRevision': context.source_map_revision,
                'sourceMapFingerprintPrefix': context.fingerprint_prefix,
                'lastEventAt': timezone.now().isoformat(),
                'providerCalls': provider.provider_calls if provider else 0,
                'errorCode': type(exc).__name__[:64],
            }
        )
        ExamProject.objects.filter(id=document.project_id).update(
            status=ExamProject.Status.FAILED,
            error_code='exam_v4_extraction_failed',
            error_detail=f'Extraction failed with {type(exc).__name__}.',
            workflow_state=state,
        )
        emit_v4_event(
            'exam_prep_v4.extraction.task_failed',
            context=context,
            level=logging.ERROR,
            elapsedMs=round((timezone.now() - started).total_seconds() * 1000, 2),
            errorCode=type(exc).__name__,
            transient=transient,
            providerCalls=provider.provider_calls if provider else 0,
        )
        return {
            'status': 'failed',
            'run_id': context.run_id,
            'task_id': context.task_id,
            'error_code': type(exc).__name__,
        }
    finally:
        cache.delete(lock_key)
        cache.delete(_dispatch_key(document))


def dispatch_exam_prep_v4_sources(document_ids: Iterable[int]) -> str:
    """Publish one source-preparation task per document in a Celery group."""

    ids = [int(document_id) for document_id in document_ids]
    if not ids:
        raise ValueError('At least one document id is required for dispatch.')
    result = group(
        process_exam_prep_v4_source.s(document_id)
        for document_id in ids
    ).apply_async()
    return str(result.id)
