"""Owner-scoped production extraction control endpoints for V4."""
from __future__ import annotations

from typing import Any

from celery import current_app
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.permissions import IsTeacherUser
from apps.classes.services.exam_prep_v4_observability import (
    ExtractionRunContext,
    emit_v4_event,
)
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled
from apps.classes.tasks_v4 import dispatch_exam_prep_v4_extraction


_ACTIVE_STATUSES = {
    ExamProject.Status.SEGMENTING,
    ExamProject.Status.EXTRACTING_QUESTIONS,
    ExamProject.Status.EXTRACTING_ANSWERS,
    ExamProject.Status.MATCHING,
}
_TERMINAL_STATUSES = {
    ExamProject.Status.AWAITING_REVIEW,
    ExamProject.Status.READY_TO_PUBLISH,
    ExamProject.Status.PUBLISHED,
    ExamProject.Status.CANCELLED,
    ExamProject.Status.FAILED,
}
_SAFE_COUNTERS = (
    'pageCount',
    'segmentCount',
    'blockCount',
    'fragmentCount',
    'questionCount',
    'answerSolutionCount',
    'matchedCount',
    'outOfScopeCount',
    'unresolvedCount',
    'ambiguousCount',
    'conflictCount',
    'issueCount',
    'providerCalls',
    'ocrCalls',
    'ocrRetries',
    'ocrFallbackCount',
    'ocrBboxCalls',
    'retryCountdownSeconds',
)


def _require_v4() -> None:
    if not exam_prep_v4_enabled():
        raise Http404


def _owned_document(*, teacher, project_id: int, document_id: int):
    document = (
        ExamSourceDocument.objects.select_related('project')
        .filter(
            id=document_id,
            project_id=project_id,
            project__teacher=teacher,
        )
        .first()
    )
    if document is None:
        raise Http404
    return document.project, document


def _nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _safe_runtime_payload(
    project: ExamProject,
    document: ExamSourceDocument,
) -> dict[str, Any]:
    state = project.workflow_state if isinstance(project.workflow_state, dict) else {}
    counters = {
        key: _nonnegative_int(state.get(key))
        for key in _SAFE_COUNTERS
        if state.get(key) is not None
    }
    run_id = str(state.get('runId') or '').strip()[:64] or None
    task_id = str(state.get('taskId') or '').strip()[:64] or None
    stage = str(state.get('stage') or '').strip().lower()[:64]
    last_event_at = str(state.get('lastEventAt') or '').strip()[:64] or None
    return {
        'projectId': project.id,
        'documentId': document.id,
        'projectStatus': project.status,
        'documentStatus': document.status,
        'active': project.status in _ACTIVE_STATUSES,
        'terminal': project.status in _TERMINAL_STATUSES,
        'retryable': bool(
            document.status == ExamSourceDocument.Status.CONFIRMED
            and document.teacher_confirmed_revision == document.classification_revision
            and document.teacher_confirmed_fingerprint
            == document.source_map_fingerprint
            and project.status != ExamProject.Status.PUBLISHED
        ),
        'cancellationRequested': bool(
            project.cancel_requested or state.get('cancellationRequested') is True
        ),
        'runId': run_id,
        'taskId': task_id,
        'attempt': max(1, _nonnegative_int(state.get('attempt'), 1)),
        'stage': stage,
        'progressPercent': min(100, _nonnegative_int(state.get('progressPercent'))),
        'warningCount': _nonnegative_int(state.get('warningCount')),
        'sourceMapRevision': document.classification_revision,
        'sourceMapFingerprintPrefix': document.source_map_fingerprint[:12] or None,
        'lastEventAt': last_event_at,
        'counters': counters,
        'errorCode': project.error_code or None,
        'updatedAt': project.updated_at,
    }


def _event_context(
    project: ExamProject,
    document: ExamSourceDocument,
) -> ExtractionRunContext | None:
    state = project.workflow_state if isinstance(project.workflow_state, dict) else {}
    run_id = str(state.get('runId') or '').strip()
    task_id = str(state.get('taskId') or '').strip()
    if not (run_id and task_id):
        return None
    return ExtractionRunContext(
        run_id=run_id,
        task_id=task_id,
        project_id=project.id,
        document_id=document.id,
        source_map_revision=document.classification_revision,
        source_map_fingerprint=document.source_map_fingerprint,
        attempt=max(1, _nonnegative_int(state.get('attempt'), 1)),
    )


