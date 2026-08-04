import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_page_review import (
    audit_page_first_projection,
    render_projection_transcript,
    retain_failed_page_evidence,
)


pytestmark = pytest.mark.django_db


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _question(number: int, *, answer='2', text='متن سؤال'):
    return {
        'question_id': f'default-q-{number}',
        'scope_key': 'default',
        'section_key': 'default',
        'source_question_number': str(number),
        'question_text_markdown': text,
        'options': [
            {'label': '1', 'text_markdown': 'گزینه یک'},
            {'label': '2', 'text_markdown': 'گزینه دو'},
            {'label': '3', 'text_markdown': 'گزینه سه'},
            {'label': '4', 'text_markdown': 'گزینه چهار'},
        ],
        'correct_option_label': answer,
        'correct_option_text_markdown': '',
        'teacher_solution_markdown': 'حل تشریحی',
        'final_answer_markdown': f'گزینه {answer}',
        'confidence': 0.9,
        'issues': [],
        'source_pages': [2, 9],
    }


def _projection(questions):
    return {'exam_prep': {'title': 'آزمون زیست', 'questions': questions}}


def _page_first_session(
    teacher,
    projection,
    *,
    status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
    failed_page_numbers=None,
):
    failed_pages = list(failed_page_numbers or [])
    return ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون زیست',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=status,
        exam_prep_json=json.dumps(projection, ensure_ascii=False),
        transcript_markdown='خروجی قدیمی',
        workflow_state={
            'engine': 'page_first',
            'stage': 'ready_for_review',
            'readyForReview': True,
            'publicationBlocked': True,
            'failedPageNumbers': failed_pages,
            'extractionAudit': {
                'status': 'needs_review',
                'failedPageNumbers': failed_pages,
            },
        },
    )


def test_canonical_projection_audit_detects_gaps_and_invalid_correct_option():
    projection = _projection([
        _question(1),
        _question(3, answer='7'),
    ])

    audit = audit_page_first_projection(projection)

    assert audit['status'] == 'needs_review'
    assert audit['questionCount'] == 2
    assert audit['questionNumberGaps'] == {'default': [2]}
    codes = {issue['code'] for issue in audit['issues']}
    assert 'missing_question_number' in codes
    assert 'correct_option_not_in_options' in codes
    assert audit['criticalIssueCount'] == 2


def test_empty_projection_has_explicit_critical_issue():
    audit = audit_page_first_projection(_projection([]))

    assert audit['status'] == 'needs_review'
    assert audit['questionCount'] == 0
    assert audit['criticalIssueCount'] == 1
    assert [issue['code'] for issue in audit['issues']] == ['no_questions']


def test_failed_page_evidence_stays_critical_after_projection_is_valid():
    audit = audit_page_first_projection(_projection([_question(1)]))

    retained = retain_failed_page_evidence(audit, [8, 6, 8])

    assert retained['status'] == 'needs_review'
    assert retained['failedPageNumbers'] == [6, 8]
    assert retained['criticalIssueCount'] == 2
    assert [
        issue['sourcePages']
        for issue in retained['issues']
        if issue['code'] == 'failed_chunk'
    ] == [[6], [8]]


def test_canonical_projection_transcript_is_readable():
    projection = _projection([_question(18, answer='3', text='کدام گزینه درست است؟')])
    audit = audit_page_first_projection(projection)

    transcript = render_projection_transcript(projection, audit)

    assert '# آزمون زیست' in transcript
    assert '## سؤال 18' in transcript
    assert 'کدام گزینه درست است؟' in transcript
    assert '3) گزینه سه' in transcript
    assert '**پاسخ صحیح:** گزینه 3' in transcript
    assert '**راه‌حل تشریحی:**' in transcript


def test_valid_teacher_edit_moves_page_first_session_to_publishable_status():
    teacher = _teacher()
    invalid = _projection([
        {
            **_question(1),
            'correct_option_label': '',
            'teacher_solution_markdown': '',
            'final_answer_markdown': '',
        }
    ])
    session = _page_first_session(teacher, invalid)
    valid = _projection([_question(1, answer='2')])

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': valid},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['status'] == ClassCreationSession.Status.EXAM_STRUCTURED
    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_STRUCTURED
    assert session.workflow_state['publicationBlocked'] is False
    assert session.workflow_state['extractionAudit']['status'] == 'passed'
    assert session.workflow_state['extractionAudit']['criticalIssueCount'] == 0
    assert session.transcript_markdown.startswith('# آزمون زیست')
    assert '## سؤال 1' in session.transcript_markdown


def test_invalid_teacher_edit_stays_blocked_and_keeps_reviewable_output():
    teacher = _teacher()
    session = _page_first_session(teacher, _projection([_question(1)]))
    invalid = _projection([
        {
            **_question(1),
            'question_text_markdown': '',
            'options': [],
        }
    ])

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': invalid},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['status'] == ClassCreationSession.Status.EXAM_TRANSCRIBED
    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED
    assert session.workflow_state['publicationBlocked'] is True
    audit = session.workflow_state['extractionAudit']
    assert audit['status'] == 'needs_review'
    assert audit['criticalIssueCount'] == 1
    assert {issue['code'] for issue in audit['issues']} == {'no_questions'}
    assert json.loads(session.exam_prep_json) == _projection([])


def test_valid_manual_json_cannot_clear_failed_physical_page():
    teacher = _teacher()
    session = _page_first_session(
        teacher,
        _projection([_question(1)]),
        failed_page_numbers=[6],
    )

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': _projection([_question(1)])},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['status'] == ClassCreationSession.Status.EXAM_TRANSCRIBED
    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED
    assert session.workflow_state['publicationBlocked'] is True
    assert session.workflow_state['failedPageNumbers'] == [6]
    assert session.workflow_state['extractionAudit']['failedPageNumbers'] == [6]
    assert 'صفحه‌های نیازمند بازپردازش: **6**' in session.transcript_markdown


def test_publish_endpoint_rejects_page_first_session_with_critical_issues():
    teacher = _teacher()
    session = _page_first_session(
        teacher,
        _projection([{**_question(1), 'question_text_markdown': '', 'options': []}]),
    )

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 400
    session.refresh_from_db()
    assert session.is_published is False


def test_publish_endpoint_accepts_page_first_session_after_valid_edit(monkeypatch):
    teacher = _teacher()
    session = _page_first_session(teacher, _projection([_question(1)]))
    monkeypatch.setattr(
        'apps.classes.views.send_publish_sms_task.delay',
        lambda *_args, **_kwargs: None,
    )

    edit = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': _projection([_question(1)])},
        format='json',
    )
    publish = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert edit.status_code == 200
    assert edit.data['status'] == ClassCreationSession.Status.EXAM_STRUCTURED
    assert publish.status_code == 200
    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_STRUCTURED
    assert session.is_published is True
