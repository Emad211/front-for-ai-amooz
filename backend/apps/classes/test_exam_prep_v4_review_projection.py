from __future__ import annotations

import json

import pytest

from apps.classes.models import ClassCreationSession
from apps.classes.models_v4 import ExamProject
from apps.classes.models_v4_projection import ExamV4Projection
from apps.classes.models_v4_records import (
    ExamMatchDecision,
    ExamQuestionRecord,
)
from apps.classes.models_v4_review import ExamReviewDecision
from apps.classes.services.exam_prep_v4_live_pipeline import (
    run_document_extraction_pipeline,
)
from apps.classes.services.exam_prep_v4_projection import (
    build_legacy_projection,
    publish_legacy_projection,
)
from apps.classes.services.exam_prep_v4_review import (
    finalize_teacher_exception_review,
    get_teacher_review_queue,
    persist_teacher_review_decision,
)
from apps.classes.test_exam_prep_v4_full_pipeline import (
    FakeFullPipelineProvider,
    _confirmed_document,
)


pytestmark = pytest.mark.django_db


def _exception_project():
    teacher, project, document, _pages = _confirmed_document()
    run_document_extraction_pipeline(
        document_id=document.id,
        provider=FakeFullPipelineProvider(),
    )
    decision = ExamMatchDecision.objects.get(project=project)
    decision.decision = ExamMatchDecision.Decision.CONFLICT
    decision.method = ExamMatchDecision.Method.NONE
    decision.reason_code = 'manual_review_fixture'
    decision.question_record = None
    decision.save(
        update_fields=[
            'decision',
            'method',
            'reason_code',
            'question_record',
            'updated_at',
        ]
    )
    project.refresh_from_db()
    return teacher, project, document, decision


def test_exception_review_is_immutable_and_revision_bound():
    teacher, project, _document, decision = _exception_project()
    question_id = ExamQuestionRecord.objects.get(project=project).id

    queue = get_teacher_review_queue(teacher=teacher, project_id=project.id)
    assert queue['totalCount'] == 1
    assert queue['remainingCount'] == 1
    assert queue['items'][0]['reasonCode'] == 'manual_review_fixture'

    first = persist_teacher_review_decision(
        teacher=teacher,
        project_id=project.id,
        match_decision_id=decision.id,
        action=ExamReviewDecision.Action.MATCH,
        question_record_id=question_id,
        note='اتصال دستی تأیید شد',
    )
    same = persist_teacher_review_decision(
        teacher=teacher,
        project_id=project.id,
        match_decision_id=decision.id,
        action=ExamReviewDecision.Action.MATCH,
        question_record_id=question_id,
        note='اتصال دستی تأیید شد',
    )

    assert first.reused is False
    assert same.reused is True
    assert same.review_id == first.review_id
    assert same.ready_to_finalize is True
    assert ExamReviewDecision.objects.filter(
        lifecycle_status='accepted'
    ).count() == 1

    refreshed = get_teacher_review_queue(teacher=teacher, project_id=project.id)
    result = finalize_teacher_exception_review(
        teacher=teacher,
        project_id=project.id,
        expected_question_set_fingerprint=refreshed['questionSetFingerprint'],
        expected_answer_set_fingerprint=refreshed['answerSetFingerprint'],
    )
    project.refresh_from_db()
    assert result['remainingCount'] == 0
    assert project.status == ExamProject.Status.READY_TO_PUBLISH
    assert project.workflow_state['stage'] == 'review_complete'


def test_reviewed_v4_project_projects_into_existing_student_contract(
    monkeypatch,
):
    teacher, project, _document, decision = _exception_project()
    question = ExamQuestionRecord.objects.get(project=project)
    persist_teacher_review_decision(
        teacher=teacher,
        project_id=project.id,
        match_decision_id=decision.id,
        action=ExamReviewDecision.Action.MATCH,
        question_record_id=question.id,
    )
    queue = get_teacher_review_queue(teacher=teacher, project_id=project.id)
    finalize_teacher_exception_review(
        teacher=teacher,
        project_id=project.id,
        expected_question_set_fingerprint=queue['questionSetFingerprint'],
        expected_answer_set_fingerprint=queue['answerSetFingerprint'],
    )

    first = build_legacy_projection(teacher=teacher, project_id=project.id)
    second = build_legacy_projection(teacher=teacher, project_id=project.id)

    assert first['reused'] is False
    assert second['reused'] is True
    assert second['sessionId'] == first['sessionId']
    session = ClassCreationSession.objects.get(id=first['sessionId'])
    payload = json.loads(session.exam_prep_json)
    questions = payload['exam_prep']['questions']
    assert session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
    assert session.status == ClassCreationSession.Status.EXAM_STRUCTURED
    assert session.is_published is False
    assert len(questions) == 1
    assert questions[0]['question_text_markdown'] == 'متن دقیق سؤال آزمایشی'
    assert questions[0]['correct_option_label'] == '2'
    assert questions[0]['teacher_solution_markdown']
    assert 'source_block_id' not in json.dumps(payload)
    assert 'raw_payload' not in json.dumps(payload)

    monkeypatch.setattr(
        'apps.classes.services.exam_prep_v4_projection.transaction.on_commit',
        lambda _callback: None,
    )
    published = publish_legacy_projection(teacher=teacher, project_id=project.id)
    project.refresh_from_db()
    session.refresh_from_db()
    projection = ExamV4Projection.objects.get(project=project)
    assert published['published'] is True
    assert session.is_published is True
    assert project.status == ExamProject.Status.PUBLISHED
    assert project.is_published is True
    assert projection.status == ExamV4Projection.Status.PUBLISHED
