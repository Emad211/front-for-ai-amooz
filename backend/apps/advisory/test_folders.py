"""Risman step 1 — student folders and the searchable roster: door + endpoints.

Phase A covers ``services.folders`` directly: name validation with the pinned
Persian messages, per-advisor uniqueness, and the transactional delete that
nulls ``engagement.folder``. Phase B is the API matrix — owner 200/201/200,
stranger advisor 404, wrong role 403, anonymous 401 — plus the roster
extension: ``?q=`` across Persian names and phone fragments, ``?folder=``,
the ``folders`` array and per-row ``folderId``.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    AdvisoryEngagement,
    AdvisoryStudentFolder,
)
from apps.advisory.services import folders as folder_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

FOLDERS_URL = '/api/advisory/folders/'
FOLDER_DETAIL_URL = '/api/advisory/folders/{folder_id}/'
STUDENTS_URL = '/api/advisory/students/'
ASSIGN_URL = '/api/advisory/students/{pk}/folder/'

MSG_NAME_REQUIRED = 'نام پوشه الزامی است.'
MSG_NAME_TOO_LONG = 'نام پوشه حداکثر ۶۴ نویسه است.'
MSG_DUPLICATE = 'پوشه‌ای با این نام دارید.'

D1 = datetime.date(2026, 8, 10)


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
        defaults['started_on'] = D1
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


# ── phase A · service ─────────────────────────────────────────────────────────

def test_create_folder_trims_and_persists():
    advisor = _advisor()

    folder = folder_service.create_folder(advisor, '  کنکوری‌ها  ')

    assert folder.pk is not None
    assert folder.name == 'کنکوری‌ها'
    assert folder.advisor_id == advisor.pk


@pytest.mark.parametrize('raw,message', [
    ('', MSG_NAME_REQUIRED),
    ('   ', MSG_NAME_REQUIRED),
    (None, MSG_NAME_REQUIRED),
    ('x' * 65, MSG_NAME_TOO_LONG),
])
def test_create_folder_rejects_bad_names_without_writing(raw, message):
    advisor = _advisor()

    with pytest.raises(folder_service.FolderError) as excinfo:
        folder_service.create_folder(advisor, raw)

    assert str(excinfo.value) == message
    assert AdvisoryStudentFolder.objects.count() == 0


def test_duplicate_name_is_rejected_per_advisor():
    advisor, other_advisor = _advisor(), _advisor('adv2')
    folder_service.create_folder(advisor, 'کنکوری‌ها')

    with pytest.raises(folder_service.FolderError) as excinfo:
        folder_service.create_folder(advisor, 'کنکوری‌ها')
    assert str(excinfo.value) == MSG_DUPLICATE

    # The same name under a DIFFERENT advisor is fine — folders are private.
    other = folder_service.create_folder(other_advisor, 'کنکوری‌ها')
    assert other.pk is not None


def test_rename_folder_updates_and_enforces_uniqueness():
    advisor = _advisor()
    first = folder_service.create_folder(advisor, 'اول')
    second = folder_service.create_folder(advisor, 'دوم')

    renamed = folder_service.rename_folder(first, '  اولِ تازه ')
    assert renamed.name == 'اولِ تازه'

    with pytest.raises(folder_service.FolderError) as excinfo:
        folder_service.rename_folder(second, 'اولِ تازه')
    assert str(excinfo.value) == MSG_DUPLICATE

    # Renaming a folder to its own current name is not a duplicate.
    assert folder_service.rename_folder(first, 'اولِ تازه').pk == first.pk


def test_delete_folder_nulls_engagements_in_one_transaction():
    advisor, student_a, student_b = _advisor(), _student(), _student('stu2', phone='09120000002')
    engagement_a = _engagement(advisor, student_a)
    engagement_b = _engagement(advisor, student_b)
    outside = _engagement(_advisor('adv2'), _student('stu3', phone='09120000003'))
    folder = folder_service.create_folder(advisor, 'پوشه')

    folder_service.assign_engagement_folder(engagement_a, folder)
    folder_service.assign_engagement_folder(engagement_b, folder)

    folder_service.delete_folder(folder)

    assert not AdvisoryStudentFolder.objects.filter(pk=folder.pk).exists()
    engagement_a.refresh_from_db()
    engagement_b.refresh_from_db()
    outside.refresh_from_db()
    assert engagement_a.folder_id is None
    assert engagement_b.folder_id is None
    assert outside.folder_id is None
    # The engagements themselves survive the folder's deletion (ق۷).
    assert AdvisoryEngagement.objects.filter(
        pk__in=[engagement_a.pk, engagement_b.pk],
    ).count() == 2


def test_list_and_get_folder_are_advisor_scoped():
    advisor, stranger = _advisor(), _advisor('adv2')
    mine = folder_service.create_folder(advisor, 'مال من')
    theirs = folder_service.create_folder(stranger, 'مال او')

    assert [f.pk for f in folder_service.list_folders(advisor)] == [mine.pk]
    assert folder_service.get_folder(advisor, mine.pk).pk == mine.pk
    # A foreign id and a nonexistent id are indistinguishable: both None.
    assert folder_service.get_folder(advisor, theirs.pk) is None
    assert folder_service.get_folder(advisor, 999999) is None


# ── phase B · API: folders CRUD + access matrix ───────────────────────────────

def test_folder_list_requires_authentication():
    response = APIClient().get(FOLDERS_URL)
    assert response.status_code == 401


def test_folder_routes_reject_student_role():
    advisor, student = _advisor(), _student()
    folder = folder_service.create_folder(advisor, 'پوشه')

    client = _auth(student)
    assert client.get(FOLDERS_URL).status_code == 403
    assert client.post(FOLDERS_URL, {'name': 'نو'}, format='json').status_code == 403
    assert client.patch(
        FOLDER_DETAIL_URL.format(folder_id=folder.pk), {'name': 'نو'}, format='json',
    ).status_code == 403
    assert client.delete(FOLDER_DETAIL_URL.format(folder_id=folder.pk)).status_code == 403


def test_folder_crud_happy_path_for_owner():
    advisor = _advisor()
    client = _auth(advisor)

    created = client.post(FOLDERS_URL, {'name': '  پایه دهم '}, format='json')
    assert created.status_code == 201
    body = created.json()
    assert body['name'] == 'پایه دهم'
    folder_id = body['id']

    listed = client.get(FOLDERS_URL)
    assert listed.status_code == 200
    assert [row['id'] for row in listed.json()] == [folder_id]

    renamed = client.patch(
        FOLDER_DETAIL_URL.format(folder_id=folder_id), {'name': 'دهم‌ها'}, format='json',
    )
    assert renamed.status_code == 200
    assert renamed.json() == {'id': folder_id, 'name': 'دهم‌ها'}

    deleted = client.delete(FOLDER_DETAIL_URL.format(folder_id=folder_id))
    assert deleted.status_code == 204
    assert client.get(FOLDERS_URL).json() == []


def test_stranger_advisor_gets_404_not_403_on_foreign_folder():
    owner, stranger = _advisor(), _advisor('adv2')
    folder = folder_service.create_folder(owner, 'پوشهٔ مالک')

    client = _auth(stranger)
    assert client.patch(
        FOLDER_DETAIL_URL.format(folder_id=folder.pk), {'name': 'دزدی'}, format='json',
    ).status_code == 404
    assert client.delete(FOLDER_DETAIL_URL.format(folder_id=folder.pk)).status_code == 404
    # And the foreign folder never appears in the stranger's own list.
    assert client.get(FOLDERS_URL).json() == []


@pytest.mark.parametrize('payload,message', [
    ({'name': ''}, MSG_NAME_REQUIRED),
    ({'name': '   '}, MSG_NAME_REQUIRED),
    ({}, MSG_NAME_REQUIRED),
    ({'name': 'x' * 65}, MSG_NAME_TOO_LONG),
])
def test_folder_create_error_messages_are_the_pinned_persian_ones(payload, message):
    advisor = _advisor()
    client = _auth(advisor)

    response = client.post(FOLDERS_URL, payload, format='json')

    assert response.status_code == 400
    assert response.json()['detail'] == message


def test_duplicate_name_answers_400_with_pinned_message():
    advisor = _advisor()
    client = _auth(advisor)
    assert client.post(FOLDERS_URL, {'name': 'تکراری'}, format='json').status_code == 201

    response = client.post(FOLDERS_URL, {'name': 'تکراری'}, format='json')

    assert response.status_code == 400
    assert response.json()['detail'] == MSG_DUPLICATE


def test_rename_to_blank_or_long_answers_400_with_pinned_message():
    advisor = _advisor()
    folder = folder_service.create_folder(advisor, 'پوشه')
    client = _auth(advisor)

    blank = client.patch(
        FOLDER_DETAIL_URL.format(folder_id=folder.pk), {'name': '  '}, format='json',
    )
    long = client.patch(
        FOLDER_DETAIL_URL.format(folder_id=folder.pk), {'name': 'y' * 65}, format='json',
    )

    assert blank.status_code == 400
    assert blank.json()['detail'] == MSG_NAME_REQUIRED
    assert long.status_code == 400
    assert long.json()['detail'] == MSG_NAME_TOO_LONG


# ── phase B · API: the move door ──────────────────────────────────────────────

def test_assign_folder_moves_student_and_null_detaches():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    folder = folder_service.create_folder(advisor, 'پوشه')
    client = _auth(advisor)

    moved = client.patch(
        ASSIGN_URL.format(pk=engagement.pk), {'folderId': folder.pk}, format='json',
    )
    assert moved.status_code == 200
    assert moved.json() == {'engagementId': engagement.pk, 'folderId': folder.pk}
    engagement.refresh_from_db()
    assert engagement.folder_id == folder.pk

    detached = client.patch(
        ASSIGN_URL.format(pk=engagement.pk), {'folderId': None}, format='json',
    )
    assert detached.status_code == 200
    assert detached.json()['folderId'] is None
    engagement.refresh_from_db()
    assert engagement.folder_id is None


def test_assign_folder_matrix_stranger_student_anonymous():
    owner, stranger, student = _advisor(), _advisor('adv2'), _student()
    engagement = _engagement(owner, student)
    owners_folder = folder_service.create_folder(owner, 'مالک')
    strangers_folder = folder_service.create_folder(stranger, 'غریبه')

    stranger_client = _auth(stranger)
    assert stranger_client.patch(
        ASSIGN_URL.format(pk=engagement.pk), {'folderId': owners_folder.pk}, format='json',
    ).status_code == 404

    student_client = _auth(student)
    assert student_client.patch(
        ASSIGN_URL.format(pk=engagement.pk), {'folderId': owners_folder.pk}, format='json',
    ).status_code == 403

    assert APIClient().patch(
        ASSIGN_URL.format(pk=engagement.pk), {'folderId': owners_folder.pk}, format='json',
    ).status_code == 401

    # A folder id that exists but belongs to someone else is a 400 in the BODY.
    owner_client = _auth(owner)
    bad_folder = owner_client.patch(
        ASSIGN_URL.format(pk=engagement.pk), {'folderId': strangers_folder.pk}, format='json',
    )
    assert bad_folder.status_code == 400
    assert bad_folder.json()['detail'] == 'پوشه انتخابی معتبر نیست.'


# ── phase B · API: the searchable roster ──────────────────────────────────────

def _roster_with_two_students():
    advisor = _advisor()
    zahra = _student('zahra', phone='09121110000', first_name='زهرا', last_name='محمدی')
    ali = _student('alireza', phone='09352220000', first_name='علی', last_name='کریمی')
    zahra_engagement = _engagement(advisor, zahra)
    ali_engagement = _engagement(advisor, ali)
    return advisor, zahra_engagement, ali_engagement


def test_roster_q_search_matches_persian_first_name():
    advisor, zahra_engagement, ali_engagement = _roster_with_two_students()
    client = _auth(advisor)

    found = client.get(STUDENTS_URL, {'q': 'زهرا'})

    assert found.status_code == 200
    ids = [row['id'] for row in found.json()['students']]
    assert ids == [zahra_engagement.pk]
    assert ali_engagement.pk not in ids


def test_roster_q_search_matches_last_name_username_and_phone_fragment():
    advisor, zahra_engagement, ali_engagement = _roster_with_two_students()
    client = _auth(advisor)

    by_last = client.get(STUDENTS_URL, {'q': 'کریمی'})
    assert [row['id'] for row in by_last.json()['students']] == [ali_engagement.pk]

    by_username = client.get(STUDENTS_URL, {'q': 'zahra'})
    assert [row['id'] for row in by_username.json()['students']] == [zahra_engagement.pk]

    # A phone FRAGMENT, not the whole number.
    by_phone = client.get(STUDENTS_URL, {'q': '0935'})
    assert [row['id'] for row in by_phone.json()['students']] == [ali_engagement.pk]

    # Nothing matches ⇒ an empty list, never an error.
    none = client.get(STUDENTS_URL, {'q': 'وجود ندارد'})
    assert none.status_code == 200
    assert none.json()['students'] == []


def test_roster_folder_filter_narrows_and_foreign_folder_is_404():
    advisor, zahra_engagement, ali_engagement = _roster_with_two_students()
    stranger = _advisor('adv2')
    folder = folder_service.create_folder(advisor, 'گروه الف')
    foreign = folder_service.create_folder(stranger, 'گروه بیگانه')
    folder_service.assign_engagement_folder(zahra_engagement, folder)
    client = _auth(advisor)

    filtered = client.get(STUDENTS_URL, {'folder': folder.pk})
    assert [row['id'] for row in filtered.json()['students']] == [zahra_engagement.pk]

    combined = client.get(STUDENTS_URL, {'folder': folder.pk, 'q': 'علی'})
    assert combined.json()['students'] == []

    assert client.get(STUDENTS_URL, {'folder': foreign.pk}).status_code == 404
    assert client.get(STUDENTS_URL, {'folder': 999999}).status_code == 404
    assert client.get(STUDENTS_URL, {'folder': 'not-an-int'}).status_code == 404


def test_roster_response_carries_folders_array_and_folder_ids():
    advisor, zahra_engagement, ali_engagement = _roster_with_two_students()
    second = folder_service.create_folder(advisor, 'آلفا')
    first = folder_service.create_folder(advisor, 'بِتا')
    folder_service.assign_engagement_folder(ali_engagement, second)
    client = _auth(advisor)

    payload = client.get(STUDENTS_URL).json()

    # Name order, regardless of creation order.
    assert payload['folders'] == [
        {'id': second.pk, 'name': 'آلفا'},
        {'id': first.pk, 'name': 'بِتا'},
    ]
    rows = {row['id']: row for row in payload['students']}
    assert rows[zahra_engagement.pk]['folderId'] is None
    assert rows[ali_engagement.pk]['folderId'] == second.pk


def test_roster_filters_do_not_leak_into_pending_invites_or_other_advisors():
    advisor, zahra_engagement, _ali = _roster_with_two_students()
    _pending = _engagement(
        advisor, _student('pending1', phone='09123330000'), status=Status.PENDING,
    )
    client = _auth(advisor)

    payload = client.get(STUDENTS_URL, {'q': 'زهرا'}).json()

    # The outbox is untouched by roster filters — it is one screen, one call.
    assert len(payload['pendingInvites']) == 1
    assert payload['students'][0]['id'] == zahra_engagement.pk

    # Another advisor searching the same needle finds nothing of their own.
    stranger_payload = _auth(_advisor('adv2')).get(STUDENTS_URL, {'q': 'زهرا'}).json()
    assert stranger_payload['students'] == []
