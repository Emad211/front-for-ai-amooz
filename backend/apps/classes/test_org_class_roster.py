"""Org class roster is driven by the linked study group (Part B).

An *organization* class enrolls exactly its study group's ACTIVE students, and a
teacher cannot hand-invite arbitrary students into it — the manager owns the
roster via the group. Personal (freelancer) classes keep the open phone-invite.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession, ClassInvitation
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    StudyGroup,
    StudyGroupMembership,
    StudyGroupTeacher,
)

User = get_user_model()
STRUCT = '{"root_object": {"title": "x"}, "outline": []}'


def _client(user) -> APIClient:
    token = str(RefreshToken.for_user(user).access_token)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return c


def _phones(session) -> set[str]:
    return set(ClassInvitation.objects.filter(session=session).values_list('phone', flat=True))


@pytest.mark.django_db
class TestOrgClassRoster:
    def _setup(self):
        org = Organization.objects.create(
            name='S', slug='s', student_capacity=100,
            subscription_status=Organization.SubscriptionStatus.ACTIVE,
        )
        manager = User.objects.create_user(username='mgr', password='p', role=User.Role.MANAGER)
        OrganizationMembership.objects.create(
            user=manager, organization=org,
            org_role=OrganizationMembership.OrgRole.ADMIN,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        )
        teacher = User.objects.create_user(username='tch', password='p', role=User.Role.TEACHER)
        OrganizationMembership.objects.create(
            user=teacher, organization=org,
            org_role=OrganizationMembership.OrgRole.TEACHER,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        )
        s1 = User.objects.create_user(username='s1', role=User.Role.STUDENT, phone='09120000001')
        s2 = User.objects.create_user(username='s2', role=User.Role.STUDENT, phone='09120000002')
        for s in (s1, s2):
            OrganizationMembership.objects.create(
                user=s, organization=org,
                org_role=OrganizationMembership.OrgRole.STUDENT,
                status=OrganizationMembership.MemberStatus.ACTIVE,
            )
        group = StudyGroup.objects.create(organization=org, name='G', created_by=manager)
        StudyGroupTeacher.objects.create(study_group=group, teacher=teacher, assigned_by=manager)
        StudyGroupMembership.objects.create(study_group=group, student=s1, added_by=manager)
        return org, manager, teacher, s1, s2, group

    def _org_class(self, teacher, org, group):
        return ClassCreationSession.objects.create(
            teacher=teacher, title='c', description='',
            source_file=SimpleUploadedFile('a.ogg', b'x', content_type='audio/ogg'),
            source_mime_type='audio/ogg', source_original_name='a.ogg',
            status=ClassCreationSession.Status.STRUCTURED,
            structure_json=STRUCT,
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
            organization=org, study_group=group,
        )

    def test_publish_enrolls_group_students(self):
        org, manager, teacher, s1, s2, group = self._setup()
        session = self._org_class(teacher, org, group)

        res = _client(teacher).post(f'/api/classes/creation-sessions/{session.id}/publish/')

        assert res.status_code == 200, res.content
        assert _phones(session) == {'09120000001'}  # only the group's active student

    def test_add_student_to_group_syncs_class(self):
        org, manager, teacher, s1, s2, group = self._setup()
        session = self._org_class(teacher, org, group)
        _client(teacher).post(f'/api/classes/creation-sessions/{session.id}/publish/')

        res = _client(manager).post(
            f'/api/organizations/{org.id}/study-groups/{group.id}/students/',
            {'student_id': s2.id}, format='json',
        )

        assert res.status_code == 201, res.content
        assert _phones(session) == {'09120000001', '09120000002'}

    def test_remove_student_from_group_prunes_invite(self):
        org, manager, teacher, s1, s2, group = self._setup()
        StudyGroupMembership.objects.create(study_group=group, student=s2, added_by=manager)
        session = self._org_class(teacher, org, group)
        _client(teacher).post(f'/api/classes/creation-sessions/{session.id}/publish/')
        assert _phones(session) == {'09120000001', '09120000002'}

        res = _client(manager).delete(
            f'/api/organizations/{org.id}/study-groups/{group.id}/students/{s1.id}/'
        )

        assert res.status_code == 204, res.content
        assert _phones(session) == {'09120000002'}  # s1 pruned

    def test_teacher_cannot_manual_invite_org_class(self):
        org, manager, teacher, s1, s2, group = self._setup()
        session = self._org_class(teacher, org, group)

        res = _client(teacher).post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            {'phones': ['09129999999']}, format='json',
        )

        assert res.status_code == 403, res.content
        assert not ClassInvitation.objects.filter(session=session, phone='09129999999').exists()

    def test_teacher_can_manual_invite_personal_class(self):
        org, manager, teacher, s1, s2, group = self._setup()
        personal = ClassCreationSession.objects.create(
            teacher=teacher, title='p', description='',
            source_file=SimpleUploadedFile('a.ogg', b'x', content_type='audio/ogg'),
            source_mime_type='audio/ogg', source_original_name='a.ogg',
            status=ClassCreationSession.Status.STRUCTURED, structure_json=STRUCT,
        )  # no organization → freelancer class

        res = _client(teacher).post(
            f'/api/classes/creation-sessions/{personal.id}/invites/',
            {'phones': ['09129999999']}, format='json',
        )

        assert res.status_code == 200, res.content
        assert ClassInvitation.objects.filter(session=personal, phone='09129999999').exists()

    def test_teacher_cannot_delete_org_class_invite(self):
        org, manager, teacher, s1, s2, group = self._setup()
        session = self._org_class(teacher, org, group)
        _client(teacher).post(f'/api/classes/creation-sessions/{session.id}/publish/')
        invite = ClassInvitation.objects.filter(session=session).first()
        assert invite is not None

        res = _client(teacher).delete(
            f'/api/classes/creation-sessions/{session.id}/invites/{invite.id}/'
        )

        assert res.status_code == 403, res.content
        assert ClassInvitation.objects.filter(id=invite.id).exists()
