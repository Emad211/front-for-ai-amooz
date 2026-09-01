"""Wave 6b (2026-08-31) — the five hidden evidence numbers.

testDensity (tests per logged day, 14d), mistakeResolutionDays (median
created→resolved latency of mistakes resolved in 30d, riding the new
``MistakeEntry.resolved_at`` column), planCalibration (planned ÷ actual over
overlapping days, 14d), reportRate7d (logged days ÷ 7, percent) and
advisorDosageDays (days since the last completed weekly call). Every test pins
exact numbers — including the window boundaries — plus the null paths and the
resolved_at lifecycle (first resolve stamps, un-resolve clears, migration 0021
backfills pre-existing rows).
"""

from __future__ import annotations

import datetime
import importlib

import pytest
from django.apps import apps as global_apps
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
    WeeklyCallLog,
)
from apps.advisory.services import analytics as analytics_service
from apps.advisory.services import mistakes as mistake_service
from apps.advisory.services.calendar import week_start_of

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

MY_ANALYTICS_URL = '/api/advisory/me/analytics/'
ADVISOR_GROWTH_URL = '/api/advisory/students/{pk}/growth/'


def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _engagement(advisor, student):
    return AdvisoryEngagement.objects.create(
        advisor=advisor,
        student=student,
        invited_phone=student.phone or '',
        mode=Mode.FREELANCE,
        organization=None,
        status=Status.ACTIVE,
        started_on=timezone.localdate() - datetime.timedelta(days=10),
    )


def _subject(name='ریاضی'):
    return Subject.objects.create(
        name=name, normalized_name=name, grade='10', major=None,
    )


def _selection(engagement, subject):
    return StudentSubject.objects.create(
        engagement=engagement, subject=subject, is_active=True,
    )


def _report(engagement, log_date, *, tests_taken=0):
    return DailyLog.objects.create(
        engagement=engagement, log_date=log_date, tests_taken=tests_taken,
    )


def _seed_resolved_mistake(engagement, selection, *, created_days_ago, resolved_days_ago):
    row = MistakeEntry.objects.create(
        engagement=engagement,
        student_subject=selection,
        topic=f'm-{created_days_ago}-{resolved_days_ago}',
        error_type=MistakeEntry.ErrorType.CONCEPT,
        is_resolved=True,
    )
    now = timezone.now()
    MistakeEntry.objects.filter(pk=row.pk).update(
        created_at=now - datetime.timedelta(days=created_days_ago),
        resolved_at=now - datetime.timedelta(days=resolved_days_ago),
    )
    return row


# ── the five metrics' math ────────────────────────────────────────────────────

def test_metrics_all_null_on_empty_engagement():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    _selection(engagement, _subject())

    payload = analytics_service.compute_analytics(engagement)

    assert payload['testDensity'] is None
    assert payload['mistakeResolutionDays'] is None
    assert payload['planCalibration'] is None
    assert payload['reportRate7d'] is None
    assert payload['advisorDosageDays'] is None


def test_density_math_dedupe_and_14_day_boundary():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math, physics = _subject('ریاضی'), _subject('فیزیک')
    math_sel = _selection(engagement, math)
    physics_sel = _selection(engagement, physics)

    today = timezone.localdate()
    _report(engagement, today, tests_taken=10)
    # A two-item day: its tests_taken must count once, not once per item.
    two_item_day = _report(
        engagement, today - datetime.timedelta(days=1), tests_taken=20,
    )
    DailyLogItem.objects.create(
        log=two_item_day, student_subject=math_sel, actual_minutes=20,
    )
    DailyLogItem.objects.create(
        log=two_item_day, student_subject=physics_sel, actual_minutes=25,
    )
    _report(engagement, today - datetime.timedelta(days=13), tests_taken=30)
    # One day past the window: excluded from both the sum and the divisor.
    _report(engagement, today - datetime.timedelta(days=14), tests_taken=1000)

    payload = analytics_service.compute_analytics(engagement)

    assert payload['testDensity'] == 20.0  # (10 + 20 + 30) / 3 logged days


