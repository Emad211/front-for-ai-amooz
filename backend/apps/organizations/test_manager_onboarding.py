"""Tests for org creation with manager mobile + SMS onboarding + role security."""
import pytest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.organizations.models import (
    InvitationCode,
    Organization,
    OrganizationMembership,
)

User = get_user_model()
pytestmark = pytest.mark.django_db

STRONG = 'Str0ngPass!42'


def _platform_admin():
    return User.objects.create_user(username='padmin', password='p', role=User.Role.ADMIN)


def _admin_client():
    client = APIClient()
    client.force_authenticate(user=_platform_admin())
    return client


def _create_org(client, *, name='مدرسه البرز', slug='alborz', manager_phone='', manager_name=''):
    payload = {'name': name, 'slug': slug}
    if manager_phone:
        payload['manager_phone'] = manager_phone
    if manager_name:
        payload['manager_name'] = manager_name
    return client.post('/api/organizations/', payload, format='json')


# ---------------------------------------------------------------------------
# org creation binds the admin code to the manager phone
# ---------------------------------------------------------------------------

def test_org_create_binds_admin_code_to_manager_phone():
    res = _create_org(_admin_client(), manager_phone='0912 000 0000', manager_name='آقای مدیر')
    assert res.status_code == 201
    assert res.data['managerPhone'] == '09120000000'
    code = InvitationCode.objects.get(code=res.data['adminActivationCode'])
    assert code.phone == '09120000000'
    assert code.target_role == InvitationCode.TargetRole.ADMIN
    assert code.max_uses == 1


def test_manager_invite_sms_enqueued_on_commit(django_capture_on_commit_callbacks):
    with patch('apps.classes.tasks.send_org_manager_invite_sms_task.delay') as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            res = _create_org(_admin_client(), manager_phone='09120000000')
    assert res.status_code == 201
    assert mock_delay.called


def test_org_create_without_phone_skips_sms(django_capture_on_commit_callbacks):
    with patch('apps.classes.tasks.send_org_manager_invite_sms_task.delay') as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            res = _create_org(_admin_client())
    assert res.status_code == 201
    assert not mock_delay.called
    code = InvitationCode.objects.get(code=res.data['adminActivationCode'])
    assert code.phone == ''


# ---------------------------------------------------------------------------
# SECURITY: redeeming an org-admin code must NOT grant platform-admin powers
# ---------------------------------------------------------------------------

def test_redeeming_admin_code_does_not_grant_platform_admin():
    res = _create_org(_admin_client(), slug='x', name='X', manager_phone='09120000000')
    code_val = res.data['adminActivationCode']

    anon = APIClient()
    r2 = anon.post('/api/organizations/redeem-code/', {
        'code': code_val, 'phone': '09120000000', 'password': STRONG, 'first_name': 'مدیر',
    }, format='json')
    assert r2.status_code == 201
    assert 'access' in r2.data  # JWT issued

    user = User.objects.get(username='09120000000')
    # Platform role is TEACHER — NOT ADMIN — and no staff/superuser powers.
    assert user.role == 'TEACHER'
    assert not user.is_staff
    assert not user.is_superuser
    assert user.phone == '09120000000'

    membership = OrganizationMembership.objects.get(user=user)
    assert membership.org_role == OrganizationMembership.OrgRole.ADMIN

    org = Organization.objects.get(slug='x')
    assert org.owner_id == user.id


def test_bound_code_rejects_a_different_phone():
    res = _create_org(_admin_client(), slug='x', name='X', manager_phone='09120000000')
    code_val = res.data['adminActivationCode']
    anon = APIClient()
    r2 = anon.post('/api/organizations/redeem-code/', {
        'code': code_val, 'phone': '09129999999', 'password': STRONG,
    }, format='json')
    assert r2.status_code == 400
    assert not User.objects.filter(username='09129999999').exists()


def test_bound_code_requires_phone():
    res = _create_org(_admin_client(), slug='x', name='X', manager_phone='09120000000')
    code_val = res.data['adminActivationCode']
    anon = APIClient()
    r2 = anon.post('/api/organizations/redeem-code/', {
        'code': code_val, 'username': 'someone', 'password': STRONG,
    }, format='json')
    assert r2.status_code == 400


def test_student_code_maps_to_student_role():
    org = Organization.objects.create(name='Y', slug='y')
    code = InvitationCode.objects.create(
        organization=org, target_role=InvitationCode.TargetRole.STUDENT,
    )
    anon = APIClient()
    r = anon.post('/api/organizations/redeem-code/', {
        'code': code.code, 'username': 'stud1', 'password': STRONG,
    }, format='json')
    assert r.status_code == 201
    assert User.objects.get(username='stud1').role == 'STUDENT'


def test_manager_can_login_after_onboarding():
    """End-to-end: onboarded manager can obtain a JWT via /api/token/."""
    res = _create_org(_admin_client(), slug='x', name='X', manager_phone='09120000000')
    code_val = res.data['adminActivationCode']
    anon = APIClient()
    anon.post('/api/organizations/redeem-code/', {
        'code': code_val, 'phone': '09120000000', 'password': STRONG,
    }, format='json')

    token_res = APIClient().post('/api/token/', {
        'username': '09120000000', 'password': STRONG,
    }, format='json')
    assert token_res.status_code == 200
    assert 'access' in token_res.data
