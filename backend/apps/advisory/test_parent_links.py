"""Wave 5 (2026-08-31) — the parent link, parent OTP login and weekly digest.

The parent is the first reader of advisory data who is neither the student nor
the advisor, so this file pins three things the rest of the suite assumes:

* the **access matrix** — advisors own the invite lifecycle (404-not-403 for a
  foreign/ended engagement, per ق۶), parents own two read-only routes gated on
  ``IsParentUser``, the student gets one transparency list, and nobody else
  gets anything;
* the **no-leak rule** (B2, restated for parents) — the OTP request answers
  the same 202 for a phone nobody invited, and enqueues nothing for it;
* the **privacy filter** — the digest is numbers only: mood, notes, mistake
  texts, call logs and assessment scores must not appear as keys *or* as
  values anywhere in the serialized body.
"""

from __future__ import annotations

import datetime
import itertools
import json
import time
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from model_bakery import baker
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from apps.advisory.models import (
    AdvisoryAccessLog,
    AdvisoryEngagement,
    DailyLog,
    DailyLogItem,
    MistakeEntry,
    ParentLink,
    StudyChallenge,
    StudyExamScore,
    StudyPlan,
    StudyPlanItem,
    StudentSubject,
    Subject,
    TopicProgress,
    WeeklyCallLog,
)
from apps.advisory.services import parent_links as parent_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

TODAY = datetime.date(2026, 8, 31)

ADVISOR_PARENTS_URL = '/api/advisory/students/{pk}/parents/'
ADVISOR_PARENT_URL = '/api/advisory/students/{pk}/parents/{link_id}/'
PARENT_OTP_REQUEST_URL = '/api/advisory/parent/login/request/'
PARENT_OTP_VERIFY_URL = '/api/advisory/parent/login/verify/'
PARENT_MY_LINKS_URL = '/api/advisory/parent/me/links/'
PARENT_DIGEST_URL = '/api/advisory/parent/me/links/{link_id}/digest/'
MY_PARENTS_URL = '/api/advisory/me/parents/'

MSG_BAD_PHONE = 'شمارهٔ همراه معتبر نیست (۰۹…).'
MSG_QUOTA = 'حداکثر دو والد برای هر دانش‌آموز مجاز است.'
MSG_DUPLICATE_PHONE = 'این شماره قبلاً برای این دانش‌آموز ثبت شده است.'
MSG_BAD_OTP = 'کد واردشده درست یا معتبر نیست.'
MSG_NO_ENGAGEMENT = 'همکاری پیدا نشد.'
MSG_NO_LINK = 'پیوند والد پیدا نشد.'

DIGEST_KEYS = {
    'asOf', 'weekMinutes', 'weekPlanMinutes', 'adherencePercent', 'testsTaken',
    'examTrend', 'openMistakesCount', 'reviewDueCount', 'activeChallengeTitle',
    'streak',
}


def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _parent(username='par', phone='09123334444', **kwargs):
    return baker.make(User, username=username, role=User.Role.PARENT, phone=phone, **kwargs)


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


def _link(engagement, *, phone='09123334444', relation='father', status=ParentLink.Status.PENDING, **kwargs):
    return ParentLink.objects.create(
        engagement=engagement, phone=phone, relation=relation, status=status, **kwargs,
    )


def _subject(name='ریاضی'):
    return Subject.objects.create(name=name, normalized_name=name, grade='10', major=None)


def _selection(engagement, subject):
    return StudentSubject.objects.create(engagement=engagement, subject=subject, is_active=True)


@pytest.fixture
def no_invite_sms():
    with patch.object(parent_service, 'enqueue_parent_invite_sms') as mock:
        yield mock


@pytest.fixture
def no_otp_sms():
    with patch.object(parent_service, 'enqueue_parent_login_otp_sms') as mock:
        yield mock


# ── advisor invite lifecycle ──────────────────────────────────────────────────

