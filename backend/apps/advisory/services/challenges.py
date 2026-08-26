"""The write door for the 7-day study challenge (restart step 9, گام ۹).

``StudyChallenge`` / ``StudyChallengeDay`` are tenancy-bearing, so every
mutation goes through this one module after the view has resolved ownership
via ``scope.advisor_engagement`` or ``scope.student_active_engagement`` —
exactly like ``monthly.py`` for the outlook. The exact Persian validation
messages are this module's contract; serializers stay shape-only so the wire
errors never drift from here.

The rules that live here and nowhere else:

* ``end_date`` is **server-computed** as ``start_date + 6 days`` on every
  create and every start-date edit; any client-sent value is ignored.
* At most ``MAX_ACTIVE_CHALLENGES`` challenges per engagement may sit in
  ACTIVE at once.
* Status moves one way: ACTIVE → DONE or ACTIVE → CANCELLED. Anything else is
  a 409, not a 400 — the request is well-formed but the row's state forbids it.
* Days are a set-replace of rows ``{dayNumber, goal, summary}``. Writing days
  on a non-ACTIVE challenge is a 409 for BOTH sides. In student mode a day row
  may carry nothing beyond goal/summary — the numbering itself stays advisor-
  owned.
"""

from __future__ import annotations

import datetime

from django.db import transaction

from ..models import (
    MAX_ACTIVE_CHALLENGES,
    MAX_CHALLENGE_DAYS,
    CHALLENGE_STATUS_CHOICES,
    StudyChallenge,
    StudyChallengeDay,
)

# Pinned wire messages (byte-for-byte contract with the frontend).
MSG_CAP = 'حداکثر ۳ چالش فعال می‌توانید داشته باشید.'
MSG_DAY_NUMBER = 'شمارهٔ روز باید بین ۱ تا ۷ باشد.'
MSG_STUDENT_FIELDS = 'فقط هدف و خلاصهٔ روز را می‌توانید ثبت کنید.'
MSG_STATUS_LOCKED = 'وضعیت چالش برگشت‌پذیر نیست.'
MSG_CLOSED = 'چالش پایان یافته است.'

# Defensive beyond the pinned contract: without these an over-long CharField
# value or a repeated day number would surface as a DataError/IntegrityError
# 500 instead of an actionable 400.
MSG_TITLE_LEN = 'عنوان چالش نمی‌تواند بیش از ۱۲۰ نویسه باشد.'
MSG_ROUTINE_LEN = 'روتین روزانه نمی‌تواند بیش از ۲۰۰ نویسه باشد.'
MSG_EXECUTION_LEN = 'نوع اجرا نمی‌تواند بیش از ۲۰۰ نویسه باشد.'
MSG_OBSERVER_LEN = 'مجری و ناظر نمی‌تواند بیش از ۱۲۰ نویسه باشد.'
MSG_GOAL_LEN = 'هدف روز نمی‌تواند بیش از ۲۰۰ نویسه باشد.'
MSG_DAY_DUP = 'برای هر روز فقط یک ردیف بفرستید.'
MSG_STATUS_INVALID = 'وضعیت چالش نامعتبر است.'

_STATUS_CODES = {code for code, _label in CHALLENGE_STATUS_CHOICES}
_TERMINAL_STATUSES = {'DONE', 'CANCELLED'}

# Wire keys a student may send inside one day row. Everything else is rejected
# with the pinned message instead of being silently dropped.
_STUDENT_DAY_KEYS = {'dayNumber', 'goal', 'summary'}


class ChallengeError(Exception):
    """400-family validation error; ``str(exc)`` is the Persian wire message."""


class ChallengeStateError(ChallengeError):
    """409-family state conflict; ``str(exc)`` is the Persian wire message."""


def _fail(message: str) -> None:
    raise ChallengeError(message)


def _conflict(message: str) -> None:
    raise ChallengeStateError(message)


def list_challenges(engagement):
    """Every challenge of this engagement, newest first, days prefetched.

    Takes a resolved engagement (the caller proved ownership via
    ``scope.advisor_engagement`` or ``student_active_engagement``), so it does
    no scoping of its own.
    """
    return (
        StudyChallenge.objects.filter(engagement=engagement)
        .prefetch_related('days')
        .order_by('-start_date', '-id')
    )


def get_challenge(engagement, challenge_id) -> StudyChallenge | None:
    """One challenge of *this* engagement, or ``None`` — never another's."""
    return (
        StudyChallenge.objects.filter(engagement=engagement, pk=challenge_id)
        .prefetch_related('days')
        .first()
    )


