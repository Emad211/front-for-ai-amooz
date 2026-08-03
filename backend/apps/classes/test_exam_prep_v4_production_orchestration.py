from __future__ import annotations

import json
import logging
import uuid

import pytest
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services.exam_prep_v4_observability import (
    ExtractionRunContext,
    emit_v4_event,
)
from apps.classes.tasks_v4 import (
    dispatch_exam_prep_v4_extraction,
    process_exam_prep_v4_extraction,
)


pytestmark = pytest.mark.django_db


def _confirmed_document():
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(
        teacher=teacher,
        title='Production orchestration fixture',
        status=ExamProject.Status.SEGMENTING,
        workflow_state={
            'stage': 'source_map_confirmed',
            'progressPercent': 30,
        },
    )
    fingerprint = 'a' * 64
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='PRIVATE_SOURCE_NAME.pdf',
        status=ExamSourceDocument.Status.CONFIRMED,
        page_count=3,
        classification_revision=4,
        source_map_fingerprint=fingerprint,
        teacher_confirmed_at=timezone.now(),
        teacher_confirmed_by=teacher,
        teacher_confirmed_revision=4,
        teacher_confirmed_fingerprint=fingerprint,
        error_detail='PRIVATE_DOCUMENT_ERROR',
    )
    return teacher, project, document


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _status_url(project_id: int, document_id: int) -> str:
    return (
        f'/api/classes/exam-prep-v4/projects/{project_id}/documents/'
        f'{document_id}/extraction/status/'
    )


def _cancel_url(project_id: int, document_id: int) -> str:
    return (
        f'/api/classes/exam-prep-v4/projects/{project_id}/documents/'
        f'{document_id}/extraction/cancel/'
    )


def _retry_url(project_id: int, document_id: int) -> str:
    return (
        f'/api/classes/exam-prep-v4/projects/{project_id}/documents/'
        f'{document_id}/extraction/retry/'
    )


def test_dispatch_is_correlated_and_idempotent(monkeypatch):
    _teacher, project, document = _confirmed_document()
    sent: list[dict] = []

    monkeypatch.setattr(
        'apps.classes.tasks_v4.cache.add',
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        'apps.classes.tasks_v4.process_exam_prep_v4_extraction.apply_async',
        lambda **kwargs: sent.append(kwargs),
    )

    first = dispatch_exam_prep_v4_extraction(document.id)
    second = dispatch_exam_prep_v4_extraction(document.id)

    project.refresh_from_db()
    assert first.queued is True
    assert first.reused is False
    assert second.reused is True
    assert second.run_id == first.run_id
    assert second.task_id == first.task_id
    assert len(sent) == 1
    assert sent[0]['task_id'] == first.task_id
    assert sent[0]['queue'] == 'pipeline'
    assert project.workflow_state['runId'] == first.run_id
    assert project.workflow_state['taskId'] == first.task_id
    assert project.workflow_state['sourceMapRevision'] == 4
    assert project.workflow_state['sourceMapFingerprintPrefix'] == 'a' * 12
    assert project.workflow_state['cancellationRequested'] is False