def test_invite_access_matrix():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    ended = _engagement(advisor, _student(username='ended', phone='09120000002'), status=Status.ENDED)
    url = ADVISOR_PARENTS_URL.format(pk=engagement.pk)

    assert APIClient().post(url, {'phone': '09123334444', 'relation': 'father'}, format='json').status_code == 401
    assert _auth(student).post(url, {'phone': '09123334444', 'relation': 'father'}, format='json').status_code == 403
    teacher = baker.make(User, username='t1', role=User.Role.TEACHER)
    assert _auth(teacher).post(url, {}, format='json').status_code == 403
    assert _auth(_advisor(username='stranger')).post(
        url, {'phone': '09123334444', 'relation': 'father'}, format='json',
    ).status_code == 404
    assert _auth(advisor).post(
        ADVISOR_PARENTS_URL.format(pk=ended.pk),
        {'phone': '09123334444', 'relation': 'father'}, format='json',
    ).status_code == 404


def test_invite_creates_pending_link_and_enqueues_exactly_one_sms(no_invite_sms):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).post(
        ADVISOR_PARENTS_URL.format(pk=engagement.pk),
        {'phone': '۰۹۱۲۳۳۳۴۴۴۴', 'relation': 'mother'},
        format='json',
    )

    assert resp.status_code == 202
    assert resp.data == {'status': 'sent'}
    no_invite_sms.assert_called_once()
    link = ParentLink.objects.get(engagement=engagement)
    assert link.phone == '09123334444'
    assert link.relation == 'mother'
    assert link.status == ParentLink.Status.PENDING
    assert link.parent_id is None
    assert link.created_by == advisor


def test_invite_rejects_bad_phone_and_bad_relation():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    url = ADVISOR_PARENTS_URL.format(pk=engagement.pk)

    bad_phone = _auth(advisor).post(url, {'phone': '4567', 'relation': 'father'}, format='json')
    assert bad_phone.status_code == 400
    assert MSG_BAD_PHONE in str(bad_phone.data)

    bad_relation = _auth(advisor).post(
        url, {'phone': '09123334444', 'relation': 'uncle'}, format='json',
    )
    assert bad_relation.status_code == 400


def test_invite_quota_two_active_max_and_revoked_frees_a_slot(no_invite_sms):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    url = ADVISOR_PARENTS_URL.format(pk=engagement.pk)

    first = _auth(advisor).post(url, {'phone': '09123330001', 'relation': 'father'}, format='json')
    second = _auth(advisor).post(url, {'phone': '09123330002', 'relation': 'mother'}, format='json')
    assert first.status_code == 202
    assert second.status_code == 202

    third = _auth(advisor).post(url, {'phone': '09123330003', 'relation': 'guardian'}, format='json')
    assert third.status_code == 400
    assert third.data['detail'] == MSG_QUOTA

    # A revoked link is history, not a standing claim: the slot frees up.
    ParentLink.objects.filter(phone='09123330001').update(status=ParentLink.Status.REVOKED)
    again = _auth(advisor).post(url, {'phone': '09123330003', 'relation': 'guardian'}, format='json')
    assert again.status_code == 202


def test_invite_duplicate_phone_is_400_not_500(no_invite_sms):
    """Regression: the same (engagement, phone) twice used to surface the DB
    IntegrityError as a 500; it must answer the Persian duplicate message."""
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    url = ADVISOR_PARENTS_URL.format(pk=engagement.pk)

    first = _auth(advisor).post(url, {'phone': '09123330001', 'relation': 'father'}, format='json')
    assert first.status_code == 202

    dup = _auth(advisor).post(url, {'phone': '09123330001', 'relation': 'mother'}, format='json')
    assert dup.status_code == 400
    assert dup.data['detail'] == MSG_DUPLICATE_PHONE


