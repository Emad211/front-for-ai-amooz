"""The write door for the advisor's weekly call log (restart step 10, گام ۱۰).

``WeeklyCallLog`` is tenancy-bearing, so every mutation goes through this
module after the view has resolved ownership via ``scope.advisor_engagement``.

The list side is a **materialized view of four weeks**: stored rows answer for
their week; absent weeks are filled virtually with ``done=False`` and the
rotating default topic for that engagement-week. A stored topic always wins
over the default — an advisor who edited «موضوع» meant it.

Locked product rule (گام ۱۰): advisor-internal — no student route exists.
"""

from __future__ import annotations

import datetime

from django.db import transaction
from django.utils import timezone

from ..models import WeeklyCallLog
from .calendar import ensure_saturday, week_start_of

# The rotating default topic per engagement-week (week 1 → index 0, and so on,
# cycling mod 4). Order is the paper booklet's order; do not reorder.
DEFAULT_CALL_TOPICS = [
    'ارائۀ برنامۀ هفتگی و هدف‌گذاری',
    'انجام دقیق برنامه و گزارش‌کار',
    'تحلیل آزمون و برنامۀ جبرانی',
    'ارزیابی ماهانه و نقاط قوت/ضعف',
]

# The list always answers with exactly this many weeks, ending at the current
# week (the current Saturday anchor inclusive).
CALL_LOG_WEEKS = 4


class CallLogError(Exception):
    """400-family validation error; ``str(exc)`` is the Persian wire message."""


# Marks «this optional key was not sent» on PUT — same convention as
# ``daily_logs._UNSET``: only absence means keep-the-stored-value.
UNSET = object()


def week_index_for(engagement, week_start) -> int:
    """Which engagement-week ``week_start`` is: ``floor((ws - started_on)/7d)``.

    Clamped at 0 so a pre-engagement anchor cannot go negative, and a NULL
    ``started_on`` (impossible for an ACTIVE row, defended anyway) reads as
    week 0 — the narrowest honest answer, mirroring ``scope.log_date_window``.
    """
    started_on = getattr(engagement, 'started_on', None)
    if started_on is None:
        return 0
    return max(0, (week_start - started_on).days // 7)


def default_topic_for(engagement, week_start) -> str:
    """The rotating default topic for one engagement-week."""
    index = week_index_for(engagement, week_start)
    return DEFAULT_CALL_TOPICS[index % len(DEFAULT_CALL_TOPICS)]


def _item(row) -> dict:
    """One wire-shaped week item off a stored row."""
    return {
        'weekStart': row.week_start,
        'done': row.done,
        'callDate': row.call_date,
        'topic': row.topic,
        'note': row.note,
    }


def list_call_logs(engagement) -> list[dict]:
    """The four most recent weeks ending at the current week, oldest first.

    Stored rows win wholesale; absent weeks materialize virtually with
    ``done=False``, no call date, an empty note, and the default topic for
    their engagement-week index. Ascending order so the card reads like the
    paper checklist: week 1 at the top, the current week last.
    """
    current_week = week_start_of(timezone.localdate())
    weeks = [
        current_week - datetime.timedelta(days=7 * offset)
        for offset in range(CALL_LOG_WEEKS - 1, -1, -1)
    ]
    stored = {
        row.week_start: row
        for row in WeeklyCallLog.objects.filter(
            engagement=engagement, week_start__in=weeks,
        )
    }
    items = []
    for week in weeks:
        row = stored.get(week)
        if row is not None:
            items.append(_item(row))
        else:
            items.append({
                'weekStart': week,
                'done': False,
                'callDate': None,
                'topic': default_topic_for(engagement, week),
                'note': '',
            })
    return items


def upsert_call_log(engagement, week_start, *, done, call_date=UNSET, topic=UNSET, note=UNSET):
    """Create or update the single call-log row for ``(engagement, week_start)``.

    ``done`` is required every time; ``call_date``/``topic``/``note`` left at
    ``UNSET`` keep their stored values (upsert semantics), so ticking «انجام
    شد» never wipes a note the advisor already wrote. On **create**, an absent
    topic seeds the week's default topic rather than an empty string — an
    untouched row should still show what the week was supposed to be about;
    once stored, that topic is the advisor's to edit and it then always wins.
    """
    try:
        ensure_saturday(week_start)
    except ValueError as exc:
        raise CallLogError('تاریخ باید شنبه باشد.') from exc

    with transaction.atomic():
        create_topic = default_topic_for(engagement, week_start) if topic is UNSET else topic
        row, created = WeeklyCallLog.objects.get_or_create(
            engagement=engagement,
            week_start=week_start,
            defaults={
                'done': done,
                'call_date': None if call_date is UNSET else call_date,
                'topic': create_topic,
                'note': '' if note is UNSET else note,
            },
        )
        if not created:
            update_fields = ['done', 'updated_at']
            row.done = done
            if call_date is not UNSET:
                row.call_date = call_date
                update_fields.append('call_date')
            if topic is not UNSET:
                row.topic = topic
                update_fields.append('topic')
            if note is not UNSET:
                row.note = note
                update_fields.append('note')
            row.save(update_fields=update_fields)
    return row
