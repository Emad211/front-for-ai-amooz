"""Regression tests for invite-redeem limit enforcement (max_uses + capacity).

These guard the data-integrity fix where the validity/capacity checks now run
UNDER the select_for_update row lock instead of only in the serializer pre-check.
(True row-level serialization needs Postgres; sqlite makes select_for_update a
no-op, so these assert the logical guards rather than thread interleaving.)
"""
import pytest
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
URL = '/api/organizations/redeem-code/'


def _student_code(org, **kw):
    return InvitationCode.objects.create(
        organization=org, target_role=InvitationCode.TargetRole.STUDENT, **kw
    )


def test_redeem_rejected_when_capacity_full():
    org = Organization.objects.create(name='O', slug='o', student_capacity=1)
    # Fill the single seat with an active student member.
    s1 = User.objects.create_user(username='s1', password='p', role=User.Role.STUDENT)
    OrganizationMembership.objects.create(
        organization=org, user=s1,
        org_role=OrganizationMembership.OrgRole.STUDENT,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    )
    code = _student_code(org, max_uses=30)

    res = APIClient().post(URL, {
        'code': code.code, 'phone': '09120000001', 'password': STRONG,
    }, format='json')

    # Rejected (the custom exception handler genericizes the field message, so
    # assert the BEHAVIOR rather than the masked text).
    assert res.status_code == 400
    # No orphan account / membership created.
    assert not User.objects.filter(username='09120000001').exists()
    assert OrganizationMembership.objects.filter(
        organization=org, org_role=OrganizationMembership.OrgRole.STUDENT,
    ).count() == 1


def test_redeem_succeeds_under_capacity():
    org = Organization.objects.create(name='O', slug='o', student_capacity=5)
    code = _student_code(org, max_uses=30)

    res = APIClient().post(URL, {
        'code': code.code, 'phone': '09120000002', 'password': STRONG,
    }, format='json')

    assert res.status_code in (200, 201), res.data
    assert OrganizationMembership.objects.filter(
        organization=org, org_role=OrganizationMembership.OrgRole.STUDENT,
    ).count() == 1
    code.refresh_from_db()
    assert code.use_count == 1


def test_redeem_rejected_when_uses_exhausted():
    org = Organization.objects.create(name='O', slug='o', student_capacity=100)
    code = _student_code(org, max_uses=1, use_count=1)  # already exhausted

    res = APIClient().post(URL, {
        'code': code.code, 'phone': '09120000003', 'password': STRONG,
    }, format='json')

    assert res.status_code == 400
    assert not User.objects.filter(username='09120000003').exists()