def test_report_rate_math_and_7_day_boundary():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    today = timezone.localdate()
    _report(engagement, today)
    _report(engagement, today - datetime.timedelta(days=3))
    _report(engagement, today - datetime.timedelta(days=6))
    _report(engagement, today - datetime.timedelta(days=7))  # outside the week

    payload = analytics_service.compute_analytics(engagement)

    assert payload['reportRate7d'] == 43  # round(3 / 7 * 100)

    other = _engagement(
        _advisor(username='adv2'), _student(username='stu2', phone='09120000002'),
    )
    _report(other, today - datetime.timedelta(days=8))
    assert analytics_service.compute_analytics(other)['reportRate7d'] is None


def test_mistake_resolution_median_and_30_day_boundary():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    selection = _selection(engagement, _subject())

    _seed_resolved_mistake(
        engagement, selection, created_days_ago=6, resolved_days_ago=4,
    )  # latency 2
    _seed_resolved_mistake(
        engagement, selection, created_days_ago=11, resolved_days_ago=7,
    )  # latency 4
    _seed_resolved_mistake(
        engagement, selection, created_days_ago=39, resolved_days_ago=29,
    )  # latency 10, resolved on the window's first day — in
    # Resolved 31 days ago: outside the window. Were it counted, the median
    # of [2, 4, 10, 14] would read 7 instead of 4.
    _seed_resolved_mistake(
        engagement, selection, created_days_ago=45, resolved_days_ago=31,
    )
    MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection,
        topic='open', error_type=MistakeEntry.ErrorType.FORGET,
        is_resolved=False,
    )

    payload = analytics_service.compute_analytics(engagement)

    assert payload['mistakeResolutionDays'] == 4


def test_plan_calibration_math_and_overlap_rule():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    selection = _selection(engagement, _subject())

    today = timezone.localdate()
    plan = StudyPlan.objects.create(
        engagement=engagement,
        start_date=today - datetime.timedelta(days=2),
        duration_days=3,
        status=StudyPlan.Status.PUBLISHED,
    )
    StudyPlanItem.objects.create(
        plan=plan, day_offset=0, student_subject=selection, planned_minutes=60,
    )
    StudyPlanItem.objects.create(
        plan=plan, day_offset=1, student_subject=selection, planned_minutes=40,
    )
    # Today carries a plan item but no log yet → not an overlapping day.
    StudyPlanItem.objects.create(
        plan=plan, day_offset=2, student_subject=selection, planned_minutes=50,
    )

    def _logged_day(offset, minutes):
        log = _report(engagement, today - datetime.timedelta(days=offset))
        DailyLogItem.objects.create(
            log=log, student_subject=selection, actual_minutes=minutes,
        )

    _logged_day(2, 30)   # planned 60 / actual 30  → overlapping
    _logged_day(1, 80)   # planned 40 / actual 80  → overlapping
    _logged_day(3, 100)  # logged day with no plan item → excluded

    payload = analytics_service.compute_analytics(engagement)

    assert payload['planCalibration'] == 0.91  # (60 + 40) / (30 + 80)


def test_plan_calibration_null_without_overlapping_days():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    selection = _selection(engagement, _subject())

    today = timezone.localdate()
    plan = StudyPlan.objects.create(
        engagement=engagement, start_date=today, duration_days=1,
        status=StudyPlan.Status.PUBLISHED,
    )
    StudyPlanItem.objects.create(
        plan=plan, day_offset=0, student_subject=selection, planned_minutes=60,
    )
    log = _report(engagement, today - datetime.timedelta(days=1))
    DailyLogItem.objects.create(
        log=log, student_subject=selection, actual_minutes=60,
    )

    payload = analytics_service.compute_analytics(engagement)

    assert payload['planCalibration'] is None


