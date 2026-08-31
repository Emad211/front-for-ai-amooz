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

Step 8 (S8) adds three **read-side, pure** metric helpers at the bottom of this
module — ``plan_adherence_percent``, ``feed_overall_adherence`` and
``feed_mood_average``. They write nothing; they only measure what the write
door above has already made true.

Validation order in ``save_draft`` mirrors ``daily_logs.save_day`` exactly:
start → duration → items (offset → subject → minutes → duplicates), all checked
**before any write**, so a request with one bad row changes nothing at all.
Ownership is not re-checked here: the view resolves the engagement through
``scope.advisor_engagement`` (404-not-403) before calling in, same as S4/S5.
"""

from __future__ import annotations

import datetime

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ..models import (
    MAX_PLAN_DURATION_DAYS,
    MAX_PLAN_MINUTES_PER_ITEM,
    MAX_PLAN_TEST_MINUTES,
    MASTERY_COLOR_CHOICES,
    DAY_NOTE_FIELDS,
    MAX_DAY_NOTE_CHARS,
    STUDY_FEED_VIEW_ACTION,
    AdvisoryAccessLog,
    DailyLogItem,
    StudyPlan,
    StudyPlanItem,
)
from . import scope
from .calendar import week_start_of

# Sentinel for «the client did not send this plan-level key»: an absent
# ``dayNotes`` must leave the stored column untouched so a legacy planner PUT
# cannot wipe notes it never knew about, while an explicit ``{}`` clears them.
UNSET = object()


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


# ── restart step 4 (wave-2 phase 2): per-row enrichment + day notes ──────────

class TopicTooLong(StudyPlanError):
    """400 — a row's topic exceeds the 200-char column bound."""

    def __init__(self):
        super().__init__('موضوع نمی‌تواند بیش از ۲۰۰ نویسه باشد.')


class UnitLabelTooLong(StudyPlanError):
    """400 — a row's unit label exceeds the 60-char column bound."""

    def __init__(self):
        super().__init__('واحد نمی‌تواند بیش از ۶۰ نویسه باشد.')


class TestMinutesOutOfRange(StudyPlanError):
    """400 — test minutes outside 0..480 (or not an integer at all)."""

    def __init__(self):
        super().__init__('زمان تست باید بین ۰ تا ۴۸۰ دقیقه باشد.')


class InvalidMasteryColor(StudyPlanError):
    """400 — a mastery color outside RED/YELLOW/GREEN."""

    def __init__(self):
        super().__init__('رنگ تسلط نامعتبر است.')


class InvalidDayNotes(StudyPlanError):
    """400 — ``day_notes`` violates the allowed shape.

    Every violation folds into one message on purpose: keys outside '0'..'6',
    non-string keys, unknown sub-fields, non-string values and over-long texts
    are all «your payload does not match the day-note shape», and enumerating
    them separately would only invite clients to probe the validator.
    """

    def __init__(self):
        super().__init__('یادداشت روزها نامعتبر است.')


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


def _validate_day_notes(day_notes) -> dict:
    """Validate the day-note shape and return it unchanged.

    Allowed: ``{"<0..6>": {"school"|"exams"|"konkurClass"|"preReading": str≤120}}``.
    Keys must be strings (an int ``7`` is as wrong as the string ``'7'`` — JSON
    object keys are strings on the wire, so a non-string key can only come from a
    caller bypassing JSON). Anything else raises ``InvalidDayNotes``.
    """
    if not isinstance(day_notes, dict):
        raise InvalidDayNotes()
    allowed_days = {str(d) for d in range(7)}
    for key, block in day_notes.items():
        if not isinstance(key, str) or key not in allowed_days:
            raise InvalidDayNotes()
        if not isinstance(block, dict):
            raise InvalidDayNotes()
        for sub_key, value in block.items():
            if sub_key not in DAY_NOTE_FIELDS:
                raise InvalidDayNotes()
            if not isinstance(value, str) or len(value) > MAX_DAY_NOTE_CHARS:
                raise InvalidDayNotes()
    return day_notes


