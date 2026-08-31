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

from django.utils import timezone

from ..models import (
    DailyLog,
    MistakeEntry,
    StudyExamScore,
    StudyPlan,
    TopicProgress,
)
from .study_plans import plan_adherence_percent

BALANCE_WINDOW_DAYS = 30
BACKLOG_ROWS_LIMIT = 20


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
    """One pass over the window's logs: the per-subject minute totals and a
    ``(date, subject) → minutes`` index the backlog compare runs against."""
    rows = DailyLog.objects.filter(engagement=engagement).filter(
        log_date__gte=window_start, log_date__lte=today,
    ).values(
        'log_date',
        'items__student_subject__subject__name',
        'items__actual_minutes',
    )

    balance_map: dict[str, int] = {}
    actual_by_key: dict[tuple[datetime.date, str], int] = {}
    log_dates: set[datetime.date] = set()
    for row in rows:
        log_dates.add(row['log_date'])
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
    return subject_balance, actual_by_key, log_dates


def compute_analytics(engagement) -> dict:
    today = timezone.localdate()
    window_start = today - datetime.timedelta(days=BALANCE_WINDOW_DAYS)

    subject_balance, actual_by_key, log_dates = _balance_and_index(
        engagement, window_start, today,
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
    backlog_rows = []
    published = StudyPlan.objects.filter(
        engagement=engagement, status=StudyPlan.Status.PUBLISHED,
    ).prefetch_related('items__student_subject__subject')
    for plan in published:
        for item in plan.items.all():
            item_date = plan.start_date + datetime.timedelta(days=item.day_offset)
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
    }