def test_invite_list_masks_phone_and_shows_status():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    _link(engagement, phone='09123330001', relation='father')
    _link(engagement, phone='09123330002', relation='mother', status=ParentLink.Status.ACTIVE)

    resp = _auth(advisor).get(ADVISOR_PARENTS_URL.format(pk=engagement.pk))

    assert resp.status_code == 200
    links = resp.data['links']
    assert len(links) == 2
    assert {row['phoneMasked'] for row in links} == {'0912***0001', '0912***0002'}
    assert {row['relation'] for row in links} == {'father', 'mother'}
    assert {row['status'] for row in links} == {'PENDING', 'ACTIVE'}
    assert all(row['createdAt'] and row['id'] for row in links)
    # A phone never leaves the server unmasked — check the rendered wire body,
    # not the in-memory data (that is what a client would actually receive).
    assert '09123330001' not in JSONRenderer().render(resp.data).decode()


def test_revoke_sets_revoked_and_foreign_link_is_404():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    link = _link(engagement, phone='09123330001')
    other_link = _link(
        _engagement(_advisor(username='adv2'), _student(username='stu2', phone='09120000003')),
        phone='09123330009',
    )

    foreign = _auth(advisor).delete(
        ADVISOR_PARENT_URL.format(pk=engagement.pk, link_id=other_link.pk),
    )
    assert foreign.status_code == 404

    resp = _auth(advisor).delete(ADVISOR_PARENT_URL.format(pk=engagement.pk, link_id=link.pk))
    assert resp.status_code == 204
    link.refresh_from_db()
    assert link.status == ParentLink.Status.REVOKED
    assert ParentLink.objects.filter(pk=link.pk).exists()  # audit trail kept


# ── parent OTP login ──────────────────────────────────────────────────────────

def test_otp_request_unknown_phone_is_uniform_202_and_enqueues_nothing(no_otp_sms):
    resp = APIClient().post(PARENT_OTP_REQUEST_URL, {'phone': '09129999999'}, format='json')
    assert resp.status_code == 202
    assert resp.data == {'status': 'sent'}
    no_otp_sms.assert_not_called()


def test_otp_request_issued_for_pending_link_and_for_existing_parent(no_otp_sms):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    _link(engagement, phone='09123330001')

    resp = APIClient().post(PARENT_OTP_REQUEST_URL, {'phone': '09123330001'}, format='json')
    assert resp.status_code == 202
    assert no_otp_sms.call_count == 1
    phone, code = no_otp_sms.call_args[0]
    assert phone == '09123330001'
    assert len(code) == 6 and code.isdigit()

    # A phone with an existing PARENT account also gets the code, even with
    # no live link (the account itself is a login target).
    no_otp_sms.reset_mock()
    _parent(phone='09123330002')
    resp = APIClient().post(PARENT_OTP_REQUEST_URL, {'phone': '09123330002'}, format='json')
    assert resp.status_code == 202
    no_otp_sms.assert_called_once()


def test_otp_request_cooldown_suppresses_immediate_resend(no_otp_sms):
    advisor, student = _advisor(), _student()
    _link(_engagement(advisor, student), phone='09123330001')

    first = APIClient().post(PARENT_OTP_REQUEST_URL, {'phone': '09123330001'}, format='json')
    second = APIClient().post(PARENT_OTP_REQUEST_URL, {'phone': '09123330001'}, format='json')

    assert first.status_code == 202
    assert second.status_code == 202  # uniform — cooldown is invisible
    assert no_otp_sms.call_count == 1


