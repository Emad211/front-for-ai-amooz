"""Regression tests for the TOCTOU guard in invite-code redemption (HIGH fix).

The validity/capacity checks used to run ONLY in the serializer, on an unlocked
read taken before the row was locked — so two concurrent redemptions could both
pass and both create a membership (e.g. a single-use admin code minting two
MANAGER accounts). The view now re-validates the freshly-locked row.

We can't exercise a real DB race in a unit test, so we simulate the TOCTOU
window by neutralizing the serializer pre-check (monkeypatch) and asserting the
view's own under-lock guard rejects an exhausted / over-capacity code.
"""

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.organizations.models import InvitationCode, Organization, OrganizationMembership
from apps.organizations.serializers import RedeemInvitationSerializer

User = get_user_model()
REDEEM_URL = '/api/organizations/redeem-code/'
PASSWORD = 'StrongPass123!@#'


def _active_org(**kw):
    defaults = dict(
        subscription_status=Organization.SubscriptionStatus.ACTIVE,
        student_capacity=100, owner=None,
    )
    defaults.update(kw)
    return baker.make('organizations.Organization', **defaults)


def _bypass_serializer(monkeypatch):
    # Make the serializer pre-check a no-op (returns the code), simulating the
    # stale "passed before the row was locked" state.
    monkeypatch.setattr(
        RedeemInvitationSerializer, 'validate_code', lambda self, v: v.strip().upper()
    )


@pytest.mark.django_db
def test_redeem_reenforces_max_uses_under_lock(monkeypatch):
    _bypass_serializer(monkeypatch)
    org = _active_org()
    baker.make(
        'organizations.InvitationCode', organization=org,
        target_role=InvitationCode.TargetRole.ADMIN, code='ADMINCODE',
        max_uses=1, use_count=1, is_active=True, expires_at=None,
    )

    resp = APIClient().post(
        REDEEM_URL, {'code': 'ADMINCODE', 'username': 'newmgr', 'password': PASSWORD},
        format='json',
    )

    assert resp.status_code == 409, resp.content
    assert not User.objects.filter(username='newmgr').exists()
    assert OrganizationMembership.objects.filter(organization=org).count() == 0


@pytest.mark.django_db
def test_redeem_reenforces_capacity_under_lock(monkeypatch):
    _bypass_serializer(monkeypatch)
    org = _active_org(student_capacity=1)
    filler = baker.make('accounts.User')
    baker.make(
        'organizations.OrganizationMembership', user=filler, organization=org,
        org_role=OrganizationMembership.OrgRole.STUDENT,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    )
    baker.make(
        'organizations.InvitationCode', organization=org,
        target_role=InvitationCode.TargetRole.STUDENT, code='STUCODE',
        max_uses=100, use_count=0, is_active=True, expires_at=None,
    )

    resp = APIClient().post(
        REDEEM_URL, {'code': 'STUCODE', 'username': 'newstu', 'password': PASSWORD},
        format='json',
    )

    assert resp.status_code == 409, resp.content
    assert not User.objects.filter(username='newstu').exists()


@pytest.mark.django_db
def test_redeem_happy_path_still_works():
    # No bypass — full flow. A valid admin code creates a MANAGER + membership.
    org = _active_org()
    code = baker.make(
        'organizations.InvitationCode', organization=org,
        target_role=InvitationCode.TargetRole.ADMIN, code='GOODCODE',
        max_uses=1, use_count=0, is_active=True, expires_at=None,
    )

    resp = APIClient().post(
        REDEEM_URL, {'code': 'GOODCODE', 'username': 'mgr1', 'password': PASSWORD},
        format='json',
    )

    assert resp.status_code == 201, resp.content
    u = User.objects.get(username='mgr1')
    assert u.role == 'MANAGER'
    assert OrganizationMembership.objects.filter(user=u, organization=org).count() == 1
    code.refresh_from_db()
    assert code.use_count == 1
