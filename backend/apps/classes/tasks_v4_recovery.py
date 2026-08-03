"""Periodic fail-closed recovery for stale Exam Prep V4 extraction runs."""
from __future__ import annotations

from datetime import timedelta
import os

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.classes.models_v4 import ExamProject
from apps.classes.services.exam_prep_v4_observability import emit_v4_event


_ACTIVE_STATUSES = (
    ExamProject.Status.SEGMENTING,
    ExamProject.Status.EXTRACTING_QUESTIONS,
    ExamProject.Status.EXTRACTING_ANSWERS,
    ExamProject.Status.MATCHING,
)


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _last_activity(project: ExamProject):
    state = project.workflow_state if isinstance(project.workflow_state, dict) else {}
    raw = str(state.get('lastEventAt') or '').strip()
    parsed = parse_datetime(raw) if raw else None
    if parsed is not None:
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    return project.updated_at


@shared_task(
    queue='default',
    acks_late=True,
    reject_on_worker_lost=True,
)
def recover_exam_prep_v4_stale_runs(
    max_age_minutes: int | None = None,
    limit: int = 200,
) -> dict:
    """Mark stale active runs failed and request cooperative worker stop."""

    selected_age = max_age_minutes or _positive_int_env(
        'EXAM_PREP_V4_STALE_RUN_MINUTES',
        120,
    )
    selected_limit = min(1000, max(1, int(limit)))
    cutoff = timezone.now() - timedelta(minutes=selected_age)
    candidate_ids = list(
        ExamProject.objects.filter(status__in=_ACTIVE_STATUSES)
        .order_by('updated_at')
        .values_list('id', flat=True)[:selected_limit]
    )

    recovered_ids: list[int] = []
    for project_id in candidate_ids:
        with transaction.atomic():
            project = (
                ExamProject.objects.select_for_update()
                .filter(id=project_id, status__in=_ACTIVE_STATUSES)
                .first()
            )
            if project is None or _last_activity(project) >= cutoff:
                continue
            state = (
                dict(project.workflow_state)
                if isinstance(project.workflow_state, dict)
                else {}
            )
            previous_stage = str(state.get('stage') or '')[:64]
            state.update(
                {
                    'stage': 'stale_extraction_recovered',
                    'previousStage': previous_stage,
                    'cancellationRequested': True,
                    'lastEventAt': timezone.now().isoformat(),
                    'errorCode': 'stale_extraction_run',
                }
            )
            project.status = ExamProject.Status.FAILED
            project.cancel_requested = True
            project.error_code = 'stale_extraction_run'
            project.error_detail = 'Extraction run exceeded the stale activity window.'
            project.workflow_state = state
            project.save(
                update_fields=[
                    'status',
                    'cancel_requested',
                    'error_code',
                    'error_detail',
                    'workflow_state',
                    'updated_at',
                ]
            )
            recovered_ids.append(project.id)
            emit_v4_event(
                'exam_prep_v4.extraction.stale_run_recovered',
                projectId=project.id,
                runId=state.get('runId'),
                taskId=state.get('taskId'),
                previousStage=previous_stage,
                maxAgeMinutes=selected_age,
                errorCode='stale_extraction_run',
            )

    return {
        'status': 'completed',
        'candidateCount': len(candidate_ids),
        'recoveredCount': len(recovered_ids),
        'projectIds': recovered_ids,
        'maxAgeMinutes': selected_age,
    }
