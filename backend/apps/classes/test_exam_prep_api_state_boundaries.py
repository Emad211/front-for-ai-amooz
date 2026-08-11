import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE


pytestmark = pytest.mark.django_db


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _projection():
    return {
        'exam_prep': {
            'title': 'آزمون تولیدی',
            'questions': [
                {
                    'question_id': 'default-q-1',
                    'scope_key': 'default',
                    'section_key': 'default',
                    'source_question_number': '1',
                    'question_text_markdown': 'کدام گزینه درست است؟',
                    'options': [
                        {'label': '1', 'text_markdown': 'گزینه یک'},
                        {'label': '2', 'text_markdown': 'گزینه دو'},
                    ],
                    'correct_option_label': '2',
                    'teacher_solution_markdown': 'راه حل',
                    'final_answer_markdown': 'گزینه ۲',
                    'confidence': 0.99,
                    'issues': [],
                    'source_pages': [1, 2],
                }
            ],
        }
    }


def _production_audit(*, blocked: int = 0):
    region_statuses = (
        ['verified_source', 'verified_source']
        if blocked == 0
        else ['blocked_model_disagreement', 'verified_source']
    )
    return {
        'engine': PRODUCTION_ENGINE,
        'status': 'passed' if blocked == 0 else 'needs_review',
        'questionCount': 1,
        'criticalIssueCount': blocked,
        'ocrSourcePages': 2,
        'ocrResolvedModels': ['mistral-ocr-latest'],
        'nativeAnswerEvidence': {'schemaVersion': 2, 'trusted': True},
        'questionIntervals': [
            {'start': 1, 'end': 1, 'scopeKey': 'default'},
        ],
        'visualPipeline': {
            'schemaVersion': 2,
            'sourceSha256': 'a' * 64,
            'stats': {'unresolvedRegions': 0, 'storageFailures': 0},
            'unresolvedRegions': [],
            'criticalIssueCodes': [],
        },
        'riskRegionCount': 2,
        'riskSuspiciousRegionCount': blocked,
        'targetedRegionPrimaryCalls': 2,
        'targetedRegionUnresolved': blocked,
        'riskEngine': {
            'schemaVersion': 1,
            'policy': {
                'allRegionsReceivePrimary': True,
                'targetedEvaluation': False,
            },
            'stats': {
                'regions': 2,
                'missingRegions': 0,
                'primaryCalls': 2,
                'blocked': blocked,
            },
            'budget': {
                'preflightExceeded': False,
                'deadlineExceeded': False,
            },
            'regions': [
                {
                    'targetId': f'region-{index}',
                    'questionNumber': 1,
                    'kind': kind,
                    'status': region_statuses[index],
                }
                for index, kind in enumerate(('question', 'solution'))
            ],
        },
    }


def _production_workflow(*, ready: bool = True, audit=None):
    return {
        'engine': PRODUCTION_ENGINE,
        'stage': 'ready_for_review',
        'readyForReview': ready,
        'publicationBlocked': False,
        'failedPageNumbers': [],
        'extractionAudit': _production_audit() if audit is None else audit,
    }


def _exam_session(teacher, **overrides):
    values = {
        'teacher': teacher,
        'title': 'آزمون تولیدی',
        'pipeline_type': ClassCreationSession.PipelineType.EXAM_PREP,
        'status': ClassCreationSession.Status.EXAM_STRUCTURED,
        'exam_prep_json': json.dumps(_projection(), ensure_ascii=False),
        'workflow_state': _production_workflow(),
    }
    values.update(overrides)
    return ClassCreationSession.objects.create(**values)


def test_generic_class_detail_get_hides_exam_prep_session():
    teacher = _teacher()
    session = _exam_session(teacher)

    response = _auth(teacher).get(
        f'/api/classes/creation-sessions/{session.id}/'
    )

    assert response.status_code == 404
    assert ClassCreationSession.objects.filter(id=session.id).exists()


def test_generic_class_detail_patch_cannot_mutate_exam_prep_session():
    teacher = _teacher()
    session = _exam_session(teacher)

    response = _auth(teacher).patch(
        f'/api/classes/creation-sessions/{session.id}/',
        {'title': 'عنوان دستکاری‌شده'},
        format='json',
    )

    assert response.status_code == 404
    session.refresh_from_db()
    assert session.title == 'آزمون تولیدی'


def test_generic_class_detail_delete_cannot_bypass_exam_cleanup():
    teacher = _teacher()
    session = _exam_session(teacher)

    response = _auth(teacher).delete(
        f'/api/classes/creation-sessions/{session.id}/'
    )

    assert response.status_code == 404
    assert ClassCreationSession.objects.filter(id=session.id).exists()


@pytest.mark.parametrize(
    'terminal_status',
    [
        ClassCreationSession.Status.FAILED,
        ClassCreationSession.Status.CANCELLED,
    ],
)
def test_review_patch_rejects_terminal_production_session(terminal_status):
    teacher = _teacher()
    session = _exam_session(teacher, status=terminal_status)
    original_json = session.exam_prep_json

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'title': 'نباید ذخیره شود', 'exam_prep_json': _projection()},
        format='json',
    )

    assert response.status_code == 409
    session.refresh_from_db()
    assert session.status == terminal_status
    assert session.title == 'آزمون تولیدی'
    assert session.exam_prep_json == original_json


def test_review_patch_rejects_production_draft_without_stage_artifact():
    teacher = _teacher()
    session = _exam_session(
        teacher,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
        workflow_state=_production_workflow(audit={}),
    )

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': _projection()},
        format='json',
    )

    assert response.status_code == 409
    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED
    assert session.workflow_state['extractionAudit'] == {}


@pytest.mark.parametrize(
    ('session_status', 'workflow'),
    [
        (ClassCreationSession.Status.FAILED, _production_workflow()),
        (ClassCreationSession.Status.CANCELLED, _production_workflow()),
        (
            ClassCreationSession.Status.EXAM_TRANSCRIBED,
            _production_workflow(audit={}),
        ),
    ],
)
def test_edit_signal_does_not_promote_terminal_or_incomplete_production_state(
    session_status,
    workflow,
):
    teacher = _teacher()
    session = _exam_session(
        teacher,
        status=session_status,
        workflow_state=workflow,
    )

    session.exam_prep_json = json.dumps(_projection(), ensure_ascii=False)
    session.save(update_fields=['exam_prep_json'])

    session.refresh_from_db()
    assert session.status == session_status


def test_publish_rejects_production_session_without_complete_stage_audit():
    teacher = _teacher()
    session = _exam_session(
        teacher,
        workflow_state=_production_workflow(
            audit={'status': 'passed', 'criticalIssueCount': 0}
        ),
    )

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 409
    session.refresh_from_db()
    assert session.is_published is False


def test_publish_rejects_production_session_not_ready_for_review():
    teacher = _teacher()
    session = _exam_session(
        teacher,
        workflow_state=_production_workflow(ready=False),
    )

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 409
    session.refresh_from_db()
    assert session.is_published is False


def test_publish_accepts_complete_production_stage_audit(monkeypatch):
    teacher = _teacher()
    session = _exam_session(teacher)
    monkeypatch.setattr(
        'apps.classes.views.send_publish_sms_task.delay',
        lambda *_args, **_kwargs: None,
    )

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 200
    session.refresh_from_db()
    assert session.is_published is True
