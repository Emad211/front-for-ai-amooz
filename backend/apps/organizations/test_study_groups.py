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


@pytest.mark.django_db
class TestStudyGroupClassLink:
    def test_class_count_counts_only_class_sessions(self, org, manager):
        from apps.classes.models import ClassCreationSession

        g = baker.make(StudyGroup, organization=org, name='g1')
        baker.make(
            ClassCreationSession, teacher=manager, organization=org, study_group=g,
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
        )
        baker.make(
            ClassCreationSession, teacher=manager, organization=org, study_group=g,
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
        )
        # An exam-prep session in the same group must NOT be counted as a class.
        baker.make(
            ClassCreationSession, teacher=manager, organization=org, study_group=g,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )

        res = _auth(manager).get(LIST.format(org.id))
        assert res.status_code == 200
        row = next(r for r in res.data if r['id'] == g.id)
        assert row['classCount'] == 2


CLASSES = '/api/organizations/{}/classes/'
COSTS = '/api/organizations/{}/costs/'


@pytest.mark.django_db
class TestOrgOversightAndCosts:
    def test_classes_oversight_lists_all_teachers_classes(self, org, manager):
        from apps.classes.models import ClassCreationSession
        t1 = _member(org, OrgRole.TEACHER)
        t2 = _member(org, OrgRole.TEACHER)
        baker.make(ClassCreationSession, teacher=t1, organization=org, title='C1',
                   pipeline_type=ClassCreationSession.PipelineType.CLASS)
        baker.make(ClassCreationSession, teacher=t2, organization=org, title='C2',
                   pipeline_type=ClassCreationSession.PipelineType.CLASS)
        res = _auth(manager).get(CLASSES.format(org.id))
        assert res.status_code == 200
        assert {'C1', 'C2'} <= {c['title'] for c in res.data}

    def test_classes_oversight_forbidden_for_teacher(self, org):
        teacher = _member(org, OrgRole.TEACHER)
        assert _auth(teacher).get(CLASSES.format(org.id)).status_code == 403

    def test_costs_breakdown_is_exact_and_org_scoped(self, org, manager):
        from apps.classes.models import ClassCreationSession
        from apps.commons.models import LLMUsageLog
        t1 = _member(org, OrgRole.TEACHER)
        g = baker.make(StudyGroup, organization=org, name='G1')
        s1 = baker.make(ClassCreationSession, teacher=t1, organization=org, study_group=g,
                        pipeline_type=ClassCreationSession.PipelineType.CLASS)
        s2 = baker.make(ClassCreationSession, teacher=t1, organization=org,
                        pipeline_type=ClassCreationSession.PipelineType.CLASS)
        baker.make(LLMUsageLog, session_id=s1.id, user=t1, feature='transcription',
                   estimated_cost_toman=1000, total_tokens=100)
        baker.make(LLMUsageLog, session_id=s1.id, user=t1, feature='structure',
                   estimated_cost_toman=500, total_tokens=50)
        baker.make(LLMUsageLog, session_id=s2.id, user=t1, feature='transcription',
                   estimated_cost_toman=250, total_tokens=25)
        # Usage on a NON-org session must be excluded from the org's totals.
        other = baker.make(ClassCreationSession, teacher=t1, organization=None)
        baker.make(LLMUsageLog, session_id=other.id, user=t1, feature='transcription',
                   estimated_cost_toman=9999, total_tokens=999)

        res = _auth(manager).get(COSTS.format(org.id))
        assert res.status_code == 200
        assert res.data['total']['toman'] == 1750.0   # 1000+500+250 (NOT 9999)
        assert res.data['total']['tokens'] == 175
        assert len(res.data['byClass']) == 2
        groups = {row['studyGroupName']: row['toman'] for row in res.data['byGroup']}
        assert groups.get('G1') == 1500.0 and groups.get('بدون گروه') == 250.0
        feats = {row['feature']: row['toman'] for row in res.data['byFeature']}
        assert feats['transcription'] == 1250.0 and feats['structure'] == 500.0

    def test_costs_forbidden_for_teacher(self, org):
        teacher = _member(org, OrgRole.TEACHER)
        assert _auth(teacher).get(COSTS.format(org.id)).status_code == 403
