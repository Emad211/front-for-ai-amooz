"""Unit B — ``services/calendar.py``: the locked Saturday week anchor (ق۴).

Pure date math, zero tokens, zero DB. The formula is a cross-feature contract
(weekly assessments, challenges and monthly outlooks will all read it), so both
functions are pinned here: ``week_start_of`` against hand-computed anchors for
every weekday, and ``ensure_saturday``'s pass-through/refuse split.
"""

from __future__ import annotations

import datetime

import pytest

from apps.advisory.services.calendar import ensure_saturday, week_start_of

pytestmark = pytest.mark.unit


def _d(iso: str) -> datetime.date:
    return datetime.date.fromisoformat(iso)


@pytest.mark.parametrize('day,expected', [
    # 2026-08-22 is a Saturday: the week starts on itself.
    ('2026-08-22', '2026-08-22'),
    # Sunday steps back one day…
    ('2026-08-23', '2026-08-22'),
    # …Wednesday three…
    ('2026-08-26', '2026-08-22'),
    # …and Friday six.
    ('2026-08-28', '2026-08-22'),
    # The next Saturday opens a fresh week.
    ('2026-08-29', '2026-08-29'),
])
def test_week_start_of_anchors_every_weekday_to_its_saturday(day, expected):
    assert week_start_of(_d(day)) == _d(expected)


def test_ensure_saturday_passes_a_saturday_through():
    saturday = _d('2026-08-22')
    assert ensure_saturday(saturday) == saturday


@pytest.mark.parametrize('iso', ['2026-08-23', '2026-08-28', '2026-08-24'])
def test_ensure_saturday_refuses_every_non_saturday(iso):
    with pytest.raises(ValueError):
        ensure_saturday(_d(iso))
