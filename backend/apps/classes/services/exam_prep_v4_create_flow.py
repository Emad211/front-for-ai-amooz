"""Compatibility helpers for the existing teacher exam-preparation create flow."""
from __future__ import annotations

from typing import Any

from celery import current_app
from django.db import transaction
from django.utils import timezone

from apps.classes.models import ClassCreationSession
from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.models_v4_bridge import ExamV4SessionBridge
from apps.classes.models_v4_projection import ExamV4Projection


_ACTIVE_PROJECT_STATUSES = {
    ExamProject.Status.DRAFT,
    ExamProject.Status.UPLOADING,
    ExamProject.Status.CLASSIFYING,
    ExamProject.Status.AWAITING_SOURCE_CONFIRMATION,
    ExamProject.Status.SEGMENTING,
    ExamProject.Status.EXTRACTING_QUESTIONS,
    ExamProject.Status.EXTRACTING_ANSWERS,
    ExamProject.Status.MATCHING,
}


def _project_state(project: ExamProject) -> dict[str, Any]:
    return dict(project.workflow_state) if isinstance(project.workflow_state, dict) else {}


def _legacy_status(project: ExamProject) -> str:
    if project.status == ExamProject.Status.FAILED:
        return ClassCreationSession.Status.FAILED
    if project.status == ExamProject.Status.CANCELLED:
        return ClassCreationSession.Status.CANCELLED
    if project.status == ExamProject.Status.PUBLISHED:
        return ClassCreationSession.Status.EXAM_STRUCTURED
    if project.status in {
        ExamProject.Status.AWAITING_REVIEW,
        ExamProject.Status.READY_TO_PUBLISH,
    }:
        return ClassCreationSession.Status.EXAM_TRANSCRIBED
    if project.status in {
        ExamProject.Status.SEGMENTING,
        ExamProject.Status.EXTRACTING_QUESTIONS,
        ExamProject.Status.EXTRACTING_ANSWERS,
        ExamProject.Status.MATCHING,
    }:
        return ClassCreationSession.Status.EXAM_STRUCTURING
    return ClassCreationSession.Status.EXAM_TRANSCRIBING


def _legacy_workflow(project: ExamProject) -> dict[str, Any]:
    state = _project_state(project)
    progress = max(0, min(100, int(state.get('progressPercent') or 0)))
    message = str(state.get('message') or '').strip()
    warnings: list[str] = []
    warning_count = max(0, int(state.get('warningCount') or 0))
    if warning_count:
        warnings.append(f'{warning_count} مورد برای بررسی ثبت شده است.')

    if project.status == ExamProject.Status.FAILED:
        stage = 'failed'
        message = message or 'پردازش فایل کامل نشد.'
    elif project.status == ExamProject.Status.CANCELLED:
        stage = 'cancelled'
        message = message or 'پردازش متوقف شد.'
    elif project.status in {
        ExamProject.Status.AWAITING_REVIEW,
        ExamProject.Status.READY_TO_PUBLISH,
        ExamProject.Status.PUBLISHED,
    }:
        stage = 'ready_for_review'
        message = message or 'نتیجه برای بازبینی و انتشار آماده است.'
        progress = max(progress, 80 if project.status != ExamProject.Status.PUBLISHED else 100)
    elif project.status in {
        ExamProject.Status.SEGMENTING,
        ExamProject.Status.EXTRACTING_QUESTIONS,
        ExamProject.Status.EXTRACTING_ANSWERS,
        ExamProject.Status.MATCHING,
    }:
        stage = 'extracting_questions'
        message = message or 'در حال استخراج و تطبیق سؤال‌ها و پاسخ‌ها هستیم.'
        progress = max(progress, 35)
    else:
        stage = 'reading_source'
        message = message or 'در حال بررسی ساختار صفحات PDF هستیم.'
        progress = max(progress, 10)

    return {
        'stage': stage,
        'progressPercent': progress,
        'message': message,
        'warnings': warnings,
        'readyForReview': stage == 'ready_for_review',
        # The student detail endpoint uses this stable project binding to
        # preserve protected V4 source-crop URLs from the projection.  Keep
        # the older sourceAwareProjectId key for the create-flow bridge.
        'v4ProjectId': project.id,
        'sourceAwareProjectId': project.id,
    }


