"""Tests for admin user-list pagination (opt-in) + the user stats endpoint.

The admin user table grows with the whole platform, so the list endpoint must be
paginatable (bounded per request) and the dashboard stat cards must NOT depend on
fetching the entire table. Pagination is opt-in (via ?page / ?page_size) to keep
the legacy bare-array contract working until the admin UI is migrated.
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership


def _auth_client(user) -> APIClient:
    token = str(RefreshToken.for_user(user).access_token)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.mark.django_db
class TestAdminUserListPagination:
    def test_default_returns_bare_array(self):
        """No ?page/?page_size -> legacy bare array (backward compatible)."""
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        baker.make(User, role=User.Role.STUDENT, _quantity=3)
        resp = _auth_client(admin).get('/api/admin/users/')
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_opt_in_pagination_envelope(self):
        """?page=1 -> standard {count,next,previous,results} envelope."""
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        baker.make(User, role=User.Role.STUDENT, _quantity=3)
        resp = _auth_client(admin).get('/api/admin/users/?page=1')
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        assert set(body.keys()) >= {'count', 'next', 'previous', 'results'}
        assert body['count'] == 4  # admin + 3 students
        assert isinstance(body['results'], list)

    def test_page_size_hard_capped(self):
        """?page_size beyond max_page_size is clamped to 200 — a single request
        can never serialize an unbounded slice of the table."""
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        baker.make(User, role=User.Role.STUDENT, _quantity=205)
        resp = _auth_client(admin).get('/api/admin/users/?page=1&page_size=9999')
        assert resp.status_code == 200
        body = resp.json()
        assert body['count'] == 206  # 205 students + admin
        assert len(body['results']) == 200  # capped, not 206
        assert body['next'] is not None

    def test_pagination_preserves_role_filter(self):
        """Server-side filters compose with pagination."""
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        baker.make(User, role=User.Role.STUDENT, _quantity=3)
        baker.make(User, role=User.Role.TEACHER, _quantity=2)
        resp = _auth_client(admin).get('/api/admin/users/?page=1&role=STUDENT')
        assert resp.status_code == 200
        body = resp.json()
        assert body['count'] == 3
        assert all(u['role'] == 'STUDENT' for u in body['results'])


@pytest.mark.django_db
class TestAdminUserStats:
    def test_returns_aggregate_counts(self):
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        baker.make(User, role=User.Role.TEACHER, is_active=True, _quantity=2)
        baker.make(User, role=User.Role.STUDENT, is_active=True, _quantity=3)
        baker.make(User, role=User.Role.STUDENT, is_active=False)  # inactive

        resp = _auth_client(admin).get('/api/admin/users/stats/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == 7
        assert body['admins'] == 1
        assert body['teachers'] == 2
        assert body['students'] == 4
        assert body['active'] == 6

    def test_requires_admin(self):
        student = baker.make(User, role=User.Role.STUDENT, is_active=True)
        resp = _auth_client(student).get('/api/admin/users/stats/')
        assert resp.status_code == 403

    def test_includes_managers_count(self):
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        baker.make(User, role=User.Role.MANAGER, _quantity=2)
        resp = _auth_client(admin).get('/api/admin/users/stats/')
        assert resp.json()['managers'] == 2


@pytest.mark.django_db
class TestAdminAssignOrgManager:
    """Platform admin can designate an existing user as an org MANAGER (a
    distinct role, NOT a teacher) straight from the user panel."""

    def _org(self, slug='org-x'):
        return Organization.objects.create(name='Org', slug=slug, student_capacity=100)

    def test_assign_makes_user_manager_with_membership_and_owner(self):
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        target = baker.make(User, role=User.Role.STUDENT)
        org = self._org()

        resp = _auth_client(admin).post(
            f'/api/admin/users/{target.id}/org-manager/',
            {'organization_id': org.id}, format='json',
        )
        assert resp.status_code == 200
        target.refresh_from_db()
        org.refresh_from_db()
        # Distinct MANAGER role (not TEACHER) + active org-admin membership.
        assert target.role == User.Role.MANAGER
        m = OrganizationMembership.objects.get(user=target, organization=org)
        assert m.org_role == OrganizationMembership.OrgRole.ADMIN
        assert m.status == OrganizationMembership.MemberStatus.ACTIVE
        assert org.owner_id == target.id
        # The serializer surfaces the managed org.
        assert any(o['id'] == org.id for o in resp.json()['managedOrganizations'])

    def test_assign_does_not_demote_platform_admin(self):
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        other = baker.make(User, role=User.Role.ADMIN)
        org = self._org()
        resp = _auth_client(admin).post(
            f'/api/admin/users/{other.id}/org-manager/',
            {'organization_id': org.id}, format='json',
        )
        assert resp.status_code == 200
        other.refresh_from_db()
        assert other.role == User.Role.ADMIN  # NOT downgraded to MANAGER

    def test_revoke_removes_membership_and_reverts_role(self):
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        target = baker.make(User, role=User.Role.STUDENT)
        org = self._org()
        client = _auth_client(admin)
        client.post(
            f'/api/admin/users/{target.id}/org-manager/',
            {'organization_id': org.id}, format='json',
        )
        resp = client.delete(f'/api/admin/users/{target.id}/org-manager/{org.id}/')
        assert resp.status_code == 200
        target.refresh_from_db()
        org.refresh_from_db()
        assert not OrganizationMembership.objects.filter(
            user=target, organization=org,
            org_role=OrganizationMembership.OrgRole.ADMIN,
        ).exists()
        # No longer manages any org → reverted from MANAGER to STUDENT; owner cleared.
        assert target.role == User.Role.STUDENT
        assert org.owner_id is None

    def test_assign_requires_platform_admin(self):
        student = baker.make(User, role=User.Role.STUDENT, is_active=True)
        target = baker.make(User, role=User.Role.STUDENT)
        org = self._org()
        resp = _auth_client(student).post(
            f'/api/admin/users/{target.id}/org-manager/',
            {'organization_id': org.id}, format='json',
        )
        assert resp.status_code == 403

    def test_managed_organizations_in_user_list(self):
        admin = baker.make(User, role=User.Role.ADMIN, is_active=True)
        target = baker.make(User, role=User.Role.STUDENT)
        org = self._org()
        client = _auth_client(admin)
        client.post(
            f'/api/admin/users/{target.id}/org-manager/',
            {'organization_id': org.id}, format='json',
        )
        rows = client.get('/api/admin/users/').json()
        row = next(r for r in rows if r['id'] == target.id)
        assert any(o['id'] == org.id for o in row['managedOrganizations'])
