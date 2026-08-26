"""The write door for the monthly outlook + strategies (restart step 8, گام ۸).

``MonthlyOutlook`` / ``MonthlyOutlookEntry`` / ``MonthlyStrategy`` are
tenancy-bearing, so every mutation goes through this one module after the view
has resolved ownership via ``scope.advisor_engagement`` or
``scope.student_active_engagement`` — exactly like ``intake.py`` for the intake
form. The exact Persian validation messages are this module's contract;
serializers stay shape-only so the wire errors never drift from here.

Two public functions:

* ``get_or_init_outlook(engagement, month_start)`` — the read side; a never-
  saved month reads back as the all-empty payload, not a 404.
* ``upsert_outlook(engagement, month_start, payload)`` — a **set-replace of
  the whole month**: entries and strategies rebuilt in one transaction,
  whatever is absent is gone.

ق۵ lives here too, negatively: ``month_start`` is an opaque Gregorian key and
an entry's ``date`` is never checked for membership in that month — boundary
calendars are legal by design.
"""

from __future__ import annotations

from django.db import transaction

from ..models import (
    MAX_MONTHLY_STRATEGIES,
    STRATEGY_EXECUTOR_CHOICES,
    MonthlyOutlook,
    MonthlyOutlookEntry,
    MonthlyStrategy,
)

# Restated next to the door that enforces it, so tests and docs read one number.
POSITION_MIN = 1
POSITION_MAX = MAX_MONTHLY_STRATEGIES

# Pinned wire messages (byte-for-byte contract with the frontend).
MSG_POSITION_DUP = 'برای هر پوزیشن فقط یک استراتژی مجاز است.'
MSG_POSITION_RANGE = 'پوزیشن استراتژی باید بین ۱ تا ۱۰ باشد.'
MSG_EXECUTOR = 'مجری استراتژی نامعتبر است.'

# Defensive beyond the pinned contract: without these a repeated entry date or
# an over-long CharField value would surface as an IntegrityError/DataError 500
# instead of an actionable 400.
MSG_ENTRY_DUP = 'برای هر روز فقط یک ردیف بفرستید.'
MSG_EVENT_LEN = 'مناسبت نمی‌تواند بیش از ۱۲۰ نویسه باشد.'
MSG_NOTE_LEN = 'تقویم تحصیلی نمی‌تواند بیش از ۲۰۰ نویسه باشد.'
MSG_TITLE_LEN = 'عنوان استراتژی نمی‌تواند بیش از ۱۲۰ نویسه باشد.'

_EXECUTOR_CODES = {code for code, _label in STRATEGY_EXECUTOR_CHOICES}


class MonthlyOutlookError(Exception):
    """400-family validation error; ``str(exc)`` is the Persian wire message."""


def _fail(message: str) -> None:
    raise MonthlyOutlookError(message)


def get_or_init_outlook(engagement, month_start) -> MonthlyOutlook:
    """Return the engagement's outlook for this month, creating an empty one if needed.

    Both child relations come prefetched so the serializer renders the whole
    payload without an N+1, each in its model-declared order.
    """
    MonthlyOutlook.objects.get_or_create(engagement=engagement, month_start=month_start)
    return (
        MonthlyOutlook.objects.filter(engagement=engagement, month_start=month_start)
        .prefetch_related('entries', 'strategies')
        .first()
    )


def _clean_entries(entries) -> list[dict]:
    """Validate the day rows of one outlook payload into storable dicts."""
    cleaned = []
    seen_dates: set = set()
    for row in entries:
        date = row.get('date')
        if date is None:
            _fail('تاریخ روز الزامی است.')
        # No month-membership check on purpose (ق۵): boundary calendars win.
        if date in seen_dates:
            _fail(MSG_ENTRY_DUP)
        seen_dates.add(date)

        event = row.get('event') or ''
        if len(event) > 120:
            _fail(MSG_EVENT_LEN)
        academic_note = row.get('academic_note') or ''
        if len(academic_note) > 200:
            _fail(MSG_NOTE_LEN)

        cleaned.append({
            'date': date,
            'event': event,
            'academic_note': academic_note,
            'tasks': row.get('tasks') or '',
        })
    cleaned.sort(key=lambda item: item['date'])
    return cleaned


def _clean_strategies(strategies) -> list[dict]:
    """Validate the strategy slots; range, executor and duplicates are pinned."""
    cleaned = []
    seen_positions: set[int] = set()
    for row in strategies:
        position = row.get('position')
        # ``bool`` is an ``int`` subclass in Python; True/False are not slots.
        if (
            isinstance(position, bool)
            or not isinstance(position, int)
            or not (POSITION_MIN <= position <= POSITION_MAX)
        ):
            _fail(MSG_POSITION_RANGE)

        executor = row.get('executor')
        if executor not in _EXECUTOR_CODES:
            _fail(MSG_EXECUTOR)

        if position in seen_positions:
            _fail(MSG_POSITION_DUP)
        seen_positions.add(position)

        title = row.get('title') or ''
        if len(title) > 120:
            _fail(MSG_TITLE_LEN)

        cleaned.append({
            'position': position,
            'title': title,
            'executor': executor,
            'body': row.get('body') or '',
        })
    cleaned.sort(key=lambda item: item['position'])
    return cleaned


def upsert_outlook(engagement, month_start, payload: dict) -> MonthlyOutlook:
    """Make the stored month equal exactly what was sent, and return it.

    ``payload`` is the validated serializer data with snake_case keys. Entries
    and strategies are hard-deleted and re-created inside one transaction —
    like the intake timetable, they describe the *current* reading of the
    month, so there is no row history worth preserving. An omitted/empty list
    clears that side.
    """
    if not isinstance(payload, dict):
        _fail('بدنهٔ برنامهٔ ماه نامعتبر است.')

    cleaned_entries = _clean_entries(payload.get('entries') or [])
    cleaned_strategies = _clean_strategies(payload.get('strategies') or [])

    with transaction.atomic():
        outlook, _ = MonthlyOutlook.objects.get_or_create(
            engagement=engagement, month_start=month_start,
        )
        outlook.entries.all().delete()
        outlook.strategies.all().delete()
        MonthlyOutlookEntry.objects.bulk_create([
            MonthlyOutlookEntry(outlook=outlook, **row) for row in cleaned_entries
        ])
        MonthlyStrategy.objects.bulk_create([
            MonthlyStrategy(outlook=outlook, **row) for row in cleaned_strategies
        ])

    return get_or_init_outlook(engagement, month_start)
