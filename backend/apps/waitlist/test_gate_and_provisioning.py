"""Waitlist as a security GATE + provisioning idempotency (security-auditor lens).

The suite already proves the happy mechanics: intake creates no account
(`test_intake`), approve issues a token / provisions an org+code and SMSes it
(`test_admin_review`, `test_sms_link`), the token is single-use / expiring
(`test_complete_registration`), and an already-decided request can't be
re-approved (409). Not duplicated.

What was NOT asserted — the attacker's view of the gate:
* a PENDING or REJECTED applicant owns no account, so they cannot obtain a JWT
  and cannot reach any authenticated endpoint (the gate holds end-to-end), and
* a double-approve must not double-provision — 409 alone isn't enough; the org,
  its invite code, and the already-SMSed registration token must all be stable.
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import InvitationCode, Organization
from apps.waitlist.models import AccessRequest

pytestmark = [pytest.mark.django_db]

INTAKE = '/api/waitlist/requests/'
ME = '/api/accounts/me/'
TOKEN = '/api/token/'


def _admin():
    return baker.make('accounts.User', role=User.Role.ADMIN, is_staff=True)


def _no_sms(monkeypatch):
    calls = []
    monkeypatch.setattr(
        'apps.waitlist.views.notify_access_request_approved',
        lambda ar, frontend_base='': calls.append(ar.pk) or True,
    )
    return calls


@pytest.mark.api
@pytest.mark.permission
class TestGateBlocksUnapprovedApplicants:
    def test_pending_applicant_has_no_account_and_cannot_get_a_token(self):
        """Submitting an intake must NOT mint credentials — the phone can't log in."""
        client = APIClient()
        resp = client.post(INTAKE, {
            'kind': 'teacher', 'full_name': 'علی احمدی',
            'phone': '09120000000', 'email': 'ali@example.com', 'expertise': 'ریاضی',
        }, format='json')
        assert resp.status_code == 201, resp.content
        assert not User.objects.filter(phone='09120000000').exists()

        # The applicant cannot authenticate by phone (there is no account yet).
        token = client.post(TOKEN, {
            'username': '09120000000', 'password': 'anything123!',
        }, format='json')
        assert token.status_code == 401
        assert 'access' not in (token.data or {})

    def test_anonymous_cannot_reach_protected_endpoint(self):
        """The gate implies deny-by-default: no token -> no protected access."""
        assert APIClient().get(ME).status_code == 401

    def test_rejected_applicant_still_has_no_account(self):
        """A rejected request never back-fills an account, so login stays impossible."""
        admin = _admin()
        ar = AccessRequest.objects.create(
            kind=AccessRequest.Kind.TEACHER, full_name='رد شده',
            phone='09120000009', status=AccessRequest.Status.PENDING,
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)
        rej = admin_client.post(
            f'/api/waitlist/admin/requests/{ar.pk}/reject/',
            {'reason': 'ناقص'}, format='json',
        )
        assert rej.status_code == 200
        assert not User.objects.filter(phone='09120000009').exists()
        token = APIClient().post(TOKEN, {
            'username': '09120000009', 'password': 'anything123!',
        }, format='json')
        assert token.status_code == 401


@pytest.mark.integration
class TestApprovalProvisioningIsIdempotent:
    def test_double_approve_org_does_not_double_provision(self, monkeypatch):
        _no_sms(monkeypatch)
        ar = AccessRequest.objects.create(
            kind=AccessRequest.Kind.ORGANIZATION, full_name='مدیر مدرسه',
            phone='09120000001', org_name='دبیرستان البرز', city='تهران',
            expected_students=250, status=AccessRequest.Status.PENDING,
        )
        client = APIClient()
        client.force_authenticate(user=_admin())

        first = client.post(f'/api/waitlist/admin/requests/{ar.pk}/approve/')
        assert first.status_code == 200, first.content
        ar.refresh_from_db()
        org_id = ar.created_organization_id
        token_after_first = ar.registration_token
        assert org_id is not None
        org_count = Organization.objects.count()
        code_count = InvitationCode.objects.count()

        # A second approve must be refused AND must not provision a second org,
        # a second code, or rotate the token already SMSed to the applicant.
        second = client.post(f'/api/waitlist/admin/requests/{ar.pk}/approve/')
        assert second.status_code == 409
        ar.refresh_from_db()
        assert Organization.objects.count() == org_count
        assert InvitationCode.objects.count() == code_count
        assert ar.created_organization_id == org_id
        assert ar.registration_token == token_after_first