def _validate_body(
    engagement, start_date, duration_days, items, day_notes=UNSET,
) -> list[dict]:
    """Run the full validation order and return normalized item dicts.

    Returns ``[{'day_offset', 'subject_id', 'planned_minutes', 'topic',
    'unit_label', 'test_minutes', 'mastery_color'}]`` — the exact vocabulary the
    set-replace consumes. Raises before any write. Enrichment checks run per row
    after the core bounds (offset → subject → minutes) and before the duplicate
    scan; plan-level ``day_notes`` validates last.
    """
    started = getattr(engagement, 'started_on', None) or timezone.localdate()
    if start_date < started:
        raise PlanStartBeforeEngagement()

    if not isinstance(duration_days, int) or isinstance(duration_days, bool) or not (
        1 <= duration_days <= MAX_PLAN_DURATION_DAYS
    ):
        raise InvalidPlanDuration()

    wanted = []
    for item in items:
        test_minutes = item.get('test_minutes')
        if test_minutes is not None:
            if isinstance(test_minutes, bool) or not isinstance(test_minutes, int):
                raise TestMinutesOutOfRange()
        wanted.append({
            'day_offset': int(item['day_offset']),
            'subject_id': int(item['subject_id']),
            'planned_minutes': int(item['planned_minutes']),
            'topic': str(item.get('topic') or ''),
            'unit_label': str(item.get('unit_label') or ''),
            'test_minutes': test_minutes,
            'mastery_color': item.get('mastery_color') or None,
            'start_time': item.get('start_time') or None,
        })

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

    valid_colors = {code for code, _label in MASTERY_COLOR_CHOICES}
    for row in wanted:
        if not (1 <= row['planned_minutes'] <= MAX_PLAN_MINUTES_PER_ITEM):
            raise PlannedMinutesOutOfRange()
        # Restart step 4 enrichment — column bounds first, then enum/range.
        if len(row['topic']) > 200:
            raise TopicTooLong()
        if len(row['unit_label']) > 60:
            raise UnitLabelTooLong()
        if row['test_minutes'] is not None and not (
            0 <= row['test_minutes'] <= MAX_PLAN_TEST_MINUTES
        ):
            raise TestMinutesOutOfRange()
        if row['mastery_color'] is not None and row['mastery_color'] not in valid_colors:
            raise InvalidMasteryColor()

    seen = set()
    for row in wanted:
        key = (row['day_offset'], row['subject_id'])
        if key in seen:
            raise DuplicatePlanRow()
        seen.add(key)

    if day_notes is not UNSET:
        _validate_day_notes(day_notes)

    return wanted


def _selected_row_id(engagement, subject_id) -> int | None:
    """The active ``StudentSubject`` row id behind a catalog-subject id."""
    return (
        scope.student_subjects(engagement)
        .filter(subject_id=subject_id)
        .values_list('pk', flat=True)
        .first()
    )


