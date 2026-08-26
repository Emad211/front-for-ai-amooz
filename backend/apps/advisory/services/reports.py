"""The reporting engine behind risman step 2 (roadmap §۵ گام ۲).

A read-side sibling of ``overview.py``: pure aggregations over the tenancy the
caller has already resolved — zero LLM, zero writes, zero scoping of its own.
Every function takes an engagement (or an advisor) that the view resolved
through ``scope.advisor_engagement`` / ``scope.visible_engagements`` and only
measures what is already true.

The clipping rules mirror the study feed's locked semantics
(``study_plans.feed_overall_adherence``):

* **planned** counts PUBLISHED-plan item minutes whose computed date
  (``start_date + day_offset``) falls in ``[date_from, min(date_to, today)]`` —
  a plan still underway is measured against elapsed days only, never against
  days that have not happened yet;
* **actual** sums ``DailyLogItem.actual_minutes`` with ``log_date`` in
  ``[date_from, date_to]`` — logs cannot exist in the future (C3 write bound),
  so no extra clamp is needed;
* a coverage ratio with zero planned minutes is ``None`` («ثبت نشده»), never a
  fake 0%.

Wire keys are camelCase per ق۸; dates are ISO strings. ``student_report``
returns the exam-score rows themselves (newest first) so the view can project
them through the shared ``ExamScoreItemSerializer`` — one wire shape for the
scores table everywhere it appears.

``advisor_report`` is consumed by risman step 3 (org panel) but built here now:
per-ACTIVE-engagement aggregates plus three tool counters over the range.
"""

from __future__ import annotations

import datetime

from django.db.models import Sum
from django.utils import timezone

from ..models import (
    DailyLog,
    DailyLogItem,
    StudyExamAnalysis,
    StudyExamScore,
    StudyPlan,
    WeeklyAssessment,
)
from . import scope


def _coverage_percent(actual: int, planned: int) -> int | None:
    """``round(actual ÷ planned × 100)``, or ``None`` when nothing was planned."""
    if planned <= 0:
        return None
    return round(actual / planned * 100)


def _published_items(engagement):
    """PUBLISHED plans of this engagement with items + subjects prefetched."""
    return StudyPlan.objects.filter(
        engagement=engagement,
        status=StudyPlan.Status.PUBLISHED,
    ).prefetch_related('items__student_subject__subject')


def _planned_buckets(
    engagement, date_from: datetime.date, date_to: datetime.date,
    today: datetime.date | None = None,
) -> tuple[dict[datetime.date, int], dict[int, int], dict[int, str]]:
    """Planned minutes keyed by day and by subject, clipped like the feed.

    Returns ``(by_day, by_subject, subject_names)``. An item's day is
    ``plan.start_date + day_offset`` — the same arithmetic the feed and the
    plan serializer publish — and only days inside
    ``[date_from, min(date_to, today)]`` count, so future rows of an underway
    plan never punish the ratio.
    """
    if today is None:
        today = timezone.localdate()
    measurable_end = min(date_to, today)
    by_day: dict[datetime.date, int] = {}
    by_subject: dict[int, int] = {}
    names: dict[int, str] = {}
    for plan in _published_items(engagement):
        for item in plan.items.all():
            day = plan.start_date + datetime.timedelta(days=item.day_offset)
            if not (date_from <= day <= measurable_end):
                continue
            by_day[day] = by_day.get(day, 0) + item.planned_minutes
            subject_id = item.student_subject.subject_id
            by_subject[subject_id] = (
                by_subject.get(subject_id, 0) + item.planned_minutes
            )
            names.setdefault(subject_id, item.student_subject.subject.name)
    return by_day, by_subject, names


