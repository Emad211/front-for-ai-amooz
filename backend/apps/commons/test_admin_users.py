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

    def test_assign_refuses_an_advisor_instead_of_silently_clobbering_the_role(self):
        """An ADVISOR must not be turned into a MANAGER behind the admin's back.

        The platform role drives the landing route, so a silent flip would strand
        an advisor with live engagements outside /advisor — broken, but looking
        like it worked. Refuse loudly; make the admin change the role first.
        """
        admin = _admin()
        advisor = baker.make(User, role=User.Role.ADVISOR)
        org = baker.make(Organization, owner=None)

        res = _auth(admin).post(ASSIGN.format(advisor.id), {'organization_id': org.id}, format='json')

        assert res.status_code == 400, res.data
        advisor.refresh_from_db()
        assert advisor.role == User.Role.ADVISOR
        assert not OrganizationMembership.objects.filter(user=advisor, organization=org).exists()
        assert org.owner_id is None

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


@pytest.mark.django_db
class TestFreelancerToggle:
    DETAIL = '/api/admin/users/{}/'
    def test_list_exposes_is_freelancer(self):
        admin = _admin()
        baker.make(User, role=User.Role.TEACHER, is_freelancer=False)
        res = _auth(admin).get(LIST)
        assert res.status_code == 200
        assert all('isFreelancer' in row for row in res.data)

    def test_admin_can_toggle_is_freelancer(self):
        admin = _admin()
        teacher = baker.make(User, role=User.Role.TEACHER, is_freelancer=True)

        res = _auth(admin).patch(
            self.DETAIL.format(teacher.id), {'is_freelancer': False}, format='json',
        )
        assert res.status_code == 200, res.data
        assert res.data['isFreelancer'] is False
        teacher.refresh_from_db()
        assert teacher.is_freelancer is False

        # And back on again.
        res = _auth(admin).patch(
            self.DETAIL.format(teacher.id), {'is_freelancer': True}, format='json',
        )
        assert res.status_code == 200
        teacher.refresh_from_db()
        assert teacher.is_freelancer is True


@pytest.mark.django_db
class TestPromoteToAdvisor:
    """This PATCH is the ONLY way an ADVISOR account comes into existence.

    accounts.User is not registered in Django admin and there is no
    create-user endpoint; public self-registration is STUDENT-only
    (RegisterSerializer._VALID_ROLES). So the runbook is: the advisor signs up
    normally, then a platform admin flips their role here. If this PATCH ever
    stops accepting 'ADVISOR', the whole مشاور feature becomes unreachable in
    production while every advisory test still passes — hence this test.
    """

    DETAIL = '/api/admin/users/{}/'

    def test_admin_can_promote_a_student_to_advisor(self):
        admin = _admin()
        student = baker.make(User, role=User.Role.STUDENT)

        res = _auth(admin).patch(
            self.DETAIL.format(student.id), {'role': 'ADVISOR'}, format='json',
        )

        assert res.status_code == 200, res.data
        student.refresh_from_db()
        assert student.role == User.Role.ADVISOR
        # Promotion must not smuggle in platform-admin powers.
        assert student.is_staff is False
        assert student.is_superuser is False

    def test_promotion_does_not_create_an_advisor_profile_row(self):
        """post_save's profile chain is create-only and has no ADVISOR branch."""
        admin = _admin()
        student = baker.make(User, role=User.Role.STUDENT)

        _auth(admin).patch(
            self.DETAIL.format(student.id), {'role': 'ADVISOR'}, format='json',
        )

        student.refresh_from_db()
        assert not hasattr(student, 'teacherprofile')
        assert not hasattr(student, 'adminprofile')

    def test_advisor_can_be_demoted_back(self):
        """Rollback for the S1 live check is "revert the role" — it must work."""
        admin = _admin()
        advisor = baker.make(User, role=User.Role.ADVISOR)

        res = _auth(admin).patch(
            self.DETAIL.format(advisor.id), {'role': 'STUDENT'}, format='json',
        )

        assert res.status_code == 200, res.data
        advisor.refresh_from_db()
        assert advisor.role == User.Role.STUDENT

    def test_non_admin_cannot_promote_anyone_to_advisor(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        student = baker.make(User, role=User.Role.STUDENT)

        res = _auth(teacher).patch(
            self.DETAIL.format(student.id), {'role': 'ADVISOR'}, format='json',
        )

        assert res.status_code in (401, 403)
        student.refresh_from_db()
        assert student.role == User.Role.STUDENT

    def test_unauthenticated_cannot_promote_anyone_to_advisor(self):
        student = baker.make(User, role=User.Role.STUDENT)

        res = APIClient().patch(
            self.DETAIL.format(student.id), {'role': 'ADVISOR'}, format='json',
        )

        assert res.status_code in (401, 403)
        student.refresh_from_db()
        assert student.role == User.Role.STUDENT