class ExamPrepV4ExtractionStatusView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, project_id: int, document_id: int):
        _require_v4()
        project, document = _owned_document(
            teacher=request.user,
            project_id=project_id,
            document_id=document_id,
        )
        return Response(
            _safe_runtime_payload(project, document),
            status=status.HTTP_200_OK,
        )


class ExamPrepV4ExtractionRetryView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, project_id: int, document_id: int):
        _require_v4()
        project, document = _owned_document(
            teacher=request.user,
            project_id=project_id,
            document_id=document_id,
        )
        if project.status == ExamProject.Status.PUBLISHED:
            return Response(
                {
                    'code': 'extraction_retry_not_allowed',
                    'detail': 'آزمون منتشرشده قابل پردازش مجدد نیست.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            dispatch = dispatch_exam_prep_v4_extraction(
                document.id,
                force=True,
            )
        except ValueError:
            return Response(
                {
                    'code': 'source_map_not_confirmed',
                    'detail': 'ابتدا نسخهٔ فعلی نقشهٔ صفحات را تأیید کنید.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            return Response(
                {
                    'code': 'extraction_dispatch_failed',
                    'detail': 'ارسال پردازش مجدد به صف انجام نشد.',
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        project.refresh_from_db()
        payload = _safe_runtime_payload(project, document)
        payload['dispatch'] = {
            'runId': dispatch.run_id,
            'taskId': dispatch.task_id,
            'queued': dispatch.queued,
            'reused': dispatch.reused,
        }
        return Response(
            payload,
            status=(
                status.HTTP_202_ACCEPTED
                if dispatch.queued
                else status.HTTP_200_OK
            ),
        )


class ExamPrepV4ExtractionCancelView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, project_id: int, document_id: int):
        _require_v4()
        project, document = _owned_document(
            teacher=request.user,
            project_id=project_id,
            document_id=document_id,
        )
        if project.status == ExamProject.Status.PUBLISHED:
            return Response(
                {
                    'code': 'extraction_cancel_not_allowed',
                    'detail': 'آزمون منتشرشده قابل لغو نیست.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        if project.status == ExamProject.Status.CANCELLED:
            return Response(
                _safe_runtime_payload(project, document),
                status=status.HTTP_200_OK,
            )

        was_active = project.status in _ACTIVE_STATUSES
        state = (
            dict(project.workflow_state)
            if isinstance(project.workflow_state, dict)
            else {}
        )
        state.update(
            {
                'stage': 'cancellation_requested' if was_active else 'cancelled',
                'cancellationRequested': True,
                'lastEventAt': timezone.now().isoformat(),
            }
        )
        project.cancel_requested = True
        project.workflow_state = state
        if not was_active:
            project.status = ExamProject.Status.CANCELLED
        project.error_code = ''
        project.error_detail = ''
        update_fields = [
            'cancel_requested',
            'workflow_state',
            'error_code',
            'error_detail',
            'updated_at',
        ]
        if not was_active:
            update_fields.insert(0, 'status')
        project.save(update_fields=update_fields)

        context = _event_context(project, document)
        emit_v4_event(
            'exam_prep_v4.extraction.cancellation_requested',
            context=context,
            projectId=project.id,
            documentId=document.id,
            active=was_active,
        )
        task_id = str(state.get('taskId') or '').strip()
        if task_id:
            try:
                current_app.control.revoke(task_id, terminate=False)
            except Exception:
                emit_v4_event(
                    'exam_prep_v4.extraction.revoke_failed',
                    context=context,
                    projectId=project.id,
                    documentId=document.id,
                    errorCode='celery_revoke_failed',
                )

        project.refresh_from_db()
        return Response(
            _safe_runtime_payload(project, document),
            status=(
                status.HTTP_202_ACCEPTED
                if was_active
                else status.HTTP_200_OK
            ),
        )
