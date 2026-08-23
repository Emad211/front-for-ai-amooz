"""S6/S7 (§14) — study plans: the advisor's write door and its endpoints.

``save_draft`` is a **wholesale upsert of the single DRAFT slot** and
``publish_draft`` / ``unpublish_plan`` are the two-state flip around it; this
file pins both halves. The service tests hold the semantics invisible from the
wire (idempotence, item set-replace, one-slot-per-engagement, overlap with
edge-touch allowed, stale-subject revalidation at publish) and the negative
matrix in §14.3's exact order — start → duration → items, all before any write.
The API tests hold the wire contract: the feed's four ``days`` modes with the C3
clamp, plan intersection filtering, the strict permission matrix (foreign
engagement is 404-not-403, student 403, anon 401), and the D4 accounting —
**exactly one** ``AdvisoryAccessLog(action='study_feed_view')`` per successful
feed read, and none on any error.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    MAX_PLAN_DURATION_DAYS,
    MAX_PLAN_MINUTES_PER_ITEM,
    AdvisoryAccessLog,
    AdvisoryEngagement,
    StudentSubject,
    StudyPlan,
    StudyPlanItem,
    Subject,
)
from apps.advisory.services import daily_logs as log_service
from apps.advisory.services import study_plans as plan_service
from apps.advisory.services.scope import student_published_plans

User = get_user_model()
Status = AdvisoryEngagement.Status
PlanStatus = StudyPlan.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

GRADE = '10'


def _today() -> datetime.date:
    return timezone.localdate()


def _shift(days: int) -> datetime.date:
    return _today() + datetime.timedelta(days=days)


def _iso(day: datetime.date) -> str:
    return day.isoformat()


# ── builders (mirroring test_daily_logs.py) ───────────────────────────────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', *, grade=GRADE, major=None, **kwargs):
    user = baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)
    profile = user.studentprofile
    profile.grade = grade
    profile.major = major
    profile.save(update_fields=['grade', 'major'])
    return user


def _engagement(advisor, student, *, status=Status.ACTIVE, **kwargs):
    """A freelance engagement in ``status``, started 30 days ago by default.

    Plans need room in the past for overlap windows, so unlike the S5 builder
    the default ``started_on`` sits back a month; pass ``started_on=`` to move it.
    """
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': status,
        'started_on': _shift(-30),
    }
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _subject(name, *, grade=GRADE, major=None, organization=None, is_active=True):
    return baker.make(
        Subject, name=name, grade=grade, major=major,
        organization=organization, is_active=is_active,
    )


def _selection(engagement, *subjects):
    return [
        baker.make(StudentSubject, engagement=engagement, subject=s, is_active=True)
        for s in subjects
    ]


def _plan(engagement, *, start, duration, status=PlanStatus.DRAFT):
    """A plan row directly in the store — what save_draft/publish would leave."""
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


def _save(engagement, *, start, duration, items=()):
    """Call the write door with ``(day_offset, subject_id, minutes)`` triples."""
    return plan_service.save_draft(
        engagement,
        start_date=start,
        duration_days=duration,
        items=[
            {'day_offset': d, 'subject_id': sid, 'planned_minutes': m}
            for d, sid, m in items
        ],
    )


def _draft_body(start, duration, items=()) -> dict:
    return {
        'startDate': _iso(start),
        'durationDays': duration,
        'items': [
            {'dayOffset': d, 'subjectId': sid, 'plannedMinutes': m}
            for d, sid, m in items
        ],
    }


def _feed_url(engagement) -> str:
    return f'/api/advisory/students/{engagement.pk}/study-feed/'


def _draft_url(engagement) -> str:
    return f'/api/advisory/students/{engagement.pk}/study-plan/draft/'


def _publish_url(engagement) -> str:
    return f'/api/advisory/students/{engagement.pk}/study-plan/draft/publish/'


def _unpublish_url(engagement, plan_id) -> str:
    return f'/api/advisory/students/{engagement.pk}/study-plan/{plan_id}/unpublish/'


def _plans_url(engagement) -> str:
    return f'/api/advisory/students/{engagement.pk}/study-plans/'


# ── service: draft upsert ─────────────────────────────────────────────────────

class TestSaveDraft:
    def test_creates_the_slot_and_returns_the_scope_shape(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math, physics = _subject('ریاضی'), _subject('فیزیک')
        math_row, physics_row = _selection(engagement, math, physics)

        plan = _save(engagement, start=_today(), duration=7, items=[
            (0, math.id, 60), (1, physics.id, 45),
        ])

        assert StudyPlan.objects.count() == 1
        assert plan.status == PlanStatus.DRAFT
        assert plan.start_date == _today()
        assert plan.duration_days == 7
        stored = {(i.day_offset, i.student_subject_id): i.planned_minutes
                  for i in plan.items.all()}
        assert stored == {(0, math_row.pk): 60, (1, physics_row.pk): 45}
        # Scope-shaped on purpose: the response serializes the prefetched object.
        assert 'items' in getattr(plan, '_prefetched_objects_cache', {})

    def test_saving_twice_is_idempotent_one_slot_only(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        first = _save(engagement, start=_today(), duration=7, items=[(0, math.id, 60)])
        second = _save(engagement, start=_today(), duration=7, items=[(0, math.id, 60)])

        assert second.pk == first.pk
        assert StudyPlan.objects.filter(
            engagement=engagement, status=PlanStatus.DRAFT,
        ).count() == 1
        assert StudyPlanItem.objects.count() == 1

    def test_a_new_body_replaces_the_draft_wholesale(self):
        """Set-replace: new dates, new length, old rows gone.

        Deliberately unlike DailyLogItem's update_or_create: a draft has no
        history value, so nothing about the previous save survives.
        """
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math, physics = _subject('a'), _subject('b')
        math_row, _row = _selection(engagement, math, physics)

        _save(engagement, start=_today(), duration=14,
              items=[(0, math.id, 60), (2, physics.id, 30)])
        replaced = _save(engagement, start=_shift(3), duration=7,
                         items=[(1, math.id, 90)])

        assert replaced.start_date == _shift(3)
        assert replaced.duration_days == 7
        assert [(i.day_offset, i.student_subject_id, i.planned_minutes)
                for i in replaced.items.all()] == [(1, math_row.pk, 90)]
        assert StudyPlan.objects.filter(engagement=engagement).count() == 1

    def test_start_before_engagement_is_rejected_before_any_write(self):
        advisor, student = _advisor(), _student()
        started_on = _shift(-5)
        engagement = _engagement(advisor, student, started_on=started_on)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.PlanStartBeforeEngagement):
            _save(engagement, start=started_on - datetime.timedelta(days=1),
                  duration=7, items=[(0, math.id, 60)])

        assert StudyPlan.objects.count() == 0
        assert StudyPlanItem.objects.count() == 0

    @pytest.mark.parametrize('duration', [0, 91, -3])
    def test_duration_outside_1_90_is_rejected(self, duration):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.InvalidPlanDuration):
            _save(engagement, start=_today(), duration=duration, items=[])

        assert StudyPlan.objects.count() == 0

    @pytest.mark.parametrize('duration', [1, MAX_PLAN_DURATION_DAYS])
    def test_duration_boundaries_are_accepted(self, duration):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        plan = _save(engagement, start=_today(), duration=duration, items=[])
        assert plan.duration_days == duration

    def test_offset_equal_to_duration_is_rejected_but_duration_minus_one_passes(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.DayOffsetOutOfRange) as excinfo:
            _save(engagement, start=_today(), duration=7, items=[(7, math.id, 60)])
        assert excinfo.value.day_offset == 7
        assert StudyPlan.objects.count() == 0

        ok = _save(engagement, start=_today(), duration=7, items=[(6, math.id, 60)])
        assert ok.items.count() == 1

    def test_unknown_or_dropped_subject_is_rejected(self):
        """Nonexistent and deactivated selections fold into the same 400."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        kept, dropped = _subject('a'), _subject('b')
        _selection(engagement, kept, dropped)
        StudentSubject.objects.filter(
            engagement=engagement, subject=dropped,
        ).update(is_active=False)

        with pytest.raises(plan_service.SubjectNotInSelection) as excinfo:
            _save(engagement, start=_today(), duration=7,
                  items=[(0, dropped.id, 30), (1, 999_999, 30)])
        assert excinfo.value.subject_ids == [dropped.id, 999_999]
        assert StudyPlan.objects.count() == 0

    def test_duplicate_day_subject_pair_is_rejected(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.DuplicatePlanRow):
            _save(engagement, start=_today(), duration=7, items=[
                (0, math.id, 30), (0, math.id, 60),
            ])
        assert StudyPlan.objects.count() == 0

    @pytest.mark.parametrize('minutes', [0, 961])
    def test_planned_minutes_outside_1_960_are_rejected(self, minutes):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.PlannedMinutesOutOfRange):
            _save(engagement, start=_today(), duration=7, items=[(0, math.id, minutes)])
        assert StudyPlan.objects.count() == 0

    @pytest.mark.parametrize('minutes', [1, MAX_PLAN_MINUTES_PER_ITEM])
    def test_planned_minutes_boundaries_are_accepted(self, minutes):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        plan = _save(engagement, start=_today(), duration=7, items=[(0, math.id, minutes)])
        assert plan.items.get().planned_minutes == minutes