def _actual_buckets(
    engagement, date_from: datetime.date, date_to: datetime.date,
) -> tuple[dict[datetime.date, int], dict[int, int], dict[int, str]]:
    """Actual logged minutes keyed by day and by subject, range-clamped.

    One grouped query over ``DailyLogItem``; deactivated selections are kept on
    purpose (minutes already recorded survive their subject being dropped — see
    ``DailyLogItem``'s docstring).
    """
    by_day: dict[datetime.date, int] = {}
    by_subject: dict[int, int] = {}
    names: dict[int, str] = {}
    rows = (
        DailyLogItem.objects.filter(
            log__engagement=engagement,
            log__log_date__gte=date_from,
            log__log_date__lte=date_to,
        )
        .values(
            'log__log_date',
            'student_subject__subject_id',
            'student_subject__subject__name',
        )
        .annotate(total=Sum('actual_minutes'))
    )
    for row in rows:
        day = row['log__log_date']
        subject_id = row['student_subject__subject_id']
        minutes = int(row['total'] or 0)
        by_day[day] = by_day.get(day, 0) + minutes
        by_subject[subject_id] = by_subject.get(subject_id, 0) + minutes
        names.setdefault(subject_id, row['student_subject__subject__name'])
    return by_day, by_subject, names


def planner_report(engagement, date_from: datetime.date, date_to: datetime.date) -> dict:
    """«گزارش برنامه»: planned-vs-actual per day, per subject, and in total.

    ``days`` covers every date of the *measurable* window
    ``[date_from, min(date_to, today)]`` ascending — days beyond today carry no
    possible data (planned is clipped there, logs cannot exist there), so they
    are not emitted as zero-noise rows. ``subjects`` is the union of subjects
    with planned or actual minutes, ordered by name; ``coveragePercent`` is
    quiet-null when nothing was planned for that row.
    """
    today = timezone.localdate()
    measurable_end = min(date_to, today)

    planned_by_day, planned_by_subject, planned_names = _planned_buckets(
        engagement, date_from, date_to, today,
    )
    actual_by_day, actual_by_subject, actual_names = _actual_buckets(
        engagement, date_from, date_to,
    )

    days = [
        {
            'date': day.isoformat(),
            'planned': planned_by_day.get(day, 0),
            'actual': actual_by_day.get(day, 0),
        }
        for day in _iter_days(date_from, measurable_end)
    ]

    subject_ids = set(planned_by_subject) | set(actual_by_subject)
    subjects = sorted(
        (
            {
                'subjectId': subject_id,
                'name': planned_names.get(subject_id)
                or actual_names.get(subject_id, ''),
                'planned': planned_by_subject.get(subject_id, 0),
                'actual': actual_by_subject.get(subject_id, 0),
                'coveragePercent': _coverage_percent(
                    actual_by_subject.get(subject_id, 0),
                    planned_by_subject.get(subject_id, 0),
                ),
            }
            for subject_id in subject_ids
        ),
        key=lambda row: row['name'],
    )

    total_planned = sum(planned_by_subject.values())
    total_actual = sum(actual_by_subject.values())
    return {
        'days': days,
        'subjects': subjects,
        'totals': {
            'planned': total_planned,
            'actual': total_actual,
            'coveragePercent': _coverage_percent(total_actual, total_planned),
        },
    }


def student_report(engagement, date_from: datetime.date, date_to: datetime.date) -> dict:
    """«گزارش دانش‌آموز»: study/test series, subject share, exam scores.

    * ``studySeries`` — per-date Σ ``DailyLogItem`` minutes, dates with minutes
      > 0 only, ascending (a reported-but-empty day is «no data», not 0);
    * ``testSeries`` — per-date ``DailyLog.tests_taken`` where > 0, ascending;
    * ``subjectShare`` — per-subject total minutes descending with
      ``sharePercent`` rounded to 1 decimal (null-safe when the grand total is
      0, which also means the list itself is empty);
    * ``examScores`` — ``StudyExamScore`` rows with ``exam_date`` in range,
      newest first (the model's own ordering), returned as rows so the view
      reuses the shared score serializer.
    """
    study_rows = (
        DailyLogItem.objects.filter(
            log__engagement=engagement,
            log__log_date__gte=date_from,
            log__log_date__lte=date_to,
        )
        .values('log__log_date')
        .annotate(total=Sum('actual_minutes'))
        .filter(total__gt=0)
        .order_by('log__log_date')
    )
    study_series = [
        {'date': row['log__log_date'].isoformat(), 'minutes': int(row['total'])}
        for row in study_rows
    ]

    test_rows = (
        DailyLog.objects.filter(
            engagement=engagement,
            log_date__gte=date_from,
            log_date__lte=date_to,
            tests_taken__gt=0,
        )
        .order_by('log_date')
        .values('log_date', 'tests_taken')
    )
    test_series = [
        {'date': row['log_date'].isoformat(), 'testsTaken': row['tests_taken']}
        for row in test_rows
    ]

    share_rows = (
        DailyLogItem.objects.filter(
            log__engagement=engagement,
            log__log_date__gte=date_from,
            log__log_date__lte=date_to,
        )
        .values(
            'student_subject__subject_id',
            'student_subject__subject__name',
        )
        .annotate(total=Sum('actual_minutes'))
        .filter(total__gt=0)
        .order_by('-total', 'student_subject__subject__name')
    )
    grand_total = sum(int(row['total']) for row in share_rows)
    subject_share = [
        {
            'subjectId': row['student_subject__subject_id'],
            'name': row['student_subject__subject__name'],
            'minutes': int(row['total']),
            'sharePercent': (
                round(int(row['total']) / grand_total * 100, 1)
                if grand_total > 0
                else None
            ),
        }
        for row in share_rows
    ]

    exam_scores = list(
        StudyExamScore.objects.filter(
            engagement=engagement,
            exam_date__gte=date_from,
            exam_date__lte=date_to,
        )
        .select_related('subject')
        .order_by('-exam_date', '-id')
    )

    return {
        'studySeries': study_series,
        'testSeries': test_series,
        'subjectShare': subject_share,
        'examScores': exam_scores,
    }


