"""Shared calendar math for the week-anchored advisory features (restart plan ق۴).

The Iranian week starts on **Saturday** (شنبه), and every week-oriented advisory
surface — weekly assessments, challenges, monthly outlooks — must agree on where
a week begins. This module is the ONE place that formula is written (ق۴: «این
فرمول یک‌بار در ``services/calendar.py`` نوشته می‌شود و همهٔ مدل‌های هفته‌محور از
همان می‌خوانند — نه از کپی محلی»); nothing here may grow a local copy elsewhere.

Deliberately pure: stdlib ``datetime`` only, no model imports, no tenancy, no
I/O. That is also why it needs no entry in ``test_import_boundaries``' exempt
list — it never touches an advisory model.
"""

from __future__ import annotations

import datetime

# ``datetime.date.weekday()`` is Monday=0 … Sunday=6; Saturday is 5.
SATURDAY_WEEKDAY = 5


def week_start_of(d: datetime.date) -> datetime.date:
    """Return the Saturday that anchors the week containing ``d``.

    The locked formula (ق۴)::

        d - timedelta(days=(d.weekday() + 2) % 7)

    The ``+ 2`` re-bases Python's Monday-first ``weekday()`` onto a Saturday
    anchor: Saturday maps to 0 (the week start itself) and Friday to 6 (the week's
    last day). Examples: a Saturday returns itself; a Sunday steps back one day;
    a Friday steps back six.
    """
    return d - datetime.timedelta(days=(d.weekday() + 2) % 7)


def ensure_saturday(d: datetime.date) -> datetime.date:
    """Validate that ``d`` is a Saturday week anchor and pass it through.

    Shared validator for every endpoint that takes a ``week_start``-shaped date:
    anything that is not a Saturday cannot name a week under the ق۴ convention,
    so it raises ``ValueError`` for the caller to turn into a 400. Returns ``d``
    unchanged on success so it can sit inline in a validation chain.
    """
    if d.weekday() != SATURDAY_WEEKDAY:
        raise ValueError(f'{d.isoformat()} is not a Saturday (weekday={d.weekday()}).')
    return d