# ── service: publish / unpublish ──────────────────────────────────────────────

class TestPublishUnpublish:
    def test_publish_without_a_draft_raises_plan_not_found(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        with pytest.raises(plan_service.PlanNotFound):
            plan_service.publish_draft(engagement)

    def test_publishing_an_empty_draft_is_rejected(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        _save(engagement, start=_today(), duration=7, items=[])

        with pytest.raises(plan_service.EmptyPlanPublish):
            plan_service.publish_draft(engagement)

        assert StudyPlan.objects.get().status == PlanStatus.DRAFT

    def test_publish_revalidates_items_against_current_selections(self):
        """A subject dropped after saving makes the stale draft unpublishable."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math, chemistry = _subject('a'), _subject('b')
        _selection(engagement, math, chemistry)

        _save(engagement, start=_today(), duration=7,
              items=[(0, math.id, 30), (1, chemistry.id, 30)])
        StudentSubject.objects.filter(
            engagement=engagement, subject=chemistry,
        ).update(is_active=False)

        with pytest.raises(plan_service.SubjectNotInSelection) as excinfo:
            plan_service.publish_draft(engagement)
        assert excinfo.value.subject_ids == [chemistry.id]
        # The draft itself is untouched — still DRAFT, still complete.
        draft = StudyPlan.objects.get()
        assert draft.status == PlanStatus.DRAFT
        assert draft.items.count() == 2

    def test_publish_flips_status_and_the_student_sees_it(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        _save(engagement, start=_today(), duration=7, items=[(0, math.id, 60)])

        published = plan_service.publish_draft(engagement)

        assert published.status == PlanStatus.PUBLISHED
        assert [p.pk for p in student_published_plans(student)] == [published.pk]

    def test_overlapping_published_horizon_is_rejected_and_draft_survives(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        _plan(engagement, start=_shift(1), duration=10, status=PlanStatus.PUBLISHED)
        _save(engagement, start=_shift(5), duration=7, items=[(0, math.id, 60)])

        with pytest.raises(plan_service.PlanOverlap):
            plan_service.publish_draft(engagement)

        draft = StudyPlan.objects.get(status=PlanStatus.DRAFT)
        assert draft.start_date == _shift(5)
        assert StudyPlan.objects.filter(status=PlanStatus.PUBLISHED).count() == 1

    def test_edge_touching_horizons_are_accepted(self):
        """end == other.start is NOT an overlap — inclusive intervals may touch."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        first = _plan(engagement, start=_today(), duration=7,
                      status=PlanStatus.PUBLISHED)
        assert first.end_date == _shift(6)
        _save(engagement, start=_shift(7), duration=5, items=[(0, math.id, 60)])

        second = plan_service.publish_draft(engagement)

        assert second.status == PlanStatus.PUBLISHED
        assert StudyPlan.objects.filter(status=PlanStatus.PUBLISHED).count() == 2

    def test_unpublish_returns_the_plan_to_draft_and_hides_it_from_the_student(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        _save(engagement, start=_today(), duration=7, items=[(0, math.id, 60)])
        published = plan_service.publish_draft(engagement)

        rolled_back = plan_service.unpublish_plan(engagement, published.pk)

        assert rolled_back.status == PlanStatus.DRAFT
        assert list(student_published_plans(student)) == []
        # The rollback keeps the plan's own items — it becomes the editable draft.
        assert rolled_back.items.count() == 1

    def test_unpublish_of_a_draft_or_foreign_id_is_not_found(self):
        mine_advisor = _advisor('adv_mine')
        my_student = _student('stu_mine', '09120000001')
        other_advisor = _advisor('adv_other')
        other_student = _student('stu_other', '09120000002')
        my_engagement = _engagement(mine_advisor, my_student)
        foreign_engagement = _engagement(other_advisor, other_student)

        my_draft = _plan(my_engagement, start=_today(), duration=7)
        foreign_published = _plan(
            foreign_engagement, start=_today(), duration=7,
            status=PlanStatus.PUBLISHED,
        )

        with pytest.raises(plan_service.PlanNotFound):
            plan_service.unpublish_plan(my_engagement, my_draft.pk)
        with pytest.raises(plan_service.PlanNotFound):
            plan_service.unpublish_plan(my_engagement, foreign_published.pk)

    def test_unpublish_replaces_a_newer_scratch_draft(self):
        """The rollback wins the single slot; the never-published draft is gone."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)
        _save(engagement, start=_today(), duration=7, items=[(0, math.id, 60)])
        published = plan_service.publish_draft(engagement)

        scratch = _plan(engagement, start=_shift(20), duration=3)
        _item(scratch, math_row, 0, 15)

        rolled_back = plan_service.unpublish_plan(engagement, published.pk)

        assert rolled_back.status == PlanStatus.DRAFT
        assert rolled_back.items.count() == 1
        assert not StudyPlanItem.objects.filter(plan=scratch).exists()
        assert StudyPlan.objects.filter(engagement=engagement).count() == 1


# ── API: feed ─────────────────────────────────────────────────────────────────

class TestStudyFeedAPI:
    @pytest.mark.parametrize('raw,expected_from', [
        ('7', lambda: _shift(-6)),
        ('14', lambda: _shift(-13)),
        ('30', lambda: _shift(-29)),
        ('all', lambda: _shift(-30)),
    ])
    def test_four_days_modes_compute_the_range(self, raw, expected_from):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student, started_on=_shift(-30))

        resp = _auth(advisor).get(_feed_url(engagement), {'days': raw})

        assert resp.status_code == 200
        assert resp.data['range']['from'] == expected_from()
        assert resp.data['range']['to'] == _today()

    def test_c3_clamp_started_yesterday_caps_from_at_started_on(self):
        """Ask for 30 days but the engagement began yesterday ⇒ from == started_on."""
        advisor, student = _advisor(), _student()
        started_on = _shift(-1)
        engagement = _engagement(advisor, student, started_on=started_on)

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '30'})

        assert resp.status_code == 200
        assert resp.data['range']['from'] == started_on

    def test_invalid_days_param_is_400_with_the_exact_message(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '3'})

        assert resp.status_code == 400
        assert resp.data['detail'] == 'بازه باید یکی از ۷، ۱۴، ۳۰ یا all باشد.'

    def test_feed_returns_only_logged_days_ascending_with_items(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student, started_on=_shift(-10))
        math = _subject('ریاضی')
        _selection(engagement, math)
        log_service.save_day(engagement, _shift(-2), mood=3, note='دیروز',
                             items=[{'subject_id': math.id, 'minutes': 45}],
                             student=student)
        log_service.save_day(engagement, _today(), mood=5, note='امروز',
                             items=[{'subject_id': math.id, 'minutes': 30}],
                             student=student)

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '7'})

        assert resp.status_code == 200
        days = resp.data['days']
        # Serializer-rendered dates arrive as ISO strings (the JSON wire shape).
        assert [d['date'] for d in days] == [_iso(_shift(-2)), _iso(_today())]
        assert days[0]['totalMinutes'] == 45
        assert days[0]['mood'] == 3
        assert days[0]['note'] == 'دیروز'
        assert days[0]['items'] == [
            {'subjectId': math.id, 'name': 'ریاضی', 'minutes': 45},
        ]

    def test_feed_filters_plans_by_intersection_with_the_range(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student, started_on=_shift(-40))
        intersecting = _plan(engagement, start=_shift(-2), duration=7,
                             status=PlanStatus.PUBLISHED)
        _plan(engagement, start=_shift(-20), duration=5, status=PlanStatus.PUBLISHED)
        _plan(engagement, start=_shift(10), duration=5, status=PlanStatus.PUBLISHED)
        _plan(engagement, start=_today(), duration=3)  # drafts never appear

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '7'})

        assert resp.status_code == 200
        assert [p['id'] for p in resp.data['plans']] == [intersecting.pk]
        assert resp.data['plans'][0]['status'] == 'PUBLISHED'

    def test_successful_feed_writes_exactly_one_access_log(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        assert _auth(advisor).get(_feed_url(engagement)).status_code == 200

        assert AdvisoryAccessLog.objects.count() == 1
        row = AdvisoryAccessLog.objects.get()
        assert row.reader_id == advisor.pk
        assert row.engagement_id == engagement.pk
        assert row.action == 'study_feed_view'

        # Every successful read adds exactly one more — never zero, never two.
        assert _auth(advisor).get(_feed_url(engagement)).status_code == 200
        assert AdvisoryAccessLog.objects.count() == 2

    def test_failed_reads_write_no_access_log_rows(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        other_advisor, other_student = _advisor('adv2'), _student('stu2', '09120000002')
        foreign = _engagement(other_advisor, other_student)

        # 400 — invalid window parameter.
        bad_window = _auth(advisor).get(_feed_url(engagement), {'days': '3'})
        assert bad_window.status_code == 400
        # 404 — an engagement that is not this advisor's.
        not_mine = _auth(advisor).get(_feed_url(foreign))
        assert not_mine.status_code == 404
        # 403 — a student poking the advisor route.
        forbidden = _auth(student).get(_feed_url(engagement))
        assert forbidden.status_code == 403

        assert AdvisoryAccessLog.objects.count() == 0

    def test_anonymous_gets_401_and_logs_nothing(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        assert APIClient().get(_feed_url(engagement)).status_code == 401
        assert AdvisoryAccessLog.objects.count() == 0


# ── API: planner endpoints and permissions ────────────────────────────────────

class TestPlannerAPI:
    def test_put_draft_roundtrip_and_planout_shape(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        put = _auth(advisor).put(
            _draft_url(engagement),
            _draft_body(_today(), 7, [(0, math.id, 60)]),
            format='json',
        )
        assert put.status_code == 200
        body = put.data
        assert body['startDate'] == _iso(_today())
        # ``endDate`` rides a SerializerMethodField, so it stays a raw date here
        # (both render to the same ISO string on the wire).
        assert body['endDate'] == _shift(6)
        assert body['durationDays'] == 7
        assert body['status'] == 'DRAFT'
        assert body['items'] == [{
            'dayOffset': 0,
            'date': _today(),
            'subjectId': math.id,
            'name': 'ریاضی',
            'plannedMinutes': 60,
        }]

        listed = _auth(advisor).get(_plans_url(engagement))
        assert listed.status_code == 200
        assert [p['id'] for p in listed.data['plans']] == [body['id']]
        assert listed.data['plans'][0]['status'] == 'DRAFT'

    def test_put_draft_rejects_bad_bodies_with_400_and_persian_detail(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        early = _auth(advisor).put(
            _draft_url(engagement),
            _draft_body(_shift(-31), 7, [(0, math.id, 60)]),
            format='json',
        )
        assert early.status_code == 400
        assert early.data['detail'] == 'تاریخ شروع نمی‌تواند پیش از شروع همکاری باشد.'

        too_long = _auth(advisor).put(
            _draft_url(engagement), _draft_body(_today(), 91), format='json',
        )
        assert too_long.status_code == 400
        assert too_long.data['detail'] == 'طول برنامه باید بین ۱ و ۹۰ روز باشد.'

    def test_publish_and_unpublish_roundtrip_through_the_api(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        put = _auth(advisor).put(
            _draft_url(engagement), _draft_body(_today(), 7, [(0, math.id, 60)]),
            format='json',
        )
        plan_id = put.data['id']

        published = _auth(advisor).post(_publish_url(engagement))
        assert published.status_code == 200
        assert published.data['id'] == plan_id
        assert published.data['status'] == 'PUBLISHED'

        seen = _auth(student).get('/api/advisory/me/plans/')
        assert seen.status_code == 200
        assert [p['id'] for p in seen.data['plans']] == [plan_id]

        rolled = _auth(advisor).post(_unpublish_url(engagement, plan_id))
        assert rolled.status_code == 200
        assert rolled.data['status'] == 'DRAFT'

        gone = _auth(student).get('/api/advisory/me/plans/')
        assert gone.data['plans'] == []

    def test_me_plans_orders_newest_first_and_hides_drafts(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        older = _plan(engagement, start=_today(), duration=7,
                      status=PlanStatus.PUBLISHED)
        newer = _plan(engagement, start=_shift(7), duration=5,
                      status=PlanStatus.PUBLISHED)
        _plan(engagement, start=_shift(30), duration=3)  # DRAFT: invisible

        resp = _auth(student).get('/api/advisory/me/plans/')

        assert [p['id'] for p in resp.data['plans']] == [newer.pk, older.pk]

    def test_me_plans_without_an_advisor_is_a_quiet_empty_list(self):
        resp = _auth(_student()).get('/api/advisory/me/plans/')
        assert resp.status_code == 200
        assert resp.data == {'plans': []}

    def test_publishing_an_empty_draft_via_api_is_400(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        _auth(advisor).put(_draft_url(engagement), _draft_body(_today(), 7),
                           format='json')

        resp = _auth(advisor).post(_publish_url(engagement))
        assert resp.status_code == 400
        assert resp.data['detail'] == 'برنامهٔ خالی قابل انتشار نیست.'

    def test_unpublishing_a_missing_plan_via_api_is_404(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        resp = _auth(advisor).post(_unpublish_url(engagement, 999_999))
        assert resp.status_code == 404
        assert resp.data['detail'] == 'برنامه پیدا نشد.'

    def test_another_advisor_gets_404_on_every_route(self):
        mine = _advisor('adv_mine')
        other = _advisor('adv_other')
        engagement = _engagement(mine, _student())
        plan = _plan(engagement, start=_today(), duration=7,
                     status=PlanStatus.PUBLISHED)
        intruder = _auth(other)

        assert intruder.get(_feed_url(engagement)).status_code == 404
        assert intruder.put(
            _draft_url(engagement), _draft_body(_today(), 7), format='json',
        ).status_code == 404
        assert intruder.post(_publish_url(engagement)).status_code == 404
        assert intruder.post(_unpublish_url(engagement, plan.pk)).status_code == 404
        assert intruder.get(_plans_url(engagement)).status_code == 404
        assert AdvisoryAccessLog.objects.count() == 0

    def test_students_and_teachers_are_forbidden_on_advisor_routes(self, teacher_user):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        for client in (_auth(student), _auth(teacher_user)):
            assert client.get(_feed_url(engagement)).status_code == 403
            assert client.put(
                _draft_url(engagement), _draft_body(_today(), 7), format='json',
            ).status_code == 403
            assert client.post(_publish_url(engagement)).status_code == 403
            assert client.post(_unpublish_url(engagement, 1)).status_code == 403
            assert client.get(_plans_url(engagement)).status_code == 403

    def test_anonymous_is_unauthorized_on_advisor_routes(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        anon = APIClient()

        assert anon.get(_feed_url(engagement)).status_code == 401
        assert anon.put(
            _draft_url(engagement), _draft_body(_today(), 7), format='json',
        ).status_code == 401
        assert anon.post(_publish_url(engagement)).status_code == 401
        assert anon.get(_plans_url(engagement)).status_code == 401

    def test_a_non_student_is_rejected_on_me_plans(self):
        assert _auth(_advisor()).get('/api/advisory/me/plans/').status_code == 403
        assert APIClient().get('/api/advisory/me/plans/').status_code == 401
