import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE
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


def _production_stage_audit(*, blocked=False):
    blocked_count = int(blocked)
    return {
        'engine': PRODUCTION_ENGINE,
        'status': 'needs_review' if blocked else 'passed',
        'questionCount': 1,
        'criticalIssueCount': blocked_count,
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
        'riskSuspiciousRegionCount': blocked_count,
        'targetedRegionPrimaryCalls': 2,
        'targetedRegionUnresolved': blocked_count,
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
                'blocked': blocked_count,
            },
            'budget': {
                'preflightExceeded': False,
                'deadlineExceeded': False,
            },
            'regions': [
                {
                    'targetId': 'question-1',
                    'questionNumber': 1,
                    'kind': 'question',
                    'status': (
                        'blocked_model_disagreement'
                        if blocked
                        else 'verified_source'
                    ),
                },
                {
                    'targetId': 'solution-1',
                    'questionNumber': 1,
                    'kind': 'solution',
                    'status': 'verified_source',
                },
            ],
        },
    }


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


def _mistral_session(
    teacher,
    projection,
    *,
    visual_contracts=None,
    extra_audit=None,
):
    session = _page_first_session(teacher, projection)
    questions = (projection.get('exam_prep') or {}).get('questions') or []
    stage5_blocked = any(
        'stage5_finalization_blocked' in (question.get('issues') or [])
        for question in questions
        if isinstance(question, dict)
    )
    session.workflow_state = {
        **session.workflow_state,
        'engine': PRODUCTION_ENGINE,
        'extractionAudit': {
            **_production_stage_audit(blocked=stage5_blocked),
            **session.workflow_state['extractionAudit'],
            **dict(extra_audit or {}),
            'visualSourceContracts': dict(visual_contracts or {}),
        },
    }
    session.save(update_fields=['workflow_state', 'updated_at'])
    return session


def test_canonical_projection_audit_detects_gaps_and_invalid_correct_option():
    projection = _projection([
        _question(1),
        _question(3, answer='7'),
    ])

    audit = audit_page_first_projection(projection)

    # A missing question number and an out-of-range answer key are advisory: both
    # questions still have a stem and options, so the exam stays publishable
    # (owner policy `همیشه مجاز`). They remain visible in criticalIssueCount.
    assert audit['status'] == 'passed'
    assert audit['questionCount'] == 2
    assert audit['questionsNeedingReview'] == 0
    assert audit['usableQuestionCount'] == 2
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


def test_mistral_stage5_advisory_issue_does_not_block_publish():
    teacher = _teacher()
    question = {
        **_question(1),
        'issues': ['stage5_finalization_blocked'],
        'teacher_reviewed_issue_codes': ['stage5_finalization_blocked'],
    }
    session = _mistral_session(teacher, _projection([question]))

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': _projection([question])},
        format='json',
    )

    assert response.status_code == 200
    session.refresh_from_db()
    # `stage5_finalization_blocked` is advisory only: the re-audit recomputes
    # issues from the projection (stem + options both present) and never blocks
    # on the stamp, so the draft becomes publishable — owner policy `همیشه مجاز`.
    assert session.status == ClassCreationSession.Status.EXAM_STRUCTURED
    assert session.workflow_state['publicationBlocked'] is False


def test_mistral_teacher_acknowledgement_does_not_hide_structural_errors():
    teacher = _teacher()
    question = {
        **_question(1),
        'question_text_markdown': '',
        'issues': ['stage5_finalization_blocked'],
        'teacher_reviewed_issue_codes': ['stage5_finalization_blocked'],
    }
    session = _mistral_session(teacher, _projection([question]))

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': _projection([question])},
        format='json',
    )

    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED
    codes = {
        issue['code']
        for issue in session.workflow_state['extractionAudit']['issues']
    }
    assert 'no_questions' in codes


def test_mistral_review_preserves_server_visual_source_contracts():
    teacher = _teacher()
    question = _question(1)
    contract = {'default-q-1': {'schemaVersion': 1, 'requiredAssetIds': []}}
    session = _mistral_session(
        teacher,
        _projection([question]),
        visual_contracts=contract,
    )

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': _projection([question])},
        format='json',
    )

    assert response.status_code == 200
    session.refresh_from_db()
    assert (
        session.workflow_state['extractionAudit']['visualSourceContracts']
        == contract
    )


