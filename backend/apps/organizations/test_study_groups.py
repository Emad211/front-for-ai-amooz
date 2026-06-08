"""Tests for study groups (cohorts) — models, permissions, roster, course link."""
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    StudyGroup,
    StudyGroupMembership,
    StudyGroupTeacher,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _user(username, role=User.Role.TEACHER, **kw):
    return User.objects.create_user(username=username, password='p', role=role, **kw)


def _org(name='Org', slug='org'):
    return Organization.objects.create(name=name, slug=slug)


def _member(org, user, org_role):
    return OrganizationMembership.objects.create(organization=org, user=user, org_role=org_role)


def _admin_client(org):
    admin = _user('admin1')
    _member(org, admin, OrganizationMembership.OrgRole.ADMIN)
    client = APIClient()
    client.force_authenticate(user=admin)
    return client, admin


def _base(org):
    return f'/api/organizations/{org.id}/study-groups/'


# ---------------------------------------------------------------------------
# create / permissions
# ---------------------------------------------------------------------------

def test_org_admin_can_create_study_group():
    org = _org()
    client, _ = _admin_client(org)
    res = client.post(_base(org), {'name': 'دهم ریاضی', 'grade_label': 'دهم', 'subject': 'ریاضی'}, format='json')
    assert res.status_code == 201
    assert res.data['name'] == 'دهم ریاضی'
    assert res.data['studentCount'] == 0 and res.data['teacherCount'] == 0
    assert StudyGroup.objects.filter(organization=org, name='دهم ریاضی').exists()


def test_non_admin_cannot_create_study_group():
    org = _org()
    outsider = _user('rando')
    _member(org, outsider, OrganizationMembership.OrgRole.TEACHER)  # plain teacher, not admin
    client = APIClient()
    client.force_authenticate(user=outsider)
    res = client.post(_base(org), {'name': 'X'}, format='json')
    assert res.status_code == 403


def test_duplicate_group_name_rejected():
    org = _org()
    client, _ = _admin_client(org)
    client.post(_base(org), {'name': 'دهم ریاضی'}, format='json')
    res = client.post(_base(org), {'name': 'دهم ریاضی'}, format='json')
    assert res.status_code == 400


def test_list_returns_counts():
    org = _org()
    client, _ = _admin_client(org)
    g = StudyGroup.objects.create(organization=org, name='G')
    student = _user('s1', role=User.Role.STUDENT)
    _member(org, student, OrganizationMembership.OrgRole.STUDENT)
    StudyGroupMembership.objects.create(study_group=g, student=student)
    res = client.get(_base(org))
    assert res.status_code == 200
    row = next(r for r in res.data if r['id'] == g.id)
    assert row['studentCount'] == 1


# ---------------------------------------------------------------------------
# teacher assignment
# ---------------------------------------------------------------------------

def test_assign_org_teacher_to_group():
    org = _org()
    client, _ = _admin_client(org)
    g = StudyGroup.objects.create(organization=org, name='G')
    teacher = _user('teach', role=User.Role.TEACHER)
    _member(org, teacher, OrganizationMembership.OrgRole.TEACHER)
    res = client.post(f'{_base(org)}{g.id}/teachers/', {'user_id': teacher.id}, format='json')
    assert res.status_code == 200
    assert StudyGroupTeacher.objects.filter(study_group=g, teacher=teacher).exists()
    assert res.data['teacherCount'] == 1


def test_cannot_assign_non_member_as_teacher():
    org = _org()
    client, _ = _admin_client(org)
    g = StudyGroup.objects.create(organization=org, name='G')
    stranger = _user('stranger')  # not an org member
    res = client.post(f'{_base(org)}{g.id}/teachers/', {'user_id': stranger.id}, format='json')
    assert res.status_code == 400


def test_unassign_teacher():
    org = _org()
    client, _ = _admin_client(org)
    g = StudyGroup.objects.create(organization=org, name='G')
    teacher = _user('teach', role=User.Role.TEACHER)
    _member(org, teacher, OrganizationMembership.OrgRole.TEACHER)
    StudyGroupTeacher.objects.create(study_group=g, teacher=teacher)
    res = client.delete(f'{_base(org)}{g.id}/teachers/{teacher.id}/')
    assert res.status_code == 204
    assert not StudyGroupTeacher.objects.filter(study_group=g, teacher=teacher).exists()


