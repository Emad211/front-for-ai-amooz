"""Restart step 9 — the 7-day challenge: service door and its endpoints.

``create_challenge`` / ``update_challenge`` / ``replace_days`` are the write
doors; ``GET|POST /api/advisory/students/<pk>/challenges/``, ``GET|PATCH|DELETE
.../challenges/<id>/``, ``PUT .../challenges/<id>/days/``, ``GET
/api/advisory/me/challenges/`` and ``PUT /api/advisory/me/challenges/<id>/days/``
are their only routes in. The service tests hold the server-computed horizon
(``end_date = start + 6``, client value ignored), the 3-active ceiling, the
one-way status machine, and the pinned Persian validation matrix including the
student's goal/summary-only rule. The API tests hold the wire contract and the
access matrix — owner advisor 2xx, stranger advisor 404, wrong role 403,
anonymous 401.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    AdvisoryEngagement,
    StudyChallenge,
    StudyChallengeDay,
)
from apps.advisory.services import challenges as challenge_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

START = datetime.date(2026, 8, 10)
END = datetime.date(2026, 8, 16)          # start + 6, always server-computed
START_ISO = '2026-08-10'

CHALLENGES_URL = '/api/advisory/students/{pk}/challenges/'
CHALLENGE_DETAIL_URL = '/api/advisory/students/{pk}/challenges/{challenge_id}/'
CHALLENGE_DAYS_URL = '/api/advisory/students/{pk}/challenges/{challenge_id}/days/'
MY_CHALLENGES_URL = '/api/advisory/me/challenges/'
MY_CHALLENGE_DAYS_URL = '/api/advisory/me/challenges/{challenge_id}/days/'

MSG_CAP = 'حداکثر ۳ چالش فعال می‌توانید داشته باشید.'
MSG_DAY_NUMBER = 'شمارهٔ روز باید بین ۱ تا ۷ باشد.'
MSG_STUDENT_FIELDS = 'فقط هدف و خلاصهٔ روز را می‌توانید ثبت کنید.'
MSG_STATUS_LOCKED = 'وضعیت چالش برگشت‌پذیر نیست.'
MSG_CLOSED = 'چالش پایان یافته است.'
MSG_DAY_DUP = 'برای هر روز فقط یک ردیف بفرستید.'


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
        defaults['started_on'] = START
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _challenge(engagement, *, status='ACTIVE', start=START, **kwargs):
    return StudyChallenge.objects.create(
        engagement=engagement,
        title='چالش بیدارباش',
        goal_text='خواب منظم',
        daily_routine='ساعت ۶ صبح',
        execution_note='روزانه',
        observer='مادر',
        problem_target='دیر خوابیدن',
        start_date=start,
        end_date=start + datetime.timedelta(days=6),
        status=status,
        **kwargs,
    )


def _payload(**overrides):
    """A valid create body; `endDate` is sent on purpose to prove it is ignored."""
    payload = {
        'title': 'چالش مطالعۀ صبحگاهی',
        'goalText': 'روزی دو ساعت مطالعۀ متمرکز',
        'dailyRoutine': '۶ تا ۸ صبح',
        'executionNote': 'هر روز بدون استثنا',
        'observer': 'مشاور',
        'problemTarget': 'شروع دیر مطالعه',
        'startDate': START_ISO,
        'endDate': '2027-01-01',
    }
    payload.update(overrides)
    return payload


def _service_payload(**overrides):
    """A valid snake_case payload for direct service calls."""
    payload = {
        'title': 'چالش مطالعۀ صبحگاهی',
        'goal_text': 'روزی دو ساعت',
        'daily_routine': '۶ تا ۸ صبح',
        'execution_note': '',
        'observer': '',
        'problem_target': '',
        'start_date': START,
    }
    payload.update(overrides)
    return payload


def _days_payload(**overrides):
    payload = {
        'days': [
            {'dayNumber': 1, 'goal': 'فصل اول', 'summary': ''},
            {'dayNumber': 2, 'goal': '', 'summary': 'انجام شد'},
            {'dayNumber': 3, 'goal': '', 'summary': ''},
        ],
    }
    payload.update(overrides)
    return payload


# ── service ───────────────────────────────────────────────────────────────────

def test_create_computes_end_date_and_ignores_any_client_value():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    challenge = challenge_service.create_challenge(
        engagement, {**_service_payload(), 'end_date': datetime.date(2027, 1, 1)},
    )

    assert challenge.status == 'ACTIVE'
    assert challenge.start_date == START
    assert challenge.end_date == END


def test_active_cap_is_three_and_terminal_rows_do_not_count():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    for _ in range(3):
        challenge_service.create_challenge(engagement, _service_payload())
    with pytest.raises(challenge_service.ChallengeError) as excinfo:
        challenge_service.create_challenge(engagement, _service_payload())
    assert str(excinfo.value) == MSG_CAP

    # Finishing one frees a slot; a cancelled one does too.
    first = StudyChallenge.objects.filter(engagement=engagement).first()
    challenge_service.update_challenge(first, {'status': 'DONE'})
    freed = challenge_service.create_challenge(engagement, _service_payload())
    assert freed.status == 'ACTIVE'

    other = StudyChallenge.objects.filter(
        engagement=engagement, status='ACTIVE',
    ).exclude(pk=freed.pk).first()
    challenge_service.update_challenge(other, {'status': 'CANCELLED'})
    assert challenge_service.create_challenge(engagement, _service_payload()).pk


@pytest.mark.parametrize('current,next_status', [
    ('ACTIVE', 'DONE'),
    ('ACTIVE', 'CANCELLED'),
])
def test_forward_transitions_apply(current, next_status):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement, status=current)

    updated = challenge_service.update_challenge(challenge, {'status': next_status})
    assert updated.status == next_status


@pytest.mark.parametrize('current,next_status', [
    ('DONE', 'ACTIVE'),
    ('DONE', 'CANCELLED'),
    ('CANCELLED', 'ACTIVE'),
    ('CANCELLED', 'DONE'),
])
def test_every_other_transition_is_a_409(current, next_status):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement, status=current)

    with pytest.raises(challenge_service.ChallengeStateError) as excinfo:
        challenge_service.update_challenge(challenge, {'status': next_status})
    assert str(excinfo.value) == MSG_STATUS_LOCKED


def test_resending_the_current_status_is_a_no_op():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement, status='DONE')

    updated = challenge_service.update_challenge(challenge, {'status': 'DONE'})
    assert updated.status == 'DONE'


def test_update_rejects_an_unknown_status_code_with_400():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    with pytest.raises(challenge_service.ChallengeError):
        challenge_service.update_challenge(challenge, {'status': 'PAUSED'})


def test_patch_changes_only_the_provided_metadata_keys():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    updated = challenge_service.update_challenge(
        challenge, {'title': 'عنوان تازه', 'start_date': datetime.date(2026, 9, 1)},
    )
    assert updated.title == 'عنوان تازه'
    assert updated.goal_text == 'خواب منظم'          # untouched
    # A moved start re-derives the horizon.
    assert updated.end_date == datetime.date(2026, 9, 7)


def test_replace_days_set_replaces_and_orders_by_day_number():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    challenge_service.replace_days(challenge, [
        {'dayNumber': 5, 'goal': 'پنجم', 'summary': ''},
        {'dayNumber': 2, 'goal': 'دوم', 'summary': 'ب'},
        {'dayNumber': 1, 'goal': 'اول', 'summary': 'الف'},
    ])
    numbers = [d.day_number for d in StudyChallengeDay.objects.filter(challenge=challenge)]
    assert numbers == [1, 2, 5]

    challenge_service.replace_days(challenge, [{'dayNumber': 7, 'goal': '', 'summary': ''}])
    numbers = [d.day_number for d in StudyChallengeDay.objects.filter(challenge=challenge)]
    assert numbers == [7]


@pytest.mark.parametrize('rows,message', [
    ([{'dayNumber': 0, 'goal': ''}], MSG_DAY_NUMBER),
    ([{'dayNumber': 8, 'goal': ''}], MSG_DAY_NUMBER),
    ([{'dayNumber': 'two', 'goal': ''}], MSG_DAY_NUMBER),
    ([{'dayNumber': 3, 'goal': ''}, {'dayNumber': 3, 'goal': ''}], MSG_DAY_DUP),
])
def test_replace_days_rejects_bad_rows_without_writing(rows, message):
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    with pytest.raises(challenge_service.ChallengeError) as excinfo:
        challenge_service.replace_days(challenge, rows)
    assert str(excinfo.value) == message
    assert StudyChallengeDay.objects.count() == 0


def test_student_mode_rejects_any_field_beyond_goal_and_summary():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    with pytest.raises(challenge_service.ChallengeError) as excinfo:
        challenge_service.replace_days(
            challenge,
            [{'dayNumber': 1, 'goal': 'هدف', 'summary': '', 'title': 'نفوذ'}],
            student_mode=True,
        )
    assert str(excinfo.value) == MSG_STUDENT_FIELDS
    assert StudyChallengeDay.objects.count() == 0


def test_writing_days_on_a_non_active_challenge_is_a_409_for_both_sides():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    for status in ('DONE', 'CANCELLED'):
        challenge = _challenge(engagement, status=status)
        with pytest.raises(challenge_service.ChallengeStateError) as excinfo:
            challenge_service.replace_days(challenge, [{'dayNumber': 1}])
        assert str(excinfo.value) == MSG_CLOSED
        with pytest.raises(challenge_service.ChallengeStateError):
            challenge_service.replace_days(
                challenge, [{'dayNumber': 1}], student_mode=True,
            )


# ── API: advisor side ─────────────────────────────────────────────────────────

def test_advisor_post_creates_with_server_computed_end_date():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).post(CHALLENGES_URL.format(pk=engagement.pk), _payload(), format='json')

    assert resp.status_code == 201
    assert resp.data['status'] == 'ACTIVE'
    assert resp.data['startDate'] == START_ISO
    assert resp.data['endDate'] == '2026-08-16'      # NOT the client's 2027-01-01
    assert resp.data['days'] == []


def test_advisor_get_lists_newest_first_with_days_prefetched():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    older = _challenge(engagement, start=datetime.date(2026, 7, 1))
    newer = _challenge(engagement)
    StudyChallengeDay.objects.create(challenge=newer, day_number=1, goal='روز اول')

    resp = _auth(advisor).get(CHALLENGES_URL.format(pk=engagement.pk))

    assert resp.status_code == 200
    assert [row['id'] for row in resp.data] == [newer.pk, older.pk]
    assert resp.data[0]['days'] == [{'dayNumber': 1, 'goal': 'روز اول', 'summary': ''}]


def test_advisor_patch_updates_metadata_and_status():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    resp = _auth(advisor).patch(
        CHALLENGE_DETAIL_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        {'title': 'عنوان تازه', 'status': 'DONE'},
        format='json',
    )

    assert resp.status_code == 200
    assert resp.data['title'] == 'عنوان تازه'
    assert resp.data['status'] == 'DONE'


def test_advisor_patch_backwards_transition_is_409_with_pinned_body():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement, status='DONE')

    resp = _auth(advisor).patch(
        CHALLENGE_DETAIL_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        {'status': 'ACTIVE'},
        format='json',
    )

    assert resp.status_code == 409
    assert resp.data == {'detail': MSG_STATUS_LOCKED}


def test_advisor_delete_removes_the_challenge_and_its_days():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)
    StudyChallengeDay.objects.create(challenge=challenge, day_number=1)

    resp = _auth(advisor).delete(
        CHALLENGE_DETAIL_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
    )

    assert resp.status_code == 204
    assert StudyChallenge.objects.count() == 0
    assert StudyChallengeDay.objects.count() == 0


def test_advisor_days_put_set_replaces():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    resp = _auth(advisor).put(
        CHALLENGE_DAYS_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        _days_payload(),
        format='json',
    )

    assert resp.status_code == 200
    assert [d['dayNumber'] for d in resp.data['days']] == [1, 2, 3]

    second = _auth(advisor).put(
        CHALLENGE_DAYS_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        {'days': [{'dayNumber': 7, 'goal': '', 'summary': 'پایان'}]},
        format='json',
    )
    assert [d['dayNumber'] for d in second.data['days']] == [7]
    assert StudyChallengeDay.objects.filter(challenge=challenge).count() == 1


def test_advisor_days_put_on_a_finished_challenge_is_409():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement, status='DONE')

    resp = _auth(advisor).put(
        CHALLENGE_DAYS_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        _days_payload(),
        format='json',
    )

    assert resp.status_code == 409
    assert resp.data == {'detail': MSG_CLOSED}


# ── API: student side ─────────────────────────────────────────────────────────

def test_student_list_without_an_engagement_is_a_quiet_200():
    resp = _auth(_student()).get(MY_CHALLENGES_URL)
    assert resp.status_code == 200
    assert resp.data == {'active': False, 'challenges': []}


def test_student_list_mirrors_the_advisor_challenges():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    _challenge(engagement)

    resp = _auth(student).get(MY_CHALLENGES_URL)

    assert resp.status_code == 200
    assert resp.data['active'] is True
    assert len(resp.data['challenges']) == 1
    assert resp.data['challenges'][0]['title'] == 'چالش بیدارباش'


def test_student_days_put_roundtrip_on_an_active_challenge():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    resp = _auth(student).put(
        MY_CHALLENGE_DAYS_URL.format(challenge_id=challenge.pk),
        {'days': [{'dayNumber': 1, 'goal': 'هدف امروز', 'summary': 'خلاصه'}]},
        format='json',
    )

    assert resp.status_code == 200
    assert resp.data['days'] == [{'dayNumber': 1, 'goal': 'هدف امروز', 'summary': 'خلاصه'}]


def test_student_days_put_rejects_extra_fields_with_pinned_message():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    resp = _auth(student).put(
        MY_CHALLENGE_DAYS_URL.format(challenge_id=challenge.pk),
        {'days': [{'dayNumber': 1, 'goal': '', 'summary': '', 'status': 'DONE'}]},
        format='json',
    )

    assert resp.status_code == 400
    assert resp.data == {'detail': MSG_STUDENT_FIELDS}


def test_student_days_put_rejects_out_of_range_day_numbers():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    resp = _auth(student).put(
        MY_CHALLENGE_DAYS_URL.format(challenge_id=challenge.pk),
        {'days': [{'dayNumber': 9, 'goal': '', 'summary': ''}]},
        format='json',
    )

    assert resp.status_code == 400
    assert resp.data == {'detail': MSG_DAY_NUMBER}


def test_student_days_put_on_a_finished_challenge_is_409():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement, status='DONE')

    resp = _auth(student).put(
        MY_CHALLENGE_DAYS_URL.format(challenge_id=challenge.pk),
        _days_payload(),
        format='json',
    )

    assert resp.status_code == 409
    assert resp.data == {'detail': MSG_CLOSED}


# ── API: the permission matrix ────────────────────────────────────────────────

@pytest.mark.permission
def test_stranger_advisor_gets_404_not_403_on_every_challenge_route():
    owner, stranger = _advisor('adv_owner'), _advisor('adv_stranger')
    student = _student()
    engagement = _engagement(owner, student)
    challenge = _challenge(engagement)

    client = _auth(stranger)
    assert client.get(CHALLENGES_URL.format(pk=engagement.pk)).status_code == 404
    assert client.post(
        CHALLENGES_URL.format(pk=engagement.pk), _payload(), format='json',
    ).status_code == 404
    assert client.get(
        CHALLENGE_DETAIL_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
    ).status_code == 404
    assert client.patch(
        CHALLENGE_DETAIL_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        {'status': 'DONE'}, format='json',
    ).status_code == 404
    assert client.delete(
        CHALLENGE_DETAIL_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
    ).status_code == 404
    assert client.put(
        CHALLENGE_DAYS_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        _days_payload(), format='json',
    ).status_code == 404
    assert StudyChallenge.objects.count() == 1


@pytest.mark.permission
def test_a_student_is_forbidden_on_every_advisor_challenge_route():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    challenge = _challenge(engagement)

    client = _auth(student)
    assert client.get(CHALLENGES_URL.format(pk=engagement.pk)).status_code == 403
    assert client.post(
        CHALLENGES_URL.format(pk=engagement.pk), _payload(), format='json',
    ).status_code == 403
    assert client.patch(
        CHALLENGE_DETAIL_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        {}, format='json',
    ).status_code == 403
    assert client.delete(
        CHALLENGE_DETAIL_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
    ).status_code == 403
    assert client.put(
        CHALLENGE_DAYS_URL.format(pk=engagement.pk, challenge_id=challenge.pk),
        _days_payload(), format='json',
    ).status_code == 403


@pytest.mark.permission
def test_an_advisor_is_forbidden_on_the_student_challenge_routes():
    client = _auth(_advisor())
    assert client.get(MY_CHALLENGES_URL).status_code == 403
    assert client.put(
        MY_CHALLENGE_DAYS_URL.format(challenge_id=1), _days_payload(), format='json',
    ).status_code == 403


@pytest.mark.permission
def test_anonymous_is_rejected_on_every_new_route():
    anon = APIClient()
    assert anon.get(CHALLENGES_URL.format(pk=1)).status_code == 401
    assert anon.post(CHALLENGES_URL.format(pk=1), _payload(), format='json').status_code == 401
    assert anon.get(MY_CHALLENGES_URL).status_code == 401
    assert anon.put(
        MY_CHALLENGE_DAYS_URL.format(challenge_id=1), _days_payload(), format='json',
    ).status_code == 401
