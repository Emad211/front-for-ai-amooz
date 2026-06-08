"""Tests for the org-manager-scoped settings endpoint.

The manager (platform role TEACHER, org_role admin) may edit the descriptive
profile of their own org, but NOT the platform-controlled billing levers
(slug, student_capacity, subscription_status, owner).
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


def test_manager_can_read_org_settings():
    org = _org()
    manager = _user('mgr')
    OrganizationMembership.objects.create(
        organization=org, user=manager, org_role=OrganizationMembership.OrgRole.ADMIN
    )
    client = APIClient()
    client.force_authenticate(user=manager)
    res = client.get(_url(org))
    assert res.status_code == 200
    assert res.data['name'] == 'Org'
    assert res.data['studentCapacity'] == 100


def test_manager_can_edit_profile_fields():
    org = _org()
    manager = _user('mgr')
    OrganizationMembership.objects.create(
        organization=org, user=manager, org_role=OrganizationMembership.OrgRole.ADMIN
    )
    client = APIClient()
    client.force_authenticate(user=manager)
    res = client.patch(
        _url(org),
        {'name': 'دبیرستان نمونه', 'phone': '02112345678', 'address': 'تهران'},
        format='json',
    )
    assert res.status_code == 200
    org.refresh_from_db()
    assert org.name == 'دبیرستان نمونه'
    assert org.phone == '02112345678'
    assert org.address == 'تهران'


def test_manager_cannot_change_capacity_or_slug():
    org = _org()
    manager = _user('mgr')
    OrganizationMembership.objects.create(
        organization=org, user=manager, org_role=OrganizationMembership.OrgRole.ADMIN
    )
    client = APIClient()
    client.force_authenticate(user=manager)
    res = client.patch(
        _url(org),
        {'name': 'X', 'student_capacity': 99999, 'slug': 'hacked',
         'subscription_status': 'suspended'},
        format='json',
    )
    assert res.status_code == 200
    org.refresh_from_db()
    assert org.name == 'X'                 # editable field applied
    assert org.student_capacity == 100     # billing lever untouched
    assert org.slug == 'org'               # slug untouched
    assert org.subscription_status != 'suspended'


def test_blank_name_rejected():
    org = _org()
    manager = _user('mgr')
    OrganizationMembership.objects.create(
        organization=org, user=manager, org_role=OrganizationMembership.OrgRole.ADMIN
    )
    client = APIClient()
    client.force_authenticate(user=manager)
    res = client.patch(_url(org), {'name': '   '}, format='json')
    assert res.status_code == 400


def test_plain_teacher_forbidden():
    org = _org()
    teacher = _user('t')
    OrganizationMembership.objects.create(
        organization=org, user=teacher, org_role=OrganizationMembership.OrgRole.TEACHER
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    assert client.get(_url(org)).status_code == 403
    assert client.patch(_url(org), {'name': 'x'}, format='json').status_code == 403


def test_non_member_forbidden():
    org = _org()
    outsider = _user('out')
    client = APIClient()
    client.force_authenticate(user=outsider)
    assert client.get(_url(org)).status_code == 403