# ---------------------------------------------------------------------------
# student membership
# ---------------------------------------------------------------------------

def test_add_org_student_to_group():
    org = _org()
    client, _ = _admin_client(org)
    g = StudyGroup.objects.create(organization=org, name='G')
    student = _user('s1', role=User.Role.STUDENT)
    _member(org, student, OrganizationMembership.OrgRole.STUDENT)
    res = client.post(f'{_base(org)}{g.id}/students/', {'user_id': student.id}, format='json')
    assert res.status_code == 200
    assert StudyGroupMembership.objects.filter(study_group=g, student=student).exists()


def test_cannot_add_teacher_as_student():
    org = _org()
    client, _ = _admin_client(org)
    g = StudyGroup.objects.create(organization=org, name='G')
    teacher = _user('teach', role=User.Role.TEACHER)
    _member(org, teacher, OrganizationMembership.OrgRole.TEACHER)
    res = client.post(f'{_base(org)}{g.id}/students/', {'user_id': teacher.id}, format='json')
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# detail roster + course link + assigned-teacher read access
# ---------------------------------------------------------------------------

def test_detail_includes_roster_and_courses():
    org = _org()
    client, _ = _admin_client(org)
    g = StudyGroup.objects.create(organization=org, name='G')
    teacher = _user('teach', role=User.Role.TEACHER)
    _member(org, teacher, OrganizationMembership.OrgRole.TEACHER)
    StudyGroupTeacher.objects.create(study_group=g, teacher=teacher)
    student = _user('s1', role=User.Role.STUDENT)
    _member(org, student, OrganizationMembership.OrgRole.STUDENT)
    StudyGroupMembership.objects.create(study_group=g, student=student)
    course = ClassCreationSession.objects.create(
        teacher=teacher, title='ریاضی فصل ۱', organization=org, study_group=g,
        source_file=SimpleUploadedFile('a.ogg', b'x', content_type='audio/ogg'),
        source_mime_type='audio/ogg', source_original_name='a.ogg',
        status=ClassCreationSession.Status.RECAPPED,
    )
    res = client.get(f'{_base(org)}{g.id}/')
    assert res.status_code == 200
    assert len(res.data['students']) == 1
    assert res.data['classCount'] == 1
    assert any(c['id'] == course.id for c in res.data['courses'])


def test_assigned_teacher_can_read_group_but_outsider_cannot():
    org = _org()
    _admin_client(org)  # create admin (unused client)
    g = StudyGroup.objects.create(organization=org, name='G')
    teacher = _user('teach', role=User.Role.TEACHER)
    _member(org, teacher, OrganizationMembership.OrgRole.TEACHER)
    StudyGroupTeacher.objects.create(study_group=g, teacher=teacher)

    tclient = APIClient(); tclient.force_authenticate(user=teacher)
    assert tclient.get(f'{_base(org)}{g.id}/').status_code == 200

    outsider = _user('out', role=User.Role.TEACHER)
    oclient = APIClient(); oclient.force_authenticate(user=outsider)
    assert oclient.get(f'{_base(org)}{g.id}/').status_code == 403


def test_my_study_groups_lists_only_taught_groups():
    org = _org()
    client, _ = _admin_client(org)
    g1 = StudyGroup.objects.create(organization=org, name='G1')
    g2 = StudyGroup.objects.create(organization=org, name='G2')
    teacher = _user('teach', role=User.Role.TEACHER)
    _member(org, teacher, OrganizationMembership.OrgRole.TEACHER)
    StudyGroupTeacher.objects.create(study_group=g1, teacher=teacher)
    tclient = APIClient(); tclient.force_authenticate(user=teacher)
    res = tclient.get(f'/api/organizations/{org.id}/my-study-groups/')
    assert res.status_code == 200
    ids = {r['id'] for r in res.data}
    assert ids == {g1.id}
