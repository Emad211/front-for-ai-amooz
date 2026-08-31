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
    MAX_PLAN_TEST_MINUTES,
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
        assert body['dayNotes'] == {}
        assert body['items'] == [{
            'dayOffset': 0,
            'date': _today(),
            'subjectId': math.id,
            'name': 'ریاضی',
            'plannedMinutes': 60,
            # Restart step 4: enrichment columns default on a legacy-shaped PUT.
            'topic': '',
            'unitLabel': '',
            'testMinutes': None,
            'masteryColor': None,
            'startTime': None,
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


# ── S8: adherence metric + mood average ───────────────────────────────────────

def _log_day(engagement, student, day, minutes_by_subject, *, mood=None):
    """One reported day through the write door; maps subject → minutes."""
    return log_service.save_day(
        engagement,
        day,
        mood=mood,
        note='',
        items=[
            {'subject_id': subject.id, 'minutes': minutes}
            for subject, minutes in minutes_by_subject.items()
        ],
        student=student,
    )


class TestPlanAdherencePercent:
    def test_elapsed_only_denominator_excludes_future_items(self):
        """Started 5d ago / duration 30: future-day rows stay out of the denominator."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        plan = _plan(engagement, start=_shift(-5), duration=30,
                     status=PlanStatus.PUBLISHED)
        _item(plan, math_row, 0, 60)   # shift(-5) — elapsed
        _item(plan, math_row, 2, 60)   # shift(-3) — elapsed
        _item(plan, math_row, 10, 60)  # shift(+5) — future
        _log_day(engagement, student, _shift(-5), {math: 30})
        _log_day(engagement, student, _shift(-3), {math: 30})

        # Elapsed planned = 120, actual = 60 ⇒ 50. Counting the future row
        # would make the denominator 180 and the answer 33.
        assert plan_service.plan_adherence_percent(plan, today=_today()) == 50

    def test_inclusive_edges_start_and_end_days_both_count(self):
        """Logs on the plan's first and last day are inside the window."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        plan = _plan(engagement, start=_shift(-6), duration=7,
                     status=PlanStatus.PUBLISHED)
        _item(plan, math_row, 0, 40)  # shift(-6) — the start day itself
        _item(plan, math_row, 6, 60)  # today — the end day itself
        _log_day(engagement, student, _shift(-6), {math: 20})
        _log_day(engagement, student, _today(), {math: 30})

        # planned = 100, actual = 50 ⇒ 50. Dropping either edge breaks the
        # symmetry: no start-day log ⇒ 30, no end-day item ⇒ 75, no end-day
        # log ⇒ 20 — every wrong variant misses 50.
        assert plan_service.plan_adherence_percent(plan, today=_today()) == 50

    def test_minutes_logged_outside_the_plan_are_excluded_from_the_numerator(self):
        """Before-start and after-end logs belong to no commitment of this plan."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        plan = _plan(engagement, start=_shift(-3), duration=3,
                     status=PlanStatus.PUBLISHED)
        _item(plan, math_row, 0, 100)
        _log_day(engagement, student, _shift(-10), {math: 200})  # before start
        _log_day(engagement, student, _shift(-2), {math: 100})   # inside
        _log_day(engagement, student, _today(), {math: 200})     # after end

        assert plan_service.plan_adherence_percent(plan, today=_today()) == 100

    def test_null_when_zero_items_have_elapsed(self):
        """A plan that has not started yet has no ratio — never a misleading 0."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        plan = _plan(engagement, start=_shift(1), duration=5,
                     status=PlanStatus.PUBLISHED)
        _item(plan, math_row, 0, 60)

        assert plan_service.plan_adherence_percent(plan, today=_today()) is None

    def test_ratio_is_rounded_to_the_nearest_integer(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        plan = _plan(engagement, start=_shift(-2), duration=3,
                     status=PlanStatus.PUBLISHED)
        _item(plan, math_row, 0, 100)
        _item(plan, math_row, 1, 100)
        _item(plan, math_row, 2, 100)
        _log_day(engagement, student, _shift(-2), {math: 100})
        _log_day(engagement, student, _shift(-1), {math: 100})

        # 200 ÷ 300 = 66.67% ⇒ 67.
        assert plan_service.plan_adherence_percent(plan, today=_today()) == 67


class TestFeedOverallAdherence:
    def test_weighted_across_two_differently_sized_plans_not_an_average(self):
        """Σactual ÷ Σplanned once — a small plan's 100% cannot outweigh a big 50%."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        big = _plan(engagement, start=_shift(-10), duration=7,
                    status=PlanStatus.PUBLISHED)
        for offset in range(7):
            _item(big, math_row, offset, 10)
        _log_day(engagement, student, _shift(-9), {math: 20})
        _log_day(engagement, student, _shift(-7), {math: 15})

        small = _plan(engagement, start=_shift(-3), duration=3,
                      status=PlanStatus.PUBLISHED)
        for offset in range(3):
            _item(small, math_row, offset, 10)
        _log_day(engagement, student, _shift(-2), {math: 30})

        overall = plan_service.feed_overall_adherence(
            engagement, [big, small], _shift(-30), _today(), today=_today(),
        )

        # (35 + 30) ÷ (70 + 30) = 65%. The naive mean of per-plan percents
        # (50% and 100%) would read 75 — exactly the bug this shape forbids.
        assert overall == 65

    def test_range_clipping_counts_only_the_selected_window(self):
        """A plan spanning past the range contributes only its clipped slice."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        plan = _plan(engagement, start=_shift(-20), duration=40,
                     status=PlanStatus.PUBLISHED)
        _item(plan, math_row, 13, 100)  # shift(-7) — just before the 7d window
        _item(plan, math_row, 18, 100)  # shift(-2) — inside it
        _log_day(engagement, student, _shift(-7), {math: 80})
        _log_day(engagement, student, _shift(-2), {math: 50})

        whole = plan_service.feed_overall_adherence(
            engagement, [plan], _shift(-30), _today(), today=_today(),
        )
        trailing_week = plan_service.feed_overall_adherence(
            engagement, [plan], _shift(-6), _today(), today=_today(),
        )

        # Whole horizon: 130 ÷ 200 = 65. Clipped to the last 7 days the
        # shift(-7) row drops out on BOTH sides: 50 ÷ 100 = 50.
        assert whole == 65
        assert trailing_week == 50

    def test_drafts_and_out_of_range_plans_contribute_nothing(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        live = _plan(engagement, start=_shift(-3), duration=3,
                     status=PlanStatus.PUBLISHED)
        _item(live, math_row, 0, 100)
        _log_day(engagement, student, _shift(-2), {math: 50})

        scratch = _plan(engagement, start=_shift(-5), duration=10,
                        status=PlanStatus.DRAFT)
        _item(scratch, math_row, 0, 900)
        future = _plan(engagement, start=_shift(5), duration=3,
                       status=PlanStatus.PUBLISHED)
        _item(future, math_row, 0, 900)

        overall = plan_service.feed_overall_adherence(
            engagement, [live, scratch, future], _shift(-30), _today(),
            today=_today(),
        )

        # Only the published, in-range plan survives: 50 ÷ 100 = 50. The draft's
        # 900 planned minutes and the future plan's clip-empty window vanish.
        assert overall == 50

    @pytest.mark.parametrize('plans', [[], None])
    def test_null_when_there_is_nothing_to_measure(self, plans):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        assert plan_service.feed_overall_adherence(
            engagement, plans or [], _shift(-7), _today(), today=_today(),
        ) is None

    def test_null_when_surviving_plans_carry_no_elapsed_planned_minutes(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        future = _plan(engagement, start=_shift(1), duration=3,
                       status=PlanStatus.PUBLISHED)
        _item(future, math_row, 0, 60)
        _log_day(engagement, student, _today(), {math: 45})

        assert plan_service.feed_overall_adherence(
            engagement, [future], _shift(-7), _today(), today=_today(),
        ) is None


class TestFeedMoodAverage:
    def test_mean_of_non_null_moods_ignores_unrecorded_days(self):
        days = [{'mood': 3}, {'mood': None}, {'mood': 5}]
        assert plan_service.feed_mood_average(days) == 4.0

    def test_rounded_to_one_decimal(self):
        days = [{'mood': 4}, {'mood': 4}, {'mood': 5}]
        assert plan_service.feed_mood_average(days) == 4.3

    def test_all_null_and_empty_are_null(self):
        assert plan_service.feed_mood_average([{'mood': None}]) is None
        assert plan_service.feed_mood_average([]) is None


class TestAdherenceWire:
    def test_feed_carries_adherence_percent_and_mood_average(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        big = _plan(engagement, start=_shift(-10), duration=7,
                    status=PlanStatus.PUBLISHED)
        for offset in range(7):
            _item(big, math_row, offset, 10)
        _log_day(engagement, student, _shift(-9), {math: 20}, mood=3)
        _log_day(engagement, student, _shift(-7), {math: 15})
        small = _plan(engagement, start=_shift(-3), duration=3,
                      status=PlanStatus.PUBLISHED)
        for offset in range(3):
            _item(small, math_row, offset, 10)
        _log_day(engagement, student, _shift(-2), {math: 30}, mood=5)

        resp = _auth(advisor).get(_feed_url(engagement), {'days': 'all'})

        assert resp.status_code == 200
        assert resp.data['adherencePercent'] == 65
        assert resp.data['moodAverage'] == 4.0
        # Every rendered plan row carries the field too.
        assert all('percent' in plan for plan in resp.data['plans'])

    def test_feed_is_quiet_null_with_no_plans_and_no_moods(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        _log_day(engagement, student, _today(), {math: 30}, mood=None)

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '7'})

        assert resp.status_code == 200
        assert resp.data['adherencePercent'] is None
        assert resp.data['moodAverage'] is None

    def test_percent_is_null_for_a_draft_and_measured_for_published(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        draft = _plan(engagement, start=_shift(-3), duration=3)
        _item(draft, math_row, 0, 60)
        published = _plan(engagement, start=_shift(-10), duration=3,
                          status=PlanStatus.PUBLISHED)
        _item(published, math_row, 0, 60)
        _log_day(engagement, student, _shift(-9), {math: 30})

        listed = _auth(advisor).get(_plans_url(engagement))

        assert listed.status_code == 200
        by_id = {p['id']: p for p in listed.data['plans']}
        assert by_id[draft.pk]['percent'] is None
        assert by_id[published.pk]['percent'] == 50

    def test_me_plans_inherits_the_percent_field(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        future = _plan(engagement, start=_shift(1), duration=3,
                       status=PlanStatus.PUBLISHED)
        _item(future, math_row, 0, 60)

        seen = _auth(student).get('/api/advisory/me/plans/')

        assert seen.status_code == 200
        assert seen.data['plans'][0]['id'] == future.pk
        # Nothing has elapsed yet ⇒ quiet null on the student's side too.
        assert seen.data['plans'][0]['percent'] is None


# ── restart step 4 (wave-2 phase 2): row enrichment + day notes ───────────────

def _enriched_item(**overrides):
    """A draft item dict with every enrichment key at a legal value."""
    base = {
        'day_offset': 0,
        'subject_id': None,
        'planned_minutes': 60,
        'topic': 'مشتق',
        'unit_label': 'فصل ۲',
        'test_minutes': 30,
        'mastery_color': 'RED',
    }
    base.update(overrides)
    return base


class TestDraftEnrichment:
    """The four per-row enrichment columns and the plan-level ``day_notes``."""

    def test_all_four_fields_and_day_notes_roundtrip(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        plan = plan_service.save_draft(
            engagement,
            start_date=_today(),
            duration_days=7,
            items=[_enriched_item(subject_id=math.id)],
            day_notes={'0': {'school': 'آزمون ریاضی', 'preReading': 'مرور جزوه'},
                       '3': {'konkurClass': 'کلاس فیزیک'}},
        )

        item = plan.items.get()
        assert item.topic == 'مشتق'
        assert item.unit_label == 'فصل ۲'
        assert item.test_minutes == 30
        assert item.mastery_color == 'RED'
        assert plan.day_notes == {
            '0': {'school': 'آزمون ریاضی', 'preReading': 'مرور جزوه'},
            '3': {'konkurClass': 'کلاس فیزیک'},
        }

    @pytest.mark.parametrize('minutes', [0, MAX_PLAN_TEST_MINUTES])
    def test_test_minutes_boundaries_are_accepted(self, minutes):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        plan = plan_service.save_draft(
            engagement, start_date=_today(), duration_days=7,
            items=[_enriched_item(subject_id=math.id, test_minutes=minutes)],
        )
        assert plan.items.get().test_minutes == minutes

    @pytest.mark.parametrize('minutes', [-1, 481])
    def test_test_minutes_outside_0_480_is_rejected(self, minutes):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.TestMinutesOutOfRange):
            plan_service.save_draft(
                engagement, start_date=_today(), duration_days=7,
                items=[_enriched_item(subject_id=math.id, test_minutes=minutes)],
            )
        assert StudyPlan.objects.count() == 0

    def test_a_non_integer_test_minutes_is_rejected(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.TestMinutesOutOfRange):
            plan_service.save_draft(
                engagement, start_date=_today(), duration_days=7,
                items=[_enriched_item(subject_id=math.id, test_minutes='سی')],
            )
        assert StudyPlan.objects.count() == 0

    def test_an_unknown_mastery_color_is_rejected_with_the_exact_message(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.InvalidMasteryColor):
            plan_service.save_draft(
                engagement, start_date=_today(), duration_days=7,
                items=[_enriched_item(subject_id=math.id, mastery_color='BLUE')],
            )
        assert StudyPlan.objects.count() == 0

    def test_an_over_long_topic_is_rejected_before_any_write(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.TopicTooLong):
            plan_service.save_draft(
                engagement, start_date=_today(), duration_days=7,
                items=[_enriched_item(subject_id=math.id, topic='x' * 201)],
            )
        assert StudyPlanItem.objects.count() == 0

    def test_day_notes_key_seven_is_rejected(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.InvalidDayNotes):
            plan_service.save_draft(
                engagement, start_date=_today(), duration_days=7, items=[],
                day_notes={'7': {'school': 'نامعتبر'}},
            )
        assert StudyPlan.objects.count() == 0

    def test_day_notes_int_key_is_rejected_like_string_out_of_range(self):
        """JSON keys are strings; an int key can only bypass JSON — reject it."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.InvalidDayNotes):
            plan_service.save_draft(
                engagement, start_date=_today(), duration_days=7, items=[],
                day_notes={7: {'school': 'نامعتبر'}},
            )

    def test_day_notes_unknown_field_is_rejected(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.InvalidDayNotes):
            plan_service.save_draft(
                engagement, start_date=_today(), duration_days=7, items=[],
                day_notes={'0': {'hobby': 'شطرنج'}},
            )

    def test_day_notes_over_long_text_is_rejected(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        with pytest.raises(plan_service.InvalidDayNotes):
            plan_service.save_draft(
                engagement, start_date=_today(), duration_days=7, items=[],
                day_notes={'1': {'exams': 'x' * 121}},
            )

    def test_legacy_save_leaves_enrichment_and_day_notes_untouched(self):
        """A pre-step-4 caller sends only the three core keys: enrichment stores
        column defaults AND previously saved day notes survive."""
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        first = plan_service.save_draft(
            engagement, start_date=_today(), duration_days=7,
            items=[{'day_offset': 0, 'subject_id': math.id, 'planned_minutes': 60}],
            day_notes={'2': {'school': 'اردو'}},
        )
        second = plan_service.save_draft(
            engagement, start_date=_today(), duration_days=7,
            items=[{'day_offset': 0, 'subject_id': math.id, 'planned_minutes': 90}],
        )

        item = second.items.get()
        assert item.planned_minutes == 90
        assert item.topic == ''
        assert item.unit_label == ''
        assert item.test_minutes is None
        assert item.mastery_color is None
        assert second.day_notes == first.day_notes == {'2': {'school': 'اردو'}}

    def test_explicit_empty_day_notes_clears_stored_notes(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        plan_service.save_draft(
            engagement, start_date=_today(), duration_days=7, items=[],
            day_notes={'0': {'school': 'اردو'}},
        )
        cleared = plan_service.save_draft(
            engagement, start_date=_today(), duration_days=7, items=[],
            day_notes={},
        )
        assert cleared.day_notes == {}


class TestEnrichmentWire:
    """PlanOut carries the new keys end-to-end through PUT / publish / mirror."""

    def test_put_draft_returns_enrichment_and_day_notes(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        body = _draft_body(_today(), 7, [(0, math.id, 60)])
        body['items'][0].update({
            'topic': 'حد و پیوستگی', 'unitLabel': 'فصل ۱',
            'testMinutes': 45, 'masteryColor': 'YELLOW',
        })
        body['dayNotes'] = {'0': {'school': 'زنگ اول آزمون'}, '6': {'preReading': 'مرور'}}

        put = _auth(advisor).put(_draft_url(engagement), body, format='json')
        assert put.status_code == 200
        assert put.data['dayNotes'] == {
            '0': {'school': 'زنگ اول آزمون'}, '6': {'preReading': 'مرور'},
        }
        item = put.data['items'][0]
        assert item['topic'] == 'حد و پیوستگی'
        assert item['unitLabel'] == 'فصل ۱'
        assert item['testMinutes'] == 45
        assert item['masteryColor'] == 'YELLOW'

    def test_publish_keeps_the_new_keys_and_the_student_mirror_carries_them(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        body = _draft_body(_today(), 7, [(0, math.id, 60)])
        body['items'][0].update({
            'topic': 'مشتق', 'masteryColor': 'GREEN', 'testMinutes': 20,
        })
        _auth(advisor).put(_draft_url(engagement), body, format='json')

        published = _auth(advisor).post(_publish_url(engagement))
        assert published.status_code == 200
        assert published.data['status'] == 'PUBLISHED'
        assert published.data['items'][0]['masteryColor'] == 'GREEN'
        assert published.data['items'][0]['topic'] == 'مشتق'

        seen = _auth(student).get('/api/advisory/me/plans/')
        item = seen.data['plans'][0]['items'][0]
        assert item['unitLabel'] == ''
        assert item['testMinutes'] == 20
        assert item['masteryColor'] == 'GREEN'

    def test_api_rejects_bad_day_notes_with_the_exact_message(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        body = _draft_body(_today(), 7, [(0, math.id, 60)])
        body['dayNotes'] = {'9': {'school': 'بیرون از هفته'}}
        resp = _auth(advisor).put(_draft_url(engagement), body, format='json')
        assert resp.status_code == 400
        assert resp.data['detail'] == 'یادداشت روزها نامعتبر است.'

    def test_api_rejects_bad_mastery_color_with_the_exact_message(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        body = _draft_body(_today(), 7, [(0, math.id, 60)])
        body['items'][0]['masteryColor'] = 'PURPLE'
        resp = _auth(advisor).put(_draft_url(engagement), body, format='json')
        assert resp.status_code == 400
        assert resp.data['detail'] == 'رنگ تسلط نامعتبر است.'

    def test_api_rejects_out_of_range_test_minutes_with_the_exact_message(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        body = _draft_body(_today(), 7, [(0, math.id, 60)])
        body['items'][0]['testMinutes'] = 481
        resp = _auth(advisor).put(_draft_url(engagement), body, format='json')
        assert resp.status_code == 400
        assert resp.data['detail'] == 'زمان تست باید بین ۰ تا ۴۸۰ دقیقه باشد.'


class TestFeedUncompensated:
    """The «جبران‌نشده» flag over PUBLISHED plans of each date's week."""

    def _week_start(self):
        from apps.advisory.services.calendar import week_start_of
        return week_start_of(_today())

    def test_planned_but_unlogged_slot_surfaces_as_uncompensated_true(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student, started_on=_shift(-30))
        math, physics = _subject('ریاضی'), _subject('فیزیک')
        math_row, physics_row = _selection(engagement, math, physics)

        ws = self._week_start()
        today_offset = (_today() - ws).days
        plan = _plan(engagement, start=ws, duration=7, status=PlanStatus.PUBLISHED)
        _item(plan, math_row, today_offset, 45)
        _item(plan, physics_row, today_offset, 45)
        # The student logged only physics today — math's 45 planned minutes
        # were never compensated.
        _log_day(engagement, student, _today(), {physics: 10})

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '7'})

        assert resp.status_code == 200
        today = next(d for d in resp.data['days'] if d['date'] == _iso(_today()))
        by_subject = {i['subjectId']: i for i in today['items']}
        assert set(by_subject) == {math.id, physics.id}
        assert by_subject[math.id]['uncompensated'] is True
        assert by_subject[math.id]['minutes'] == 0
        assert by_subject[physics.id]['uncompensated'] is False
        assert by_subject[physics.id]['minutes'] == 10
        # Slot detail rides along on both.
        assert by_subject[math.id]['name'] == 'ریاضی'
        assert by_subject[physics.id]['masteryColor'] is None

    def test_logged_minutes_make_the_matching_slot_false_not_true(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student, started_on=_shift(-30))
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        ws = self._week_start()
        today_offset = (_today() - ws).days
        plan = _plan(engagement, start=ws, duration=7, status=PlanStatus.PUBLISHED)
        _item(plan, math_row, today_offset, 45)
        _log_day(engagement, student, _today(), {math: 10})

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '7'})

        today = next(d for d in resp.data['days'] if d['date'] == _iso(_today()))
        assert len(today['items']) == 1
        assert today['items'][0]['uncompensated'] is False
        assert today['totalMinutes'] == 10

    def test_a_week_without_a_published_plan_carries_no_flag_at_all(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student, started_on=_shift(-30))
        math = _subject('ریاضی')
        _selection(engagement, math)

        # A PUBLISHED plan covering LAST week only — today's week is bare.
        last_week_start = self._week_start() - datetime.timedelta(days=7)
        _plan(engagement, start=last_week_start, duration=7,
              status=PlanStatus.PUBLISHED)
        _log_day(engagement, student, _today(), {math: 25})

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '7'})

        today = next(d for d in resp.data['days'] if d['date'] == _iso(_today()))
        assert today['items'], 'the logged day must still render its item'
        for item in today['items']:
            assert 'uncompensated' not in item

    def test_draft_plan_slots_never_flag(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student, started_on=_shift(-30))
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        ws = self._week_start()
        today_offset = (_today() - ws).days
        draft = _plan(engagement, start=ws, duration=7)  # DRAFT: invisible
        _item(draft, math_row, today_offset, 45)
        _log_day(engagement, student, _today(), {math: 5})

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '7'})

        today = next(d for d in resp.data['days'] if d['date'] == _iso(_today()))
        assert len(today['items']) == 1
        assert 'uncompensated' not in today['items'][0]

    def test_total_minutes_ignore_injected_uncompensated_rows(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student, started_on=_shift(-30))
        math = _subject('ریاضی')
        math_row, = _selection(engagement, math)

        ws = self._week_start()
        today_offset = (_today() - ws).days
        plan = _plan(engagement, start=ws, duration=7, status=PlanStatus.PUBLISHED)
        _item(plan, math_row, today_offset, 45)
        _log_day(engagement, student, _today(), {math: 15})

        resp = _auth(advisor).get(_feed_url(engagement), {'days': '7'})

        today = next(d for d in resp.data['days'] if d['date'] == _iso(_today()))
        assert today['totalMinutes'] == 15
