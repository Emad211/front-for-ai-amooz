"""Multi-tenant isolation (HIGH RISK — tenancy). security-auditor lens.

The existing suite already proves: study-group *detail* 404s across orgs
(`test_study_groups.test_cross_org_isolation`), costs exclude non-org sessions
(`test_costs_breakdown_is_exact_and_org_scoped`), an org-admin can't *manage*
another org (`tests.test_org_admin_cannot_manage_other_org`), and TEACHER/STUDENT
are forbidden from oversight endpoints.

What was NOT covered — and is the classic IDOR — is a **valid MANAGER of org A
hitting org B's endpoints**: every read/write must fail closed (403), leaking
none of org B's members / study-groups / classes / AI-cost. Plus the reverse
leak: injecting an org-B member into an org-A study group. These are the negatives
this file adds. All routes gate on ``IsOrgAdmin.check(user, org_pk)``, which is
``organization_id``-scoped, so wrong-org managers never reach the queryset.
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    StudyGroup,
)

OrgRole = OrganizationMembership.OrgRole
MStatus = OrganizationMembership.MemberStatus

pytestmark = [pytest.mark.django_db, pytest.mark.permission]

MEMBERS = '/api/organizations/{}/members/'
DASHBOARD = '/api/organizations/{}/dashboard/'
GROUPS = '/api/organizations/{}/study-groups/'
GROUP_DETAIL = '/api/organizations/{}/study-groups/{}/'
GROUP_TEACHERS = '/api/organizations/{}/study-groups/{}/teachers/'
GROUP_STUDENTS = '/api/organizations/{}/study-groups/{}/students/'
CLASSES = '/api/organizations/{}/classes/'
COSTS = '/api/organizations/{}/costs/'


def _auth(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _platform_role(org_role):
    if org_role in (OrgRole.ADMIN, OrgRole.DEPUTY):
        return User.Role.MANAGER
    if org_role == OrgRole.TEACHER:
        return User.Role.TEACHER
    return User.Role.STUDENT


def _member(org, org_role):
    user = baker.make(User, role=_platform_role(org_role))
    baker.make(
        OrganizationMembership, user=user, organization=org,
        org_role=org_role, status=MStatus.ACTIVE,
    )
    return user


@pytest.fixture
def org_a():
    return baker.make(Organization, subscription_status=Organization.SubscriptionStatus.ACTIVE)


@pytest.fixture
def org_b():
    return baker.make(Organization, subscription_status=Organization.SubscriptionStatus.ACTIVE)


@pytest.fixture
def manager_a(org_a):
    return _member(org_a, OrgRole.ADMIN)


class TestManagerCannotReadOtherOrg:
    """A valid manager of org A is a stranger to org B — every read is 403,
    even though org B holds real, seeded data (so there IS something to leak)."""

    def test_cannot_list_other_org_members(self, org_a, org_b, manager_a):
        _member(org_b, OrgRole.STUDENT)  # org B has members to hide
        res = _auth(manager_a).get(MEMBERS.format(org_b.id))
        assert res.status_code == 403

    def test_cannot_view_other_org_dashboard(self, org_a, org_b, manager_a):
        res = _auth(manager_a).get(DASHBOARD.format(org_b.id))
        assert res.status_code == 403

    def test_cannot_list_other_org_study_groups(self, org_a, org_b, manager_a):
        baker.make(StudyGroup, organization=org_b, name='b-secret')
        res = _auth(manager_a).get(GROUPS.format(org_b.id))
        assert res.status_code == 403

    def test_cannot_read_other_org_group_detail(self, org_a, org_b, manager_a):
        g = baker.make(StudyGroup, organization=org_b, name='b-secret')
        res = _auth(manager_a).get(GROUP_DETAIL.format(org_b.id, g.id))
        assert res.status_code == 403

    def test_cannot_read_other_org_classes_oversight(self, org_a, org_b, manager_a):
        from apps.classes.models import ClassCreationSession
        tb = _member(org_b, OrgRole.TEACHER)
        baker.make(ClassCreationSession, teacher=tb, organization=org_b, title='B-CLASS',
                   pipeline_type=ClassCreationSession.PipelineType.CLASS)
        res = _auth(manager_a).get(CLASSES.format(org_b.id))
        assert res.status_code == 403
        assert 'B-CLASS' not in str(res.data)  # no leak of the title

    def test_cannot_read_other_org_costs(self, org_a, org_b, manager_a):
        from apps.classes.models import ClassCreationSession
        from apps.commons.models import LLMUsageLog
        tb = _member(org_b, OrgRole.TEACHER)
        sb = baker.make(ClassCreationSession, teacher=tb, organization=org_b,
                        pipeline_type=ClassCreationSession.PipelineType.CLASS)
        baker.make(LLMUsageLog, session_id=sb.id, user=tb, feature='transcription',
                   estimated_cost_toman=1234, total_tokens=100)
        res = _auth(manager_a).get(COSTS.format(org_b.id))
        assert res.status_code == 403
        assert '1234' not in str(res.data)  # no cost leak


class TestManagerCannotWriteOtherOrg:
    """A manager of org A cannot mutate org B — create/patch/delete all 403."""

    def test_cannot_create_group_in_other_org(self, org_a, org_b, manager_a):
        res = _auth(manager_a).post(GROUPS.format(org_b.id), {'name': 'intruder'}, format='json')
        assert res.status_code == 403
        assert not StudyGroup.objects.filter(organization=org_b, name='intruder').exists()

    def test_cannot_patch_other_org_group(self, org_a, org_b, manager_a):
        g = baker.make(StudyGroup, organization=org_b, name='b1')
        res = _auth(manager_a).patch(
            GROUP_DETAIL.format(org_b.id, g.id), {'subject': 'hijacked'}, format='json',
        )
        assert res.status_code == 403
        g.refresh_from_db()
        assert g.subject != 'hijacked'

    def test_cannot_delete_other_org_group(self, org_a, org_b, manager_a):
        g = baker.make(StudyGroup, organization=org_b, name='b1')
        res = _auth(manager_a).delete(GROUP_DETAIL.format(org_b.id, g.id))
        assert res.status_code == 403
        assert StudyGroup.objects.filter(id=g.id).exists()


class TestCrossOrgMemberInjection:
    """The reverse leak: a manager of org A must not pull an org-B member into an
    org-A study group. Assignment validates org-A membership → 400, no bridge."""

    def test_cannot_assign_other_org_teacher_to_own_group(self, org_a, org_b, manager_a):
        g_a = baker.make(StudyGroup, organization=org_a, name='a-group')
        teacher_b = _member(org_b, OrgRole.TEACHER)  # member of B, NOT A
        res = _auth(manager_a).post(
            GROUP_TEACHERS.format(org_a.id, g_a.id), {'teacher_id': teacher_b.id}, format='json',
        )
        assert res.status_code == 400

    def test_cannot_add_other_org_student_to_own_group(self, org_a, org_b, manager_a):
        g_a = baker.make(StudyGroup, organization=org_a, name='a-group')
        student_b = _member(org_b, OrgRole.STUDENT)
        res = _auth(manager_a).post(
            GROUP_STUDENTS.format(org_a.id, g_a.id), {'student_id': student_b.id}, format='json',
        )
        assert res.status_code == 400
