"""S2 — ``GET /api/advisory/subjects/`` contract and negative matrix.

The endpoint looks trivial (list a table) but it is the first advisory route, so
it is where the tenancy shape gets pinned: globals for everyone, org-private
subjects only for an **active advisor of an active-subscription org**. Every
"nearly authorized" variant below is a way that gate could silently open.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import Subject
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()
OrgRole = OrganizationMembership.OrgRole
MStatus = OrganizationMembership.MemberStatus

pytestmark = [pytest.mark.django_db, pytest.mark.api]

URL = '/api/advisory/subjects/'


def _user(role, username):
    return baker.make(User, username=username, role=role)


def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor_of(org, *, username='adv', status=MStatus.ACTIVE, org_role=OrgRole.ADVISOR):
    advisor = _user(User.Role.ADVISOR, username)
    baker.make(
        OrganizationMembership,
        user=advisor,
        organization=org,
        org_role=org_role,
        status=status,
    )
    return advisor


def _names(response) -> list[str]:
    return [item['name'] for item in response.data]


# ── permission matrix ────────────────────────────────────────────────────────

@pytest.mark.permission
def test_anonymous_is_rejected():
    assert APIClient().get(URL).status_code == 401


@pytest.mark.permission
@pytest.mark.parametrize('role', [
    User.Role.STUDENT,
    User.Role.TEACHER,
    User.Role.MANAGER,
    User.Role.ADMIN,
])
def test_every_other_role_is_forbidden(role):
    """Including ADMIN: a platform admin curates the catalog in Django admin, they
    do not consume an advisor's picker (IsAdvisorUser excludes them on purpose)."""
    client = _auth(_user(role, f'u-{role}'))
    assert client.get(URL).status_code == 403


def test_advisor_is_allowed():
    client = _auth(_user(User.Role.ADVISOR, 'adv'))
    assert client.get(URL).status_code == 200


# ── wire shape ───────────────────────────────────────────────────────────────

def test_response_is_a_plain_array_not_a_paginated_envelope():
    """Pagination is global at PAGE_SIZE; a picker that truncates is a real bug."""
    for i in range(60):
        Subject.objects.create(name=f'درس {i}')

    response = _auth(_user(User.Role.ADVISOR, 'adv')).get(URL)

    assert response.status_code == 200
    assert isinstance(response.data, list)
    assert len(response.data) == 60


def test_serialized_fields_are_camel_case_and_hide_the_internal_key():
    Subject.objects.create(name='ریاضی ۱')
    response = _auth(_user(User.Role.ADVISOR, 'adv')).get(URL)

    item = response.data[0]
    assert set(item) == {
        'id', 'name', 'organizationId', 'organizationName', 'isGlobal', 'isActive',
    }
    assert item['isGlobal'] is True
    assert item['organizationId'] is None


def test_globals_are_listed_before_org_private_subjects():
    """PG sorts NULLs last in ASC, so this ordering needs nulls_first explicitly."""
    org = baker.make(Organization, slug='org-a')
    advisor = _advisor_of(org)
    Subject.objects.create(name='ی‌درس سازمانی', organization=org)
    Subject.objects.create(name='الف‌درس سراسری')

    names = _names(_auth(advisor).get(URL))
    assert names == ['الف‌درس سراسری', 'ی‌درس سازمانی']


# ── visibility ───────────────────────────────────────────────────────────────

def test_global_subjects_are_visible_without_any_membership():
    Subject.objects.create(name='ریاضی ۱')
    assert _names(_auth(_user(User.Role.ADVISOR, 'adv')).get(URL)) == ['ریاضی ۱']


def test_inactive_subjects_are_hidden():
    Subject.objects.create(name='ریاضی ۱')
    Subject.objects.create(name='درس بازنشسته', is_active=False)
    assert _names(_auth(_user(User.Role.ADVISOR, 'adv')).get(URL)) == ['ریاضی ۱']


@pytest.mark.permission
def test_advisor_of_org_a_never_sees_org_b_subjects():
    org_a = baker.make(Organization, slug='org-a')
    org_b = baker.make(Organization, slug='org-b')
    advisor = _advisor_of(org_a)
    Subject.objects.create(name='درس آ', organization=org_a)
    Subject.objects.create(name='درس ب', organization=org_b)

    assert _names(_auth(advisor).get(URL)) == ['درس آ']


@pytest.mark.permission
def test_suspended_membership_loses_org_subjects_immediately():
    """Membership is checked live — no signal fires on suspension."""
    org = baker.make(Organization, slug='org-a')
    advisor = _advisor_of(org, status=MStatus.SUSPENDED)
    Subject.objects.create(name='درس سازمانی', organization=org)

    assert _names(_auth(advisor).get(URL)) == []


@pytest.mark.permission
@pytest.mark.parametrize('org_role', [OrgRole.STUDENT, OrgRole.TEACHER, OrgRole.ADMIN])
def test_non_advisor_membership_grants_no_org_subjects(org_role):
    """Being *in* an org is not the same as advising for it."""
    org = baker.make(Organization, slug='org-a')
    advisor = _advisor_of(org, org_role=org_role)
    Subject.objects.create(name='درس سازمانی', organization=org)

    assert _names(_auth(advisor).get(URL)) == []


@pytest.mark.permission
@pytest.mark.parametrize('subscription', [
    Organization.SubscriptionStatus.EXPIRED,
    Organization.SubscriptionStatus.SUSPENDED,
])
def test_non_active_subscription_hides_org_subjects(subscription):
    org = baker.make(Organization, slug='org-a', subscription_status=subscription)
    advisor = _advisor_of(org)
    Subject.objects.create(name='درس سازمانی', organization=org)
    Subject.objects.create(name='درس سراسری')

    assert _names(_auth(advisor).get(URL)) == ['درس سراسری']


def test_membership_in_two_orgs_unions_both_catalogs():
    org_a = baker.make(Organization, slug='org-a')
    org_b = baker.make(Organization, slug='org-b')
    advisor = _advisor_of(org_a)
    baker.make(
        OrganizationMembership,
        user=advisor,
        organization=org_b,
        org_role=OrgRole.ADVISOR,
        status=MStatus.ACTIVE,
    )
    Subject.objects.create(name='درس آ', organization=org_a)
    Subject.objects.create(name='درس ب', organization=org_b)
    Subject.objects.create(name='درس سراسری')

    assert sorted(_names(_auth(advisor).get(URL))) == sorted(
        ['درس سراسری', 'درس آ', 'درس ب']
    )
