import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    Enrollment,
    StudentUnitProgress,
    TeacherStudentAccess,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def _user(username, role, phone):
    return User.objects.create_user(username=username, password='pass', role=role, phone=phone)


def _session(teacher, title='کلاس', *, organization=None):
    return ClassCreationSession.objects.create(
        teacher=teacher,
        title=title,
        description='',
        organization=organization,
        pipeline_type=ClassCreationSession.PipelineType.CLASS,
        source_file=SimpleUploadedFile('audio.ogg', b'fake', content_type='audio/ogg'),
        source_mime_type='audio/ogg',
        source_original_name='audio.ogg',
        status=ClassCreationSession.Status.RECAPPED,
        is_published=True,
    )


def test_pending_invite_is_not_a_real_student():
    teacher = _user('teacher', User.Role.TEACHER, '09120000001')
    session = _session(teacher)
    ClassInvitation.objects.create(session=session, phone='09120000002', invite_code='PENDING')
    client = APIClient()
    client.force_authenticate(teacher)

    students = client.get('/api/classes/teacher/students/')
    classes = client.get('/api/classes/creation-sessions/?organization=personal')
    pending = client.get('/api/classes/teacher/student-invitations/')

    assert students.status_code == classes.status_code == pending.status_code == 200
    assert students.data == []
    assert classes.data[0]['students_count'] == classes.data[0]['invites_count'] == 0
    assert len(pending.data) == 1


def test_enrollment_counts_once_globally_and_once_per_class():
    teacher = _user('teacher', User.Role.TEACHER, '09120000001')
    student = _user('student', User.Role.STUDENT, '09120000002')
    first, second = _session(teacher, 'اول'), _session(teacher, 'دوم')
    Enrollment.objects.create(session=first, student=student)
    Enrollment.objects.create(session=second, student=student)
    client = APIClient()
    client.force_authenticate(teacher)

    classes = client.get('/api/classes/creation-sessions/?organization=personal')
    summary = client.get('/api/classes/teacher/classes/summary/?organization=personal')
    students = client.get('/api/classes/teacher/students/')
    analytics = client.get('/api/classes/teacher/analytics/stats/')

    assert {row['students_count'] for row in classes.data} == {1}
    assert summary.data['totalStudents'] == 1
    assert len(students.data) == 1 and students.data[0]['enrolledClasses'] == 2
    assert next(row for row in analytics.data if row['title'] == 'کل دانش‌آموزان')['value'] == '1'


def test_suspend_and_restore_are_teacher_scoped_and_block_legacy_invite_gates():
    teacher = _user('teacher', User.Role.TEACHER, '09120000001')
    other = _user('other', User.Role.TEACHER, '09120000003')
    student = _user('student', User.Role.STUDENT, '09120000002')
    mine, theirs = _session(teacher), _session(other)
    for session in (mine, theirs):
        Enrollment.objects.create(session=session, student=student)
        ClassInvitation.objects.create(session=session, phone=student.phone, invite_code=f'I-{session.id}')
    client = APIClient()
    client.force_authenticate(teacher)

    suspended = client.patch(
        f'/api/classes/teacher/students/{student.id}/access/',
        {'status': 'suspended', 'reason': 'test'}, format='json',
    )
    assert suspended.status_code == 200
    assert TeacherStudentAccess.objects.get(teacher=teacher, student=student).is_suspended
    assert not ClassInvitation.objects.filter(session=mine, phone=student.phone).exists()
    assert ClassInvitation.objects.filter(session=theirs, phone=student.phone).exists()
    assert student.is_active

    restored = client.patch(
        f'/api/classes/teacher/students/{student.id}/access/', {'status': 'active'}, format='json',
    )
    assert restored.status_code == 200
    assert ClassInvitation.objects.filter(session=mine, phone=student.phone).exists()


def test_remove_personal_relationship_preserves_learning_history():
    teacher = _user('teacher', User.Role.TEACHER, '09120000001')
    student = _user('student', User.Role.STUDENT, '09120000002')
    session = _session(teacher)
    Enrollment.objects.create(session=session, student=student)
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='INV')
    StudentUnitProgress.objects.create(session=session, student=student, unit_external_id='u-1')
    client = APIClient()
    client.force_authenticate(teacher)

    response = client.delete(f'/api/classes/teacher/students/{student.id}/relationship/')

    assert response.status_code == 204
    assert not Enrollment.objects.filter(session=session, student=student).exists()
    assert not ClassInvitation.objects.filter(session=session, phone=student.phone).exists()
    assert StudentUnitProgress.objects.filter(session=session, student=student).exists()
    assert User.objects.filter(id=student.id, is_active=True).exists()


def test_multi_class_invite_is_idempotent_and_owner_scoped():
    teacher = _user('teacher', User.Role.TEACHER, '09120000001')
    other = _user('other', User.Role.TEACHER, '09120000003')
    first, second = _session(teacher, 'اول'), _session(teacher, 'دوم')
    foreign = _session(other, 'غریبه')
    client = APIClient()
    client.force_authenticate(teacher)
    payload = {'phones': ['09120000002', '09120000002'], 'sessionIds': [first.id, second.id]}

    created = client.post('/api/classes/teacher/student-invitations/', payload, format='json')
    repeated = client.post('/api/classes/teacher/student-invitations/', payload, format='json')
    denied = client.post('/api/classes/teacher/student-invitations/', {'phones': ['09120000002'], 'sessionIds': [foreign.id]}, format='json')

    assert created.status_code == 201 and created.data['createdCount'] == 2
    assert repeated.status_code == 201 and repeated.data['createdCount'] == 0
    assert denied.status_code == 404


def test_student_management_mutations_deny_student_role_and_cross_teacher():
    teacher = _user('teacher', User.Role.TEACHER, '09120000001')
    other = _user('other', User.Role.TEACHER, '09120000003')
    student = _user('student', User.Role.STUDENT, '09120000002')
    session = _session(teacher)
    Enrollment.objects.create(session=session, student=student)
    invitation = ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='INV')

    student_client = APIClient()
    student_client.force_authenticate(student)
    assert student_client.post(
        '/api/classes/teacher/student-invitations/',
        {'phones': ['09120000004'], 'sessionIds': [session.id]}, format='json',
    ).status_code == 403
    assert student_client.patch(
        f'/api/classes/teacher/students/{student.id}/access/', {'status': 'suspended'}, format='json',
    ).status_code == 403

    other_client = APIClient()
    other_client.force_authenticate(other)
    assert other_client.get(f'/api/classes/teacher/students/{student.id}/').status_code == 404
    assert other_client.patch(
        f'/api/classes/teacher/students/{student.id}/access/', {'status': 'suspended'}, format='json',
    ).status_code == 404
    assert other_client.delete(
        f'/api/classes/teacher/student-invitations/{invitation.id}/',
    ).status_code == 404
    assert other_client.delete(
        f'/api/classes/teacher/students/{student.id}/relationship/',
    ).status_code == 404
