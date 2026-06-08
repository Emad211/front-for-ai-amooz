"""Tests for the org-manager-scoped settings endpoint (READ-ONLY).

Product decision: the org manager (platform role TEACHER, org_role admin) may
*view* their organization's settings but never change them — editing the org
profile is reserved for the platform admin. The endpoint exposes GET only.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()
pytestmark = pytest.mark.django_db


def _user(username, role=User.Role.TEACHER, **kw):
    return User.objects.create_user(username=username, password='p', role=role, **kw)


def _org(**kw):
    return Organization.objects.create(name='Org', slug='org', student_capacity=100, **kw)


def _url(org):
    return f'/api/organizations/{org.id}/settings/'


def _manager(org):
    m = _user('mgr')
    OrganizationMembership.objects.create(
        organization=org, user=m, org_role=OrganizationMembership.OrgRole.ADMIN
    )
    client = APIClient()
    client.force_authenticate(user=m)
    return client


def test_manager_can_read_org_settings():
    org = _org()
    client = _manager(org)
    res = client.get(_url(org))
    assert res.status_code == 200
    assert res.data['name'] == 'Org'
    assert res.data['studentCapacity'] == 100


def test_manager_cannot_edit_settings():
    """A manager must not be able to mutate the org via this endpoint."""
    org = _org()
    client = _manager(org)
    # No write verb is allowed — read-only endpoint → 405 Method Not Allowed.
    assert client.patch(_url(org), {'name': 'X'}, format='json').status_code == 405
    assert client.put(_url(org), {'name': 'X'}, format='json').status_code == 405
    org.refresh_from_db()
    assert org.name == 'Org'  # unchanged


def test_plain_teacher_forbidden():
    org = _org()
    teacher = _user('t')
    OrganizationMembership.objects.create(
        organization=org, user=teacher, org_role=OrganizationMembership.OrgRole.TEACHER
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    assert client.get(_url(org)).status_code == 403


def test_non_member_forbidden():
    org = _org()
    outsider = _user('out')
    client = APIClient()
    client.force_authenticate(user=outsider)
    assert client.get(_url(org)).status_code == 403
