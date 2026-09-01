from __future__ import annotations

import json

import pytest
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    StudentExamPrepAttempt,
)
from apps.classes.models_v4 import ExamProject
from apps.classes.models_v4_bridge import ExamV4SessionBridge
from apps.classes.models_v4_projection import ExamV4Projection
from apps.classes.models_v4_records import ExamAnswerSolutionRecord, ExamQuestionRecord
from apps.classes.services.exam_prep_v4_create_flow import (
    CreateFlowProjectionConflict,
    adopt_create_flow_projection,
)
from apps.classes.services.exam_prep_v4_live_pipeline import run_document_extraction_pipeline
from apps.classes.services.exam_prep_v4_projection import (
    ProjectionIntegrityError,
    build_legacy_projection,
)
from apps.classes.services.exam_prep_v4_source_crops import render_source_crop
from apps.classes.test_exam_prep_v4_full_pipeline import (
    FakeFullPipelineProvider,
    _confirmed_document,
)


pytestmark = pytest.mark.django_db


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _prepare_projection():
    teacher, project, document, _pages = _confirmed_document()
    run_document_extraction_pipeline(
        document_id=document.id,
        provider=FakeFullPipelineProvider(),
    )
    project.status = ExamProject.Status.READY_TO_PUBLISH
    project.save(update_fields=['status', 'updated_at'])
    projection = build_legacy_projection(
        teacher=teacher,
        project_id=project.id,
    )
    session = ClassCreationSession.objects.get(id=projection['sessionId'])
    question = ExamQuestionRecord.objects.get(project=project)
    solution = ExamAnswerSolutionRecord.objects.get(project=project)
    return teacher, project, session, question, solution


def _body(response) -> bytes:
    return b''.join(response.streaming_content)


def test_projection_contains_protected_question_and_solution_refs():
    _teacher, _project, session, _question, _solution = _prepare_projection()
    payload = json.loads(session.exam_prep_json)
    visuals = payload['exam_prep']['questions'][0]['visuals']

    assert {item['role'] for item in visuals} == {'question', 'solution'}
    for item in visuals:
        assert item['selectedVariant'] == 'source'
        assert item['url'].startswith('/api/classes/exam-prep-source-crops/')
        assert 'source_block_id' not in json.dumps(item)


def test_legacy_publish_button_syncs_v4_project_and_projection(monkeypatch):
    teacher, project, session, _question, _solution = _prepare_projection()
    monkeypatch.setattr(
        'apps.classes.services.exam_prep_v4_projection.transaction.on_commit',
        lambda _callback: None,
    )

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 200
    session.refresh_from_db()
    project.refresh_from_db()
    projection = ExamV4Projection.objects.get(project=project)
    assert session.is_published is True
    assert project.is_published is True
    assert project.status == ExamProject.Status.PUBLISHED
    assert projection.status == ExamV4Projection.Status.PUBLISHED


def test_published_bridge_target_rebinds_projection_and_preserves_invites(
    monkeypatch,
):
    """A legacy publish before V4 adoption must not strand crops on a draft session."""

    teacher, project, generated, _question, _solution = _prepare_projection()
    target = baker.make(
        'classes.ClassCreationSession',
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        title='bridge target',
        is_published=True,
        published_at=timezone.now(),
        exam_prep_json='',
    )
    invite = ClassInvitation.objects.create(
        session=target,
        phone='09120000009',
        invite_code='PUBLISHED-BRIDGE',
    )
    ExamV4SessionBridge.objects.create(project=project, session=target)

    monkeypatch.setattr(
        'apps.classes.services.exam_prep_v4_projection.transaction.on_commit',
        lambda _callback: None,
    )
    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{target.id}/publish/'
    )

    projection = ExamV4Projection.objects.get(project=project)
    target.refresh_from_db()
    assert response.status_code == 200
    assert projection.session_id == target.id
    assert target.is_published is True
    assert target.published_at is not None
    assert target.exam_prep_json
    assert target.invites.filter(pk=invite.pk).exists()
    assert not ClassCreationSession.objects.filter(pk=generated.pk).exists()


def test_published_bridge_target_conflict_fails_closed():
    teacher, project, generated, _question, _solution = _prepare_projection()
    target = baker.make(
        'classes.ClassCreationSession',
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        is_published=True,
        exam_prep_json='{"exam_prep":{"title":"different","questions":[]}}',
    )
    ExamV4SessionBridge.objects.create(project=project, session=target)

    with pytest.raises(CreateFlowProjectionConflict):
        adopt_create_flow_projection(
            project_id=project.id,
            projection_payload={'projectId': project.id, 'sessionId': generated.id},
        )

    projection = ExamV4Projection.objects.get(project=project)
    assert projection.session_id == generated.id


def test_legacy_publish_repairs_half_published_v4_bridge(monkeypatch):
    teacher, project, session, _question, _solution = _prepare_projection()
    session.is_published = True
    session.save(update_fields=['is_published', 'updated_at'])
    monkeypatch.setattr(
        'apps.classes.services.exam_prep_v4_projection.transaction.on_commit',
        lambda _callback: None,
    )

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 200
    project.refresh_from_db()
    projection = ExamV4Projection.objects.get(project=project)
    assert project.is_published is True
    assert project.status == ExamProject.Status.PUBLISHED
    assert projection.status == ExamV4Projection.Status.PUBLISHED


