"""Restart step 8 — the monthly outlook: service door and its endpoints.

``upsert_outlook`` is a **set-replace of the whole month** (entries and
strategies rebuilt together); ``GET|PUT
/api/advisory/students/<pk>/monthly-outlooks/<date:month_start>/`` and ``GET
/api/advisory/me/monthly-outlooks/<date:month_start>/`` are its only routes in.
The service tests hold the semantics invisible from the wire (defaults on first
read, wholesale rebuild including real deletion, boundary dates legal per ق۵,
the pinned Persian validation matrix). The API tests hold the wire contract:
camelCase payload, the quiet student mirror, and the access matrix — owner 200,
stranger advisor 404, wrong role 403, anonymous 401.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    AdvisoryEngagement,
    MonthlyOutlook,
    MonthlyOutlookEntry,
    MonthlyStrategy,
)
from apps.advisory.services import monthly as monthly_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

MONTH = datetime.date(2026, 8, 1)
MONTH_ISO = '2026-08-01'
ADVISOR_URL = f'/api/advisory/students/{{pk}}/monthly-outlooks/{MONTH_ISO}/'
STUDENT_URL = f'/api/advisory/me/monthly-outlooks/{MONTH_ISO}/'

MSG_POSITION_DUP = 'برای هر پوزیشن فقط یک استراتژی مجاز است.'
MSG_POSITION_RANGE = 'پوزیشن استراتژی باید بین ۱ تا ۱۰ باشد.'
MSG_EXECUTOR = 'مجری استراتژی نامعتبر است.'
MSG_ENTRY_DUP = 'برای هر روز فقط یک ردیف بفرستید.'


# ── fixtures ──────────────────────────────────────────────────────────────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _engagement(advisor, student, *, status=Status.ACTIVE, **kwargs):
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': status,
    }
    if status == Status.ACTIVE:
        defaults['started_on'] = MONTH
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _flat_errors(data) -> list[str]:
    """Every leaf message of a DRF error body, however deeply it is nested."""
    if isinstance(data, dict):
        return [msg for value in data.values() for msg in _flat_errors(value)]
    if isinstance(data, list):
        return [msg for value in data for msg in _flat_errors(value)]
    return [str(data)]


def _payload(**overrides):
    """A valid full-month body; overrides replace top-level keys wholesale."""
    payload = {
        'entries': [
            {'date': '2026-08-01', 'event': 'جشن آغاز سال', 'academicNote': 'شروع ترم',
             'tasks': 'هدف‌گذاری ماه'},
            {'date': '2026-08-15', 'event': '', 'academicNote': 'امتحان میان‌ترم',
             'tasks': 'مرور'},
        ],
        'strategies': [
            {'position': 1, 'title': 'مرور روزانه', 'executor': 'STUDENT',
             'body': 'هر شب ۳۰ دقیقه'},
            {'position': 2, 'title': 'تماس هفتگی', 'executor': 'ADVISOR', 'body': ''},
        ],
    }
    payload.update(overrides)
    return payload


def _service_payload(**overrides):
    """A valid snake_case payload for direct ``upsert_outlook`` calls."""
    payload = {
        'entries': [
            {'date': datetime.date(2026, 8, 1), 'event': 'جشن', 'academic_note': '',
             'tasks': ''},
        ],
        'strategies': [
            {'position': 1, 'title': 'مرور', 'executor': 'STUDENT', 'body': ''},
        ],
    }
    payload.update(overrides)
    return payload


# ── service ───────────────────────────────────────────────────────────────────

def test_get_or_init_returns_an_all_empty_outlook_on_first_read():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    outlook = monthly_service.get_or_init_outlook(engagement, MONTH)

    assert outlook.pk is not None
    assert outlook.month_start == MONTH
    assert outlook.entries.count() == 0
    assert outlook.strategies.count() == 0
    # Second read does not duplicate the row.
    assert monthly_service.get_or_init_outlook(engagement, MONTH).pk == outlook.pk


def test_upsert_persists_entries_and_strategies_and_replaces_wholesale():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    outlook = monthly_service.upsert_outlook(
        engagement, MONTH,
        _service_payload(
            entries=[
                {'date': datetime.date(2026, 8, 2), 'event': 'الف',
                 'academic_note': 'ب', 'tasks': 'ج'},
                {'date': datetime.date(2026, 8, 3), 'event': '',
                 'academic_note': '', 'tasks': ''},
            ],
            strategies=[
                {'position': 2, 'title': 'دوم', 'executor': 'ADVISOR', 'body': 'x'},
                {'position': 1, 'title': 'اول', 'executor': 'STUDENT', 'body': ''},
            ],
        ),
    )

    # Entries ordered by date; strategies by position.
    assert [(e.date, e.event) for e in outlook.entries.all()] == [
        (datetime.date(2026, 8, 2), 'الف'),
        (datetime.date(2026, 8, 3), ''),
    ]
    assert [(s.position, s.title, s.executor) for s in outlook.strategies.all()] == [
        (1, 'اول', 'STUDENT'),
        (2, 'دوم', 'ADVISOR'),
    ]

    # Set-replace: the second save leaves exactly what it sent — the dropped
    # entry is really gone from the database, not merely hidden.
    monthly_service.upsert_outlook(
        engagement, MONTH,
        _service_payload(entries=[
            {'date': datetime.date(2026, 8, 9), 'event': 'جدید',
             'academic_note': '', 'tasks': ''},
        ]),
    )
    reloaded = monthly_service.get_or_init_outlook(engagement, MONTH)
    assert [e.date for e in reloaded.entries.all()] == [datetime.date(2026, 8, 9)]
    assert MonthlyOutlookEntry.objects.filter(outlook=outlook).count() == 1


def test_entry_date_outside_the_month_is_allowed_boundary_calendars():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    outlook = monthly_service.upsert_outlook(
        engagement, MONTH,
        _service_payload(entries=[
            {'date': datetime.date(2026, 7, 31), 'event': 'مرز',
             'academic_note': '', 'tasks': ''},
            {'date': datetime.date(2026, 9, 1), 'event': 'مرز دیگر',
             'academic_note': '', 'tasks': ''},
        ]),
    )
    assert outlook.entries.count() == 2


@pytest.mark.parametrize('overrides,message', [
    ({'strategies': [
        {'position': 3, 'title': 'الف', 'executor': 'STUDENT', 'body': ''},
        {'position': 3, 'title': 'ب', 'executor': 'ADVISOR', 'body': ''},
    ]}, MSG_POSITION_DUP),
    ({'strategies': [{'position': 0, 'title': 'الف', 'executor': 'STUDENT'}]},
     MSG_POSITION_RANGE),
    ({'strategies': [{'position': 11, 'title': 'الف', 'executor': 'STUDENT'}]},
     MSG_POSITION_RANGE),
    ({'strategies': [{'position': 2, 'title': 'الف', 'executor': 'TEACHER'}]},
     MSG_EXECUTOR),
    ({'entries': [
        {'date': datetime.date(2026, 8, 5), 'event': '', 'academic_note': ''},
        {'date': datetime.date(2026, 8, 5), 'event': '', 'academic_note': ''},
    ]}, MSG_ENTRY_DUP),
])
def test_upsert_rejects_invalid_payloads_without_writing(overrides, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    with pytest.raises(monthly_service.MonthlyOutlookError) as excinfo:
        monthly_service.upsert_outlook(engagement, MONTH, _service_payload(**overrides))
    assert str(excinfo.value) == message
    # Nothing was written: no outlook row, no children.
    assert MonthlyOutlook.objects.filter(engagement=engagement).count() == 0
    assert MonthlyStrategy.objects.count() == 0


def test_exactly_ten_strategy_slots_are_legal():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    outlook = monthly_service.upsert_outlook(
        engagement, MONTH,
        _service_payload(strategies=[
            {'position': i, 'title': f'اسلات {i}', 'executor': 'STUDENT'}
            for i in range(1, 11)
        ]),
    )
    assert outlook.strategies.count() == 10


# ── API: advisor side ─────────────────────────────────────────────────────────

def test_advisor_get_defaults_to_the_empty_payload_when_never_saved():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).get(ADVISOR_URL.format(pk=engagement.pk))

    assert resp.status_code == 200
    assert resp.data['monthStart'] == MONTH_ISO
    assert resp.data['entries'] == []
    assert resp.data['strategies'] == []


def test_advisor_put_roundtrips_the_full_payload():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    put = _auth(advisor).put(ADVISOR_URL.format(pk=engagement.pk), _payload(), format='json')
    assert put.status_code == 200
    assert put.data['monthStart'] == MONTH_ISO
    assert put.data['entries'][0] == {
        'date': '2026-08-01', 'event': 'جشن آغاز سال',
        'academicNote': 'شروع ترم', 'tasks': 'هدف‌گذاری ماه',
    }
    assert put.data['strategies'][1] == {
        'position': 2, 'title': 'تماس هفتگی', 'executor': 'ADVISOR', 'body': '',
    }

    seen = _auth(advisor).get(ADVISOR_URL.format(pk=engagement.pk))
    assert seen.status_code == 200
    assert seen.data['entries'] == put.data['entries']
    assert seen.data['strategies'] == put.data['strategies']


def test_advisor_put_replaces_the_whole_month():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    first = _auth(advisor).put(
        ADVISOR_URL.format(pk=engagement.pk), _payload(), format='json',
    )
    assert first.status_code == 200

    second = _auth(advisor).put(
        ADVISOR_URL.format(pk=engagement.pk),
        _payload(entries=[], strategies=[]),
        format='json',
    )
    assert second.status_code == 200
    assert second.data['entries'] == []
    assert second.data['strategies'] == []
    outlook = MonthlyOutlook.objects.get(engagement=engagement, month_start=MONTH)
    assert outlook.entries.count() == 0
    assert outlook.strategies.count() == 0


@pytest.mark.parametrize('body,message', [
    (_payload(strategies=[
        {'position': 4, 'title': 'الف', 'executor': 'STUDENT'},
        {'position': 4, 'title': 'ب', 'executor': 'ADVISOR'},
    ]), MSG_POSITION_DUP),
    (_payload(strategies=[{'position': 12, 'title': 'الف', 'executor': 'STUDENT'}]),
     MSG_POSITION_RANGE),
    (_payload(strategies=[{'position': 1, 'title': 'الف', 'executor': 'PARENT'}]),
     MSG_EXECUTOR),
])
def test_advisor_put_rejects_bad_strategies_with_400(body, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).put(ADVISOR_URL.format(pk=engagement.pk), body, format='json')

    assert resp.status_code == 400
    assert message in _flat_errors(resp.data)


# ── API: student mirror ───────────────────────────────────────────────────────

def test_student_get_without_an_engagement_is_a_quiet_200():
    resp = _auth(_student()).get(STUDENT_URL)
    assert resp.status_code == 200
    assert resp.data == {'active': False, 'outlook': None}


def test_student_get_with_an_active_advisor_mirrors_the_month():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    _auth(advisor).put(ADVISOR_URL.format(pk=engagement.pk), _payload(), format='json')

    resp = _auth(student).get(STUDENT_URL)

    assert resp.status_code == 200
    assert resp.data['active'] is True
    assert resp.data['outlook']['strategies'][0]['title'] == 'مرور روزانه'


# ── API: the permission matrix ────────────────────────────────────────────────

@pytest.mark.permission
def test_stranger_advisor_gets_404_not_403():
    owner, stranger = _advisor('adv_owner'), _advisor('adv_stranger')
    student = _student()
    engagement = _engagement(owner, student)

    client = _auth(stranger)
    assert client.get(ADVISOR_URL.format(pk=engagement.pk)).status_code == 404
    assert client.put(
        ADVISOR_URL.format(pk=engagement.pk), _payload(), format='json',
    ).status_code == 404
    assert MonthlyOutlook.objects.count() == 0


@pytest.mark.permission
def test_a_student_is_forbidden_on_the_advisor_route():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    client = _auth(student)
    assert client.get(ADVISOR_URL.format(pk=engagement.pk)).status_code == 403
    assert client.put(
        ADVISOR_URL.format(pk=engagement.pk), _payload(), format='json',
    ).status_code == 403


@pytest.mark.permission
def test_an_advisor_is_forbidden_on_the_student_route():
    client = _auth(_advisor())
    assert client.get(STUDENT_URL).status_code == 403


@pytest.mark.permission
def test_anonymous_is_rejected_on_every_new_route():
    anon = APIClient()
    assert anon.get(STUDENT_URL).status_code == 401
    assert anon.get(ADVISOR_URL.format(pk=1)).status_code == 401
    assert anon.put(ADVISOR_URL.format(pk=1), _payload(), format='json').status_code == 401


def test_an_invalid_calendar_date_in_the_path_is_a_routing_404():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    url = f'/api/advisory/students/{engagement.pk}/monthly-outlooks/2026-02-30/'
    resp = _auth(advisor).get(url)
    assert resp.status_code == 404
