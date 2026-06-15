"""Tests for the admin review + approval flow (Phase 2)."""

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import InvitationCode, Organization
from apps.waitlist.models import AccessRequest

LIST_URL = '/api/waitlist/admin/requests/'


def _admin():
    return baker.make('accounts.User', role=User.Role.ADMIN, is_staff=True)


def _teacher_request(**kw):
    defaults = dict(
        kind=AccessRequest.Kind.TEACHER, full_name='علی احمدی',
        phone='09120000000', email='ali@example.com', expertise='ریاضی',
        status=AccessRequest.Status.PENDING,
    )
    defaults.update(kw)
    return AccessRequest.objects.create(**defaults)


def _org_request(**kw):
    defaults = dict(
        kind=AccessRequest.Kind.ORGANIZATION, full_name='مدیر مدرسه',
        phone='09120000001', org_name='دبیرستان البرز', city='تهران',
        expected_students=250, status=AccessRequest.Status.PENDING,
    )
    defaults.update(kw)
    return AccessRequest.objects.create(**defaults)


def _no_sms(monkeypatch):
    """Capture (and neutralize) the approval SMS so tests assert wiring, not Mediana."""
    calls = []
    monkeypatch.setattr(
        'apps.waitlist.views.notify_access_request_approved',
        lambda ar: calls.append(ar.pk) or True,
    )
    return calls


# ── Permissions ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_list_requires_admin():
    _teacher_request()
    client = APIClient()
    # Anonymous
    assert client.get(LIST_URL).status_code in (401, 403)
    # Authenticated non-admin (a student)
    student = baker.make('accounts.User', role=User.Role.STUDENT)
    client.force_authenticate(user=student)
    assert client.get(LIST_URL).status_code == 403


@pytest.mark.django_db
def test_approve_requires_admin(monkeypatch):
    _no_sms(monkeypatch)
    ar = _teacher_request()
    client = APIClient()
    teacher = baker.make('accounts.User', role=User.Role.TEACHER)
    client.force_authenticate(user=teacher)
    resp = client.post(f'/api/waitlist/admin/requests/{ar.pk}/approve/')
    assert resp.status_code == 403
    ar.refresh_from_db()
    assert ar.status == AccessRequest.Status.PENDING


# ── Listing / filtering ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_admin_can_list_and_filter():
    _teacher_request()
    _org_request()
    client = APIClient()
    client.force_authenticate(user=_admin())

    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert resp.json()['count'] == 2

    resp = client.get(LIST_URL, {'kind': 'organization'})
    assert resp.json()['count'] == 1
    assert resp.json()['results'][0]['kind'] == 'organization'


# ── Teacher approval ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_approve_teacher_issues_token_and_notifies(monkeypatch):
    calls = _no_sms(monkeypatch)
    ar = _teacher_request()
    before_orgs = Organization.objects.count()

    client = APIClient()
    admin = _admin()
    client.force_authenticate(user=admin)
    resp = client.post(f'/api/waitlist/admin/requests/{ar.pk}/approve/')

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['status'] == 'approved'
    assert data['registration_token']          # a token was minted
    assert len(data['registration_token']) > 20

    ar.refresh_from_db()
    assert ar.reviewed_by_id == admin.id
    assert ar.reviewed_at is not None
    assert ar.token_expires_at is not None
    # Teacher approval must NOT create an organization.
    assert Organization.objects.count() == before_orgs
    # SMS wiring fired once for this request.
    assert calls == [ar.pk]


# ── Organization approval ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_approve_org_provisions_org_and_admin_code(monkeypatch):
    calls = _no_sms(monkeypatch)
    ar = _org_request()

    client = APIClient()
    client.force_authenticate(user=_admin())
    resp = client.post(f'/api/waitlist/admin/requests/{ar.pk}/approve/')

    assert resp.status_code == 200, resp.content
    ar.refresh_from_db()
    assert ar.status == AccessRequest.Status.APPROVED
    assert ar.created_organization is not None

    org = ar.created_organization
    assert org.name == 'دبیرستان البرز'
    assert org.student_capacity == 250

    admin_code = InvitationCode.objects.get(organization=org, target_role=InvitationCode.TargetRole.ADMIN)
    # For orgs the registration token IS the admin activation code.
    assert ar.registration_token == admin_code.code
    assert calls == [ar.pk]


# ── Reject ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_reject_sets_status_and_reason():
    ar = _teacher_request()
    client = APIClient()
    client.force_authenticate(user=_admin())
    resp = client.post(
        f'/api/waitlist/admin/requests/{ar.pk}/reject/',
        {'reason': 'مدارک ناقص'}, format='json',
    )
    assert resp.status_code == 200, resp.content
    ar.refresh_from_db()
    assert ar.status == AccessRequest.Status.REJECTED
    assert ar.reject_reason == 'مدارک ناقص'


# ── Idempotency guards ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_cannot_approve_already_decided(monkeypatch):
    _no_sms(monkeypatch)
    ar = _teacher_request(status=AccessRequest.Status.APPROVED)
    client = APIClient()
    client.force_authenticate(user=_admin())
    resp = client.post(f'/api/waitlist/admin/requests/{ar.pk}/approve/')
    assert resp.status_code == 409


@pytest.mark.django_db
def test_cannot_reject_already_decided():
    ar = _teacher_request(status=AccessRequest.Status.REJECTED)
    client = APIClient()
    client.force_authenticate(user=_admin())
    resp = client.post(f'/api/waitlist/admin/requests/{ar.pk}/reject/')
    assert resp.status_code == 409


@pytest.mark.django_db
def test_approve_missing_returns_404(monkeypatch):
    _no_sms(monkeypatch)
    client = APIClient()
    client.force_authenticate(user=_admin())
    assert client.post('/api/waitlist/admin/requests/999999/approve/').status_code == 404