def test_mistral_review_get_and_patch_preserve_immutable_stage5_audit():
    teacher = _teacher()
    question = _question(1)
    stage_audit = _production_stage_audit()
    immutable = {
        'riskEngine': stage_audit['riskEngine'],
        'nativeAnswerEvidence': stage_audit['nativeAnswerEvidence'],
        'totalEstimatedCostUsd': '0.731',
        'totalProviderCalls': 312,
        'visualAssetRegistry': {'asset-1': {'id': 'asset-1'}},
    }
    session = _mistral_session(
        teacher,
        _projection([question]),
        extra_audit=immutable,
    )

    get_response = _auth(teacher).get(
        f'/api/classes/exam-prep-sessions/{session.id}/'
    )
    assert get_response.status_code == 200
    session.refresh_from_db()
    for key, value in immutable.items():
        assert session.workflow_state['extractionAudit'][key] == value

    patch_response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': _projection([question])},
        format='json',
    )
    assert patch_response.status_code == 200
    session.refresh_from_db()
    for key, value in immutable.items():
        assert session.workflow_state['extractionAudit'][key] == value


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


def test_publish_endpoint_allows_page_first_session_despite_content_issues(monkeypatch):
    """Owner policy `همیشه مجاز`: content issues never block the publish button.

    A non-production (page_first) draft carrying a broken question still
    publishes — the broken question only lands in the advisory review lane; it
    does not gate publication.
    """
    teacher = _teacher()
    session = _page_first_session(
        teacher,
        _projection([{**_question(1), 'question_text_markdown': '', 'options': []}]),
    )
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


def test_publish_endpoint_rejects_non_owner_teacher():
    owner = _teacher()
    intruder = _teacher()
    session = _page_first_session(owner, _projection([_question(1)]))

    response = _auth(intruder).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 404
    session.refresh_from_db()
    assert session.is_published is False


def test_publish_endpoint_blocks_forged_production_workflow():
    """Anti-forgery (Gate B) is the one content-independent gate that survives.

    A workflow claiming the production engine but missing durable five-stage
    evidence must never publish, even though publishing is otherwise always
    allowed. Hand-written workflow JSON cannot impersonate the pipeline.
    """
    teacher = _teacher()
    session = _page_first_session(teacher, _projection([_question(1)]))
    session.workflow_state = {
        **session.workflow_state,
        'engine': PRODUCTION_ENGINE,
        'stage': 'ready_for_review',
        'readyForReview': True,
        # No ocrSourcePages / questionIntervals / riskEngine — the artifact is a
        # forgery, so production_review_artifact_is_valid must reject it.
        'extractionAudit': {'engine': PRODUCTION_ENGINE, 'status': 'passed'},
    }
    session.save(update_fields=['workflow_state', 'updated_at'])

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 409
    assert response.data['code'] == 'production_audit_required'
    session.refresh_from_db()
    assert session.is_published is False


def test_publish_endpoint_allows_degraded_run_with_recheck_call_inflation(monkeypatch):
    """Owner policy `همیشه مجاز`: a real degraded run still publishes.

    A single legitimate degraded recheck (`maxPrimaryDegradedRechecksPerRegion`)
    makes ``primaryCalls`` exceed ``regions`` — a healthy signal, not a forgery.
    Gate B is pure anti-forgery, so it must not treat call-count inflation (or a
    blocked region) as grounds to refuse publication.
    """
    teacher = _teacher()
    session = _page_first_session(
        teacher,
        _projection([_question(1)]),
        status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
    )
    degraded_audit = _production_stage_audit(blocked=True)
    # One region absorbed a degraded recheck: two primary calls over one region.
    degraded_audit['riskEngine']['stats']['regions'] = 2
    degraded_audit['riskEngine']['stats']['primaryCalls'] = 3
    degraded_audit['riskEngine']['stats']['blocked'] = 1
    degraded_audit['targetedRegionPrimaryCalls'] = 3
    degraded_audit['targetedRegionUnresolved'] = 1
    degraded_audit['riskRegionCount'] = 2
    session.workflow_state = {
        **session.workflow_state,
        'engine': PRODUCTION_ENGINE,
        'publicationBlocked': True,
        'extractionAudit': degraded_audit,
    }
    session.save(update_fields=['workflow_state', 'updated_at'])
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


