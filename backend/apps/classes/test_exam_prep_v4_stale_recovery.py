from __future__ import annotations

from datetime import timedelta
import uuid

import pytest
from django.utils import timezone
from model_bakery import baker

from apps.classes.models_v4 import ExamProject
from apps.classes.tasks_v4_recovery import recover_exam_prep_v4_stale_runs


pytestmark = pytest.mark.django_db


def test_stale_active_run_is_failed_closed_and_requests_worker_stop():
    teacher = baker.make('accounts.User', role='TEACHER')
    stale_time = timezone.now() - timedelta(hours=3)
    project = ExamProject.objects.create(
        teacher=teacher,
        title='Stale extraction fixture',
        status=ExamProject.Status.EXTRACTING_QUESTIONS,
        workflow_state={
            'stage': 'question_extraction',
            'progressPercent': 50,
            'runId': str(uuid.uuid4()),
            'taskId': str(uuid.uuid4()),
            'lastEventAt': stale_time.isoformat(),
        },
    )

    result = recover_exam_prep_v4_stale_runs.run(
        max_age_minutes=60,
        limit=10,
    )

    project.refresh_from_db()
    assert result['recoveredCount'] == 1
    assert result['projectIds'] == [project.id]
    assert project.status == ExamProject.Status.FAILED
    assert project.cancel_requested is True
    assert project.error_code == 'stale_extraction_run'
    assert project.workflow_state['stage'] == 'stale_extraction_recovered'
    assert project.workflow_state['previousStage'] == 'question_extraction'
    assert project.workflow_state['cancellationRequested'] is True


def test_recent_active_run_is_not_recovered():
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(
        teacher=teacher,
        title='Recent extraction fixture',
        status=ExamProject.Status.EXTRACTING_ANSWERS,
        workflow_state={
            'stage': 'answer_solution_extraction',
            'lastEventAt': timezone.now().isoformat(),
        },
    )

    result = recover_exam_prep_v4_stale_runs.run(
        max_age_minutes=60,
        limit=10,
    )

    project.refresh_from_db()
    assert result['recoveredCount'] == 0
    assert project.status == ExamProject.Status.EXTRACTING_ANSWERS
    assert project.cancel_requested is False
