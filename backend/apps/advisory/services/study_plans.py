"""The write door for study plans (S7, §14 redesign).

``StudyPlan`` / ``StudyPlanItem`` are tenancy-bearing, so — exactly like
``invites.py``, ``student_subjects.py`` and ``daily_logs.py`` before it — every
mutation goes through this one module, never through a view. ``scope.py`` reads
across tenancy; this writes into it.

Three public functions, mirroring the two-state lifecycle:

* ``save_draft`` — upsert the engagement's **single** DRAFT slot wholesale
  (set-replace of the item rows). A draft is the advisor's unsent scratchpad:
  unlike ``DailyLogItem`` — where ``created_at`` is preserved because the row is
  the student's own record of something that happened — a draft has no history
  value, so its items are hard-deleted and re-made on every save, and this is
  documented here as deliberate.
* ``publish_draft`` — re-validate everything against the *current* state
  (selections may have changed since the draft was written), check non-overlap
  with the other PUBLISHED plans, then flip DRAFT → PUBLISHED under
  ``select_for_update``.
* ``unpublish_plan`` — the §5 rollback lever: PUBLISHED → DRAFT.

Validation order in ``save_draft`` mirrors ``daily_logs.save_day`` exactly:
start → duration → items (offset → subject → minutes → duplicates), all checked
**before any write**, so a request with one bad row changes nothing at all.
Ownership is not re-checked here: the view resolves the engagement through
``scope.advisor_engagement`` (404-not-403) before calling in, same as S4/S5.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ..models import (
    MAX_PLAN_DURATION_DAYS,
    MAX_PLAN_MINUTES_PER_ITEM,
    STUDY_FEED_VIEW_ACTION,
    AdvisoryAccessLog,
    StudyPlan,
    StudyPlanItem,
)
from . import scope


class StudyPlanError(Exception):
    """Base class so a view can catch the whole family in one clause."""


class PlanStartBeforeEngagement(StudyPlanError):
    """400 — the plan starts before the engagement began (C3 for writes)."""

    def __init__(self):
        super().__init__('تاریخ شروع نمی‌تواند پیش از شروع همکاری باشد.')


class InvalidPlanDuration(StudyPlanError):
    """400 — duration outside 1..90."""

    def __init__(self):
        super().__init__('طول برنامه باید بین ۱ و ۹۰ روز باشد.')


class DayOffsetOutOfRange(StudyPlanError):
    """400 — an item's day offset is not inside the plan's own length."""

    def __init__(self, day_offset):
        self.day_offset = day_offset
        super().__init__(f'روز {day_offset} خارج از طول برنامه است.')


class SubjectNotInSelection(StudyPlanError):
    """400 — a subject that is not currently on this student's list.

    Folds together "does not exist", "never picked" and "picked then dropped",
    like the S5 sibling of the same name: telling them apart would leak the shape
    of other students' selections.
    """

    def __init__(self, subject_ids):
        self.subject_ids = list(subject_ids)
        super().__init__('این درس در فهرست درس‌های شما نیست.')


class PlannedMinutesOutOfRange(StudyPlanError):
    """400 — planned minutes outside 1..960 (the log's scale, shared on purpose)."""

    def __init__(self):
        super().__init__('دقیقه‌ی برنامه‌ریزی‌شده باید بین ۱ تا ۹۶۰ باشد.')


class DuplicatePlanRow(StudyPlanError):
    """400 — two rows for one (day_offset, subject) pair."""

    def __init__(self):
        super().__init__('برای هر روز و درس فقط یک ردیف بفرستید.')


class PlanNotFound(StudyPlanError):
    """404 — no such draft/plan **for this engagement**.

    A foreign plan id and a nonexistent one are indistinguishable on purpose,
    same as the engagement-level 404-not-403 convention: confirming existence to
    a caller who does not own the row is the leak.
    """

    def __init__(self):
        super().__init__('برنامه پیدا نشد.')


class EmptyPlanPublish(StudyPlanError):
    """400 — publishing a draft with zero items would show the student nothing."""

    def __init__(self):
        super().__init__('برنامهٔ خالی قابل انتشار نیست.')


class PlanOverlap(StudyPlanError):
    """400 — the horizon intersects another PUBLISHED plan of this engagement."""

    def __init__(self):
        super().__init__('این بازه با برنامهٔ منتشرشدهٔ دیگری همپوشانی دارد.')


def _validate_body(engagement, start_date, duration_days, items) -> list[dict]:
    """Run the full validation order and return normalized item dicts.

    Returns ``[{'day_offset': int, 'subject_id': int, 'planned_minutes': int}]``
    — the exact vocabulary the set-replace consumes. Raises before any write.
    """
    started = getattr(engagement, 'started_on', None) or timezone.localdate()
    if start_date < started:
        raise PlanStartBeforeEngagement()

    if not isinstance(duration_days, int) or isinstance(duration_days, bool) or not (
        1 <= duration_days <= MAX_PLAN_DURATION_DAYS
    ):
        raise InvalidPlanDuration()

    wanted = [
        {
            'day_offset': int(item['day_offset']),
            'subject_id': int(item['subject_id']),
            'planned_minutes': int(item['planned_minutes']),
        }
        for item in items
    ]

    for row in wanted:
        if not (0 <= row['day_offset'] < duration_days):
            raise DayOffsetOutOfRange(row['day_offset'])

    subject_ids = {row['subject_id'] for row in wanted}
    selected = (
        set(
            scope.student_subjects(engagement)
            .filter(subject_id__in=subject_ids)
            .values_list('subject_id', flat=True)
        )
        if subject_ids
        else set()
    )
    missing = [sid for sid in sorted(subject_ids) if sid not in selected]
    if missing:
        raise SubjectNotInSelection(missing)

    for row in wanted:
        if not (1 <= row['planned_minutes'] <= MAX_PLAN_MINUTES_PER_ITEM):
            raise PlannedMinutesOutOfRange()

    seen = set()
    for row in wanted:
        key = (row['day_offset'], row['subject_id'])
        if key in seen:
            raise DuplicatePlanRow()
        seen.add(key)

    return wanted


def _selected_row_id(engagement, subject_id) -> int | None:
    """The active ``StudentSubject`` row id behind a catalog-subject id."""
    return (
        scope.student_subjects(engagement)
        .filter(subject_id=subject_id)
        .values_list('pk', flat=True)
        .first()
    )


def save_draft(engagement, *, start_date, duration_days, items) -> StudyPlan:
    """Make the engagement's single DRAFT slot equal exactly what was sent.

    The slot is upserted (one DRAFT row per engagement, by constraint) and its
    items are **hard-replaced**: drafts carry no history, so unlike the daily
    log's ``update_or_create`` there is nothing to preserve across saves.
    Concurrent savers serialize on the engagement row lock, which is what keeps
    the get_or_create from racing past the partial unique constraint.
    """
    wanted = _validate_body(engagement, start_date, duration_days, items)

    with transaction.atomic():
        # Row-level lock on the tenancy carrier: two racing PUTs then resolve the
        # draft slot strictly one after the other instead of both creating one.
        engagement.__class__.objects.select_for_update().get(pk=engagement.pk)
        plan, _ = StudyPlan.objects.get_or_create(
            engagement=engagement,
            status=StudyPlan.Status.DRAFT,
            defaults={'start_date': start_date, 'duration_days': duration_days},
        )
        plan.start_date = start_date
        plan.duration_days = duration_days
        plan.save(update_fields=['start_date', 'duration_days', 'updated_at'])

        plan.items.all().delete()
        StudyPlanItem.objects.bulk_create([
            StudyPlanItem(
                plan=plan,
                day_offset=row['day_offset'],
                student_subject_id=_selected_row_id(engagement, row['subject_id']),
                planned_minutes=row['planned_minutes'],
            )
            for row in wanted
        ])

    return scope.advisor_plans(engagement).get(pk=plan.pk)


def publish_draft(engagement) -> StudyPlan:
    """Flip the engagement's DRAFT to PUBLISHED, re-validating against now.

    Order matters and none of it is incidental: no draft ⇒ 404 (nothing to
    publish is a different fact from a bad request); empty items ⇒ 400; every
    item re-checked against the **currently active** selections — a subject the
    advisor dropped after saving the draft makes the stale draft unpublishable;
    then the overlap test against the other PUBLISHED plans, comparing inclusive
    horizons ``[start, start + duration - 1]`` where touching an edge (this end
    == other's start) is **not** an overlap. Only then does the flip happen,
    under a row lock so two concurrent publishes cannot both win.
    """
    with transaction.atomic():
        plan = (
            StudyPlan.objects.select_for_update()
            .filter(engagement=engagement, status=StudyPlan.Status.DRAFT)
            .first()
        )
        if plan is None:
            raise PlanNotFound()

        if not plan.items.exists():
            raise EmptyPlanPublish()

        active_ids = set(
            scope.student_subjects(engagement).values_list('subject_id', flat=True)
        )
        missing = sorted({
            item.student_subject.subject_id
            for item in plan.items.all()
            if item.student_subject.subject_id not in active_ids
        })
        if missing:
            raise SubjectNotInSelection(missing)

        new_start = plan.start_date
        new_end = plan.end_date
        others = StudyPlan.objects.filter(
            engagement=engagement,
            status=StudyPlan.Status.PUBLISHED,
        ).exclude(pk=plan.pk)
        for other in others:
            # Inclusive intervals that merely touch at an edge do not intersect:
            # strict inequalities are what make «پایان == شروعِ دیگری» legal.
            if new_start < other.end_date and new_end > other.start_date:
                raise PlanOverlap()

        plan.status = StudyPlan.Status.PUBLISHED
        plan.save(update_fields=['status', 'updated_at'])

    return scope.advisor_plans(engagement).get(pk=plan.pk)


def unpublish_plan(engagement, plan_id) -> StudyPlan:
    """Roll a PUBLISHED plan back to DRAFT (the §5 lever).

    The draft slot is unique per engagement, so rolling back into it may collide
    with a newer scratch draft. The collision resolves in favour of the rollback:
    the unpublished plan becomes the draft, and any other DRAFT — which by
    definition was never visible to the student and carries no history — is
    deleted outright (items first, because the item FK is PROTECT).
    """
    with transaction.atomic():
        plan = (
            StudyPlan.objects.select_for_update()
            .filter(
                engagement=engagement,
                pk=plan_id,
                status=StudyPlan.Status.PUBLISHED,
            )
            .first()
        )
        if plan is None:
            raise PlanNotFound()

        stale_drafts = list(
            StudyPlan.objects.select_for_update()
            .filter(engagement=engagement, status=StudyPlan.Status.DRAFT)
            .exclude(pk=plan.pk)
        )
        for stale in stale_drafts:
            stale.items.all().delete()
            stale.delete()

        plan.status = StudyPlan.Status.DRAFT
        plan.save(update_fields=['status', 'updated_at'])

    return scope.advisor_plans(engagement).get(pk=plan.pk)


def record_study_feed_view(engagement, reader) -> None:
    """Append the one D4 line: this reader opened this engagement's study feed.

    Called by the feed view **after** the payload is built — a failed read
    (400/403/404) writes nothing, so the log counts successful views and only
    those. Append-only by design: no update, no delete, no read path anywhere in
    the API.
    """
    AdvisoryAccessLog.objects.create(
        reader=reader,
        engagement=engagement,
        action=STUDY_FEED_VIEW_ACTION,
    )