# --- Owner regression: a real (drifted) production run must stay usable --------
#
# The 137-question Konkur booklet the owner ran completed the full five-stage
# pipeline, but its persisted ``visualPipeline.sourceSha256`` came back blank (a
# resumed-OCR run) — a Stage-3 fingerprint that has nothing to do with whether
# the pipeline actually ran. The strict ``production_review_artifact_is_valid``
# gate fail-closes on that single drifted field, and because the SAME gate
# guarded publish, the review PATCH conflict check, AND the re-audit refresh,
# one drift made the run permanently unpublishable and un-editable with zero
# teacher recourse — violating the owner-locked `همیشه مجاز` policy. The shallow
# ``production_run_is_authentic`` gate keeps such a run publishable/editable
# while still rejecting a forgery (see the preserved forged-workflow test).
_DRIFTED_VISUAL_PIPELINE = {
    'schemaVersion': 2,
    # A resumed-OCR run persisted a blank digest; the strict gate demands 64 hex
    # chars, so it rejects an otherwise-complete real run.
    'sourceSha256': '',
    'stats': {'unresolvedRegions': 0, 'storageFailures': 0},
    'unresolvedRegions': [],
    'criticalIssueCodes': [],
}
# Page-level issues the OCR recorded against a whole page, not a numbered
# question (``questionNumber == 0``), so a teacher cannot clear them by editing
# or deleting any single question — exactly the owner's red card of "۸ مشکل کلی
# به سؤال مشخصی متصل نشده است". They are NOT review-blocking (that gate needs a
# positive question number), so review-needed already reads 0.
_DETACHED_PAGE_ISSUES = [
    {
        'code': 'missing_question_text',
        'scopeKey': 'default',
        'questionNumber': 0,
        'severity': 'critical',
        'sourcePages': [5],
    },
    {
        'code': 'missing_options',
        'scopeKey': 'default',
        'questionNumber': 0,
        'severity': 'critical',
        'sourcePages': [7],
    },
]


def _drifted_production_session(teacher, questions):
    """A completed production run whose stored audit drifted from the strict schema.

    Every Stage-1/Stage-2 authenticity fingerprint is intact (so it is
    unmistakably a real pipeline run, not hand-authored forgery), but
    ``visualPipeline`` has a blank ``sourceSha256`` and the audit still carries
    detached page-level residue issues that no current question can clear.
    """

    return _mistral_session(
        teacher,
        _projection(questions),
        extra_audit={
            'status': 'needs_review',
            'questionCount': len(questions),
            'visualPipeline': dict(_DRIFTED_VISUAL_PIPELINE),
            'issues': [dict(issue) for issue in _DETACHED_PAGE_ISSUES],
            'criticalIssueCount': len(_DETACHED_PAGE_ISSUES),
            'questionsNeedingReview': 0,
        },
    )


def test_publish_endpoint_allows_drifted_authentic_production_run(monkeypatch):
    """`همیشه مجاز`: a real run with a drifted deep-schema field still publishes.

    Reproduces the owner's toast ``خروجی معتبر و آماده بازبینی مراحل ۱ تا ۵ برای
    انتشار موجود نیست.`` (``production_audit_required``). The run completed all
    five stages; only ``visualPipeline.sourceSha256`` drifted. It must publish.
    """
    teacher = _teacher()
    session = _drifted_production_session(teacher, [_question(1), _question(2)])
    monkeypatch.setattr(
        'apps.classes.views.send_publish_sms_task.delay',
        lambda *_args, **_kwargs: None,
    )

    response = _auth(teacher).post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 200, response.data
    session.refresh_from_db()
    assert session.is_published is True


def test_review_patch_persists_delete_on_drifted_production_run():
    """Reproduces "نه ادیت ها ثبت میشه نه پاک کردن ها".

    The teacher deletes one of two questions on a drifted run. The strict gate
    made the PATCH conflict-check refuse (409) BEFORE ``session.save``, so the
    reduced projection never persisted. The shallow gate lets the edit through
    and the deletion survives reload.
    """
    teacher = _teacher()
    session = _drifted_production_session(teacher, [_question(1), _question(2)])

    response = _auth(teacher).patch(
        f'/api/classes/exam-prep-sessions/{session.id}/',
        {'exam_prep_json': _projection([_question(1)])},
        format='json',
    )

    assert response.status_code == 200, response.data
    session.refresh_from_db()
    stored = json.loads(session.exam_prep_json)
    numbers = [
        question['source_question_number']
        for question in stored['exam_prep']['questions']
    ]
    assert numbers == ['1']


def test_review_get_clears_detached_page_issues_on_drifted_run():
    """The red card of detached page-level issues must clear on a healthy run.

    A GET recomputes the audit from the (question-keyed) projection, which can
    only emit issues for questions that currently exist — so the detached
    ``questionNumber == 0`` residue vanishes and the run reads as passed. The
    strict gate blocked that refresh entirely, freezing the stale residue.
    """
    teacher = _teacher()
    session = _drifted_production_session(teacher, [_question(1), _question(2)])

    response = _auth(teacher).get(
        f'/api/classes/exam-prep-sessions/{session.id}/'
    )

    assert response.status_code == 200
    audit = response.data['extractionAudit']
    detached_blocking = [
        issue
        for issue in (audit.get('issues') or [])
        if issue.get('code') in {'missing_question_text', 'missing_options'}
        and int(issue.get('questionNumber') or 0) == 0
    ]
    assert detached_blocking == []
    assert audit['status'] == 'passed'
    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_STRUCTURED
