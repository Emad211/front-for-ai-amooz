"""Restart step 7 — the advisor's weekly assessment: service door and endpoint.

``upsert_weekly_assessment`` writes the single row per ``(engagement,
week_start)``; ``GET|PUT /api/advisory/students/<pk>/weekly-assessments/`` is
its only route in — and by locked decision there is **no** student route, which
the negative test at the bottom pins. The service tests hold the criteria
contract (exactly 15, unique codes), the upsert-not-duplicate rule, the
one-decimal average and every pinned Persian message. The API tests hold the
wire shape (criteria list + DESC assessments), the query-parameter handling,
and the access matrix.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import AdvisoryEngagement, WeeklyAssessment
from apps.advisory.services import assessments as assessment_service
from apps.advisory.services.calendar import week_start_of

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

URL = '/api/advisory/students/{pk}/weekly-assessments/'
ME_URL = '/api/advisory/me/weekly-assessments/'

MSG_SATURDAY = 'تاریخ باید شنبه باشد.'
MSG_INCOMPLETE = 'همۀ ۱۵ معیار باید امتیاز داشته باشند.'


def _full_scores(**overrides):
    scores = {code: 3 for code, _ in assessment_service.WEEKLY_ASSESSMENT_CRITERIA}
    scores.update(overrides)
    return scores


# ── fixtures ──────────────────────────────────────────────────────────────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _engagement(advisor, student, **kwargs):
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': Status.ACTIVE,
        'started_on': timezone.localdate(),
    }
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _flat_errors(data) -> list[str]:
    if isinstance(data, dict):
        return [msg for value in data.values() for msg in _flat_errors(value)]
    if isinstance(data, list):
        return [msg for value in data for msg in _flat_errors(value)]
    return [str(data)]


def _this_saturday():
    return week_start_of(timezone.localdate())


# ── service ───────────────────────────────────────────────────────────────────

def test_the_criteria_constant_is_exactly_fifteen_unique_coded_criteria():
    criteria = assessment_service.WEEKLY_ASSESSMENT_CRITERIA
    assert len(criteria) == 15
    codes = [code for code, _ in criteria]
    assert len(set(codes)) == 15
    assert all(isinstance(label, str) and label for _, label in criteria)
    # Spot-check first and last against the plan doc's pinned tuples.
    assert criteria[0] == ('plan_order', 'نظم و هماهنگی در اجرای برنامه')
    assert criteria[-1] == ('home_environment', 'شرایط محیط منزل')


def test_upsert_creates_then_updates_in_place_preserving_created_by():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    week = _this_saturday()

    first = assessment_service.upsert_weekly_assessment(
        engagement, week, _full_scores(plan_order=5), 'هفتهٔ خوب', advisor,
    )
    second = assessment_service.upsert_weekly_assessment(
        engagement, week, _full_scores(plan_order=2), '', advisor,
    )

    assert second.pk == first.pk
    assert WeeklyAssessment.objects.count() == 1
    assert second.scores['plan_order'] == 2
    assert second.advisor_summary == ''
    assert second.created_by_id == advisor.pk   # first author survives updates


@pytest.mark.parametrize('week_offset', [0, 3])
def test_a_non_saturday_week_start_is_rejected(week_offset):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    bad_day = _this_saturday() + datetime.timedelta(days=1 + week_offset)

    with pytest.raises(assessment_service.WeeklyAssessmentError) as excinfo:
        assessment_service.upsert_weekly_assessment(
            engagement, bad_day, _full_scores(), '', advisor,
        )
    assert str(excinfo.value) == MSG_SATURDAY


def test_incomplete_scores_are_rejected_with_the_pinned_message():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    scores = _full_scores()
    del scores['sleep_routine']

    with pytest.raises(assessment_service.WeeklyAssessmentError) as excinfo:
        assessment_service.upsert_weekly_assessment(
            engagement, _this_saturday(), scores, '', advisor,
        )
    assert str(excinfo.value) == MSG_INCOMPLETE


@pytest.mark.parametrize('bad_value', [0, 6, True, '4', 4.0, None])
def test_an_out_of_band_or_non_int_score_names_the_criterion_label(bad_value):
    label = 'روتین خواب'
    with pytest.raises(assessment_service.WeeklyAssessmentError) as excinfo:
        assessment_service.validate_scores(_full_scores(sleep_routine=bad_value))
    assert str(excinfo.value) == f'امتیاز معیار {label} باید عددی بین ۱ تا ۵ باشد.'


def test_an_unknown_code_is_rejected_naming_the_raw_code():
    with pytest.raises(assessment_service.WeeklyAssessmentError) as excinfo:
        assessment_service.validate_scores(_full_scores(bogus_extra=3))
    assert str(excinfo.value) == 'امتیاز معیار bogus_extra باید عددی بین ۱ تا ۵ باشد.'


def test_average_is_the_one_decimal_mean_of_all_fifteen():
    # 13×3 + 5 + 4 = 48 → 48/15 = 3.2 exactly at one decimal place.
    scores = _full_scores(plan_order=5, exam_discipline=4)
    assert assessment_service.assessment_average(scores) == 3.2


# ── API: GET ──────────────────────────────────────────────────────────────────

def test_get_returns_the_criteria_list_and_desc_sorted_assessments():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    this_week = _this_saturday()
    last_week = this_week - datetime.timedelta(days=7)
    assessment_service.upsert_weekly_assessment(
        engagement, this_week, _full_scores(), 'جاری', advisor,
    )
    assessment_service.upsert_weekly_assessment(
        engagement, last_week, _full_scores(study_hours=5), 'گذشته', advisor,
    )

    resp = _auth(advisor).get(URL.format(pk=engagement.pk))

    assert resp.status_code == 200
    assert resp.data['criteria'] == [
        {'code': code, 'label': label}
        for code, label in assessment_service.WEEKLY_ASSESSMENT_CRITERIA
    ]
    weeks = [item['weekStart'] for item in resp.data['assessments']]
    assert weeks == [this_week.isoformat(), last_week.isoformat()]   # newest first
    first = resp.data['assessments'][0]
    assert first['scores']['plan_order'] == 3
    assert first['advisorSummary'] == 'جاری'
    assert first['average'] == 3.0


def test_get_with_no_assessments_still_answers_the_criteria_list():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).get(URL.format(pk=engagement.pk))
    assert resp.status_code == 200
    assert len(resp.data['criteria']) == 15
    assert resp.data['assessments'] == []


# ── API: PUT ──────────────────────────────────────────────────────────────────

def test_put_happy_path_upserts_and_returns_the_single_item_shape():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    week = _this_saturday()
    url = f'{URL.format(pk=engagement.pk)}?week_start={week.isoformat()}'

    body = {'scores': _full_scores(mood_level=4), 'advisorSummary': 'انگیزه بالا'}
    put = _auth(advisor).put(url, body, format='json')
    assert put.status_code == 200
    assert put.data['weekStart'] == week.isoformat()
    assert put.data['scores'] == _full_scores(mood_level=4)
    assert put.data['advisorSummary'] == 'انگیزه بالا'
    # 14×3 + 1×4 = 46 → 46/15 → 3.1 at one decimal place.
    assert put.data['average'] == 3.1
    assert WeeklyAssessment.objects.count() == 1

    # Re-saving the same week updates instead of duplicating.
    again = _auth(advisor).put(url, {'scores': _full_scores()}, format='json')
    assert again.status_code == 200
    assert WeeklyAssessment.objects.count() == 1
    assert again.data['scores'] == _full_scores()


def test_put_requires_the_week_start_parameter():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).put(
        URL.format(pk=engagement.pk), {'scores': _full_scores()}, format='json',
    )
    assert resp.status_code == 400
    assert resp.data['detail'] == 'پارامتر week_start الزامی است.'


@pytest.mark.parametrize('raw', ['2026-13-45', 'someday'])
def test_put_rejects_malformed_week_start(raw):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).put(
        f'{URL.format(pk=engagement.pk)}?week_start={raw}',
        {'scores': _full_scores()}, format='json',
    )
    assert resp.status_code == 400
    assert resp.data['detail'] == 'تاریخ باید به شکل YYYY-MM-DD باشد.'


def test_put_rejects_a_non_saturday_week_start_with_400():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    sunday = _this_saturday() + datetime.timedelta(days=1)

    resp = _auth(advisor).put(
        f'{URL.format(pk=engagement.pk)}?week_start={sunday.isoformat()}',
        {'scores': _full_scores()}, format='json',
    )
    assert resp.status_code == 400
    assert resp.data['detail'] == MSG_SATURDAY
    assert WeeklyAssessment.objects.count() == 0


def test_put_rejects_incomplete_scores_with_400():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    scores = _full_scores()
    del scores['focus_quality']

    resp = _auth(advisor).put(
        f"{URL.format(pk=engagement.pk)}?week_start={_this_saturday().isoformat()}",
        {'scores': scores}, format='json',
    )
    assert resp.status_code == 400
    assert MSG_INCOMPLETE in _flat_errors(resp.data)
    assert WeeklyAssessment.objects.count() == 0


# ── API: the permission matrix and the locked no-student-route rule ──────────

@pytest.mark.permission
def test_stranger_advisor_gets_404_not_403():
    owner, stranger = _advisor('adv_owner'), _advisor('adv_stranger')
    student = _student()
    engagement = _engagement(owner, student)

    client = _auth(stranger)
    assert client.get(URL.format(pk=engagement.pk)).status_code == 404
    assert client.put(
        f"{URL.format(pk=engagement.pk)}?week_start={_this_saturday().isoformat()}",
        {'scores': _full_scores()}, format='json',
    ).status_code == 404
    assert WeeklyAssessment.objects.count() == 0


@pytest.mark.permission
def test_a_student_is_forbidden_on_the_advisor_route():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    client = _auth(student)
    assert client.get(URL.format(pk=engagement.pk)).status_code == 403
    assert client.put(
        f"{URL.format(pk=engagement.pk)}?week_start={_this_saturday().isoformat()}",
        {'scores': _full_scores()}, format='json',
    ).status_code == 403


@pytest.mark.permission
def test_there_is_no_student_route_for_assessments():
    """گام ۷ lock: the assessment is advisor-internal — the me-path must not exist."""
    resp = _auth(_student()).get(ME_URL)
    assert resp.status_code == 404
