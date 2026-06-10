"""Admin-panel user management: org-manager assign/revoke + stats + list field.

Covers AdminUserOrgManagerView (assign/revoke), AdminUserStatsView.managers,
and UserListSerializer.managedOrganizations.
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership

ASSIGN = '/api/admin/users/{}/org-manager/'
REVOKE = '/api/admin/users/{}/org-manager/{}/'
STATS = '/api/admin/users/stats/'
LIST = '/api/admin/users/'


def _auth(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return client


def _admin() -> User:
    return baker.make(User, role=User.Role.ADMIN, is_staff=True, is_superuser=True)


def _admin_membership(user, org):
    return baker.make(
        OrganizationMembership, user=user, organization=org,
        org_role=OrganizationMembership.OrgRole.ADMIN,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    )


@pytest.mark.django_db
class TestAssignOrgManager:
    def test_assign_promotes_to_manager_creates_membership_and_adopts_owner(self):
        admin = _admin()
        target = baker.make(User, role=User.Role.STUDENT)
        org = baker.make(Organization, owner=None)

        res = _auth(admin).post(ASSIGN.format(target.id), {'organization_id': org.id}, format='json')
        assert res.status_code == 200, res.data

        target.refresh_from_db()
        org.refresh_from_db()
        assert target.role == User.Role.MANAGER
        m = OrganizationMembership.objects.get(user=target, organization=org)
        assert m.org_role == OrganizationMembership.OrgRole.ADMIN
        assert m.status == OrganizationMembership.MemberStatus.ACTIVE
        assert org.owner_id == target.id  # org had no owner → adopted
        assert any(o['id'] == org.id for o in res.data['managedOrganizations'])

    def test_assign_does_not_demote_a_platform_admin(self):
        admin = _admin()
        other_admin = baker.make(User, role=User.Role.ADMIN)
        org = baker.make(Organization, owner=None)

        res = _auth(admin).post(ASSIGN.format(other_admin.id), {'organization_id': org.id}, format='json')
        assert res.status_code == 200
        other_admin.refresh_from_db()
        assert other_admin.role == User.Role.ADMIN  # NOT demoted to MANAGER
        assert OrganizationMembership.objects.filter(user=other_admin, organization=org).exists()

    def test_assign_does_not_steal_existing_owner(self):
        admin = _admin()
        owner = baker.make(User, role=User.Role.MANAGER)
        org = baker.make(Organization, owner=owner)
        target = baker.make(User, role=User.Role.STUDENT)

        _auth(admin).post(ASSIGN.format(target.id), {'organization_id': org.id}, format='json')
        org.refresh_from_db()
        assert org.owner_id == owner.id  # unchanged

    def test_assign_unknown_org_returns_404(self):
        admin = _admin()
        target = baker.make(User, role=User.Role.STUDENT)
        res = _auth(admin).post(ASSIGN.format(target.id), {'organization_id': 999999}, format='json')
        assert res.status_code == 404

    def test_non_admin_forbidden(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        target = baker.make(User, role=User.Role.STUDENT)
        org = baker.make(Organization, owner=None)
        res = _auth(teacher).post(ASSIGN.format(target.id), {'organization_id': org.id}, format='json')
        assert res.status_code in (401, 403)

    def test_requires_authentication(self):
        target = baker.make(User, role=User.Role.STUDENT)
        org = baker.make(Organization, owner=None)
        res = APIClient().post(ASSIGN.format(target.id), {'organization_id': org.id}, format='json')
        assert res.status_code in (401, 403)


@pytest.mark.django_db
class TestRevokeOrgManager:
    def test_revoke_removes_membership_clears_owner_reverts_to_student(self):
        admin = _admin()
        mgr = baker.make(User, role=User.Role.MANAGER)
        org = baker.make(Organization, owner=mgr)
        _admin_membership(mgr, org)

        res = _auth(admin).delete(REVOKE.format(mgr.id, org.id))
        assert res.status_code == 200, res.data

        mgr.refresh_from_db()
        org.refresh_from_db()
        assert not OrganizationMembership.objects.filter(
            user=mgr, organization=org, org_role=OrganizationMembership.OrgRole.ADMIN,
        ).exists()
        assert org.owner_id is None
        assert mgr.role == User.Role.STUDENT  # dangling manager reverts

    def test_revoke_keeps_manager_if_still_manages_another_org(self):
        admin = _admin()
        mgr = baker.make(User, role=User.Role.MANAGER)
        org1 = baker.make(Organization, owner=mgr)
        org2 = baker.make(Organization)
        _admin_membership(mgr, org1)
        _admin_membership(mgr, org2)

        _auth(admin).delete(REVOKE.format(mgr.id, org1.id))
        mgr.refresh_from_db()
        assert mgr.role == User.Role.MANAGER  # still manages org2


@pytest.mark.django_db
class TestUserStatsAndList:
    def test_stats_includes_managers_count(self):
        admin = _admin()
        baker.make(User, role=User.Role.MANAGER, _quantity=2)
        res = _auth(admin).get(STATS)
        assert res.status_code == 200
        assert res.data['managers'] == 2

    def test_list_includes_managed_organizations(self):
        admin = _admin()
        mgr = baker.make(User, role=User.Role.MANAGER)
        org = baker.make(Organization, name='X-Org')
        _admin_membership(mgr, org)

        res = _auth(admin).get(LIST)
        assert res.status_code == 200
        row = next(u for u in res.data if u['id'] == mgr.id)
        assert any(o['id'] == org.id and o['name'] == 'X-Org' for o in row['managedOrganizations'])

    def test_list_non_manager_has_empty_managed_orgs(self):
        admin = _admin()
        student = baker.make(User, role=User.Role.STUDENT)
        res = _auth(admin).get(LIST)
        assert res.status_code == 200
        row = next(u for u in res.data if u['id'] == student.id)
        assert row['managedOrganizations'] == []