def advisor_report(advisor, date_from: datetime.date, date_to: datetime.date) -> dict:
    """Per-student aggregates + tool counters across the advisor's roster.

    One row per **ACTIVE** engagement (the same roster
    ``scope.advisor_students`` serves, same ordering), each carrying the
    planner semantics above clipped to this range plus the range's
    ``testsTaken``. The three tool counters measure the advisor's own usage of
    the feature over the range: PUBLISHED plans starting in-range, weekly
    assessments anchored in-range, and exam analyses created in-range — all
    scoped through ``visible_engagements`` so a removed org advisor's numbers
    stop counting the moment their membership row disappears.
    """
    today = timezone.localdate()
    measurable_end = min(date_to, today)

    engagements = scope.advisor_students(advisor)
    students = []
    for engagement in engagements:
        planned_by_day, _, _ = _planned_buckets(
            engagement, date_from, date_to, today,
        )
        actual_by_day, _, _ = _actual_buckets(engagement, date_from, date_to)
        total_planned = sum(planned_by_day.values())
        total_actual = sum(actual_by_day.values())
        tests_taken = (
            DailyLog.objects.filter(
                engagement=engagement,
                log_date__gte=date_from,
                log_date__lte=date_to,
            ).aggregate(total=Sum('tests_taken'))['total']
            or 0
        )
        students.append({
            'engagementId': engagement.pk,
            'studentName': _display_name(engagement.student),
            'planned': total_planned,
            'actual': total_actual,
            'coveragePercent': _coverage_percent(total_actual, total_planned),
            'testsTaken': int(tests_taken),
        })

    visible_ids = scope.visible_engagements(advisor).values('pk')
    tools = {
        # A PUBLISHED plan starting beyond today cannot have been published for
        # elapsed work yet; clamping keeps the counter a measurement, not a
        # forecast — same spirit as the per-day clip above.
        'plansPublished': StudyPlan.objects.filter(
            engagement_id__in=visible_ids,
            status=StudyPlan.Status.PUBLISHED,
            start_date__gte=date_from,
            start_date__lte=min(date_to, today),
        ).count(),
        'assessmentsWritten': WeeklyAssessment.objects.filter(
            engagement_id__in=visible_ids,
            week_start__gte=date_from,
            week_start__lte=date_to,
        ).count(),
        'analysesCreated': StudyExamAnalysis.objects.filter(
            engagement_id__in=visible_ids,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        ).count(),
    }

    return {'students': students, 'tools': tools}


def _iter_days(start: datetime.date, end: datetime.date):
    """Every date of the inclusive window, ascending; empty when inverted."""
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += datetime.timedelta(days=1)


def _display_name(user) -> str:
    """Same label rule as the roster serializer: full name, else username."""
    if user is None:
        return ''
    full = ' '.join(filter(None, [user.first_name, user.last_name])).strip()
    return full or user.username
