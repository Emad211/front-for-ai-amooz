"""Research wave (2026-08-31) — goal, mistake notebook, topic coverage,
analytics and the plan/log enrichment fields.

The API tests hold the wire contract and the access matrix — owner student
2xx, no-advisor reads quiet, no-advisor writes 409, wrong role 403, anonymous
401. The service tests pin the rules that must never drift: the goal's
required title, the mistake door's active-subject rule, the spaced-review
default (+2 days on NEEDS_REVIEW, cleared on MASTERED), topic uniqueness, and
the new plan/log enrichment keys round-tripping through the real doors.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    AdvisoryEngagement,
    DailyLog,
    DailyLogItem,
    MistakeEntry,
    StudentSubject,
    StudyPlan,
    StudyPlanItem,
    Subject,
    TopicProgress,
)
from apps.advisory.services import analytics as analytics_service
from apps.advisory.services import goals as goal_service
from apps.advisory.services import topics as topic_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

TODAY = datetime.date(2026, 8, 31)

MY_GOAL_URL = '/api/advisory/me/goal/'
MY_MISTAKES_URL = '/api/advisory/me/mistakes/'
MY_MISTAKE_URL = '/api/advisory/me/mistakes/{id}/'
MY_TOPICS_URL = '/api/advisory/me/topics/'
MY_TOPIC_URL = '/api/advisory/me/topics/{id}/'
MY_ANALYTICS_URL = '/api/advisory/me/analytics/'
MY_STUDY_LOG_URL = '/api/advisory/me/study-log/'
PLAN_DRAFT_URL = '/api/advisory/students/{pk}/study-plan/draft/'

MSG_NO_ADVISOR = 'ابتدا مشاور خود را تأیید کنید.'
MSG_DUP_TOPIC = 'این مبحث از قبل در فهرست هست.'
MSG_EMPTY_GOAL = 'متن هدف نمی‌تواند خالی باشد.'
MSG_BAD_SUBJECT = 'درس انتخاب‌شده در فهرست درس‌های فعال شما نیست.'


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
        defaults['started_on'] = TODAY - datetime.timedelta(days=10)
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _subject(name='ریاضی'):
    return Subject.objects.create(
        name=name, normalized_name=name, grade='10', major=None,
    )


def _selection(engagement, subject):
    return StudentSubject.objects.create(
        engagement=engagement, subject=subject, is_active=True,
    )


def _goal_payload(**overrides):
    payload = {
        'targetTitle': 'پزشکی، دانشگاه شهید بهشتی',
        'targetRank': 'زیر ۱۰۰۰ کشوری',
        'currentRank': '۱۲۰۰۰',
        'note': 'تست زیست را جدی بگیر.',
    }
    payload.update(overrides)
    return payload


def _mistake_payload(subject_id, **overrides):
    payload = {
        'subjectId': subject_id,
        'topic': 'اصطکاک',
        'status': 'WRONG',
        'errorType': 'CONCEPT',
        'cause': 'جهت نیرو را اشتباه گرفتم',
        'fixNote': 'اصطکاک خلاف حرکت نسبی است',
        'nextAction': 'چهار تست مشابه',
        'priority': 'HIGH',
        'sourceRef': 'قلم‌چی شهریور، سؤال ۱۲',
    }
    payload.update(overrides)
    return payload


def _topic_payload(subject_id, **overrides):
    payload = {'subjectId': subject_id, 'topic': 'توابع'}
    payload.update(overrides)
    return payload


# ── goal ──────────────────────────────────────────────────────────────────────

def test_goal_get_is_quiet_without_advisor():
    resp = _auth(_student()).get(MY_GOAL_URL)
    assert resp.status_code == 200
    assert resp.data == {'active': False, 'goal': None}


def test_goal_put_roundtrip_and_second_put_updates():
    advisor, student = _advisor(), _student()
    _engagement(advisor, student)

    resp = _auth(student).put(MY_GOAL_URL, _goal_payload(), format='json')
    assert resp.status_code == 200
    assert resp.data['targetTitle'] == 'پزشکی، دانشگاه شهید بهشتی'
    assert resp.data['targetRank'] == 'زیر ۱۰۰۰ کشوری'

    second = _auth(student).put(
        MY_GOAL_URL, _goal_payload(targetTitle='دندان‌پزشکی'), format='json',
    )
    assert second.status_code == 200
    assert second.data['targetTitle'] == 'دندان‌پزشکی'
    assert second.data['note'] == 'تست زیست را جدی بگیر.'


def test_goal_put_rejects_blank_title_with_persian_400():
    advisor, student = _advisor(), _student()
    _engagement(advisor, student)
    resp = _auth(student).put(
        MY_GOAL_URL, _goal_payload(targetTitle='   '), format='json',
    )
    assert resp.status_code == 400
    assert resp.data['detail'] == MSG_EMPTY_GOAL


def test_goal_access_matrix():
    assert APIClient().put(MY_GOAL_URL, {}, format='json').status_code == 401
    stranger = _student(username='other', phone='09120000009')
    resp = _auth(stranger).put(MY_GOAL_URL, _goal_payload(), format='json')
    assert resp.status_code == 409
    assert resp.data['detail'] == MSG_NO_ADVISOR
    teacher = baker.make(User, username='t1', role=User.Role.TEACHER)
    assert _auth(teacher).get(MY_GOAL_URL).status_code == 403


def test_goal_service_empty_title_raises():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    with pytest.raises(goal_service.GoalError, match=MSG_EMPTY_GOAL):
        goal_service.upsert_goal(engagement, target_title='  ')


# ── mistakes ─────────────────────────────────────────────────────────────────

def test_mistakes_crud_roundtrip():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    listed = _auth(student).get(MY_MISTAKES_URL)
    assert listed.status_code == 200
    assert listed.data == {'active': True, 'mistakes': []}

    created = _auth(student).post(
        MY_MISTAKES_URL, _mistake_payload(math.id), format='json',
    )
    assert created.status_code == 201
    assert created.data['errorType'] == 'CONCEPT'
    assert created.data['isResolved'] is False
    mistake_id = created.data['id']

    patched = _auth(student).patch(
        MY_MISTAKE_URL.format(id=mistake_id),
        {'isResolved': True, 'priority': 'LOW'},
        format='json',
    )
    assert patched.status_code == 200
    assert patched.data['isResolved'] is True
    assert patched.data['priority'] == 'LOW'
    # Untouched keys keep their stored values.
    assert patched.data['topic'] == 'اصطکاک'

    deleted = _auth(student).delete(MY_MISTAKE_URL.format(id=mistake_id))
    assert deleted.status_code == 204
    assert not MistakeEntry.objects.filter(engagement=engagement).exists()


def test_mistake_rejects_subject_not_in_selection():
    advisor, student = _advisor(), _student()
    _engagement(advisor, student)
    unselected = _subject('شیمی')
    resp = _auth(student).post(
        MY_MISTAKES_URL, _mistake_payload(unselected.id), format='json',
    )
    assert resp.status_code == 400
    assert resp.data['detail'] == MSG_BAD_SUBJECT


def test_mistake_detail_is_scoped_to_own_engagement():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    selection = _selection(engagement, math)
    row = MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection, topic='X',
        error_type=MistakeEntry.ErrorType.TIME,
    )
    other_student = _student(username='other2', phone='09120000008')
    other_engagement = _engagement(_advisor(username='adv2'), other_student)
    _selection(other_engagement, math)

    resp = _auth(other_student).delete(MY_MISTAKE_URL.format(id=row.pk))
    assert resp.status_code == 404


def test_mistake_writes_without_advisor_are_409_and_reads_quiet():
    student = _student()
    assert _auth(student).get(MY_MISTAKES_URL).data == {
        'active': False, 'mistakes': [],
    }
    resp = _auth(student).post(
        MY_MISTAKES_URL, _mistake_payload(1), format='json',
    )
    assert resp.status_code == 409
    assert APIClient().get(MY_MISTAKES_URL).status_code == 401
    teacher = baker.make(User, username='t2', role=User.Role.TEACHER)
    assert _auth(teacher).get(MY_MISTAKES_URL).status_code == 403


# ── topics ───────────────────────────────────────────────────────────────────

def test_topic_spaced_review_default_and_mastered_clears():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    created = _auth(student).post(
        MY_TOPICS_URL, _topic_payload(math.id, status='NEEDS_REVIEW'),
        format='json',
    )
    assert created.status_code == 201
    expected = timezone.localdate() + datetime.timedelta(days=2)
    assert created.data['nextReviewAt'] == expected.isoformat()
    topic_id = created.data['id']

    mastered = _auth(student).patch(
        MY_TOPIC_URL.format(id=topic_id), {'status': 'MASTERED'}, format='json',
    )
    assert mastered.status_code == 200
    assert mastered.data['nextReviewAt'] is None


def test_topic_duplicate_rejected_and_stranger_write_409():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    first = _auth(student).post(MY_TOPICS_URL, _topic_payload(math.id), format='json')
    assert first.status_code == 201
    second = _auth(student).post(MY_TOPICS_URL, _topic_payload(math.id), format='json')
    assert second.status_code == 400
    assert second.data['detail'] == MSG_DUP_TOPIC

    stranger = _student(username='other3', phone='09120000007')
    assert _auth(stranger).delete(
        MY_TOPIC_URL.format(id=first.data['id'])
    ).status_code == 409


def test_topic_service_update_renames_without_duplicate():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)
    row = topic_service.create_topic(engagement, subject_id=math.id, topic='A')
    renamed = topic_service.update_topic(
        engagement, row.pk, patch={'topic': 'B'},
    )
    assert renamed.topic == 'B'
    with pytest.raises(topic_service.TopicError, match=MSG_DUP_TOPIC):
        topic_service.create_topic(engagement, subject_id=math.id, topic='B')


# ── analytics ────────────────────────────────────────────────────────────────

def test_analytics_shape_streak_balance_and_backlog():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    selection = _selection(engagement, math)

    today = timezone.localdate()
    # Two consecutive reported days → streak 2; yesterday under-logged vs plan
    # (45 actual < 60 planned → exactly one backlog row).
    for offset, minutes in ((1, 45), (0, 30)):
        log = DailyLog.objects.create(
            engagement=engagement, log_date=today - datetime.timedelta(days=offset),
        )
        DailyLogItem.objects.create(
            log=log, student_subject=selection, actual_minutes=minutes,
        )
    plan = StudyPlan.objects.create(
        engagement=engagement, start_date=today - datetime.timedelta(days=1),
        duration_days=3, status=StudyPlan.Status.PUBLISHED,
    )
    StudyPlanItem.objects.create(
        plan=plan, day_offset=0, student_subject=selection, planned_minutes=60,
    )

    payload = analytics_service.compute_analytics(engagement)
    assert payload['streak'] == 2
    assert payload['loggedToday'] is True
    assert payload['subjectBalance'] == [{'name': 'ریاضی', 'minutes': 75}]
    assert payload['backlogTotal'] == 1
    assert payload['backlog'][0]['planned'] == 60
    assert payload['backlog'][0]['actual'] == 45
    assert payload['planExecution'] is not None
    assert payload['examTrend'] == []
    assert payload['reviewDue'] == []
    assert payload['openMistakes'] == 0


def test_analytics_endpoint_quiet_and_access_matrix():
    student = _student()
    resp = _auth(student).get(MY_ANALYTICS_URL)
    assert resp.status_code == 200
    assert resp.data == {'active': False}
    assert APIClient().get(MY_ANALYTICS_URL).status_code == 401
    teacher = baker.make(User, username='t3', role=User.Role.TEACHER)
    assert _auth(teacher).get(MY_ANALYTICS_URL).status_code == 403


# ── plan/log enrichment round-trips ─────────────────────────────────────────

def test_plan_phase_strategy_and_item_start_time_roundtrip():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    resp = _auth(advisor).put(
        PLAN_DRAFT_URL.format(pk=engagement.pk),
        {
            'startDate': TODAY.isoformat(),
            'durationDays': 7,
            'phase': 'TEST',
            'strategy': 'HYBRID',
            'items': [{
                'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 60,
                'startTime': '08:30',
            }],
        },
        format='json',
    )
    assert resp.status_code == 200
    assert resp.data['phase'] == 'TEST'
    assert resp.data['strategy'] == 'HYBRID'
    assert resp.data['items'][0]['startTime'] == '08:30'

    plan = StudyPlan.objects.get(pk=resp.data['id'])
    assert plan.phase == 'TEST'
    item = StudyPlanItem.objects.get(plan=plan)
    assert item.start_time == datetime.time(8, 30)


def test_plan_rejects_invalid_phase_with_400():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    resp = _auth(advisor).put(
        PLAN_DRAFT_URL.format(pk=engagement.pk),
        {
            'startDate': TODAY.isoformat(), 'durationDays': 7, 'phase': 'BOGUS',
            'items': [{'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 60}],
        },
        format='json',
    )
    assert resp.status_code == 400


def test_log_activity_type_roundtrip():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    selection = _selection(engagement, math)

    resp = _auth(student).put(
        MY_STUDY_LOG_URL,
        {
            'date': timezone.localdate().isoformat(),
            'mood': 4,
            'note': '',
            'items': [
                {'subjectId': math.id, 'minutes': 45, 'activityType': 'TIMED_TEST'},
            ],
        },
        format='json',
    )
    assert resp.status_code == 200
    assert resp.data['log']['items'][0]['activityType'] == 'TIMED_TEST'

    item = DailyLogItem.objects.get(
        log__engagement=engagement, student_subject=selection,
    )
    assert item.activity_type == 'TIMED_TEST'


def test_log_rejects_invalid_activity_type_with_400():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    resp = _auth(student).put(
        MY_STUDY_LOG_URL,
        {
            'date': timezone.localdate().isoformat(),
            'items': [
                {'subjectId': math.id, 'minutes': 45, 'activityType': 'NAP'},
            ],
        },
        format='json',
    )
    assert resp.status_code == 400
