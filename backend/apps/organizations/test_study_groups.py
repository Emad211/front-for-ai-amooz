"""Tests for study groups (گروه آموزشی).

Manager CRUD + teacher/student assignment (org-membership-validated) + the
teacher-facing my-study-groups view + cross-org isolation.
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
    StudyGroupMembership,
    StudyGroupTeacher,
)

OrgRole = OrganizationMembership.OrgRole
MStatus = OrganizationMembership.MemberStatus

LIST = '/api/organizations/{}/study-groups/'
DETAIL = '/api/organizations/{}/study-groups/{}/'
TEACHERS = '/api/organizations/{}/study-groups/{}/teachers/'
TEACHER_RM = '/api/organizations/{}/study-groups/{}/teachers/{}/'
STUDENTS = '/api/organizations/{}/study-groups/{}/students/'
STUDENT_RM = '/api/organizations/{}/study-groups/{}/students/{}/'
MINE = '/api/organizations/{}/my-study-groups/'


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
def org():
    return baker.make(Organization, subscription_status=Organization.SubscriptionStatus.ACTIVE)


@pytest.fixture
def manager(org):
    return _member(org, OrgRole.ADMIN)


@pytest.mark.django_db
class TestStudyGroupCRUD:
    def test_manager_creates_group(self, org, manager):
        res = _auth(manager).post(
            LIST.format(org.id),
            {'name': 'دهم ریاضی', 'grade_label': 'دهم', 'subject': 'ریاضی'},
            format='json',
        )
        assert res.status_code == 201, res.data
        assert res.data['name'] == 'دهم ریاضی'
        assert res.data['studentCount'] == 0 and res.data['teacherCount'] == 0
        assert StudyGroup.objects.filter(organization=org, name='دهم ریاضی').exists()

    def test_duplicate_name_rejected(self, org, manager):
        baker.make(StudyGroup, organization=org, name='دهم ریاضی')
        res = _auth(manager).post(LIST.format(org.id), {'name': 'دهم ریاضی'}, format='json')
        assert res.status_code == 400

    def test_non_admin_cannot_create_or_list(self, org):
        teacher = _member(org, OrgRole.TEACHER)
        assert _auth(teacher).post(LIST.format(org.id), {'name': 'x'}, format='json').status_code == 403
        assert _auth(teacher).get(LIST.format(org.id)).status_code == 403

    def test_list_returns_groups(self, org, manager):
        baker.make(StudyGroup, organization=org, name='g1')
        baker.make(StudyGroup, organization=org, name='g2')
        res = _auth(manager).get(LIST.format(org.id))
        assert res.status_code == 200
        assert len(res.data) == 2

    def test_update_and_delete(self, org, manager):
        g = baker.make(StudyGroup, organization=org, name='g1')
        res = _auth(manager).patch(DETAIL.format(org.id, g.id), {'subject': 'فیزیک'}, format='json')
        assert res.status_code == 200 and res.data['subject'] == 'فیزیک'
        res = _auth(manager).delete(DETAIL.format(org.id, g.id))
        assert res.status_code == 204
        assert not StudyGroup.objects.filter(id=g.id).exists()

    def test_cross_org_isolation(self, org, manager):
        other = baker.make(Organization)
        g = baker.make(StudyGroup, organization=other, name='x')
        # The group belongs to `other`, so under `org`'s path it is invisible.
        assert _auth(manager).get(DETAIL.format(org.id, g.id)).status_code == 404


@pytest.mark.django_db
class TestStudyGroupAssignment:
    def test_assign_teacher_requires_org_teacher_membership(self, org, manager):
        g = baker.make(StudyGroup, organization=org, name='g1')
        stranger = baker.make(User, role=User.Role.TEACHER)  # not an org member
        res = _auth(manager).post(TEACHERS.format(org.id, g.id), {'teacher_id': stranger.id}, format='json')
        assert res.status_code == 400

    def test_assign_and_remove_teacher(self, org, manager):
        g = baker.make(StudyGroup, organization=org, name='g1')
        teacher = _member(org, OrgRole.TEACHER)
        res = _auth(manager).post(TEACHERS.format(org.id, g.id), {'teacher_id': teacher.id}, format='json')
        assert res.status_code == 201, res.data
        assert res.data['teacherCount'] == 1
        assert StudyGroupTeacher.objects.filter(study_group=g, teacher=teacher).exists()

        res = _auth(manager).delete(TEACHER_RM.format(org.id, g.id, teacher.id))
        assert res.status_code == 204
        assert not StudyGroupTeacher.objects.filter(study_group=g, teacher=teacher).exists()

    def test_add_student_requires_org_student_membership(self, org, manager):
        g = baker.make(StudyGroup, organization=org, name='g1')
        stranger = baker.make(User, role=User.Role.STUDENT)
        res = _auth(manager).post(STUDENTS.format(org.id, g.id), {'student_id': stranger.id}, format='json')
        assert res.status_code == 400

    def test_add_and_remove_student(self, org, manager):
        g = baker.make(StudyGroup, organization=org, name='g1')
        student = _member(org, OrgRole.STUDENT)
        res = _auth(manager).post(STUDENTS.format(org.id, g.id), {'student_id': student.id}, format='json')
        assert res.status_code == 201, res.data
        assert res.data['studentCount'] == 1
        assert any(s['id'] == student.id for s in res.data['students'])

        res = _auth(manager).delete(STUDENT_RM.format(org.id, g.id, student.id))
        assert res.status_code == 204
        assert not StudyGroupMembership.objects.filter(study_group=g, student=student).exists()


@pytest.mark.django_db
class TestMyStudyGroups:
    def test_teacher_sees_only_assigned_groups(self, org, manager):
        teacher = _member(org, OrgRole.TEACHER)
        g1 = baker.make(StudyGroup, organization=org, name='g1')
        baker.make(StudyGroup, organization=org, name='g2')
        baker.make(StudyGroupTeacher, study_group=g1, teacher=teacher)

        res = _auth(teacher).get(MINE.format(org.id))
        assert res.status_code == 200
        assert {g['id'] for g in res.data} == {g1.id}

    def test_non_member_forbidden(self, org):
        stranger = baker.make(User, role=User.Role.TEACHER)
        assert _auth(stranger).get(MINE.format(org.id)).status_code == 403