def test_otp_verify_full_flow_activates_links_and_returns_parent_jwt(no_otp_sms):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    other_engagement = _engagement(_advisor(username='adv3'), _student(username='stu3', phone='09120000005'))
    link = _link(engagement, phone='09123330001')
    other_link = _link(other_engagement, phone='09123330001', relation='mother')

    APIClient().post(PARENT_OTP_REQUEST_URL, {'phone': '09123330001'}, format='json')
    _phone, code = no_otp_sms.call_args[0]

    resp = APIClient().post(
        PARENT_OTP_VERIFY_URL, {'phone': '09123330001', 'otp': code}, format='json',
    )

    assert resp.status_code == 200
    assert resp.data['access']
    assert resp.data['refresh']
    user = resp.data['user']
    assert user['role'] == 'PARENT'
    assert user['is_profile_completed'] is True

    parent = User.objects.get(pk=user['id'])
    assert parent.role == User.Role.PARENT
    assert parent.username.startswith('parent_')
    assert parent.is_profile_completed is True

    link.refresh_from_db()
    assert link.status == ParentLink.Status.ACTIVE
    assert link.parent == parent
    assert link.activated_at == timezone.localdate()
    # Every PENDING link addressed to this phone activates, across advisors.
    other_link.refresh_from_db()
    assert other_link.status == ParentLink.Status.ACTIVE
    assert other_link.parent == parent


def test_otp_verify_wrong_and_expired_codes_fail_with_400(no_otp_sms):
    advisor, student = _advisor(), _student()
    _link(_engagement(advisor, student), phone='09123330001')

    APIClient().post(PARENT_OTP_REQUEST_URL, {'phone': '09123330001'}, format='json')

    wrong = APIClient().post(
        PARENT_OTP_VERIFY_URL, {'phone': '09123330001', 'otp': '000000'}, format='json',
    )
    assert wrong.status_code == 400
    assert wrong.data['detail'] == MSG_BAD_OTP
    # No user was minted by a failed verification.
    assert not User.objects.filter(role=User.Role.PARENT).exists()

    # Expired: age the stored record past its absolute TTL.
    key = parent_service._otp_cache_key('09123330001')
    record = cache.get(key)
    record['expires_at'] = time.time() - 1
    cache.set(key, record, 60)
    _phone, code = no_otp_sms.call_args[0]
    expired = APIClient().post(
        PARENT_OTP_VERIFY_URL, {'phone': '09123330001', 'otp': code}, format='json',
    )
    assert expired.status_code == 400
    assert expired.data['detail'] == MSG_BAD_OTP


# ── parent authenticated routes ───────────────────────────────────────────────

_UNIQUE = itertools.count(1)


def _active_parent_link():
    """A parent with one claimed ACTIVE link; unique users per call so a test
    can build two disjoint (parent, engagement) pairs without username/phone
    collisions."""
    n = next(_UNIQUE)
    advisor = _advisor(username=f'adv{n}', first_name='آرا', last_name='مشاور')
    student = _student(username=f'stu{n}', phone=f'0913000{n:04d}', first_name='سارا')
    engagement = _engagement(advisor, student)
    parent = _parent(username=f'par{n}', phone=f'0912333{n:04d}')
    link = _link(
        engagement, phone=parent.phone, relation='father', status=ParentLink.Status.ACTIVE,
        parent=parent, activated_at=TODAY,
    )
    return advisor, student, engagement, parent, link


def test_parent_links_route_matrix_and_shape():
    advisor, student, engagement, parent, link = _active_parent_link()
    # Distractors: a PENDING link and an ACTIVE link on an ENDED engagement
    # must both stay invisible to the parent.
    _link(engagement, phone='09123330077', relation='guardian')
    ended_engagement = _engagement(
        advisor, _student(username='ended2', phone='09120000006'), status=Status.ENDED,
    )
    _link(
        ended_engagement, phone=parent.phone, relation='mother',
        status=ParentLink.Status.ACTIVE, parent=parent,
    )

    assert APIClient().get(PARENT_MY_LINKS_URL).status_code == 401
    assert _auth(advisor).get(PARENT_MY_LINKS_URL).status_code == 403
    assert _auth(student).get(PARENT_MY_LINKS_URL).status_code == 403

    resp = _auth(parent).get(PARENT_MY_LINKS_URL)
    assert resp.status_code == 200
    assert len(resp.data['links']) == 1
    row = resp.data['links'][0]
    assert row['id'] == link.pk
    assert row['engagementId'] == engagement.pk
    assert row['relation'] == 'father'
    assert row['status'] == 'ACTIVE'
    assert row['studentName'] == 'سارا'
    assert row['advisorName'] == 'آرا مشاور'


