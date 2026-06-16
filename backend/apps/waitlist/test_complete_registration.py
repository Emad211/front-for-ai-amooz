"""Tests for token-gated teacher registration completion (Phase 3)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import TeacherProfile
from apps.waitlist.models import AccessRequest

User = get_user_model()
COMPLETE_URL = '/api/waitlist/complete/'
PASSWORD = 'StrongPass123!@#'


def _approved_teacher(token='tok-teacher-123456789', **kw):
    defaults = dict(
        kind=AccessRequest.Kind.TEACHER, full_name='علی احمدی',
        phone='09120000000', email='ali@example.com',
        status=AccessRequest.Status.APPROVED,
        registration_token=token,
        token_expires_at=timezone.now() + timedelta(days=7),
    )
    defaults.update(kw)
    return AccessRequest.objects.create(**defaults)


@pytest.mark.django_db
def test_complete_creates_teacher_and_returns_jwt():
    ar = _approved_teacher()
    client = APIClient()
    resp = client.post(COMPLETE_URL, {
        'token': ar.registration_token,
        'username': 'ali_teacher',
        'password': PASSWORD,
    }, format='json')

    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data['user']['role'] == 'TEACHER'
    assert data['tokens']['access'] and data['tokens']['refresh']

    user = User.objects.get(username='ali_teacher')
    assert user.role == User.Role.TEACHER
    assert user.is_active
    assert user.phone == '09120000000'
    assert user.email == 'ali@example.com'
    # full_name was split into first/last.
    assert user.first_name == 'علی' and user.last_name == 'احمدی'
    assert TeacherProfile.objects.filter(user=user, verification_status=True).exists()
    # A waitlist teacher is a freelancer — they own a personal workspace.
    assert user.is_freelancer is True

    ar.refresh_from_db()
    assert ar.token_consumed_at is not None
    assert ar.created_user_id == user.id


@pytest.mark.django_db
def test_token_cannot_be_reused():
    ar = _approved_teacher()
    client = APIClient()
    first = client.post(COMPLETE_URL, {'token': ar.registration_token, 'username': 'teach_one', 'password': PASSWORD}, format='json')
    assert first.status_code == 201, first.content
    again = client.post(COMPLETE_URL, {'token': ar.registration_token, 'username': 'teach_two', 'password': PASSWORD}, format='json')
    assert again.status_code == 400
    assert User.objects.filter(username='teach_two').count() == 0


@pytest.mark.django_db
def test_invalid_token_rejected():
    client = APIClient()
    resp = client.post(COMPLETE_URL, {'token': 'does-not-exist', 'username': 'teach_x', 'password': PASSWORD}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_expired_token_rejected():
    ar = _approved_teacher(token='tok-expired', token_expires_at=timezone.now() - timedelta(days=1))
    client = APIClient()
    resp = client.post(COMPLETE_URL, {'token': ar.registration_token, 'username': 'teach_x', 'password': PASSWORD}, format='json')
    assert resp.status_code == 400
    assert User.objects.filter(username='teach_x').count() == 0


@pytest.mark.django_db
def test_pending_request_token_not_usable():
    ar = _approved_teacher(token='tok-pending', status=AccessRequest.Status.PENDING)
    client = APIClient()
    resp = client.post(COMPLETE_URL, {'token': ar.registration_token, 'username': 'teach_x', 'password': PASSWORD}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_org_token_not_usable_at_teacher_complete():
    AccessRequest.objects.create(
        kind=AccessRequest.Kind.ORGANIZATION, full_name='مدیر', phone='09120000002',
        org_name='سازمان', status=AccessRequest.Status.APPROVED,
        registration_token='ORGCODE1', token_expires_at=timezone.now() + timedelta(days=7),
    )
    client = APIClient()
    resp = client.post(COMPLETE_URL, {'token': 'ORGCODE1', 'username': 'teach_x', 'password': PASSWORD}, format='json')
    assert resp.status_code == 400  # teacher-only endpoint; org code is not a teacher token


@pytest.mark.django_db
def test_duplicate_username_rejected():
    baker.make('accounts.User', username='taken_name')
    ar = _approved_teacher()
    client = APIClient()
    resp = client.post(COMPLETE_URL, {'token': ar.registration_token, 'username': 'taken_name', 'password': PASSWORD}, format='json')
    assert resp.status_code == 400
    # token must NOT be consumed when registration fails validation.
    ar.refresh_from_db()
    assert ar.token_consumed_at is None


@pytest.mark.django_db
def test_completed_teacher_can_login():
    ar = _approved_teacher()
    client = APIClient()
    client.post(COMPLETE_URL, {'token': ar.registration_token, 'username': 'ali_login', 'password': PASSWORD}, format='json')
    login = client.post('/api/token/', {'username': 'ali_login', 'password': PASSWORD}, format='json')
    assert login.status_code == 200
    assert login.data['access']
