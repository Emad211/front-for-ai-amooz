"""Org-manager (MANAGER platform role) onboarding + permission tests.

Redemption is now uniform & phone-based for ALL roles: code + phone create a
PASSWORDLESS shell of the mapped platform role (admin/deputy → MANAGER, teacher →
TEACHER, student → STUDENT); the user sets real credentials later in onboarding.
The org-level membership keeps the original org_role (admin/deputy/teacher).
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import (
    InvitationCode,
    Organization,
    OrganizationMembership,
)

REDEEM = '/api/organizations/redeem-code/'


def _active_org(**kwargs) -> Organization:
    return baker.make(
        Organization,
        subscription_status=Organization.SubscriptionStatus.ACTIVE,
        **kwargs,
    )


def _code(org, target_role) -> InvitationCode:
    return baker.make(
        InvitationCode,
        organization=org,
        target_role=target_role,
        is_active=True,
        max_uses=10,
    )


@pytest.mark.django_db
class TestManagerRedeem:
    def test_admin_code_makes_a_manager_not_admin_not_teacher(self):
        org = _active_org(name='مدرسه الف')
        code = _code(org, InvitationCode.TargetRole.ADMIN)

        res = APIClient().post(REDEEM, {
            'code': code.code, 'phone': '09120000000', 'first_name': 'م', 'last_name': 'م',
        }, format='json')
        assert res.status_code == 201, res.data

        user = User.objects.get(phone='09120000000', role=User.Role.MANAGER)
        assert user.role == User.Role.MANAGER and user.role != User.Role.TEACHER
        assert not user.is_staff and not user.is_superuser
        assert user.is_freelancer is False           # org-only, no personal space
        assert not user.has_usable_password()         # passwordless shell until onboarding
        m = OrganizationMembership.objects.get(user=user, organization=org)
        assert m.org_role == OrganizationMembership.OrgRole.ADMIN

    def test_deputy_code_makes_a_manager(self):
        org = _active_org(name='مدرسه ب')
        code = _code(org, InvitationCode.TargetRole.DEPUTY)

        res = APIClient().post(REDEEM, {'code': code.code, 'phone': '09120000002'}, format='json')
        assert res.status_code == 201, res.data
        assert User.objects.get(phone='09120000002', role=User.Role.MANAGER)

    def test_teacher_code_stays_teacher_org_only(self):
        org = _active_org()
        code = _code(org, InvitationCode.TargetRole.TEACHER)

        res = APIClient().post(REDEEM, {'code': code.code, 'phone': '09120000003'}, format='json')
        assert res.status_code == 201, res.data
        user = User.objects.get(phone='09120000003', role=User.Role.TEACHER)
        assert user.is_freelancer is False  # brand-new org account is org-only

    def test_student_code_stays_student(self):
        org = _active_org()
        code = _code(org, InvitationCode.TargetRole.STUDENT)

        res = APIClient().post(REDEEM, {'code': code.code, 'phone': '09120000005'}, format='json')
        assert res.status_code == 201, res.data
        assert User.objects.get(phone='09120000005', role=User.Role.STUDENT)

    def test_redeem_without_phone_is_rejected(self):
        org = _active_org()
        code = _code(org, InvitationCode.TargetRole.ADMIN)
        res = APIClient().post(REDEEM, {'code': code.code}, format='json')
        assert res.status_code == 400, res.data

    def test_manager_is_not_a_teacher_and_cannot_teach(self):
        """The redeemed manager (token from redeem) is rejected from teacher-only
        endpoints — they manage the org, they do not teach."""
        org = _active_org()
        code = _code(org, InvitationCode.TargetRole.ADMIN)

        res = APIClient().post(REDEEM, {'code': code.code, 'phone': '09120000004'}, format='json')
        assert res.status_code == 201, res.data
        access = res.data['access']

        user = User.objects.get(phone='09120000004', role=User.Role.MANAGER)
        assert user.role == User.Role.MANAGER

        mgr = APIClient()
        mgr.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        assert mgr.get('/api/classes/teacher/students/').status_code == 403

    def test_existing_freelancer_joining_org_stays_freelancer(self):
        """An authenticated freelancer (no phone needed) who redeems an org TEACHER
        code keeps their personal space — only brand-new shells are org-only."""
        org = _active_org()
        code = _code(org, InvitationCode.TargetRole.TEACHER)

        teacher = baker.make(User, role=User.Role.TEACHER, is_freelancer=True)
        client = APIClient()
        client.force_authenticate(user=teacher)
        res = client.post(REDEEM, {'code': code.code}, format='json')
        assert res.status_code == 201, res.data

        teacher.refresh_from_db()
        assert teacher.is_freelancer is True  # unchanged
        assert OrganizationMembership.objects.filter(
            user=teacher, organization=org,
            org_role=OrganizationMembership.OrgRole.TEACHER,
        ).exists()
