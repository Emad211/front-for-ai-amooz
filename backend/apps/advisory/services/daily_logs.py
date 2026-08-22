"""The write door for a student's daily study log (S5).

``DailyLog`` and ``DailyLogItem`` are tenancy-bearing, so — exactly like
``invites.py`` for the engagement and ``student_subjects.py`` for the selection —
every mutation goes through this one module, never through a view. ``scope.py``
reads across tenancy; this writes into it.

There is one public function, ``save_day``, and it is a **set-replace of a whole
day**: the caller sends everything about one date (mood, note, and the complete
list of subject/minute pairs) and the stored day is made to match. The client is a
single form with one submit button, so a partial-update API would only invite the
question "what happens to the row I left out?" — here the answer is always "it is
what you sent".

D3 in one sentence: **the student writes, the advisor only reads.** That is why the
signature takes a ``student`` and re-checks it against the engagement instead of
taking a generic actor — there is no code path by which an advisor writes a log, so
there is no path to get an advisor permission check wrong in.
"""

from __future__ import annotations

import datetime

from django.db import transaction

from ..models import (
    MAX_LOG_MINUTES_PER_DAY,
    DailyLog,
    DailyLogItem,
)
from . import scope


class DailyLogError(Exception):
    """Base class so a view can catch the whole family in one clause."""


class NotTheLogOwner(DailyLogError):
    """403 — the caller is not the student this engagement belongs to.

    Unreachable through the API: the only view calls in with an engagement it got
    from ``scope.student_active_engagement(request.user)``, so the two can't
    disagree. It exists because D3 ("an advisor may not edit a student's log") is a
    product rule, and a rule that is only upheld by *the absence of an endpoint* is
    one refactor away from being untrue. Here it is upheld by the store.
    """

    def __init__(self):
        super().__init__('ثبت گزارش روزانه فقط توسط خودِ دانش‌آموز ممکن است.')


class LogDateOutOfWindow(DailyLogError):
    """400 — the date is in the future, or before the engagement started (C3).

    Both halves come from ``scope.log_date_window`` and both matter: a future date
    would turn the S8 commitment metric from a measurement into a forecast, and a
    date before ``started_on`` would hand the advisor a window into the student's
    life from before they were hired.
    """

    def __init__(self, log_date, earliest, latest):
        self.log_date = log_date
        self.earliest = earliest
        self.latest = latest
        super().__init__('برای این تاریخ نمی‌توانید گزارش ثبت کنید.')


class SubjectNotInSelection(DailyLogError):
    """400 — a subject that is not currently on this student's list.

    Folds together the cases the caller must not be able to tell apart: the id does
    not exist, it exists but the advisor never picked it, or the advisor picked it
    once and has since dropped it. All three are "not a subject you may report
    minutes for today", and separating them would leak the shape of other students'
    selections.
    """

    def __init__(self, subject_ids):
        self.subject_ids = list(subject_ids)
        super().__init__('این درس در فهرست درس‌های شما نیست.')


class DailyTotalTooLarge(DailyLogError):
    """400 — the minutes across all subjects exceed one real day.

    The per-item ceiling is a DB check; this one cannot be, because a
    ``CheckConstraint`` cannot sum sibling rows. Without it, 60 selected subjects at
    the 960-minute per-item cap would store a 57,600-minute day and the S8 ratio
    would read 4000%.
    """

    def __init__(self, total):
        self.total = total
        self.maximum = MAX_LOG_MINUTES_PER_DAY
        super().__init__(
            f'مجموع دقیقه‌های یک روز نمی‌تواند بیشتر از {MAX_LOG_MINUTES_PER_DAY} باشد.'
        )


def save_day(engagement, log_date, *, mood, note, items, student) -> DailyLog:
    """Make the stored day equal exactly what was sent, and return it.

    ``items`` is an iterable of ``{'subject_id': int, 'minutes': int}`` — keyed on
    the **catalog** ``Subject`` id, not on the ``StudentSubject`` row id. That is the
    wire vocabulary the S4 serializer already publishes (``subjectId``), and the
    ``(engagement, subject)`` unique constraint makes the translation to the
    tenancy-bearing row unambiguous, so a private row id never has to leave the
    server.

    Order of operations, and none of it is incidental:

    1. **owner**, then **date**, then **subjects**, then **total** — all before any
       write. A request that names one unselected subject changes nothing at all;
       the transaction never opens.
    2. Items with ``minutes == 0`` are dropped, not stored. Zero is how the form says
       «I did not study this», and a stored zero-minute row would then have to be
       filtered out of every later average. (It would also fail the DB check.)
    3. The ``DailyLog`` row is created or updated, never deleted — a day with zero
       items means «I reported, and it was nothing», which the S8 metric must be able
       to tell apart from an unreported day.
    4. Items are **upserted** (``update_or_create``) rather than wiped and re-made,
       so ``created_at`` survives a student fixing a typo.
    5. Items no longer present are **hard-deleted**. This is the deliberate opposite
       of how ``student_subjects.py`` retires a selection (deactivate, never delete):
       there, the advisor is changing a plan that the student's own history hangs
       off; here, the student is correcting their own report of their own day, and
       there is nothing to preserve.

    ``mood`` and ``note`` are always overwritten, including back to ``None``/``''`` —
    the body is the whole day, so an omitted mood means «cleared», not «unchanged».
    """
    if engagement.student_id != getattr(student, 'pk', None):
        raise NotTheLogOwner()

    earliest, latest = scope.log_date_window(engagement)
    if not isinstance(log_date, datetime.date) or not (earliest <= log_date <= latest):
        raise LogDateOutOfWindow(log_date, earliest, latest)

    wanted: dict[int, int] = {}
    for item in items:
        minutes = int(item['minutes'])
        if minutes <= 0:
            continue
        wanted[int(item['subject_id'])] = minutes

    total = sum(wanted.values())
    if total > MAX_LOG_MINUTES_PER_DAY:
        raise DailyTotalTooLarge(total)

    # ``scope.student_subjects`` is active-only, which is exactly the write rule: a
    # subject the advisor has dropped can keep its *existing* minutes (see
    # ``DailyLogItem``'s docstring) but cannot receive new ones.
    row_by_subject = {
        row.subject_id: row.pk
        for row in scope.student_subjects(engagement).filter(subject_id__in=wanted)
    }
    missing = [sid for sid in wanted if sid not in row_by_subject]
    if missing:
        raise SubjectNotInSelection(missing)

    with transaction.atomic():
        log, created = DailyLog.objects.get_or_create(
            engagement=engagement,
            log_date=log_date,
            defaults={'mood': mood, 'note': note or ''},
        )
        if not created:
            log.mood = mood
            log.note = note or ''
            log.save(update_fields=['mood', 'note', 'updated_at'])

        keep_row_ids = []
        for subject_id, minutes in wanted.items():
            row_id = row_by_subject[subject_id]
            keep_row_ids.append(row_id)
            DailyLogItem.objects.update_or_create(
                log=log,
                student_subject_id=row_id,
                defaults={'actual_minutes': minutes},
            )
        DailyLogItem.objects.filter(log=log).exclude(
            student_subject_id__in=keep_row_ids,
        ).delete()

    # Re-read through scope so the caller gets the prefetched, canonically ordered
    # shape the GET path returns — one code path builds the response, not two.
    return scope.student_day_log(engagement, log_date)