def test_digest_math_and_shape():
    advisor, student, engagement, parent, link = _active_parent_link()
    math = _subject('ریاضی')
    selection = _selection(engagement, math)
    today = timezone.localdate()

    inside = DailyLog.objects.create(
        engagement=engagement, log_date=today, tests_taken=4,
    )
    DailyLogItem.objects.create(log=inside, student_subject=selection, actual_minutes=60)
    outside = DailyLog.objects.create(
        engagement=engagement, log_date=today - datetime.timedelta(days=8), tests_taken=6,
    )
    DailyLogItem.objects.create(log=outside, student_subject=selection, actual_minutes=100)
    plan = StudyPlan.objects.create(
        engagement=engagement, start_date=today, duration_days=1,
        status=StudyPlan.Status.PUBLISHED,
    )
    StudyPlanItem.objects.create(
        plan=plan, day_offset=0, student_subject=selection, planned_minutes=30,
    )
    StudyExamScore.objects.create(
        engagement=engagement, title='آزمون یک', exam_kind='SCHOOL',
        exam_date=today - datetime.timedelta(days=1), score_percent=55, tara=5000,
        created_by=advisor,
    )
    StudyExamScore.objects.create(
        engagement=engagement, title='آزمون دو', exam_kind='SCHOOL',
        exam_date=today - datetime.timedelta(days=2), score_percent=60, tara=5100,
        created_by=advisor,
    )
    StudyChallenge.objects.create(
        engagement=engagement, title='چالش تست‌زنی', start_date=today,
        end_date=today + datetime.timedelta(days=6),
    )
    MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection, topic='مبحث-محرمانه',
        error_type=MistakeEntry.ErrorType.CONCEPT,
    )
    TopicProgress.objects.create(
        engagement=engagement, student_subject=selection, topic='مرور نشده',
        status=TopicProgress.Status.NEEDS_REVIEW,
        next_review_at=today - datetime.timedelta(days=1),
    )

    resp = _auth(parent).get(PARENT_DIGEST_URL.format(link_id=link.pk))

    assert resp.status_code == 200
    assert set(resp.data) == DIGEST_KEYS
    assert resp.data['asOf'] == today.isoformat()
    assert resp.data['weekMinutes'] == 60  # the 100 minutes 8 days ago are out of the window
    assert resp.data['weekPlanMinutes'] == 30
    assert resp.data['adherencePercent'] == 100  # 60/30 clipped
    assert resp.data['testsTaken'] == 4
    assert resp.data['examTrend'] == [
        {'date': (today - datetime.timedelta(days=1)).isoformat(), 'scorePercent': 55.0, 'tara': 5000},
        {'date': (today - datetime.timedelta(days=2)).isoformat(), 'scorePercent': 60.0, 'tara': 5100},
    ]
    assert resp.data['openMistakesCount'] == 1
    assert resp.data['reviewDueCount'] == 1
    assert resp.data['activeChallengeTitle'] == 'چالش تست‌زنی'
    assert resp.data['streak'] == 1  # only today is logged


def test_digest_without_plan_is_quiet_null():
    advisor, student, engagement, parent, link = _active_parent_link()
    resp = _auth(parent).get(PARENT_DIGEST_URL.format(link_id=link.pk))
    assert resp.status_code == 200
    assert resp.data['weekMinutes'] == 0
    assert resp.data['weekPlanMinutes'] is None
    assert resp.data['adherencePercent'] is None