def sync_create_flow_session(project: ExamProject) -> ClassCreationSession | None:
    """Mirror safe project progress into the pre-existing session-shaped UI contract."""

    bridge = (
        ExamV4SessionBridge.objects.select_related('session')
        .filter(project_id=project.id)
        .first()
    )
    if bridge is None:
        return None
    state = _project_state(project)
    page_count = sum(project.source_documents.values_list('page_count', flat=True))
    error_detail = ''
    if project.status == ExamProject.Status.FAILED:
        error_detail = 'پردازش PDF با خطا متوقف شد. دوباره تلاش کنید.'
    ClassCreationSession.objects.filter(id=bridge.session_id).update(
        title=project.title,
        description=project.description,
        status=_legacy_status(project),
        workflow_state=_legacy_workflow(project),
        source_page_count=page_count,
        celery_task_id=str(state.get('taskId') or '')[:255],
        cancel_requested=project.cancel_requested,
        error_detail=error_detail,
    )
    bridge.session.refresh_from_db()
    return bridge.session


def cancel_source_aware_project_for_session(session: ClassCreationSession) -> None:
    """Propagate the existing create-page cancel action to the source-aware run."""

    bridge = (
        ExamV4SessionBridge.objects.select_related('project')
        .filter(session_id=session.id)
        .first()
    )
    if bridge is None:
        return
    project = bridge.project
    if project.status in {
        ExamProject.Status.PUBLISHED,
        ExamProject.Status.CANCELLED,
    }:
        return
    state = _project_state(project)
    task_id = str(state.get('taskId') or '').strip()
    state.update(
        {
            'stage': 'cancellation_requested' if project.status in _ACTIVE_PROJECT_STATUSES else 'cancelled',
            'message': 'درخواست توقف پردازش ثبت شد.',
            'cancellationRequested': True,
            'lastEventAt': timezone.now().isoformat(),
        }
    )
    project.cancel_requested = True
    project.workflow_state = state
    if project.status not in _ACTIVE_PROJECT_STATUSES:
        project.status = ExamProject.Status.CANCELLED
    project.save(
        update_fields=['cancel_requested', 'workflow_state', 'status', 'updated_at']
    )
    if task_id:
        try:
            current_app.control.revoke(task_id, terminate=False)
        except Exception:
            pass


def bridge_payload(*, teacher, session_id: int) -> dict[str, Any]:
    bridge = (
        ExamV4SessionBridge.objects.select_related('project', 'session')
        .filter(
            session_id=session_id,
            session__teacher=teacher,
            project__teacher=teacher,
        )
        .first()
    )
    if bridge is None:
        raise ExamV4SessionBridge.DoesNotExist
    session = sync_create_flow_session(bridge.project) or bridge.session
    document = (
        ExamSourceDocument.objects.filter(project_id=bridge.project_id)
        .order_by('upload_order', 'id')
        .first()
    )
    return {
        'projectId': bridge.project_id,
        'sessionId': session.id,
        'documentId': document.id if document else None,
        'projectStatus': bridge.project.status,
        'sessionStatus': session.status,
    }


@transaction.atomic
def adopt_create_flow_projection(
    *,
    project_id: int,
    projection_payload: dict[str, Any],
) -> dict[str, Any]:
    """Move a freshly built projection onto the draft already used by the form.

    This preserves invites and keeps one visible exam-preparation item instead of
    creating a second session after review.
    """

    bridge = (
        ExamV4SessionBridge.objects.select_for_update()
        .select_related('session')
        .filter(project_id=project_id)
        .first()
    )
    if bridge is None:
        return projection_payload
    projection = (
        ExamV4Projection.objects.select_for_update()
        .select_related('session')
        .filter(project_id=project_id)
        .first()
    )
    if projection is None or projection.session_id == bridge.session_id:
        return {**projection_payload, 'sessionId': bridge.session_id}

    target = ClassCreationSession.objects.select_for_update().get(id=bridge.session_id)
    generated = projection.session
    if target.is_published:
        return projection_payload

    copied_fields = [
        'organization',
        'study_group',
        'title',
        'description',
        'pipeline_type',
        'level',
        'duration',
        'scheduled_at',
        'source_type',
        'source_mime_type',
        'source_original_name',
        'source_page_count',
        'status',
        'transcript_markdown',
        'workflow_state',
        'structure_json',
        'exam_prep_json',
        'recap_markdown',
        'llm_provider',
        'llm_model',
        'is_published',
        'published_at',
        'error_detail',
        'cancel_requested',
    ]
    for field in copied_fields:
        setattr(target, field, getattr(generated, field))
    target.save(update_fields=[*copied_fields, 'updated_at'])

    projection.session = target
    projection.save(update_fields=['session', 'updated_at'])
    generated.delete()
    return {**projection_payload, 'sessionId': target.id}
