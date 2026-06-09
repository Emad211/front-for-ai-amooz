"""Opt-in pagination for the org member list (OrgMemberListView).

A large institute's member roster must be paginatable so a single request never
serializes an unbounded slice. Pagination is OPT-IN (?page / ?page_size) to keep
the legacy bare-array contract for the current FE (5 consumers of getMembers)
until they migrate; passing the params yields a bounded, hard-capped envelope.
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership

pytestmark = pytest.mark.django_db


def _org():
    return Organization.objects.create(name='Org', slug='org', student_capacity=1000)


def _admin_client(org):
    """A platform TEACHER who is the org's admin (org_role=admin)."""
    mgr = baker.make(User, role=User.Role.TEACHER)
    OrganizationMembership.objects.create(
        organization=org, user=mgr, org_role=OrganizationMembership.OrgRole.ADMIN,
    )
    client = APIClient()
    client.force_authenticate(user=mgr)
    return client


def _add_members(org, n, *, role=OrganizationMembership.OrgRole.STUDENT):
    users = baker.make(User, _quantity=n)
    OrganizationMembership.objects.bulk_create([
        OrganizationMembership(organization=org, user=u, org_role=role)
        for u in users
    ])


def _url(org):
    return f'/api/organizations/{org.id}/members/'


class TestOrgMemberListPagination:
    def test_default_returns_bare_array(self):
        org = _org()
        client = _admin_client(org)
        _add_members(org, 3)
        resp = client.get(_url(org))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 4  # 3 students + the admin membership

    def test_opt_in_pagination_envelope(self):
        org = _org()
        client = _admin_client(org)
        _add_members(org, 3)
        resp = client.get(_url(org) + '?page=1')
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        assert set(body.keys()) >= {'count', 'next', 'previous', 'results'}
        assert body['count'] == 4
        assert isinstance(body['results'], list)

    def test_page_size_hard_capped(self):
        org = _org()
        client = _admin_client(org)
        _add_members(org, 205)
        resp = client.get(_url(org) + '?page=1&page_size=9999')
        assert resp.status_code == 200
        body = resp.json()
        assert body['count'] == 206  # 205 students + admin
        assert len(body['results']) == 200  # capped at max_page_size, not 206
        assert body['next'] is not None

    def test_pagination_preserves_role_filter(self):
        org = _org()
        client = _admin_client(org)
        _add_members(org, 3, role=OrganizationMembership.OrgRole.STUDENT)
        _add_members(org, 2, role=OrganizationMembership.OrgRole.TEACHER)
        resp = client.get(_url(org) + '?page=1&role=student')
        assert resp.status_code == 200
        body = resp.json()
        assert body['count'] == 3
        assert all(m['orgRole'] == 'student' for m in body['results'])

    def test_non_admin_forbidden_even_with_page(self):
        """Pagination must not bypass the org-admin gate."""
        org = _org()
        _add_members(org, 2)
        outsider = baker.make(User, role=User.Role.TEACHER)
        client = APIClient()
        client.force_authenticate(user=outsider)
        assert client.get(_url(org) + '?page=1').status_code == 403