def test_status_api_is_owner_scoped_and_content_free(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document = _confirmed_document()
    project.workflow_state = {
        'stage': 'answer_solution_extraction',
        'progressPercent': 65,
        'warningCount': 2,
        'runId': str(uuid.uuid4()),
        'taskId': str(uuid.uuid4()),
        'attempt': 2,
        'sourceMapRevision': 4,
        'sourceMapFingerprintPrefix': 'a' * 12,
        'questionCount': 10,
        'providerCalls': 7,
        'privateText': 'PRIVATE_QUESTION_TEXT',
    }
    project.error_code = 'exam_v4_extraction_failed'
    project.error_detail = 'PRIVATE_PROJECT_ERROR_DETAIL'
    project.save(
        update_fields=[
            'workflow_state',
            'error_code',
            'error_detail',
            'updated_at',
        ]
    )

    response = _client(teacher).get(_status_url(project.id, document.id))

    assert response.status_code == 200
    assert response.data['runId'] == project.workflow_state['runId']
    assert response.data['taskId'] == project.workflow_state['taskId']
    assert response.data['stage'] == 'answer_solution_extraction'
    assert response.data['counters']['questionCount'] == 10
    assert response.data['counters']['providerCalls'] == 7
    assert response.data['cancellationRequested'] is False
    rendered = json.dumps(response.data, ensure_ascii=False)
    for private_value in (
        'PRIVATE_SOURCE_NAME',
        'PRIVATE_DOCUMENT_ERROR',
        'PRIVATE_PROJECT_ERROR_DETAIL',
        'PRIVATE_QUESTION_TEXT',
    ):
        assert private_value not in rendered

    other_teacher = baker.make('accounts.User', role='TEACHER')
    assert _client(other_teacher).get(
        _status_url(project.id, document.id)
    ).status_code == 404


def test_observability_redacts_unapproved_free_text(caplog):
    context = ExtractionRunContext(
        run_id=str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        project_id=1,
        document_id=2,
        source_map_revision=3,
        source_map_fingerprint='b' * 64,
    )

    with caplog.at_level(logging.INFO, logger='apps.classes.exam_prep_v4'):
        emit_v4_event(
            'exam_prep_v4.extraction.stage_completed',
            context=context,
            stage='question_extraction',
            questionCount=12,
            unsafeText='PRIVATE QUESTION CONTENT WITH SPACES',
        )

    rendered = '\n'.join(record.getMessage() for record in caplog.records)
    assert context.run_id in rendered
    assert '"questionCount":12' in rendered
    assert 'PRIVATE QUESTION CONTENT' not in rendered
    assert '"unsafeText":"redacted"' in rendered


def test_terminal_task_failure_is_visible_to_celery_and_project(
    settings,
    monkeypatch,
):
    settings.EXAM_PREP_V4_ENABLED = True
    _teacher, project, document = _confirmed_document()
    run_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    monkeypatch.setattr(
        'apps.classes.tasks_v4.cache.add',
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        'apps.classes.tasks_v4.cache.delete',
        lambda *args, **kwargs: True,
    )

    class BrokenProvider:
        def __init__(self):
            raise ValueError('PRIVATE_PROVIDER_FAILURE')

    monkeypatch.setattr(
        'apps.classes.tasks_v4.StructuredLLMExamPrepV4Provider',
        BrokenProvider,
    )

    result = process_exam_prep_v4_extraction.apply(
        args=[document.id, run_id],
        task_id=task_id,
        throw=False,
    )

    project.refresh_from_db()
    assert result.failed()
    assert project.status == ExamProject.Status.FAILED
    assert project.error_code == 'exam_v4_extraction_failed'
    assert project.workflow_state['stage'] == 'extraction_failed'
    assert project.workflow_state['runId'] == run_id
    assert project.workflow_state['taskId'] == task_id
    assert project.workflow_state['errorCode'] == 'ValueError'
    assert 'PRIVATE_PROVIDER_FAILURE' not in project.error_detail


def test_cancel_api_stops_at_task_checkpoint_and_retry_starts_fresh_run(
    settings,
    monkeypatch,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document = _confirmed_document()
    run_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    project.workflow_state = {
        'stage': 'question_extraction',
        'progressPercent': 50,
        'runId': run_id,
        'taskId': task_id,
        'attempt': 1,
        'sourceMapRevision': document.classification_revision,
        'sourceMapFingerprintPrefix': document.source_map_fingerprint[:12],
    }
    project.save(update_fields=['workflow_state', 'updated_at'])

    revoked: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        'apps.classes.views_v4_extraction.current_app.control.revoke',
        lambda selected_task_id, terminate=False: revoked.append(
            (selected_task_id, terminate)
        ),
    )
    response = _client(teacher).post(
        _cancel_url(project.id, document.id),
        {},
        format='json',
    )

    project.refresh_from_db()
    assert response.status_code == 202
    assert response.data['cancellationRequested'] is True
    assert response.data['stage'] == 'cancellation_requested'
    assert project.cancel_requested is True
    assert revoked == [(task_id, False)]

    monkeypatch.setattr(
        'apps.classes.tasks_v4.cache.add',
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        'apps.classes.tasks_v4.cache.delete',
        lambda *args, **kwargs: True,
    )
    cancelled = process_exam_prep_v4_extraction.apply(
        args=[document.id, run_id],
        task_id=task_id,
        throw=False,
    )
    project.refresh_from_db()
    assert cancelled.successful()
    assert cancelled.result['status'] == 'cancelled'
    assert project.status == ExamProject.Status.CANCELLED
    assert project.workflow_state['stage'] == 'cancelled'

    queued: list[dict] = []
    monkeypatch.setattr(
        'apps.classes.tasks_v4.process_exam_prep_v4_extraction.apply_async',
        lambda **kwargs: queued.append(kwargs),
    )
    retried = _client(teacher).post(
        _retry_url(project.id, document.id),
        {},
        format='json',
    )
    project.refresh_from_db()
    assert retried.status_code == 202
    assert retried.data['cancellationRequested'] is False
    assert retried.data['runId'] != run_id
    assert project.cancel_requested is False
    assert project.status == ExamProject.Status.SEGMENTING
    assert len(queued) == 1
