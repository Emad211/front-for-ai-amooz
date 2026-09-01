"""The student's read-only analytics bundle (research wave 2026-08-31).

One endpoint's worth of numbers the Iranian consultants' dashboards publish
and ours did not: the daily-report streak, per-subject study balance, the
exam-score trend, the current plan's execution percent, the uncompensated
backlog and the due-review queue. Pure reads over the existing tenancy tables
— no writes here, no LLM, no new permissions.

All computations are anchored to ``timezone.localdate()`` so a request near
midnight answers one coherent day, and every window is bounded (30 days of
history) so the payload cannot grow with the engagement's age.
"""

from __future__ import annotations

import datetime
import statistics

from django.utils import timezone

from ..models import (
    DailyLog,
    MistakeEntry,
    StudyExamScore,
    StudyPlan,
    TopicProgress,
    WeeklyCallLog,
)
from .study_plans import plan_adherence_percent

BALANCE_WINDOW_DAYS = 30
BACKLOG_ROWS_LIMIT = 20
# Wave 6b (2026-08-31) evidence windows, all inclusive of today:
#   14 days = [today-13, today] (testDensity, planCalibration)
#   7 days  = [today-6,  today] (reportRate7d)
#   30 days = [today-29, today] (mistakeResolutionDays)
TEST_DENSITY_WINDOW_DAYS = 14
CALIBRATION_WINDOW_DAYS = 14
REPORT_RATE_WINDOW_DAYS = 7
MISTAKE_RESOLUTION_WINDOW_DAYS = 30


def _streak(log_dates: set[datetime.date], today: datetime.date) -> int:
    """Consecutive reported days ending today — or yesterday, so a student who
    has not reported yet today does not read as broken at noon."""
    anchor = today if today in log_dates else today - datetime.timedelta(days=1)
    streak = 0
    cursor = anchor
    while cursor in log_dates:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    return streak


def _balance_and_index(engagement, window_start, today):
    """One pass over the window's logs: the per-subject minute totals, a
    ``(date, subject) → minutes`` index the backlog compare runs against, and
    the per-day ``tests_taken`` the test-density metric divides.

    ``log_date`` is unique per engagement, so the per-item join rows a day
    produces all repeat the same ``tests_taken`` — assignment (never ``+=``)
    is what keeps the density sum honest on multi-subject days.
    """
    rows = DailyLog.objects.filter(engagement=engagement).filter(
        log_date__gte=window_start, log_date__lte=today,
    ).values(
        'log_date',
        'items__student_subject__subject__name',
        'items__actual_minutes',
        'tests_taken',
    )

    balance_map: dict[str, int] = {}
    actual_by_key: dict[tuple[datetime.date, str], int] = {}
    tests_by_date: dict[datetime.date, int] = {}
    log_dates: set[datetime.date] = set()
    for row in rows:
        log_dates.add(row['log_date'])
        tests_by_date[row['log_date']] = row['tests_taken'] or 0
        name = row['items__student_subject__subject__name']
        minutes = row['items__actual_minutes'] or 0
        if name is None:
            continue
        balance_map[name] = balance_map.get(name, 0) + minutes
        key = (row['log_date'], name)
        actual_by_key[key] = actual_by_key.get(key, 0) + minutes

    subject_balance = sorted(
        ({'name': name, 'minutes': minutes} for name, minutes in balance_map.items()),
        key=lambda entry: entry['minutes'],
        reverse=True,
    )
    return subject_balance, actual_by_key, log_dates, tests_by_date


