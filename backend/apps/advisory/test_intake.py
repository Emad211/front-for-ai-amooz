"""Restart step 2 — the intake form: service door and its two endpoints.

``replace_intake`` is a **set-replace of the whole form** (classes included);
``GET|PUT /api/advisory/students/<pk>/intake/`` and ``GET|PUT
/api/advisory/me/intake/`` are its only routes in. The service tests hold the
semantics invisible from the wire (defaults on first read, wholesale class
rebuild, ``updated_by`` authorship) and the pinned Persian validation matrix.
The API tests hold the wire contract: camelCase payload with ``HH:MM`` times,
the quiet student mirror, the 409 without an advisor, and the access matrix —
owner 200, stranger advisor 404, wrong role 403, anonymous 401.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    AdvisoryEngagement,
    AdvisoryIntakeClass,
    AdvisoryIntakeProfile,
)
from apps.advisory.services import intake as intake_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

ADVISOR_URL = '/api/advisory/students/{pk}/intake/'
STUDENT_URL = '/api/advisory/me/intake/'

MSG_CAP = 'حداکثر ۱۰ کلاس می‌توانید ثبت کنید.'
MSG_WEEKDAY = 'روز هفته نامعتبر است.'
MSG_TIME = 'ساعت پایان باید بعد از ساعت شروع باشد.'
MSG_GPA = 'معدل باید بین ۰ تا ۲۰ باشد.'
MSG_MINUTES = 'دقایق مطالعهٔ آزاد نامعتبر است.'
MSG_NO_ADVISOR = 'ابتدا مشاور خود را تأیید کنید.'


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
        from django.utils import timezone
        defaults['started_on'] = timezone.localdate()
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
    """A valid full-form body; overrides replace top-level keys wholesale."""
    payload = {
        'school': 'دبیرستان نمونه',
        'city': 'تهران',
        'lastGpa': 18.5,
        'targetMajor': 'ریاضی فیزیک',
        'targetUniversity': 'شریف',
        'mockExamInstitute': 'قلم‌چی',
        'freeDayMinutes': 240,
        'classes': [
            {'name': 'ریاضی', 'teacher': 'استاد الف', 'weekday': 0,
             'startTime': '16:00', 'endTime': '18:00', 'order': 1},
            {'name': 'فیزیک', 'teacher': '', 'weekday': 2,
             'startTime': None, 'endTime': None, 'order': 2},
        ],
    }
    payload.update(overrides)
    return payload


def _service_payload(**overrides):
    """A valid snake_case payload for direct ``replace_intake`` calls."""
    payload = {
        'school': '', 'city': '', 'last_gpa': None, 'target_major': '',
        'target_university': '', 'mock_exam_institute': '', 'free_day_minutes': None,
        'classes': [],
    }
    payload.update(overrides)
    return payload


# ── service ───────────────────────────────────────────────────────────────────

def test_get_or_init_returns_an_all_empty_profile_on_first_read():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    profile = intake_service.get_or_init_intake(engagement)

    assert profile.pk is not None
    assert profile.school == ''
    assert profile.last_gpa is None
    assert profile.free_day_minutes is None
    assert profile.updated_by is None
    assert profile.classes.count() == 0
    # Second read does not duplicate the row.
    assert intake_service.get_or_init_intake(engagement).pk == profile.pk


def test_replace_intake_persists_scalars_and_rebuilds_classes():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    profile = intake_service.replace_intake(
        engagement,
        _service_payload(
            school='دبیرستان نمونه',
            last_gpa=18.5,
            free_day_minutes=240,
            classes=[
                {'name': 'ریاضی', 'teacher': 'الف', 'weekday': 0, 'order': 1},
                {'name': 'شیمی', 'teacher': '', 'weekday': 6, 'order': 0},
            ],
        ),
        actor=advisor,
    )

    assert profile.last_gpa == 18.5
    assert profile.free_day_minutes == 240
    assert profile.updated_by_id == advisor.pk
    # Ordered by the ``order`` column: شیمی (0) before ریاضی (1).
    rows = list(profile.classes.all())
    assert [(r.name, r.weekday, r.order) for r in rows] == [('شیمی', 6, 0), ('ریاضی', 0, 1)]

    # Set-replace: a second save with one row leaves exactly one row, and
    # absent scalars are cleared — including back to null.
    intake_service.replace_intake(
        engagement,
        _service_payload(classes=[{'name': 'ادبیات', 'weekday': 3}]),
        actor=student,
    )
    reloaded = intake_service.get_or_init_intake(engagement)
    assert reloaded.school == ''
    assert reloaded.last_gpa is None
    assert reloaded.free_day_minutes is None
    assert reloaded.updated_by_id == student.pk   # last writer wins
    assert [r.name for r in reloaded.classes.all()] == ['ادبیات']


@pytest.mark.parametrize('overrides,message', [
    ({'classes': [{'name': f'ک{i}', 'weekday': i % 7} for i in range(11)]}, MSG_CAP),
    ({'classes': [{'name': 'ریاضی', 'weekday': 7}]}, MSG_WEEKDAY),
    ({'classes': [{'name': 'ریاضی', 'weekday': -1}]}, MSG_WEEKDAY),
    ({'classes': [{'name': 'ریاضی', 'weekday': 0,
                   'start_time': '18:00', 'end_time': '16:00'}]}, MSG_TIME),
    ({'last_gpa': 20.01}, MSG_GPA),
    ({'last_gpa': -0.5}, MSG_GPA),
    ({'free_day_minutes': 1441}, MSG_MINUTES),
    ({'free_day_minutes': -1}, MSG_MINUTES),
])
def test_replace_intake_rejects_invalid_payloads_without_writing(overrides, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    with pytest.raises(intake_service.IntakeError) as excinfo:
        intake_service.replace_intake(
            engagement, _service_payload(**overrides), actor=advisor,
        )
    assert str(excinfo.value) == message
    # Nothing was written: no profile, no class rows.
    assert AdvisoryIntakeProfile.objects.filter(engagement=engagement).count() == 0
    assert AdvisoryIntakeClass.objects.count() == 0


def test_exactly_ten_classes_are_legal():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    profile = intake_service.replace_intake(
        engagement,
        _service_payload(
            classes=[{'name': f'کلاس {i}', 'weekday': i % 7} for i in range(10)],
        ),
        actor=advisor,
    )
    assert profile.classes.count() == 10


# ── API: advisor side ─────────────────────────────────────────────────────────

def test_advisor_get_defaults_to_the_empty_payload_when_never_saved():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).get(ADVISOR_URL.format(pk=engagement.pk))

    assert resp.status_code == 200
    assert resp.data == {
        'school': '', 'city': '', 'lastGpa': None, 'targetMajor': '',
        'targetUniversity': '', 'mockExamInstitute': '', 'freeDayMinutes': None,
        'classes': [],
    }


def test_advisor_put_roundtrips_the_full_payload_with_hhmm_times():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    put = _auth(advisor).put(ADVISOR_URL.format(pk=engagement.pk), _payload(), format='json')
    assert put.status_code == 200
    assert put.data['school'] == 'دبیرستان نمونه'
    assert put.data['lastGpa'] == 18.5          # number, not string
    assert put.data['freeDayMinutes'] == 240
    assert put.data['classes'][0] == {
        'name': 'ریاضی', 'teacher': 'استاد الف', 'weekday': 0,
        'startTime': '16:00', 'endTime': '18:00', 'order': 1,
    }
    assert put.data['classes'][1]['startTime'] is None

    seen = _auth(advisor).get(ADVISOR_URL.format(pk=engagement.pk))
    assert seen.status_code == 200
    assert seen.data['classes'] == put.data['classes']


def test_advisor_put_rejects_more_than_ten_classes_with_400():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    body = _payload(classes=[{'name': f'ک{i}', 'weekday': 0} for i in range(11)])

    resp = _auth(advisor).put(ADVISOR_URL.format(pk=engagement.pk), body, format='json')

    assert resp.status_code == 400
    assert MSG_CAP in _flat_errors(resp.data)
    assert AdvisoryIntakeProfile.objects.filter(engagement=engagement).count() == 0


@pytest.mark.parametrize('row,message', [
    ({'name': 'ریاضی', 'weekday': 9}, MSG_WEEKDAY),
    ({'name': 'ریاضی', 'weekday': 1, 'startTime': '18:30', 'endTime': '17:00'}, MSG_TIME),
])
def test_advisor_put_rejects_bad_class_rows(row, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).put(
        ADVISOR_URL.format(pk=engagement.pk), _payload(classes=[row]), format='json',
    )
    assert resp.status_code == 400
    assert message in _flat_errors(resp.data)


@pytest.mark.parametrize('overrides,message', [
    ({'lastGpa': 21}, MSG_GPA),
    ({'lastGpa': -1}, MSG_GPA),
    ({'freeDayMinutes': 2000}, MSG_MINUTES),
])
def test_advisor_put_rejects_out_of_range_scalars(overrides, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).put(
        ADVISOR_URL.format(pk=engagement.pk), _payload(**overrides), format='json',
    )
    assert resp.status_code == 400
    assert message in _flat_errors(resp.data)


# ── API: student mirror ───────────────────────────────────────────────────────

def test_student_get_without_an_engagement_is_a_quiet_200():
    resp = _auth(_student()).get(STUDENT_URL)
    assert resp.status_code == 200
    assert resp.data == {'active': False, 'intake': None}


def test_student_get_and_put_roundtrip_with_an_active_advisor():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    empty = _auth(student).get(STUDENT_URL)
    assert empty.status_code == 200
    assert empty.data['active'] is True
    assert empty.data['intake']['classes'] == []

    put = _auth(student).put(STUDENT_URL, _payload(freeDayMinutes=90), format='json')
    assert put.status_code == 200
    assert put.data['active'] is True
    assert put.data['intake']['freeDayMinutes'] == 90

    profile = AdvisoryIntakeProfile.objects.get(engagement=engagement)
    assert profile.updated_by_id == student.pk   # the student was the last writer


def test_student_put_without_an_engagement_is_409():
    resp = _auth(_student()).put(STUDENT_URL, _payload(), format='json')
    assert resp.status_code == 409
    assert resp.data['detail'] == MSG_NO_ADVISOR


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
    assert AdvisoryIntakeProfile.objects.count() == 0


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
    assert client.put(STUDENT_URL, _payload(), format='json').status_code == 403


@pytest.mark.permission
def test_anonymous_is_rejected_on_every_new_route():
    anon = APIClient()
    assert anon.get(STUDENT_URL).status_code == 401
    assert anon.put(STUDENT_URL, {}, format='json').status_code == 401
    assert anon.get(ADVISOR_URL.format(pk=1)).status_code == 401
