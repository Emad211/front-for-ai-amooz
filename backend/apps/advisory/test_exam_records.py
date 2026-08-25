"""Restart steps 5+6 — exam scores and exam analyses: door and endpoints.

Phase 1 (step 5): ``StudyExamScore`` CRUD under the 40-row ceiling, PATCH
partiality, the pinned Persian validation matrix, and the quiet student
mirror. Phase 2 (step 6) extends this file with the analysis set-replace
below. The access matrix is identical for both resources: owner advisor
200/201, stranger advisor 404, wrong role 403, anonymous 401 — and no
student write route exists anywhere.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    AdvisoryEngagement,
    StudyExamAnalysis,
    StudyExamAnalysisNote,
    StudyExamAnalysisRow,
    StudyExamScore,
    Subject,
)
from apps.advisory.services import exam_records as exam_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

SCORES_URL = '/api/advisory/students/{pk}/exam-scores/'
SCORE_DETAIL_URL = '/api/advisory/students/{pk}/exam-scores/{score_id}/'
MY_SCORES_URL = '/api/advisory/me/exam-scores/'

ANALYSES_URL = '/api/advisory/students/{pk}/exam-analyses/'
ANALYSIS_DETAIL_URL = '/api/advisory/students/{pk}/exam-analyses/{analysis_id}/'
MY_ANALYSES_URL = '/api/advisory/me/exam-analyses/'

MSG_CAP = 'سقف ثبت نمرات پر شده است.'
MSG_PERCENT = 'درصد باید بین ۰ تا ۱۰۰ باشد.'
MSG_KIND = 'نوع آزمون نامعتبر است.'
MSG_RATING = 'ارزیابی نامعتبر است.'
MSG_SUBJECT = 'درس انتخابی معتبر نیست.'

MSG_GRADE_BAND = 'بازهٔ پایه نامعتبر است.'
MSG_DOUBTFUL = 'آمار سؤالات شک‌دار نامعتبر است.'
MSG_QUESTION_NUMBER = 'شمارهٔ سؤال باید بین ۱ تا ۳۰۰ باشد.'

D1 = datetime.date(2026, 8, 10)
D2 = datetime.date(2026, 8, 20)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _engagement(advisor, student, *, status=Status.ACTIVE, **kwargs):
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': status,
    }
    if status == Status.ACTIVE:
        defaults['started_on'] = D1
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _flat_errors(data) -> list[str]:
    """Every leaf message of a DRF error body, however deeply it is nested."""
    if isinstance(data, dict):
        return [msg for value in data.values() for msg in _flat_errors(value)]
    if isinstance(data, list):
        return [msg for value in data for msg in _flat_errors(value)]
    return [str(data)]


def _score_payload(**overrides):
    """A valid full score body; overrides replace top-level keys wholesale."""
    payload = {
        'title': 'آزمون جامع ریاضی',
        'subjectId': None,
        'examKind': 'SCHOOL',
        'examDate': '2026-08-20',
        'scorePercent': 87.5,
        'tara': 7200,
        'advisorRating': 'GOOD',
        'advisorNote': 'روند خوبی دارد.',
    }
    payload.update(overrides)
    return payload


def _service_score_payload(**overrides):
    """A valid snake_case payload for direct service calls."""
    payload = {
        'title': 'آزمون جامع ریاضی',
        'subject_id': None,
        'exam_kind': 'SCHOOL',
        'exam_date': D2,
        'score_percent': 87.5,
        'tara': 7200,
        'advisor_rating': 'GOOD',
        'advisor_note': 'روند خوبی دارد.',
    }
    payload.update(overrides)
    return payload


# ── phase 1 · service ─────────────────────────────────────────────────────────

def test_create_exam_score_persists_fields_and_stamps_creator():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    score = exam_service.create_exam_score(
        engagement, _service_score_payload(), actor=advisor,
    )

    assert score.pk is not None
    assert score.title == 'آزمون جامع ریاضی'
    assert score.exam_kind == 'SCHOOL'
    assert score.exam_date == D2
    assert score.score_percent == 87.5
    assert score.tara == 7200
    assert score.advisor_rating == 'GOOD'
    assert score.created_by_id == advisor.pk


def test_exam_score_cap_is_forty_per_engagement():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    baker.make(
        StudyExamScore,
        engagement=engagement,
        title='ردیف',
        exam_kind='PERSONAL',
        exam_date=D1,
        score_percent=50,
        _quantity=exam_service.MAX_EXAM_SCORES,
    )

    assert engagement.exam_scores.count() == 40
    with pytest.raises(exam_service.ExamRecordError) as excinfo:
        exam_service.create_exam_score(
            engagement, _service_score_payload(), actor=advisor,
        )
    assert str(excinfo.value) == MSG_CAP

    # The ceiling is per engagement, not global: another engagement still works.
    other_advisor, other_student = _advisor('adv2'), _student('stu2', phone='09120000002')
    other = _engagement(other_advisor, other_student)
    assert exam_service.create_exam_score(
        other, _service_score_payload(), actor=other_advisor,
    ).pk is not None


@pytest.mark.parametrize('overrides,message', [
    ({'score_percent': 100.01}, MSG_PERCENT),
    ({'score_percent': -0.01}, MSG_PERCENT),
    ({'exam_kind': 'OLYMPIAD'}, MSG_KIND),
    ({'advisor_rating': 'PERFECT'}, MSG_RATING),
    ({'subject_id': 999999}, MSG_SUBJECT),
])
def test_create_exam_score_rejects_invalid_payloads_without_writing(overrides, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    with pytest.raises(exam_service.ExamRecordError) as excinfo:
        exam_service.create_exam_score(
            engagement, _service_score_payload(**overrides), actor=advisor,
        )
    assert str(excinfo.value) == message
    assert StudyExamScore.objects.count() == 0


def test_update_exam_score_changes_only_provided_keys():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    score = exam_service.create_exam_score(
        engagement, _service_score_payload(), actor=advisor,
    )

    updated = exam_service.update_exam_score(
        score, {'score_percent': 91, 'advisor_note': ''},
    )

    assert updated.score_percent == 91
    assert updated.advisor_note == ''
    # Untouched keys keep their stored values.
    assert updated.title == 'آزمون جامع ریاضی'
    assert updated.tara == 7200
    assert updated.advisor_rating == 'GOOD'


def test_delete_exam_score_removes_the_row():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    score = exam_service.create_exam_score(
        engagement, _service_score_payload(), actor=advisor,
    )

    exam_service.delete_exam_score(score)

    assert not StudyExamScore.objects.filter(pk=score.pk).exists()


# ── phase 1 · API: advisor side ───────────────────────────────────────────────

def test_advisor_post_creates_and_get_lists_newest_first():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    created = _auth(advisor).post(
        SCORES_URL.format(pk=engagement.pk), _score_payload(), format='json',
    )
    assert created.status_code == 201
    assert created.data == {
        'id': created.data['id'],
        'title': 'آزمون جامع ریاضی',
        'subjectId': None,
        'subjectName': None,
        'examKind': 'SCHOOL',
        'examDate': '2026-08-20',
        'scorePercent': 87.5,
        'tara': 7200,
        'advisorRating': 'GOOD',
        'advisorNote': 'روند خوبی دارد.',
    }

    # An older exam added second must sort after the newer one.
    older = _auth(advisor).post(
        SCORES_URL.format(pk=engagement.pk),
        _score_payload(examDate='2026-08-05', title='آزمون مهر'),
        format='json',
    )
    assert older.status_code == 201

    listed = _auth(advisor).get(SCORES_URL.format(pk=engagement.pk))
    assert listed.status_code == 200
    assert [row['id'] for row in listed.data] == [created.data['id'], older.data['id']]


def test_advisor_post_links_subject_and_returns_its_name():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    subject = baker.make(Subject, name='ریاضی')

    resp = _auth(advisor).post(
        SCORES_URL.format(pk=engagement.pk),
        _score_payload(subjectId=subject.pk),
        format='json',
    )

    assert resp.status_code == 201
    assert resp.data['subjectId'] == subject.pk
    assert resp.data['subjectName'] == 'ریاضی'


def test_advisor_patch_changes_only_sent_keys():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    score = exam_service.create_exam_score(
        engagement, _service_score_payload(), actor=advisor,
    )

    resp = _auth(advisor).patch(
        SCORE_DETAIL_URL.format(pk=engagement.pk, score_id=score.pk),
        {'scorePercent': 95, 'advisorRating': None},
        format='json',
    )

    assert resp.status_code == 200
    assert resp.data['scorePercent'] == 95
    assert resp.data['advisorRating'] is None      # explicit null clears
    assert resp.data['tara'] == 7200               # absent key untouched
    assert resp.data['title'] == 'آزمون جامع ریاضی'

    reloaded = StudyExamScore.objects.get(pk=score.pk)
    assert reloaded.score_percent == 95
    assert reloaded.advisor_rating is None


def test_advisor_delete_removes_the_row():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    score = exam_service.create_exam_score(
        engagement, _service_score_payload(), actor=advisor,
    )

    resp = _auth(advisor).delete(
        SCORE_DETAIL_URL.format(pk=engagement.pk, score_id=score.pk),
    )

    assert resp.status_code == 204
    assert not StudyExamScore.objects.filter(pk=score.pk).exists()


def test_advisor_post_over_the_cap_is_400_with_persian_message():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    baker.make(
        StudyExamScore,
        engagement=engagement,
        title='ردیف',
        exam_kind='PERSONAL',
        exam_date=D1,
        score_percent=50,
        _quantity=exam_service.MAX_EXAM_SCORES,
    )

    resp = _auth(advisor).post(
        SCORES_URL.format(pk=engagement.pk), _score_payload(), format='json',
    )

    assert resp.status_code == 400
    assert resp.data['detail'] == MSG_CAP


@pytest.mark.parametrize('overrides,message', [
    ({'scorePercent': 100.5}, MSG_PERCENT),
    ({'scorePercent': -1}, MSG_PERCENT),
    ({'examKind': 'OLYMPIAD'}, MSG_KIND),
    ({'advisorRating': 'PERFECT'}, MSG_RATING),
    ({'subjectId': 424242}, MSG_SUBJECT),
])
def test_advisor_post_rejects_invalid_fields_with_pinned_messages(overrides, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).post(
        SCORES_URL.format(pk=engagement.pk), _score_payload(**overrides), format='json',
    )

    assert resp.status_code == 400
    assert message in _flat_errors(resp.data)
    assert StudyExamScore.objects.count() == 0


def test_a_score_of_another_engagement_is_404_on_detail_routes():
    owner, stranger = _advisor('adv_owner'), _advisor('adv_stranger')
    engagement = _engagement(owner, _student())
    score = exam_service.create_exam_score(
        engagement, _service_score_payload(), actor=owner,
    )
    foreign_url = SCORE_DETAIL_URL.format(
        pk=_engagement(
            stranger, _student('stu_foreign', phone='09120000003'),
        ).pk, score_id=score.pk,
    )

    client = _auth(stranger)
    assert client.patch(foreign_url, {}, format='json').status_code == 404
    assert client.delete(foreign_url).status_code == 404
    # The row itself was never touched.
    assert StudyExamScore.objects.filter(pk=score.pk).exists()


# ── phase 1 · API: student mirror ─────────────────────────────────────────────

def test_student_mirror_without_an_engagement_is_a_quiet_200():
    resp = _auth(_student()).get(MY_SCORES_URL)

    assert resp.status_code == 200
    assert resp.data == {'active': False, 'scores': []}


def test_student_mirror_lists_own_scores_newest_first():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    newer = exam_service.create_exam_score(
        engagement, _service_score_payload(exam_date=D2), actor=advisor,
    )
    older = exam_service.create_exam_score(
        engagement, _service_score_payload(exam_date=D1), actor=advisor,
    )

    resp = _auth(student).get(MY_SCORES_URL)

    assert resp.status_code == 200
    assert resp.data['active'] is True
    assert [row['id'] for row in resp.data['scores']] == [newer.pk, older.pk]
    assert resp.data['scores'][0]['examKind'] == 'SCHOOL'


def test_student_has_no_write_route_for_scores():
    client = _auth(_student())
    # The mirror path exists but is GET-only: DRF dispatch answers 405, never
    # a write. No addressable child route exists at all ⇒ 404.
    assert client.post(MY_SCORES_URL, _score_payload(), format='json').status_code == 405
    assert client.put(MY_SCORES_URL, _score_payload(), format='json').status_code == 405
    assert client.delete(
        MY_SCORES_URL.rstrip('/') + '/123/',
    ).status_code == 404


# ── phase 1 · permission matrix ───────────────────────────────────────────────

@pytest.mark.permission
def test_stranger_advisor_gets_404_not_403_on_every_score_route():
    owner, stranger = _advisor('adv_owner'), _advisor('adv_stranger')
    engagement = _engagement(owner, _student())

    client = _auth(stranger)
    assert client.get(SCORES_URL.format(pk=engagement.pk)).status_code == 404
    assert client.post(
        SCORES_URL.format(pk=engagement.pk), _score_payload(), format='json',
    ).status_code == 404
    assert client.patch(
        SCORE_DETAIL_URL.format(pk=engagement.pk, score_id=1), {}, format='json',
    ).status_code == 404
    assert client.delete(
        SCORE_DETAIL_URL.format(pk=engagement.pk, score_id=1),
    ).status_code == 404
    assert StudyExamScore.objects.count() == 0


@pytest.mark.permission
def test_a_student_is_forbidden_on_the_advisor_score_routes():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    client = _auth(student)
    assert client.get(SCORES_URL.format(pk=engagement.pk)).status_code == 403
    assert client.post(
        SCORES_URL.format(pk=engagement.pk), _score_payload(), format='json',
    ).status_code == 403
    assert client.patch(
        SCORE_DETAIL_URL.format(pk=engagement.pk, score_id=1), {}, format='json',
    ).status_code == 403
    assert client.delete(
        SCORE_DETAIL_URL.format(pk=engagement.pk, score_id=1),
    ).status_code == 403


@pytest.mark.permission
def test_an_advisor_is_forbidden_on_the_student_score_route():
    client = _auth(_advisor())
    assert client.get(MY_SCORES_URL).status_code == 403


@pytest.mark.permission
def test_anonymous_is_rejected_on_every_score_route():
    anon = APIClient()
    assert anon.get(MY_SCORES_URL).status_code == 401
    assert anon.get(SCORES_URL.format(pk=1)).status_code == 401
    assert anon.post(
        SCORES_URL.format(pk=1), _score_payload(), format='json',
    ).status_code == 401


# ── phase 2 · payloads ────────────────────────────────────────────────────────

def _analysis_payload(**overrides):
    """A valid full analysis body; overrides replace top-level keys wholesale."""
    payload = {
        'examNumber': 3,
        'examDate': '2026-08-18',
        'gradeBand': 'G12S1',
        'totalTara': 6800,
        'nationalRank': 1240,
        'regionRank': 310,
        'cityRank': 95,
        'highestPercent': 88.25,
        'lowestPercent': 41.5,
        'taraDelta': 150,
        'advisorReport': 'روند صعودی دارد؛ تمرکز روی دینی باشد.',
        'rows': [
            {
                'subjectName': 'ریاضی',
                'wrongCount': 4,
                'skippedCount': 2,
                'doubtfulTotal': 10,
                'doubtfulWrong': 3,
                'doubtfulSkipped': 2,
                'doubtfulCorrect': 5,
                'causeNote': 'بی‌دقتی در علامت‌گذاری',
            },
            {
                'subjectName': 'دینی',
                'wrongCount': 9,
                'skippedCount': 0,
                'doubtfulTotal': 0,
                'doubtfulWrong': 0,
                'doubtfulSkipped': 0,
                'doubtfulCorrect': 0,
                'causeNote': '',
            },
        ],
        'notes': [
            {'questionNumber': 12, 'subjectName': 'ریاضی', 'note': 'سؤال چالشی بود.'},
            {'questionNumber': 45, 'subjectName': 'دینی', 'note': ''},
        ],
    }
    payload.update(overrides)
    return payload


def _service_analysis_payload(**overrides):
    """A valid snake_case payload for direct service calls."""
    payload = {
        'exam_number': 3,
        'exam_date': D2,
        'grade_band': 'G12S1',
        'total_tara': 6800,
        'national_rank': 1240,
        'region_rank': 310,
        'city_rank': 95,
        'highest_percent': 88.25,
        'lowest_percent': 41.5,
        'tara_delta': 150,
        'advisor_report': 'روند صعودی دارد.',
        'rows': [
            {
                'subject_name': 'ریاضی',
                'wrong_count': 4,
                'skipped_count': 2,
                'doubtful_total': 10,
                'doubtful_wrong': 3,
                'doubtful_skipped': 2,
                'doubtful_correct': 5,
                'cause_note': 'بی‌دقتی',
            },
        ],
        'notes': [
            {'question_number': 12, 'subject_name': 'ریاضی', 'note': 'چالشی.'},
        ],
    }
    payload.update(overrides)
    return payload


# ── phase 2 · service ─────────────────────────────────────────────────────────

def test_create_analysis_persists_scalars_rows_and_notes():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    analysis = exam_service.create_analysis(
        engagement, _service_analysis_payload(),
    )

    assert analysis.exam_number == 3
    assert analysis.exam_date == D2
    assert analysis.grade_band == 'G12S1'
    assert analysis.total_tara == 6800
    assert analysis.tara_delta == 150
    assert analysis.highest_percent == 88.25
    rows = list(analysis.rows.all())
    assert [r.subject_name for r in rows] == ['ریاضی']
    assert rows[0].doubtful_total == 10
    notes = list(analysis.notes.all())
    assert [n.question_number for n in notes] == [12]


def test_replace_analysis_swaps_children_wholesale_in_place():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    analysis = exam_service.create_analysis(engagement, _service_analysis_payload())
    old_row_pk = analysis.rows.first().pk

    replaced = exam_service.replace_analysis(analysis, _service_analysis_payload(
        total_tara=7000,
        rows=[_service_analysis_payload()['rows'][0] | {'subject_name': 'شیمی'}],
        notes=[],
    ))

    assert replaced.pk == analysis.pk
    assert replaced.total_tara == 7000
    # The old row really died; a new one took its place.
    assert not StudyExamAnalysisRow.objects.filter(pk=old_row_pk).exists()
    assert [r.subject_name for r in replaced.rows.all()] == ['شیمی']
    assert replaced.notes.count() == 0


def test_delete_analysis_removes_the_document_and_children():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    analysis = exam_service.create_analysis(engagement, _service_analysis_payload())

    exam_service.delete_analysis(analysis)

    assert not StudyExamAnalysis.objects.filter(pk=analysis.pk).exists()
    assert StudyExamAnalysisRow.objects.count() == 0
    assert StudyExamAnalysisNote.objects.count() == 0


@pytest.mark.parametrize('overrides,message', [
    ({'grade_band': 'G13'}, MSG_GRADE_BAND),
    ({'highest_percent': 100.01}, MSG_PERCENT),
    ({'lowest_percent': -1}, MSG_PERCENT),
    ({
        'rows': [{'subject_name': 'ریاضی', 'doubtful_total': 5, 'doubtful_wrong': 6}],
    }, MSG_DOUBTFUL),
    ({
        'rows': [{'subject_name': 'ریاضی', 'doubtful_total': 5, 'doubtful_skipped': 7}],
    }, MSG_DOUBTFUL),
    ({
        'rows': [{'subject_name': 'ریاضی', 'doubtful_total': 5, 'doubtful_correct': 8}],
    }, MSG_DOUBTFUL),
    ({'notes': [{'question_number': 0, 'subject_name': 'ریاضی'}]}, MSG_QUESTION_NUMBER),
    ({'notes': [{'question_number': 301, 'subject_name': 'ریاضی'}]}, MSG_QUESTION_NUMBER),
])
def test_create_analysis_rejects_invalid_payloads_without_writing(overrides, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    with pytest.raises(exam_service.ExamRecordError) as excinfo:
        exam_service.create_analysis(
            engagement, _service_analysis_payload(**overrides),
        )
    assert str(excinfo.value) == message
    assert StudyExamAnalysis.objects.count() == 0
    assert StudyExamAnalysisRow.objects.count() == 0
    assert StudyExamAnalysisNote.objects.count() == 0


def test_duplicate_note_question_is_reported_with_the_question_number():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    with pytest.raises(exam_service.ExamRecordError) as excinfo:
        exam_service.create_analysis(engagement, _service_analysis_payload(
            notes=[
                {'question_number': 30, 'subject_name': 'ریاضی', 'note': 'اول'},
                {'question_number': 30, 'subject_name': 'دینی', 'note': 'دوم'},
            ],
        ))
    assert str(excinfo.value) == 'برای سؤال 30 دو یادداشت ثبت شده است.'
    assert StudyExamAnalysis.objects.count() == 0


# ── phase 2 · API: advisor side ───────────────────────────────────────────────

def test_advisor_post_creates_full_document_and_get_lists_nulls_last():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    created = _auth(advisor).post(
        ANALYSES_URL.format(pk=engagement.pk), _analysis_payload(), format='json',
    )
    assert created.status_code == 201
    assert created.data['examNumber'] == 3
    assert created.data['examDate'] == '2026-08-18'
    assert created.data['gradeBand'] == 'G12S1'
    assert created.data['highestPercent'] == 88.25
    assert created.data['rows'][0] == {
        'subjectName': 'ریاضی',
        'wrongCount': 4,
        'skippedCount': 2,
        'doubtfulTotal': 10,
        'doubtfulWrong': 3,
        'doubtfulSkipped': 2,
        'doubtfulCorrect': 5,
        'causeNote': 'بی‌دقتی در علامت‌گذاری',
    }
    assert created.data['notes'] == [
        {'questionNumber': 12, 'subjectName': 'ریاضی', 'note': 'سؤال چالشی بود.'},
        {'questionNumber': 45, 'subjectName': 'دینی', 'note': ''},
    ]

    # A dated analysis and a dateless one: dated first (DESC), nulls last.
    dateless = _auth(advisor).post(
        ANALYSES_URL.format(pk=engagement.pk),
        _analysis_payload(examDate=None, examNumber=2),
        format='json',
    )
    assert dateless.status_code == 201

    listed = _auth(advisor).get(ANALYSES_URL.format(pk=engagement.pk))
    assert listed.status_code == 200
    assert [row['id'] for row in listed.data] == [created.data['id'], dateless.data['id']]


def test_advisor_get_detail_put_and_delete_roundtrip():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    created = _auth(advisor).post(
        ANALYSES_URL.format(pk=engagement.pk), _analysis_payload(), format='json',
    )
    detail_url = ANALYSIS_DETAIL_URL.format(
        pk=engagement.pk, analysis_id=created.data['id'],
    )

    seen = _auth(advisor).get(detail_url)
    assert seen.status_code == 200
    assert seen.data == created.data

    put = _auth(advisor).put(detail_url, _analysis_payload(
        totalTara=7100,
        rows=[_analysis_payload()['rows'][1]],
        notes=[{'questionNumber': 300, 'subjectName': 'عربی', 'note': 'آخرین سؤال'}],
    ), format='json')
    assert put.status_code == 200
    assert put.data['id'] == created.data['id']
    assert put.data['totalTara'] == 7100
    assert [r['subjectName'] for r in put.data['rows']] == ['دینی']
    assert [n['questionNumber'] for n in put.data['notes']] == [300]

    deleted = _auth(advisor).delete(detail_url)
    assert deleted.status_code == 204
    assert not StudyExamAnalysis.objects.filter(pk=created.data['id']).exists()


@pytest.mark.parametrize('overrides,message', [
    ({'gradeBand': 'G13'}, MSG_GRADE_BAND),
    ({'highestPercent': 120}, MSG_PERCENT),
    ({'lowestPercent': -5}, MSG_PERCENT),
    ({
        'rows': [{
            'subjectName': 'ریاضی', 'doubtfulTotal': 2,
            'doubtfulCorrect': 3,
        }],
    }, MSG_DOUBTFUL),
    ({'notes': [{'questionNumber': 301, 'subjectName': 'ریاضی'}]}, MSG_QUESTION_NUMBER),
])
def test_advisor_post_rejects_invalid_analyses_with_pinned_messages(overrides, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).post(
        ANALYSES_URL.format(pk=engagement.pk), _analysis_payload(**overrides), format='json',
    )

    assert resp.status_code == 400
    assert message in _flat_errors(resp.data)
    assert StudyExamAnalysis.objects.count() == 0


def test_duplicate_note_question_over_the_api_is_400_naming_the_question():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).post(
        ANALYSES_URL.format(pk=engagement.pk), _analysis_payload(notes=[
            {'questionNumber': 7, 'subjectName': 'ریاضی', 'note': 'الف'},
            {'questionNumber': 7, 'subjectName': 'دینی', 'note': 'ب'},
        ]), format='json',
    )

    assert resp.status_code == 400
    assert resp.data['detail'] == 'برای سؤال 7 دو یادداشت ثبت شده است.'


def test_an_analysis_of_another_engagement_is_404_on_detail_routes():
    owner, stranger = _advisor('adv_owner'), _advisor('adv_stranger')
    engagement = _engagement(owner, _student())
    analysis = exam_service.create_analysis(engagement, _service_analysis_payload())
    foreign_url = ANALYSIS_DETAIL_URL.format(
        pk=_engagement(
            stranger, _student('stu_foreign2', phone='09120000004'),
        ).pk, analysis_id=analysis.pk,
    )

    client = _auth(stranger)
    assert client.get(foreign_url).status_code == 404
    assert client.put(foreign_url, _analysis_payload(), format='json').status_code == 404
    assert client.delete(foreign_url).status_code == 404
    assert StudyExamAnalysis.objects.filter(pk=analysis.pk).exists()


# ── phase 2 · API: student mirror ─────────────────────────────────────────────

def test_student_analysis_mirror_without_an_engagement_is_a_quiet_200():
    resp = _auth(_student()).get(MY_ANALYSES_URL)

    assert resp.status_code == 200
    assert resp.data == {'active': False, 'analyses': []}


def test_student_analysis_mirror_lists_own_documents_newest_first():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    newer = exam_service.create_analysis(
        engagement, _service_analysis_payload(exam_date=D2),
    )
    older = exam_service.create_analysis(
        engagement, _service_analysis_payload(exam_date=D1),
    )

    resp = _auth(student).get(MY_ANALYSES_URL)

    assert resp.status_code == 200
    assert resp.data['active'] is True
    assert [row['id'] for row in resp.data['analyses']] == [newer.pk, older.pk]
    assert resp.data['analyses'][0]['rows'][0]['subjectName'] == 'ریاضی'


def test_student_has_no_write_route_for_analyses():
    client = _auth(_student())
    # The mirror path exists but is GET-only: DRF dispatch answers 405, never
    # a write. No addressable child route exists at all ⇒ 404.
    assert client.post(MY_ANALYSES_URL, _analysis_payload(), format='json').status_code == 405
    assert client.put(MY_ANALYSES_URL, _analysis_payload(), format='json').status_code == 405
    assert client.delete(
        MY_ANALYSES_URL.rstrip('/') + '/123/',
    ).status_code == 404


# ── phase 2 · permission matrix ───────────────────────────────────────────────

@pytest.mark.permission
def test_stranger_advisor_gets_404_not_403_on_every_analysis_route():
    owner, stranger = _advisor('adv_owner'), _advisor('adv_stranger')
    engagement = _engagement(owner, _student())

    client = _auth(stranger)
    assert client.get(ANALYSES_URL.format(pk=engagement.pk)).status_code == 404
    assert client.post(
        ANALYSES_URL.format(pk=engagement.pk), _analysis_payload(), format='json',
    ).status_code == 404
    assert client.put(
        ANALYSIS_DETAIL_URL.format(pk=engagement.pk, analysis_id=1),
        _analysis_payload(), format='json',
    ).status_code == 404
    assert client.delete(
        ANALYSIS_DETAIL_URL.format(pk=engagement.pk, analysis_id=1),
    ).status_code == 404
    assert StudyExamAnalysis.objects.count() == 0


@pytest.mark.permission
def test_a_student_is_forbidden_on_the_advisor_analysis_routes():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    client = _auth(student)
    assert client.get(ANALYSES_URL.format(pk=engagement.pk)).status_code == 403
    assert client.post(
        ANALYSES_URL.format(pk=engagement.pk), _analysis_payload(), format='json',
    ).status_code == 403
    assert client.put(
        ANALYSIS_DETAIL_URL.format(pk=engagement.pk, analysis_id=1),
        _analysis_payload(), format='json',
    ).status_code == 403
    assert client.delete(
        ANALYSIS_DETAIL_URL.format(pk=engagement.pk, analysis_id=1),
    ).status_code == 403


@pytest.mark.permission
def test_an_advisor_is_forbidden_on_the_student_analysis_route():
    client = _auth(_advisor())
    assert client.get(MY_ANALYSES_URL).status_code == 403


@pytest.mark.permission
def test_anonymous_is_rejected_on_every_analysis_route():
    anon = APIClient()
    assert anon.get(MY_ANALYSES_URL).status_code == 401
    assert anon.get(ANALYSES_URL.format(pk=1)).status_code == 401
    assert anon.post(
        ANALYSES_URL.format(pk=1), _analysis_payload(), format='json',
    ).status_code == 401