def save_draft(
    engagement, *, start_date, duration_days, items, day_notes=UNSET,
    phase='', strategy='',
) -> StudyPlan:
    """Make the engagement's single DRAFT slot equal exactly what was sent.

    The slot is upserted (one DRAFT row per engagement, by constraint) and its
    items are **hard-replaced**: drafts carry no history, so unlike the daily
    log's ``update_or_create`` there is nothing to preserve across saves.
    Concurrent savers serialize on the engagement row lock, which is what keeps
    the get_or_create from racing past the partial unique constraint.

    ``day_notes`` (restart step 4) follows the daily-log enrichment rule instead:
    ``UNSET`` (the default — the key was absent from the request) leaves the
    stored column untouched so legacy planner payloads cannot wipe notes they
    never knew about; any present value, including ``{}``, replaces it wholesale.
    Items may optionally carry ``topic``/``unit_label``/``test_minutes``/
    ``mastery_color``; absent ones store the column defaults.
    """
    wanted = _validate_body(engagement, start_date, duration_days, items, day_notes)

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
        # Research wave (2026-08-31): roadmap labels, wholesale like the rest
        # of the draft body — absent keys store the blank default.
        plan.phase = phase or ''
        plan.strategy = strategy or ''
        update_fields = [
            'start_date', 'duration_days', 'phase', 'strategy', 'updated_at',
        ]
        if day_notes is not UNSET:
            plan.day_notes = day_notes
            update_fields.append('day_notes')
        plan.save(update_fields=update_fields)

        plan.items.all().delete()
        StudyPlanItem.objects.bulk_create([
            StudyPlanItem(
                plan=plan,
                day_offset=row['day_offset'],
                student_subject_id=_selected_row_id(engagement, row['subject_id']),
                planned_minutes=row['planned_minutes'],
                topic=row['topic'],
                unit_label=row['unit_label'],
                test_minutes=row['test_minutes'],
                mastery_color=row['mastery_color'],
                start_time=row.get('start_time'),
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


# ── S8: the commitment metric (read-side, pure) ──────────────────────────────

def _logged_minutes(engagement, start_date, end_date) -> int:
    """Σ actual minutes reported on this engagement inside the inclusive window.

    One aggregate over ``DailyLogItem`` — the numerator half of every adherence
    ratio. Minutes outside the window are not "missed", they are *unmeasured*:
    a log from before the plan began belongs to no commitment of this plan, and
    counting it would let a hard-working week before the plan inflate (or, via
    the ratio's denominator staying fixed, distort) the percentage.
    """
    total = DailyLogItem.objects.filter(
        log__engagement=engagement,
        log__log_date__gte=start_date,
        log__log_date__lte=end_date,
    ).aggregate(total=Sum('actual_minutes'))['total']
    return int(total or 0)


def _planned_minutes_between(plan, start_date, end_date) -> int:
    """Σ planned minutes of the plan's rows whose computed date is in the window.

    An item has no date column — its day is ``start_date + day_offset``, the
    same arithmetic ``StudyPlanItemOutSerializer.get_date`` publishes. Summing
    in Python over ``plan.items.all()`` rides the scope prefetch wherever the
    caller came through ``scope.advisor_plans`` / ``student_published_plans``,
    so this costs no extra query on the wire paths.
    """
    return sum(
        item.planned_minutes
        for item in plan.items.all()
        if start_date <= plan.start_date + datetime.timedelta(days=item.day_offset) <= end_date
    )


def plan_adherence_percent(plan, today=None) -> int | None:
    """The one plan's adherence: ``round(actual ÷ planned × 100)``, or ``None``.

    The locked S8 shape:

    * **Numerator** — minutes logged on ``plan.engagement`` with
      ``log_date ∈ [plan.start_date .. min(plan.end_date, today)]``. Inclusive
      edges: the start day and the end day both belong to the window. Anything
      logged outside the plan's horizon is excluded entirely, which is what
      keeps the ratio an honest measurement of *this* commitment.
    * **Denominator** — planned minutes of rows whose date ≤ today only. A plan
      still underway is measured against what has **elapsed**, never against
      what is still to come: counting future days would punish a student for
      days that have not happened yet.
    * ``planned == 0`` ⇒ ``None`` — a plan with nothing elapsed yet (or nothing
      at all) has no ratio; rendering it as 0% would read as «did nothing».

    ``today`` defaults to ``timezone.localdate()`` («امروز», student-local);
    tests pass it explicitly for determinism. Status-blind by design — whether
    a DRAFT deserves a percent at all is the serializer's rule (it answers
    ``None`` unless PUBLISHED), not this formula's business.
    """
    if today is None:
        today = timezone.localdate()
    window_end = min(plan.end_date, today)
    if window_end < plan.start_date:
        # The plan has not started yet: zero elapsed items ⇒ no measurement.
        return None

    planned = sum(
        item.planned_minutes
        for item in plan.items.all()
        if plan.start_date + datetime.timedelta(days=item.day_offset) <= today
    )
    if planned <= 0:
        return None

    actual = _logged_minutes(engagement=plan.engagement,
                             start_date=plan.start_date, end_date=window_end)
    return round(actual / planned * 100)


def feed_overall_adherence(engagement, plans, date_from, date_to, today=None) -> int | None:
    """One weighted chip for the study feed: Σactual ÷ Σplanned across plans.

    Never an average of percentages — a 100% week on a 3-day plan must not
    outweigh a 50% month on a 30-day plan, so the two sums are taken first and
    divided once. Each **PUBLISHED** plan's window is clipped to the feed's
    selected range (and to today): ``[max(start, from), min(end, to, today)]``.
    A clip that comes out empty (the plan lies wholly outside the range or in
    the future) contributes nothing; survivors contribute both their clipped
    actual and their clipped planned, so the chip always describes exactly the
    range the advisor is looking at. No survivor with planned minutes ⇒
    ``None`` — quiet-null, per the owner rule for empty feeds.
    """
    if today is None:
        today = timezone.localdate()

    total_actual = 0
    total_planned = 0
    for plan in plans:
        if plan.status != StudyPlan.Status.PUBLISHED:
            continue
        clip_start = max(plan.start_date, date_from)
        clip_end = min(plan.end_date, date_to, today)
        if clip_start > clip_end:
            continue
        total_actual += _logged_minutes(
            engagement=engagement, start_date=clip_start, end_date=clip_end,
        )
        total_planned += _planned_minutes_between(
            plan, start_date=clip_start, end_date=clip_end,
        )

    if total_planned <= 0:
        return None
    return round(total_actual / total_planned * 100)


def feed_mood_average(days) -> float | None:
    """Mean of the non-null ``days[].mood`` values, rounded to 1 decimal.

    Takes the **serialized** feed-day dicts (the wire shape the view already
    built), so the null-meaningful mood convention survives the hop: a day with
    ``mood=None`` is «not recorded» and drops out of the mean rather than
    dragging it down. All days unrecorded (or no days at all) ⇒ ``None``.
    """
    moods = [day['mood'] for day in days if day.get('mood') is not None]
    if not moods:
        return None
    return round(sum(moods) / len(moods), 1)


# ── restart step 4 (wave-2 phase 2): the «جبران‌نشده» feed flag ───────────────

def attach_uncompensated_flags(days_data, plans) -> None:
    """Stamp each serialized feed day's items with the uncompensated flag, in place.

    Behavioral definition (restart step 4, pinned by tests): for a feed day ``D``,
    let ``W = week_start_of(D)``. Only when **some PUBLISHED plan intersects**
    ``[W, W+6]`` does the flag exist on that day at all. Within such a week:

    * a logged item whose ``(D, subject)`` matches a PUBLISHED-plan slot with
      ``planned_minutes > 0`` gets ``uncompensated: true`` iff the actual minutes
      recorded for that same ``(student_subject, date)`` sum to zero — else
      ``false``;
    * a slot with **no** logged minutes for its date surfaces as an injected row
      ``{subjectId, name, minutes: 0, uncompensated: true}`` so the advisor sees
      the missed commitment on the day it happened («ردیف‌های جبران‌نشده را نشان
      بده»);
    * an item matching no slot carries no flag key at all.

    Pure and additive over the already-serialized dicts: reads only prefetched
    plan items, mutates nothing in the DB, never removes a key the serializer
    wrote. ``totalMinutes`` was computed during serialization from the stored
    rows only, so injected zero-minute rows cannot distort it.
    """
    published = [p for p in plans if p.status == StudyPlan.Status.PUBLISHED]
    if not published or not days_data:
        return

    slots_by_date: dict[datetime.date, dict[int, dict]] = {}
    for plan in published:
        for item in plan.items.all():
            if item.planned_minutes <= 0:
                continue
            slot_date = plan.start_date + datetime.timedelta(days=item.day_offset)
            slots_by_date.setdefault(slot_date, {})[item.student_subject.subject_id] = {
                'name': item.student_subject.subject.name,
                'topic': item.topic,
                'unit_label': item.unit_label,
                'mastery_color': item.mastery_color,
            }

    week_has_plan: dict[datetime.date, bool] = {}

    def _covers_week(plan, week_start: datetime.date) -> bool:
        week_end = week_start + datetime.timedelta(days=6)
        return plan.start_date <= week_end and plan.end_date >= week_start

    for day in days_data:
        raw_date = day.get('date')
        if isinstance(raw_date, str):
            log_date = datetime.date.fromisoformat(raw_date)
        elif isinstance(raw_date, datetime.date):
            log_date = raw_date
        else:
            continue

        week_start = week_start_of(log_date)
        if week_start not in week_has_plan:
            week_has_plan[week_start] = any(
                _covers_week(p, week_start) for p in published
            )
        if not week_has_plan[week_start]:
            # A week without any PUBLISHED plan: the flag must not appear at all.
            continue

        day_slots = slots_by_date.get(log_date, {})
        logged_ids = set()
        for item in day['items']:
            sid = item.get('subjectId')
            meta = day_slots.get(sid)
            if meta is None:
                continue
            logged_ids.add(sid)
            item['uncompensated'] = item.get('minutes', 0) == 0
            # Slot detail rides along so the client can render topic/unit/color.
            item.setdefault('topic', meta['topic'])
            item.setdefault('unitLabel', meta['unit_label'])
            item.setdefault('masteryColor', meta['mastery_color'])

        for sid, meta in day_slots.items():
            if sid in logged_ids:
                continue
            day['items'].append({
                'subjectId': sid,
                'name': meta['name'],
                'minutes': 0,
                'uncompensated': True,
                'topic': meta['topic'],
                'unitLabel': meta['unit_label'],
                'masteryColor': meta['mastery_color'],
            })