def test_advisor_dosage_days_uses_last_done_call_up_to_today():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    today = timezone.localdate()
    past = today - datetime.timedelta(days=5)
    older = today - datetime.timedelta(days=20)
    skipped = today - datetime.timedelta(days=40)
    future = today + datetime.timedelta(days=12)

    WeeklyCallLog.objects.create(
        engagement=engagement, week_start=week_start_of(older),
        done=True, call_date=older,
    )
    WeeklyCallLog.objects.create(
        engagement=engagement, week_start=week_start_of(past),
        done=True, call_date=past,
    )
    WeeklyCallLog.objects.create(
        engagement=engagement, week_start=week_start_of(skipped),
        done=False, call_date=None,
    )
    # A done row dated in the future cannot shorten the dosage.
    WeeklyCallLog.objects.create(
        engagement=engagement, week_start=week_start_of(future),
        done=True, call_date=future,
    )

    payload = analytics_service.compute_analytics(engagement)

    assert payload['advisorDosageDays'] == 5


# ── the wire surfaces ─────────────────────────────────────────────────────────

def test_student_analytics_endpoint_carries_the_five_keys():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    _selection(engagement, _subject())

    _report(engagement, timezone.localdate(), tests_taken=7)

    resp = _auth(student).get(MY_ANALYTICS_URL)

    assert resp.status_code == 200
    assert resp.data['active'] is True
    assert resp.data['testDensity'] == 7.0
    assert resp.data['reportRate7d'] == 14  # round(1 / 7 * 100)
    assert resp.data['mistakeResolutionDays'] is None
    assert resp.data['planCalibration'] is None
    assert resp.data['advisorDosageDays'] is None


def test_advisor_growth_projection_carries_the_five_evidence_keys():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    _selection(engagement, _subject())

    _report(engagement, timezone.localdate(), tests_taken=7)

    resp = _auth(advisor).get(ADVISOR_GROWTH_URL.format(pk=engagement.pk))

    assert resp.status_code == 200
    evidence = resp.data['evidence']
    for key in (
        'testDensity', 'mistakeResolutionDays', 'planCalibration',
        'reportRate7d', 'advisorDosageDays',
    ):
        assert key in evidence
    assert evidence['testDensity'] == 7.0
    assert evidence['reportRate7d'] == 14
    assert evidence['mistakeResolutionDays'] is None
    assert evidence['planCalibration'] is None
    assert evidence['advisorDosageDays'] is None


# ── the resolved_at lifecycle ─────────────────────────────────────────────────

def test_update_mistake_stamps_first_resolve_and_clears_on_unresolve():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject()
    _selection(engagement, math)

    row = mistake_service.create_mistake(
        engagement, subject_id=math.id, topic='حد',
        status='WRONG', error_type='CONCEPT',
    )
    assert row.resolved_at is None

    resolved = mistake_service.update_mistake(
        engagement, row.pk, patch={'is_resolved': True},
    )
    first_stamp = resolved.resolved_at
    assert first_stamp is not None

    again = mistake_service.update_mistake(
        engagement, row.pk, patch={'is_resolved': True},
    )
    assert again.resolved_at == first_stamp

    reopened = mistake_service.update_mistake(
        engagement, row.pk, patch={'is_resolved': False},
    )
    assert reopened.is_resolved is False
    assert reopened.resolved_at is None

    reclosed = mistake_service.update_mistake(
        engagement, row.pk, patch={'is_resolved': True},
    )
    assert reclosed.resolved_at is not None
    assert reclosed.resolved_at >= first_stamp


def test_backfill_migration_fills_resolved_at_for_preexisting_rows():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    selection = _selection(engagement, _subject())

    resolved = MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection,
        topic='r', error_type=MistakeEntry.ErrorType.CONCEPT,
        is_resolved=True,
    )
    still_open = MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection,
        topic='o', error_type=MistakeEntry.ErrorType.FORGET,
        is_resolved=False,
    )
    already = MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection,
        topic='a', error_type=MistakeEntry.ErrorType.TIME,
        is_resolved=True,
    )
    explicit = timezone.now() - datetime.timedelta(days=5)
    MistakeEntry.objects.filter(pk=already.pk).update(resolved_at=explicit)

    migration = importlib.import_module(
        'apps.advisory.migrations.0021_mistakeentry_resolved_at',
    )
    migration.backfill_resolved_at(global_apps, None)

    resolved.refresh_from_db()
    still_open.refresh_from_db()
    already.refresh_from_db()
    assert resolved.resolved_at == resolved.updated_at
    assert still_open.resolved_at is None
    assert already.resolved_at == explicit
