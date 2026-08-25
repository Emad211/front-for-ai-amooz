"""Restart step 10 — the weekly call log: service door and endpoint.

``list_call_logs`` materializes the four most recent weeks (stored rows win,
absent weeks fill virtually with the rotating default topic) and
``upsert_call_log`` writes the single row per ``(engagement, week_start)``
with keep-when-absent semantics for the optional keys. The endpoint
``GET|PUT /api/advisory/students/<pk>/call-logs/`` is their only route in —
no student route exists (locked), pinned by a negative test. The service tests
hold the week-index math and topic rotation; the API tests hold the wire shape,
the upsert semantics and the access matrix.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import AdvisoryEngagement, WeeklyCallLog
from apps.advisory.services import calls as call_service
from apps.advisory.services.calendar import week_start_of

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

URL = '/api/advisory/students/{pk}/call-logs/'
ME_URL = '/api/advisory/me/call-logs/'

MSG_SATURDAY = 'تاریخ باید شنبه باشد.'


# ── fixtures ──────────────────────────────────────────────────────────────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _engagement(advisor, student, *, started_on=None, **kwargs):
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': Status.ACTIVE,
        'started_on': started_on if started_on is not None else timezone.localdate(),
    }
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _this_saturday():
    return week_start_of(timezone.localdate())


def _week_url(pk, week=None):
    suffix = '' if week is None else f'?week_start={week.isoformat()}'
    return f'{URL.format(pk=pk)}{suffix}'


# ── service: week-index math and topic rotation ───────────────────────────────

def test_week_index_floors_seven_day_steps_and_clamps_at_zero():
    advisor, student = _advisor(), _student()
    start = datetime.date(2026, 8, 1)          # a Saturday
    engagement = _engagement(advisor, student, started_on=start)

    assert call_service.week_index_for(engagement, start) == 0
    assert call_service.week_index_for(engagement, start + datetime.timedelta(days=6)) == 0
    assert call_service.week_index_for(engagement, start + datetime.timedelta(days=7)) == 1
    assert call_service.week_index_for(engagement, start + datetime.timedelta(days=28)) == 4
    # Before the engagement: clamped, never negative.
    assert call_service.week_index_for(engagement, start - datetime.timedelta(days=7)) == 0


def test_week_index_with_a_null_started_on_reads_as_zero():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student, started_on=None)

    assert call_service.week_index_for(engagement, _this_saturday()) == 0


def test_default_topic_rotates_through_the_four_defaults():
    advisor, student = _advisor(), _student()
    start = datetime.date(2026, 8, 1)
    engagement = _engagement(advisor, student, started_on=start)

    expected = [
        'ارائۀ برنامۀ هفتگی و هدف‌گذاری',
        'انجام دقیق برنامه و گزارش‌کار',
        'تحلیل آزمون و برنامۀ جبرانی',
        'ارزیابی ماهانه و نقاط قوت/ضعف',
        # …and week 5 wraps back to the first topic.
        'ارائۀ برنامۀ هفتگی و هدف‌گذاری',
    ]
    for offset, topic in enumerate(expected):
        week = start + datetime.timedelta(days=7 * offset)
        assert call_service.default_topic_for(engagement, week) == topic


def test_list_materializes_four_weeks_ending_current_with_virtual_defaults():
    """Started four Saturdays ago, the four listed weeks carry indexes 1..4 —
    so their default topics rotate 1, 2, 3, then wrap 4 % 4 → 0."""
    advisor, student = _advisor(), _student()
    current = _this_saturday()
    engagement = _engagement(advisor, student, started_on=current - datetime.timedelta(days=28))

    items = call_service.list_call_logs(engagement)

    assert len(items) == 4
    assert [it['weekStart'] for it in items] == [
        current - datetime.timedelta(days=21),
        current - datetime.timedelta(days=14),
        current - datetime.timedelta(days=7),
        current,
    ]
    # All virtual: not done, no date, empty note, rotating default topics.
    assert all(it['done'] is False and it['callDate'] is None and it['note'] == '' for it in items)
    assert [it['topic'] for it in items] == [
        call_service.DEFAULT_CALL_TOPICS[1],
        call_service.DEFAULT_CALL_TOPICS[2],
        call_service.DEFAULT_CALL_TOPICS[3],
        call_service.DEFAULT_CALL_TOPICS[0],
    ]


def test_pre_engagement_weeks_clamp_to_the_first_default_topic():
    advisor, student = _advisor(), _student()
    current = _this_saturday()
    engagement = _engagement(advisor, student, started_on=current)

    items = call_service.list_call_logs(engagement)

    # All four listed weeks sit at or before ``started_on`` → index clamps to 0.
    assert [it['topic'] for it in items] == [call_service.DEFAULT_CALL_TOPICS[0]] * 4


def test_a_stored_row_wins_over_the_virtual_default():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student, started_on=_this_saturday())
    current = _this_saturday()

    WeeklyCallLog.objects.create(
        engagement=engagement, week_start=current,
        done=True, call_date=current + datetime.timedelta(days=2),
        topic='موضوعِ ویرایش‌شده', note='تماس گرفته شد',
    )

    items = call_service.list_call_logs(engagement)
    stored = items[-1]
    assert stored['done'] is True
    assert stored['callDate'] == current + datetime.timedelta(days=2)
    assert stored['topic'] == 'موضوعِ ویرایش‌شده'   # stored beats the default
    assert stored['note'] == 'تماس گرفته شد'
    # The other three weeks stay virtual.
    assert all(it['done'] is False for it in items[:3])


# ── service: upsert semantics ────────────────────────────────────────────────

def test_upsert_creates_then_updates_only_the_keys_that_were_sent():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    week = _this_saturday()

    first = call_service.upsert_call_log(engagement, week, done=False)
    assert first.topic == call_service.default_topic_for(engagement, week)
    assert first.call_date is None
    assert first.note == ''

    second = call_service.upsert_call_log(
        engagement, week, done=True,
        call_date=week + datetime.timedelta(days=1), note='یادداشت',
    )
    assert second.pk == first.pk
    assert second.done is True
    assert second.note == 'یادداشت'
    # Absent keys kept their stored values.
    assert second.topic == first.topic
    assert WeeklyCallLog.objects.count() == 1


def test_upsert_rejects_a_non_saturday_week_start():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    sunday = _this_saturday() + datetime.timedelta(days=1)

    with pytest.raises(call_service.CallLogError) as excinfo:
        call_service.upsert_call_log(engagement, sunday, done=True)
    assert str(excinfo.value) == MSG_SATURDAY
    assert WeeklyCallLog.objects.count() == 0


# ── API ───────────────────────────────────────────────────────────────────────

def test_get_answers_four_wire_shaped_weeks():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).get(_week_url(engagement.pk))

    assert resp.status_code == 200
    weeks = resp.data['weeks']
    assert len(weeks) == 4
    assert set(weeks[0]) == {'weekStart', 'done', 'callDate', 'topic', 'note'}
    assert weeks[-1]['weekStart'] == _this_saturday().isoformat()


def test_put_roundtrips_and_keeps_absent_optional_keys():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    week = _this_saturday()

    first = _auth(advisor).put(
        _week_url(engagement.pk, week),
        {'done': True, 'callDate': week.isoformat(), 'note': 'هماهنگی برنامه'},
        format='json',
    )
    assert first.status_code == 200
    assert first.data == {
        'weekStart': week.isoformat(),
        'done': True,
        'callDate': week.isoformat(),
        'topic': call_service.default_topic_for(engagement, week),
        'note': 'هماهنگی برنامه',
    }

    # Second PUT sends only `done`: everything else survives.
    second = _auth(advisor).put(_week_url(engagement.pk, week), {'done': False}, format='json')
    assert second.status_code == 200
    assert second.data['done'] is False
    assert second.data['callDate'] == week.isoformat()
    assert second.data['note'] == 'هماهنگی برنامه'
    assert WeeklyCallLog.objects.count() == 1


def test_put_can_clear_an_optional_key_by_sending_it_empty():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    week = _this_saturday()

    _auth(advisor).put(
        _week_url(engagement.pk, week), {'done': True, 'note': 'متن'}, format='json',
    )
    cleared = _auth(advisor).put(
        _week_url(engagement.pk, week), {'done': True, 'note': '', 'callDate': None},
        format='json',
    )
    assert cleared.status_code == 200
    assert cleared.data['note'] == ''
    assert cleared.data['callDate'] is None


def test_put_requires_the_week_start_parameter():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).put(URL.format(pk=engagement.pk), {'done': True}, format='json')
    assert resp.status_code == 400
    assert resp.data['detail'] == 'پارامتر week_start الزامی است.'


def test_put_rejects_a_non_saturday_week_start_with_400():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    friday = _this_saturday() + datetime.timedelta(days=6)

    resp = _auth(advisor).put(
        _week_url(engagement.pk, friday), {'done': True}, format='json',
    )
    assert resp.status_code == 400
    assert resp.data['detail'] == MSG_SATURDAY
    assert WeeklyCallLog.objects.count() == 0


# ── API: the permission matrix and the locked no-student-route rule ──────────

@pytest.mark.permission
def test_stranger_advisor_gets_404_not_403():
    owner, stranger = _advisor('adv_owner'), _advisor('adv_stranger')
    student = _student()
    engagement = _engagement(owner, student)

    client = _auth(stranger)
    assert client.get(_week_url(engagement.pk)).status_code == 404
    assert client.put(
        _week_url(engagement.pk, _this_saturday()), {'done': True}, format='json',
    ).status_code == 404
    assert WeeklyCallLog.objects.count() == 0


@pytest.mark.permission
def test_a_student_is_forbidden_on_the_advisor_route():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    client = _auth(student)
    assert client.get(_week_url(engagement.pk)).status_code == 403
    assert client.put(
        _week_url(engagement.pk, _this_saturday()), {'done': True}, format='json',
    ).status_code == 403


@pytest.mark.permission
def test_there_is_no_student_route_for_call_logs():
    """گام ۱۰ lock: the call plan is advisor-internal — the me-path must not exist."""
    resp = _auth(_student()).get(ME_URL)
    assert resp.status_code == 404


@pytest.mark.permission
def test_anonymous_is_rejected_on_both_verbs():
    anon = APIClient()
    assert anon.get(URL.format(pk=1)).status_code == 401
    assert anon.put(URL.format(pk=1), {}, format='json').status_code == 401