def test_digest_privacy_filter_hides_prose():
    advisor, student, engagement, parent, link = _active_parent_link()
    math = _subject('ریاضی')
    selection = _selection(engagement, math)
    today = timezone.localdate()
    log = DailyLog.objects.create(
        engagement=engagement, log_date=today, mood=3,
        note='نشانه-یادداشت', day_goal='نشانه-هدف', motivation_note='نشانه-انگیزه',
    )
    DailyLogItem.objects.create(log=log, student_subject=selection, actual_minutes=45)
    MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection, topic='نشانه-مبحث',
        error_type=MistakeEntry.ErrorType.TIME, cause='نشانه-علت', fix_note='نشانه-راهکار',
    )
    WeeklyCallLog.objects.create(
        engagement=engagement, week_start=today, done=True, call_date=today,
        topic='نشانه-موضوع-تماس', note='نشانه-تماس',
    )

    resp = _auth(parent).get(PARENT_DIGEST_URL.format(link_id=link.pk))
    assert resp.status_code == 200

    # Keys: the digest is exactly the numeric contract set — nothing else.
    assert set(resp.data) == DIGEST_KEYS
    # Values: not one marker of the private prose appears anywhere in the body.
    body = json.dumps(resp.data, ensure_ascii=False)
    for marker in ('نشانه-یادداشت', 'نشانه-هدف', 'نشانه-انگیزه', 'نشانه-مبحث',
                   'نشانه-علت', 'نشانه-راهکار', 'نشانه-موضوع-تماس', 'نشانه-تماس'):
        assert marker not in body


def test_digest_gates_revoked_foreign_and_ended():
    advisor, student, engagement, parent, link = _active_parent_link()
    url = PARENT_DIGEST_URL.format(link_id=link.pk)

    # Foreign link id → 404.
    other = _active_parent_link()
    assert _auth(parent).get(PARENT_DIGEST_URL.format(link_id=other[4].pk)).status_code == 404

    # Revoked → 404.
    ParentLink.objects.filter(pk=link.pk).update(status=ParentLink.Status.REVOKED)
    assert _auth(parent).get(url).status_code == 404
    ParentLink.objects.filter(pk=link.pk).update(status=ParentLink.Status.ACTIVE)

    # Ended engagement → 404.
    AdvisoryEngagement.objects.filter(pk=engagement.pk).update(status=Status.ENDED)
    assert _auth(parent).get(url).status_code == 404

    # And nobody else may even try: matrix on the digest route.
    assert APIClient().get(url).status_code == 401
    assert _auth(advisor).get(url).status_code == 403
    assert _auth(student).get(url).status_code == 403


def test_digest_writes_access_log_row():
    advisor, student, engagement, parent, link = _active_parent_link()
    url = PARENT_DIGEST_URL.format(link_id=link.pk)
    assert not AdvisoryAccessLog.objects.filter(engagement=engagement).exists()

    resp = _auth(parent).get(url)

    assert resp.status_code == 200
    row = AdvisoryAccessLog.objects.get(engagement=engagement)
    assert row.action == 'parent_digest_view'
    assert row.reader == parent


# ── student transparency ──────────────────────────────────────────────────────

def test_student_sees_active_parents_only():
    advisor, student, engagement, parent, link = _active_parent_link()
    _link(engagement, phone='09123330088', relation='mother')  # PENDING → hidden
    revoked = _link(engagement, phone='09123330099', relation='guardian')
    revoked.status = ParentLink.Status.REVOKED
    revoked.save()

    assert APIClient().get(MY_PARENTS_URL).status_code == 401
    assert _auth(advisor).get(MY_PARENTS_URL).status_code == 403
    parent_on_student_route = _auth(parent).get(MY_PARENTS_URL)
    assert parent_on_student_route.status_code == 403

    resp = _auth(student).get(MY_PARENTS_URL)
    assert resp.status_code == 200
    assert resp.data == {'parents': [{
        'id': link.pk, 'relation': 'father', 'phoneMasked': f'0912***{link.phone[-4:]}',
    }]}


def test_student_without_engagement_sees_quiet_empty_list():
    resp = _auth(_student(username='lonely', phone='09120000009')).get(MY_PARENTS_URL)
    assert resp.status_code == 200
    assert resp.data == {'parents': []}