def compute_analytics(engagement) -> dict:
    today = timezone.localdate()
    window_start = today - datetime.timedelta(days=BALANCE_WINDOW_DAYS)

    subject_balance, actual_by_key, log_dates, tests_by_date = _balance_and_index(
        engagement, window_start, today,
    )

    # ── Wave 6b (2026-08-31): the five hidden evidence numbers ────────────────
    # All computed from the same pass above plus at most two bounded queries;
    # every one is None when its window holds no evidence (quiet-null).

    # testDensity: tests per *logged* day over the last 14 days — retrieval
    # practice is the strongest leading indicator we have (Dunlosky 2013).
    density_start = today - datetime.timedelta(days=TEST_DENSITY_WINDOW_DAYS - 1)
    density_dates = {d for d in log_dates if d >= density_start}
    test_density = None
    if density_dates:
        tests_total = sum(tests_by_date.get(d, 0) for d in density_dates)
        test_density = round(tests_total / len(density_dates), 1)

    # reportRate7d: the streak's non-shaming twin — a rate survives a single
    # miss. None until the week has its first report, then count/7 in percent.
    rate_start = today - datetime.timedelta(days=REPORT_RATE_WINDOW_DAYS - 1)
    week_dates = {d for d in log_dates if d >= rate_start}
    report_rate_7d = (
        round(len(week_dates) / REPORT_RATE_WINDOW_DAYS * 100) if week_dates else None
    )

    # mistakeResolutionDays: median created→resolved latency of mistakes
    # resolved in the last 30 days — how fast the notebook's loop actually
    # closes. Un-resolved rows never carry a resolved_at to measure.
    resolution_start = today - datetime.timedelta(days=MISTAKE_RESOLUTION_WINDOW_DAYS - 1)
    resolution_rows = MistakeEntry.objects.filter(
        engagement=engagement,
        is_resolved=True,
        resolved_at__isnull=False,
        resolved_at__date__gte=resolution_start,
    ).values_list('created_at', 'resolved_at')
    latencies = [
        (resolved_at - created_at).days
        for created_at, resolved_at in resolution_rows
    ]
    mistake_resolution_days = statistics.median(latencies) if latencies else None

    # advisorDosageDays: days since the advisor's last completed call — the
    # dose-response number the advisor's own panel cites.
    last_call_date = WeeklyCallLog.objects.filter(
        engagement=engagement, done=True, call_date__lte=today,
    ).order_by('-call_date').values_list('call_date', flat=True).first()
    advisor_dosage_days = (
        (today - last_call_date).days if last_call_date is not None else None
    )

    # examTrend: every stored score, oldest first — the chart the advisor's
    # «نمودار پیشرفت تحصیلی» has shown for years.
    exam_trend = list(
        StudyExamScore.objects.filter(engagement=engagement)
        .order_by('exam_date', 'id')
        .values('id', 'exam_date', 'score_percent', 'tara', 'title')
    )

    # planExecution: the PUBLISHED plan covering today with the same adherence
    # number the plan payload already publishes — one definition, two surfaces.
    current_plan = (
        StudyPlan.objects.filter(
            engagement=engagement,
            status=StudyPlan.Status.PUBLISHED,
            start_date__lte=today,
        )
        .order_by('-start_date')
        .first()
    )
    plan_execution = None
    if current_plan is not None and today <= current_plan.end_date:
        plan_execution = {
            'planId': current_plan.pk,
            'startDate': current_plan.start_date,
            'endDate': current_plan.end_date,
            'percent': plan_adherence_percent(current_plan, today),
        }

    # backlog: PUBLISHED plan rows before today whose logged minutes fell
    # short — the «جبران‌نشده» list the restart plan promised to at least show.
    # The same walk feeds planCalibration's per-day planned totals.
    calibration_start = today - datetime.timedelta(days=CALIBRATION_WINDOW_DAYS - 1)
    planned_by_date: dict[datetime.date, int] = {}
    backlog_rows = []
    published = StudyPlan.objects.filter(
        engagement=engagement, status=StudyPlan.Status.PUBLISHED,
    ).prefetch_related('items__student_subject__subject')
    for plan in published:
        for item in plan.items.all():
            item_date = plan.start_date + datetime.timedelta(days=item.day_offset)
            if calibration_start <= item_date <= today:
                planned_by_date[item_date] = (
                    planned_by_date.get(item_date, 0) + item.planned_minutes
                )
            if item_date >= today:
                continue
            subject_name = item.student_subject.subject.name
            actual = actual_by_key.get((item_date, subject_name), 0)
            if actual < item.planned_minutes:
                backlog_rows.append({
                    'date': item_date,
                    'subject': subject_name,
                    'topic': item.topic,
                    'planned': item.planned_minutes,
                    'actual': actual,
                })
    backlog_rows.sort(key=lambda row: row['date'], reverse=True)

    # planCalibration: planned ÷ actual over the last 14 days, restricted to
    # days that carry BOTH a published plan item and a logged item — ratio > 1
    # is under-planning, < 1 over-planning (Gollwitzer: specificity is the
    # lever). Overlapping days always log > 0 minutes (the item constraint),
    # so the division cannot see a zero denominator.
    actual_by_date: dict[datetime.date, int] = {}
    for (log_date, _name), minutes in actual_by_key.items():
        actual_by_date[log_date] = actual_by_date.get(log_date, 0) + minutes
    overlapping = [d for d in planned_by_date if d in actual_by_date]
    plan_calibration = None
    if overlapping:
        planned_total = sum(planned_by_date[d] for d in overlapping)
        actual_total = sum(actual_by_date[d] for d in overlapping)
        plan_calibration = round(planned_total / actual_total, 2)

    review_due = list(
        TopicProgress.objects.filter(
            engagement=engagement,
            status=TopicProgress.Status.NEEDS_REVIEW,
            next_review_at__lte=today,
        )
        .select_related('student_subject__subject')
        .values('id', 'topic', 'next_review_at', 'student_subject__subject__name')
    )

    open_mistakes_qs = MistakeEntry.objects.filter(
        engagement=engagement, is_resolved=False,
    )
    mistakes_by_type = {
        code: open_mistakes_qs.filter(error_type=code).count()
        for code, _label in MistakeEntry.ErrorType.choices
    }

    return {
        'today': today,
        'streak': _streak(log_dates, today),
        'loggedToday': today in log_dates,
        'subjectBalance': subject_balance,
        'examTrend': exam_trend,
        'planExecution': plan_execution,
        'backlog': backlog_rows[:BACKLOG_ROWS_LIMIT],
        'backlogTotal': len(backlog_rows),
        'reviewDue': review_due,
        'openMistakes': open_mistakes_qs.count(),
        'mistakesByType': mistakes_by_type,
        'testDensity': test_density,
        'mistakeResolutionDays': mistake_resolution_days,
        'planCalibration': plan_calibration,
        'reportRate7d': report_rate_7d,
        'advisorDosageDays': advisor_dosage_days,
    }
