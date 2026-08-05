import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession


pytestmark = pytest.mark.django_db


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _question(number: int):
    return {
        'question_id': f'default-q-{number}',
        'scope_key': 'default',
        'section_key': 'default',
        'source_question_number': str(number),
        'question_text_markdown': f'متن سؤال {number}',
        'options': [
            {'label': '1', 'text_markdown': 'گزینه یک'},
            {'label': '2', 'text_markdown': 'گزینه دو'},
            {'label': '3', 'text_markdown': 'گزینه سه'},
            {'label': '4', 'text_markdown': 'گزینه چهار'},
        ],
        'correct_option_label': '2',
        'correct_option_text_markdown': 'گزینه دو',
        'teacher_solution_markdown': 'این یک راه‌حل تشریحی کامل برای سؤال است.',
        'final_answer_markdown': 'گزینه ۲',
        'confidence': 0.95,
        'issues': [],
        'source_pages': [2],
    }


def _session(teacher, *, failed_pages=None):
    projection = {
        'exam_prep': {
            'title': 'آزمون ویرایش‌شده',
            'questions': [_question(1), _question(3)],
        }
    }
    pages = list(failed_pages or [])
    return ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون ویرایش‌شده',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
        exam_prep_json=json.dumps(projection, ensure_ascii=False),
        transcript_markdown='خروجی قدیمی',
        workflow_state={
            'engine': 'page_first',
            'stage': 'ready_for_review',
            'readyForReview': True,
            'publicationBlocked': True,
            'failedPageNumbers': pages,
            'extractionAudit': {
                'status': 'needs_review',
                'criticalIssueCount': 1,
                'questionsNeedingReview': 0,
                'issues': [
                    {
                        'code': 'missing_question_number',
                        'severity': 'critical',
                        'scopeKey': 'default',
                        'questionNumber': 2,
                        'sourcePages': [],
                    }
                ],
            },
        },
    )


def test_detail_get_auto_heals_intentional_deleted_question_gap(monkeypatch):
    teacher = _teacher()
    session = _session(teacher)
    monkeypatch.setattr(
        'apps.classes.views.send_publish_sms_task.delay',
        lambda *_args, **_kwargs: None,
    )

    detail = _auth(teacher).get(
        f'/api/classes/exam-prep-sessions/{session.id}/'
    )

    assert detail.status_code == 200
    assert detail.data['status'] == ClassCreationSession.Status.EXAM_STRUCTURED
    audit = detail.data['extractionAudit']
    assert audit['status'] == 'passed'
    assert audit['criticalIssueCount'] == 0
    assert audit['questionNumberGaps'] == {'default': [2]}
    gap_issue = next(
        issue for issue in audit['issues']
        if issue['code'] == 'missing_question_number'
    )
    assert gap_issue['severity'] == 'warning'

    publish = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )
    assert publish.status_code == 200
    session.refresh_from_db()
    assert session.is_published is True


def test_detail_get_keeps_unverifiable_failed_page_blocking():
    teacher = _teacher()
    session = _session(teacher, failed_pages=[6])

    detail = _auth(teacher).get(
        f'/api/classes/exam-prep-sessions/{session.id}/'
    )

    assert detail.status_code == 200
    assert detail.data['status'] == ClassCreationSession.Status.EXAM_TRANSCRIBED
    audit = detail.data['extractionAudit']
    assert audit['status'] == 'needs_review'
    assert audit['failedPageNumbers'] == [6]
    assert any(
        issue['code'] == 'failed_chunk'
        and issue['severity'] == 'critical'
        for issue in audit['issues']
    )
