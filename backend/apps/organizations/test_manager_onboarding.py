"""Org-manager (MANAGER platform role) onboarding + permission tests.

A redeemed org admin/deputy is the distinct platform role MANAGER — NOT a
platform ADMIN and NOT a TEACHER. The org-level membership stays org_role=admin.
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

STRONG = 'Manager-12345-xyz'
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
            'code': code.code, 'username': '09120000000',
            'password': STRONG, 'first_name': 'م', 'last_name': 'م',
        }, format='json')
        assert res.status_code == 201, res.data

        user = User.objects.get(username='09120000000')
        # Platform role is the distinct MANAGER — NOT ADMIN, NOT TEACHER.
        assert user.role == User.Role.MANAGER
        assert user.role != User.Role.TEACHER
        assert not user.is_staff
        assert not user.is_superuser
        # The org-level membership is still admin (org_role unchanged).
        m = OrganizationMembership.objects.get(user=user, organization=org)
        assert m.org_role == OrganizationMembership.OrgRole.ADMIN

    def test_deputy_code_makes_a_manager(self):
        org = _active_org(name='مدرسه ب')
        code = _code(org, InvitationCode.TargetRole.DEPUTY)

        res = APIClient().post(REDEEM, {
            'code': code.code, 'username': '09120000002', 'password': STRONG,
        }, format='json')
        assert res.status_code == 201, res.data
        assert User.objects.get(username='09120000002').role == User.Role.MANAGER

    def test_teacher_code_stays_teacher(self):
        org = _active_org()
        code = _code(org, InvitationCode.TargetRole.TEACHER)

        res = APIClient().post(REDEEM, {
            'code': code.code, 'username': '09120000003', 'password': STRONG,
        }, format='json')
        assert res.status_code == 201, res.data
        assert User.objects.get(username='09120000003').role == User.Role.TEACHER

    def test_student_code_stays_student(self):
        org = _active_org()
        code = _code(org, InvitationCode.TargetRole.STUDENT)

        res = APIClient().post(REDEEM, {
            'code': code.code, 'username': '09120000005', 'password': STRONG,
        }, format='json')
        assert res.status_code == 201, res.data
        assert User.objects.get(username='09120000005').role == User.Role.STUDENT

    def test_manager_is_not_a_teacher_and_cannot_teach(self):
        """A redeemed org manager is role=MANAGER and is rejected from
        teacher-only endpoints — they manage the org, they do not teach."""
        org = _active_org()
        code = _code(org, InvitationCode.TargetRole.ADMIN)

        res = APIClient().post(REDEEM, {
            'code': code.code, 'username': '09120000004', 'password': STRONG,
        }, format='json')
        assert res.status_code == 201, res.data
        access = res.data['access']

        user = User.objects.get(username='09120000004')
        assert user.role == User.Role.MANAGER

        mgr = APIClient()
        mgr.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        # Teacher-only endpoint (IsTeacherUser) must reject the manager.
        assert mgr.get('/api/classes/teacher/students/').status_code == 403
