"""Phone-based passwordless org-student onboarding + idempotent returning login.

Org *student* codes now follow the same identity model as class-invite students:
``code`` + ``phone`` creates (or logs in) a STUDENT account with no password.
This is the discoverable path for org students and the prerequisite for syncing a
study group's roster into a class (Part B). admin/deputy/teacher codes are
unaffected — they still create credentialed accounts.
"""

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.organizations.models import (
    InvitationCode,
    Organization,
    OrganizationMembership,
)

User = get_user_model()
REDEEM_URL = '/api/organizations/redeem-code/'
PHONE = '09120000001'


def _active_org(**kw):
    defaults = dict(
        subscription_status=Organization.SubscriptionStatus.ACTIVE,
        student_capacity=100, owner=None,
    )
    defaults.update(kw)
    return baker.make('organizations.Organization', **defaults)


def _student_code(org, **kw):
    defaults = dict(
        organization=org, target_role=InvitationCode.TargetRole.STUDENT,
        max_uses=100, use_count=0, is_active=True, expires_at=None,
    )
    defaults.update(kw)
    return baker.make('organizations.InvitationCode', **defaults)


@pytest.mark.django_db
class TestStudentPhoneRedeem:
    def test_phone_passwordless_join_creates_student(self):
        org = _active_org()
        code = _student_code(org)

        resp = APIClient().post(
            REDEEM_URL,
            {'code': code.code, 'phone': PHONE, 'first_name': 'سارا', 'last_name': 'رضایی'},
            format='json',
        )

        assert resp.status_code == 201, resp.content
        assert 'access' in resp.data and 'refresh' in resp.data
        u = User.objects.get(phone=PHONE, role=User.Role.STUDENT)
        assert not u.has_usable_password()   # passwordless
        assert u.first_name == 'سارا'
        assert OrganizationMembership.objects.filter(
            user=u, organization=org, org_role='student',
        ).exists()
        code.refresh_from_db()
        assert code.use_count == 1

    def test_returning_phone_is_idempotent_login(self):
        org = _active_org()
        code = _student_code(org)
        c = APIClient()

        first = c.post(REDEEM_URL, {'code': code.code, 'phone': PHONE}, format='json')
        assert first.status_code == 201, first.content

        # Same phone again → a LOGIN, not a second seat.
        second = c.post(REDEEM_URL, {'code': code.code, 'phone': PHONE}, format='json')
        assert second.status_code == 200, second.content
        assert 'access' in second.data
        assert OrganizationMembership.objects.filter(
            organization=org, org_role='student',
        ).count() == 1
        code.refresh_from_db()
        assert code.use_count == 1  # not double-counted

    def test_returning_phone_not_blocked_by_full_capacity(self):
        org = _active_org(student_capacity=1)
        code = _student_code(org)
        c = APIClient()

        assert c.post(
            REDEEM_URL, {'code': code.code, 'phone': PHONE}, format='json',
        ).status_code == 201
        assert org.is_at_capacity  # the single seat is taken by this student

        # The returning student can still log in even though the org is full.
        again = c.post(REDEEM_URL, {'code': code.code, 'phone': PHONE}, format='json')
        assert again.status_code == 200, again.content

    def test_new_phone_blocked_at_capacity(self):
        org = _active_org(student_capacity=1)
        filler = baker.make('accounts.User', role=User.Role.STUDENT, phone='09120000099')
        baker.make(
            'organizations.OrganizationMembership', user=filler, organization=org,
            org_role=OrganizationMembership.OrgRole.STUDENT,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        )
        code = _student_code(org)

        resp = APIClient().post(REDEEM_URL, {'code': code.code, 'phone': PHONE}, format='json')

        assert resp.status_code == 400, resp.content  # serializer pre-lock capacity
        assert not User.objects.filter(phone=PHONE).exists()

    def test_phone_ignored_for_admin_code(self):
        # Phone-passwordless is STUDENT-only; an admin code still needs credentials.
        org = _active_org()
        code = baker.make(
            'organizations.InvitationCode', organization=org,
            target_role=InvitationCode.TargetRole.ADMIN,
            max_uses=5, use_count=0, is_active=True, expires_at=None,
        )

        resp = APIClient().post(REDEEM_URL, {'code': code.code, 'phone': PHONE}, format='json')

        assert resp.status_code == 400, resp.content
        assert not User.objects.filter(phone=PHONE).exists()