def test_edited_projection_payload_is_not_overwritten_on_publish():
    teacher, project, session, _question, _solution = _prepare_projection()
    payload = json.loads(session.exam_prep_json)
    payload['exam_prep']['questions'][0]['question_text_markdown'] = 'اصلاح معلم'
    session.exam_prep_json = json.dumps(payload, ensure_ascii=False)
    session.save(update_fields=['exam_prep_json', 'updated_at'])

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    session.refresh_from_db()
    assert response.status_code == 409
    assert response.data['code'] == 'projection_integrity_error'
    assert 'اصلاح معلم' in session.exam_prep_json
    with pytest.raises(ProjectionIntegrityError):
        build_legacy_projection(teacher=teacher, project_id=project.id)


def test_normalizer_only_projection_edit_remains_publishable(monkeypatch):
    teacher, _project, session, _question, _solution = _prepare_projection()
    payload = json.loads(session.exam_prep_json)
    payload['exam_prep']['questions'][0]['confidence'] = None
    payload['exam_prep']['questions'][0]['issues'] = []
    session.exam_prep_json = json.dumps(payload, ensure_ascii=False)
    session.save(update_fields=['exam_prep_json', 'updated_at'])
    monkeypatch.setattr(
        'apps.classes.services.exam_prep_v4_projection.transaction.on_commit',
        lambda _callback: None,
    )

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 200
    session.refresh_from_db()
    assert session.is_published is True
    assert session.exam_prep_json


def test_owner_can_stream_both_crops_and_student_only_question(settings):
    teacher, project, session, question, solution = _prepare_projection()
    settings.EXAM_PREP_V4_ENABLED = True
    question_url = (
        f'/api/classes/exam-prep-source-crops/{project.id}/question/{question.id}/'
    )
    solution_url = (
        f'/api/classes/exam-prep-source-crops/{project.id}/solution/{solution.id}/'
    )

    owner_question = _auth(teacher).get(question_url)
    owner_solution = _auth(teacher).get(solution_url)
    assert owner_question.status_code == 200
    assert owner_solution.status_code == 200
    assert owner_question['Content-Type'].startswith('image/jpeg')
    assert _body(owner_question).startswith(b'\xff\xd8')
    assert owner_question['Cache-Control'] == 'private, no-store, max-age=0'
    assert 'storage' not in owner_question.get('Content-Disposition', '')

    student = baker.make(
        'accounts.User',
        role='STUDENT',
        phone='09120000000',
    )
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code='CROP-INVITE',
    )
    # Invitation is not sufficient while the projection is still a draft.
    assert _auth(student).get(question_url).status_code == 404

    project.is_published = True
    project.save(update_fields=['is_published', 'updated_at'])
    session.is_published = True
    session.save(update_fields=['is_published', 'updated_at'])
    assert _auth(student).get(question_url).status_code == 200
    assert _auth(student).get(solution_url).status_code == 404

    StudentExamPrepAttempt.objects.create(
        session=session,
        student=student,
        finalized=True,
        answers={},
        total_questions=1,
    )
    student_solution = _auth(student).get(solution_url)
    assert student_solution.status_code == 200
    assert _body(student_solution).startswith(b'\xff\xd8')


def test_crop_service_rejects_unknown_record_or_kind():
    _teacher, project, _session, _question, _solution = _prepare_projection()

    with pytest.raises(LookupError):
        render_source_crop(
            project_id=project.id,
            record_kind='option',
            record_id=1,
        )
    with pytest.raises(LookupError):
        render_source_crop(
            project_id=project.id,
            record_kind='question',
            record_id=999999,
        )


def test_student_result_releases_solution_evidence_only_after_finalize(settings):
    _teacher, project, session, _question, _solution = _prepare_projection()
    settings.EXAM_PREP_V4_ENABLED = True
    project.is_published = True
    project.save(update_fields=['is_published', 'updated_at'])
    session.is_published = True
    session.save(update_fields=['is_published', 'updated_at'])
    student = baker.make(
        'accounts.User',
        role='STUDENT',
        phone='09120000001',
    )
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code='RESULT-INVITE',
    )
    qid = json.loads(session.exam_prep_json)['exam_prep']['questions'][0]['question_id']
    attempt = StudentExamPrepAttempt.objects.create(
        session=session,
        student=student,
        answers={qid: '2'},
        total_questions=1,
        finalized=False,
    )
    result_url = f'/api/classes/student/exam-preps/{session.id}/result/'
    draft_item = _auth(student).get(result_url).json()['items'][0]
    assert draft_item.get('solution_markdown', '') == ''
    assert draft_item.get('solution_visuals', []) == []

    attempt.finalized = True
    attempt.correct_count = 1
    attempt.score_0_100 = 100
    attempt.save(update_fields=['finalized', 'correct_count', 'score_0_100', 'updated_at'])
    final_item = _auth(student).get(result_url).json()['items'][0]
    assert final_item['solution_markdown']
    assert final_item['solution_visuals'][0]['role'] == 'solution'
    assert final_item['solution_visuals'][0]['url'].startswith(
        '/api/classes/exam-prep-source-crops/'
    )
