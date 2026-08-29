"""The advisor cockpit overview endpoint (``GET /api/advisory/overview/``).

Contract tests for the dashboard home: the auth matrix (anonymous 401,
non-advisor 403), roster scoping (ACTIVE rows only, stranger advisors isolated,
pendingInvites matching ``/api/advisory/students/`` exactly), and the three
per-student metrics — above all ``adherence7d``, which must equal the study
feed's own «۷ روز» chip for the same engagement, because it *is* that number.
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
    StudentSubject,
    StudyChallenge,
    StudyPlan,
    StudyPlanItem,
    Subject,
)

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode
PlanStatus = StudyPlan.Status

pytestmark = [pytest.mark.django_db, pytest.mark.api]

OVERVIEW_URL = '/api/advisory/overview/'
ROSTER_URL = '/api/advisory/students/'
FEED_URL = '/api/advisory/students/{pk}/study-feed/'

METRIC_KEYS = {'activeStudents', 'pendingInvites', 'averageAdherence7d'}
ROW_KEYS = {'engagementId', 'adherence7d', 'lastLogDate', 'activeChallengeTitle'}

# Student phones are unique per role (``uniq_student_phone``), so every builder
# call mints its own number instead of sharing one literal.
_PHONE_SEQ = iter(range(9120000001, 9120099999))
# Subject identity is (name, grade, major, organization) — same rule, same fix.
_SUBJECT_SEQ = iter(range(1, 100000))


def _today() -> datetime.date:
    return timezone.localdate()


def _shift(days: int) -> datetime.date:
    return _today() + datetime.timedelta(days=days)


# ── builders (mirroring test_study_plans.py / test_exam_records.py) ──────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone=None, **kwargs):
    return baker.make(
        User,
        username=username,
        role=User.Role.STUDENT,
        phone=phone or f'0{next(_PHONE_SEQ)}',
        **kwargs,
    )


def _engagement(advisor, student, *, status=Status.ACTIVE, **kwargs):
    """A freelance engagement in ``status``, started 30 days ago by default."""
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': status,
        'started_on': _shift(-30),
    }
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _subject(name=None):
    return baker.make(
        Subject, name=name or f'درس {next(_SUBJECT_SEQ)}', grade='10', major=None,
    )


def _selection(engagement, subject):
    return baker.make(StudentSubject, engagement=engagement, subject=subject, is_active=True)


def _plan(engagement, *, start, duration, status=PlanStatus.PUBLISHED):
    return baker.make(
        StudyPlan,
        engagement=engagement,
        start_date=start,
        duration_days=duration,
        status=status,
    )


def _item(plan, selection_row, day_offset, minutes):
    return baker.make(
        StudyPlanItem,
        plan=plan,
        day_offset=day_offset,
        student_subject=selection_row,
        planned_minutes=minutes,
    )


def _log(engagement, selection_row, log_date, minutes):
    """One reported day with a single subject line of ``minutes``."""
    log = baker.make(DailyLog, engagement=engagement, log_date=log_date)
    baker.make(
        DailyLogItem, log=log, student_subject=selection_row, actual_minutes=minutes,
    )
    return log


def _challenge(engagement, title, *, start=None, status='ACTIVE'):
    day = start or _shift(-1)
    return baker.make(
        StudyChallenge,
        engagement=engagement,
        title=title,
        start_date=day,
        end_date=day + datetime.timedelta(days=6),
        status=status,
    )


# ── auth matrix ───────────────────────────────────────────────────────────────

def test_anonymous_gets_401():
    response = APIClient().get(OVERVIEW_URL)
    assert response.status_code == 401


def test_student_role_gets_403():
    response = _auth(_student()).get(OVERVIEW_URL)
    assert response.status_code == 403


def test_advisor_gets_200():
    response = _auth(_advisor()).get(OVERVIEW_URL)
    assert response.status_code == 200


# ── wire shape ────────────────────────────────────────────────────────────────

def test_response_shape_matches_the_contract_exactly():
    advisor = _advisor()
    engagement = _engagement(advisor, _student())

    data = _auth(advisor).get(OVERVIEW_URL).json()

    assert set(data.keys()) == {'metrics', 'students'}
    assert set(data['metrics'].keys()) == METRIC_KEYS
    assert len(data['students']) == 1
    assert set(data['students'][0].keys()) == ROW_KEYS
    assert data['students'][0]['engagementId'] == engagement.pk


def test_empty_advisor_gets_zeroed_metrics():
    data = _auth(_advisor()).get(OVERVIEW_URL).json()

    assert data['metrics'] == {
        'activeStudents': 0,
        'pendingInvites': 0,
        'averageAdherence7d': None,
    }
    assert data['students'] == []


# ── roster scoping ────────────────────────────────────────────────────────────

def test_students_rows_cover_only_active_engagements():
    advisor = _advisor()
    active = _engagement(advisor, _student('stu1'))
    _engagement(advisor, _student('stu2'), status=Status.PENDING)
    _engagement(advisor, _student('stu3'), status=Status.ENDED)
    _engagement(advisor, _student('stu4'), status=Status.REJECTED)

    data = _auth(advisor).get(OVERVIEW_URL).json()

    assert data['metrics']['activeStudents'] == 1
    assert [row['engagementId'] for row in data['students']] == [active.pk]


def test_pending_invites_counts_all_pending_including_expired():
    advisor = _advisor()
    _engagement(advisor, _student('stu1'), status=Status.PENDING)
    _engagement(
        advisor, _student('stu2'), status=Status.PENDING,
        invite_expires_at=timezone.now() - datetime.timedelta(days=1),
    )

    data = _auth(advisor).get(OVERVIEW_URL).json()
    roster = _auth(advisor).get(ROSTER_URL).json()

    # Expired invites stay counted — the same outbox semantics the roster
    # endpoint answers with, verified against it here so the two can't drift.
    assert data['metrics']['pendingInvites'] == 2
    assert len(roster['pendingInvites']) == data['metrics']['pendingInvites']


def test_stranger_advisor_sees_only_their_own_roster():
    owner, stranger = _advisor('owner'), _advisor('stranger')
    mine = _engagement(owner, _student('stu1'))
    theirs = _engagement(stranger, _student('stu2'))

    owner_data = _auth(owner).get(OVERVIEW_URL).json()
    stranger_data = _auth(stranger).get(OVERVIEW_URL).json()

    assert [row['engagementId'] for row in owner_data['students']] == [mine.pk]
    assert [row['engagementId'] for row in stranger_data['students']] == [theirs.pk]


# ── adherence7d: the feed's own chip ─────────────────────────────────────────

def test_adherence7d_equals_the_study_feed_chip_for_the_same_week():
    advisor = _advisor()
    engagement = _engagement(advisor, _student())
    selection = _selection(engagement, _subject())
    plan = _plan(engagement, start=_shift(-6), duration=7)
    _item(plan, selection, day_offset=0, minutes=100)
    _log(engagement, selection, _today(), 50)

    overview = _auth(advisor).get(OVERVIEW_URL).json()
    feed = _auth(advisor).get(FEED_URL.format(pk=engagement.pk)).json()

    assert overview['students'][0]['adherence7d'] == 50
    # The reuse contract, stated as data: the cockpit number IS the feed's
    # «۷ روز» chip, not an independent approximation of it.
    assert feed['adherencePercent'] == overview['students'][0]['adherence7d']


def test_adherence7d_is_null_when_no_published_plan_intersects_the_window():
    advisor = _advisor()
    engagement = _engagement(advisor, _student())
    selection = _selection(engagement, _subject())
    # Published but wholly outside the trailing week…
    stale = _plan(engagement, start=_shift(-30), duration=5)
    _item(stale, selection, day_offset=0, minutes=100)
    _log(engagement, selection, _shift(-28), 50)
    # …and a draft sitting right inside it: drafts never measure.
    draft = _plan(engagement, start=_shift(-2), duration=5, status=PlanStatus.DRAFT)
    _item(draft, selection, day_offset=0, minutes=500)

    data = _auth(advisor).get(OVERVIEW_URL).json()

    assert data['students'][0]['adherence7d'] is None
    assert data['metrics']['averageAdherence7d'] is None


def test_adherence7d_window_clamps_to_engagement_start_like_the_feed():
    advisor = _advisor()
    # Started yesterday: the trailing week collapses to [yesterday, today].
    engagement = _engagement(advisor, _student(), started_on=_shift(-1))
    selection = _selection(engagement, _subject())
    plan = _plan(engagement, start=_shift(-1), duration=7)
    _item(plan, selection, day_offset=0, minutes=200)
    _log(engagement, selection, _today(), 50)

    overview = _auth(advisor).get(OVERVIEW_URL).json()
    feed = _auth(advisor).get(FEED_URL.format(pk=engagement.pk)).json()

    assert overview['students'][0]['adherence7d'] == 25
    assert feed['adherencePercent'] == 25


# ── lastLogDate / activeChallengeTitle ───────────────────────────────────────

def test_last_log_date_is_the_newest_reported_day_or_null():
    advisor = _advisor()
    engagement = _engagement(advisor, _student())
    selection = _selection(engagement, _subject())
    _log(engagement, selection, _shift(-9), 10)
    newest = _log(engagement, selection, _shift(-2), 20)

    data = _auth(advisor).get(OVERVIEW_URL).json()

    assert data['students'][0]['lastLogDate'] == newest.log_date.isoformat()


def test_last_log_date_is_null_without_any_log():
    advisor = _advisor()
    _engagement(advisor, _student())

    data = _auth(advisor).get(OVERVIEW_URL).json()

    assert data['students'][0]['lastLogDate'] is None


def test_active_challenge_title_prefers_newest_id_and_skips_terminal_rows():
    advisor = _advisor()
    engagement = _engagement(advisor, _student())
    _challenge(engagement, 'چالش قدیمی')
    newest = _challenge(engagement, 'چالش تازه')
    _challenge(engagement, 'چالش تمام‌شده', status='DONE')
    _challenge(engagement, 'چالش لغوشده', status='CANCELLED')

    data = _auth(advisor).get(OVERVIEW_URL).json()

    assert data['students'][0]['activeChallengeTitle'] == newest.title


def test_active_challenge_title_is_null_when_only_terminal_challenges_exist():
    advisor = _advisor()
    engagement = _engagement(advisor, _student())
    _challenge(engagement, 'چالش تمام‌شده', status='DONE')

    data = _auth(advisor).get(OVERVIEW_URL).json()

    assert data['students'][0]['activeChallengeTitle'] is None


# ── averageAdherence7d ────────────────────────────────────────────────────────

def _engagement_with_adherence(advisor, username, planned, actual):
    engagement = _engagement(advisor, _student(username))
    selection = _selection(engagement, _subject())
    plan = _plan(engagement, start=_shift(-6), duration=7)
    _item(plan, selection, day_offset=0, minutes=planned)
    if actual:
        _log(engagement, selection, _today(), actual)
    return engagement


def test_average_adherence_is_mean_of_non_null_values_to_one_decimal():
    advisor = _advisor()
    _engagement_with_adherence(advisor, 'stu1', planned=100, actual=50)
    _engagement_with_adherence(advisor, 'stu2', planned=100, actual=55)

    data = _auth(advisor).get(OVERVIEW_URL).json()

    assert data['metrics']['averageAdherence7d'] == 52.5


def test_average_adherence_skips_unmeasured_students_instead_of_counting_them_as_zero():
    advisor = _advisor()
    measured = _engagement_with_adherence(advisor, 'stu1', planned=100, actual=50)
    # No plan in the window at all ⇒ adherence7d is null («nothing to
    # measure»), which must drop out of the mean rather than drag it down.
    unmeasured = _engagement(advisor, _student('stu2'))

    data = _auth(advisor).get(OVERVIEW_URL).json()

    # Rows are keyed by engagement id, not position: the roster order breaks
    # ties on invited_at, which two same-transaction rows can share.
    rows = {row['engagementId']: row for row in data['students']}
    assert rows[unmeasured.pk]['adherence7d'] is None
    assert rows[measured.pk]['adherence7d'] == 50.0
    assert data['metrics']['averageAdherence7d'] == 50.0