def _clean_metadata(payload: dict) -> dict:
    """Validate the writable scalar fields of a create/PATCH payload.

    Only keys present in ``payload`` are touched — that is what makes PATCH
    partial. ``start_date`` is special: when it changes, ``end_date`` must be
    recomputed with it so the seven-day shape cannot drift.
    """
    cleaned: dict = {}

    if 'title' in payload:
        title = payload['title'] or ''
        if len(title) > 120:
            _fail(MSG_TITLE_LEN)
        cleaned['title'] = title

    if 'goal_text' in payload:
        cleaned['goal_text'] = payload['goal_text'] or ''
    if 'daily_routine' in payload:
        routine = payload['daily_routine'] or ''
        if len(routine) > 200:
            _fail(MSG_ROUTINE_LEN)
        cleaned['daily_routine'] = routine
    if 'execution_note' in payload:
        note = payload['execution_note'] or ''
        if len(note) > 200:
            _fail(MSG_EXECUTION_LEN)
        cleaned['execution_note'] = note
    if 'observer' in payload:
        observer = payload['observer'] or ''
        if len(observer) > 120:
            _fail(MSG_OBSERVER_LEN)
        cleaned['observer'] = observer
    if 'problem_target' in payload:
        cleaned['problem_target'] = payload['problem_target'] or ''

    if 'start_date' in payload:
        # Only reachable as an explicit null on PATCH; POST requires the field
        # at the serializer level.
        if payload['start_date'] is None:
            _fail('تاریخ شروع الزامی است.')
        cleaned['start_date'] = payload['start_date']
        cleaned['end_date'] = payload['start_date'] + datetime.timedelta(days=6)

    return cleaned


def create_challenge(engagement, payload: dict) -> StudyChallenge:
    """Create one ACTIVE challenge under the 3-active ceiling.

    ``end_date`` is derived from ``start_date`` here — any client value under
    that key never reaches this function's output by construction.
    """
    cleaned = _clean_metadata(payload)
    if engagement.challenges.filter(status='ACTIVE').count() >= MAX_ACTIVE_CHALLENGES:
        _fail(MSG_CAP)
    return StudyChallenge.objects.create(
        engagement=engagement, status='ACTIVE', **cleaned,
    )


def update_challenge(challenge: StudyChallenge, payload: dict) -> StudyChallenge:
    """Apply only the provided keys of a PATCH body onto a stored row.

    Metadata keys overwrite when present. ``status`` follows the one-way
    machine: re-sending the current status is a harmless no-op, ACTIVE →
    DONE/CANCELLED applies, and every other move is a 409 — including edits to
    a challenge that has already finished.
    """
    new_status = payload.get('status')
    if new_status is not None:
        if new_status not in _STATUS_CODES:
            _fail(MSG_STATUS_INVALID)
        if (
            new_status != challenge.status
            and (challenge.status != 'ACTIVE' or new_status not in _TERMINAL_STATUSES)
        ):
            _conflict(MSG_STATUS_LOCKED)
        if new_status != challenge.status:
            challenge.status = new_status

    cleaned = _clean_metadata({
        key: value for key, value in payload.items() if key != 'status'
    })
    for field, value in cleaned.items():
        setattr(challenge, field, value)
    challenge.save()
    return get_challenge(challenge.engagement, challenge.pk)


def delete_challenge(challenge: StudyChallenge) -> None:
    """Remove one challenge outright; its days go with it (CASCADE)."""
    challenge.delete()


def _clean_days(rows, *, student_mode: bool) -> list[dict]:
    """Validate one days payload into storable dicts, ordered by day number."""
    cleaned = []
    seen_numbers: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            _fail(MSG_DAY_NUMBER)

        if student_mode and (set(row) - _STUDENT_DAY_KEYS):
            _fail(MSG_STUDENT_FIELDS)

        number = row.get('dayNumber')
        # ``bool`` is an ``int`` subclass in Python; True/False are not days.
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or not (1 <= number <= MAX_CHALLENGE_DAYS)
        ):
            _fail(MSG_DAY_NUMBER)
        if number in seen_numbers:
            _fail(MSG_DAY_DUP)
        seen_numbers.add(number)

        goal = row.get('goal') or ''
        if len(goal) > 200:
            _fail(MSG_GOAL_LEN)

        cleaned.append({
            'day_number': number,
            'goal': goal,
            'summary': row.get('summary') or '',
        })
    cleaned.sort(key=lambda item: item['day_number'])
    return cleaned


def replace_days(
    challenge: StudyChallenge,
    rows,
    *,
    student_mode: bool = False,
) -> StudyChallenge:
    """Make the stored days equal exactly what was sent, and return the challenge.

    Both sides share one shape (``{dayNumber, goal, summary}``); the difference
    is authority. A non-ACTIVE challenge accepts no writes from either side —
    its week is over, and rewriting history would make DONE a lie. Student mode
    additionally rejects any key beyond goal/summary per row.
    """
    if challenge.status != 'ACTIVE':
        _conflict(MSG_CLOSED)

    cleaned_days = _clean_days(rows or [], student_mode=student_mode)

    with transaction.atomic():
        StudyChallengeDay.objects.filter(challenge=challenge).delete()
        StudyChallengeDay.objects.bulk_create([
            StudyChallengeDay(challenge=challenge, **row) for row in cleaned_days
        ])

    return get_challenge(challenge.engagement, challenge.pk)
