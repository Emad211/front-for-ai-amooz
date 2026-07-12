import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession, ClassInvitation, StudentInviteCode


User = get_user_model()


@pytest.mark.django_db
def test_teacher_students_list_returns_invited_phones():
    teacher = User.objects.create_user(username='t_students', password='pass', role=User.Role.TEACHER, phone='09120000001')
    token = str(RefreshToken.for_user(teacher).access_token)

    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='t',
        description='',
        source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
        source_mime_type='audio/ogg',
        source_original_name='audio.ogg',
        status=ClassCreationSession.Status.TRANSCRIBED,
        transcript_markdown='hello',
        is_published=True,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # Create invite via API to ensure it uses the unified invite-code generation.
    res = client.post(
        f'/api/classes/creation-sessions/{session.id}/invites/',
        {'phones': ['09120000000', '09120000001']},
        format='json',
    )
    assert res.status_code == 200

    res2 = client.get('/api/classes/teacher/students/')
    assert res2.status_code == 200
    assert isinstance(res2.data, list)
    assert len(res2.data) == 1
    assert res2.data[0]['phone'] == '09120000000'
    assert res2.data[0]['inviteCode']

    code = StudentInviteCode.objects.get(phone='09120000000').code
    assert res2.data[0]['inviteCode'] == code


@pytest.mark.django_db
def test_class_counts_exclude_teacher_phone_and_match_the_class_roster():
    teacher = User.objects.create_user(
        username='count_teacher', password='pass', role=User.Role.TEACHER, phone='09120000001',
    )
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='کلاس شمارش',
        description='',
        source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
        source_mime_type='audio/ogg',
        source_original_name='audio.ogg',
        status=ClassCreationSession.Status.TRANSCRIBED,
        transcript_markdown='hello',
        is_published=True,
    )
    ClassInvitation.objects.create(session=session, phone=teacher.phone, invite_code='SELF')
    ClassInvitation.objects.create(session=session, phone='09120000002', invite_code='STUDENT')

    client = APIClient()
    client.force_authenticate(user=teacher)

    classes = client.get('/api/classes/creation-sessions/')
    detail = client.get(f'/api/classes/creation-sessions/{session.id}/')
    roster = client.get(f'/api/classes/creation-sessions/{session.id}/students/')
    students = client.get('/api/classes/teacher/students/')

    assert classes.status_code == detail.status_code == roster.status_code == students.status_code == 200
    assert classes.data[0]['invites_count'] == 1
    assert detail.data['invites_count'] == 1
    assert len(roster.data) == 1
    assert len(students.data) == 1


@pytest.mark.django_db
def test_teacher_analytics_counts_unique_students_and_first_invites_only():
    teacher = User.objects.create_user(
        username='analytics_teacher', password='pass', role=User.Role.TEACHER, phone='09120000010',
    )

    def make_session(title, pipeline_type=ClassCreationSession.PipelineType.CLASS):
        return ClassCreationSession.objects.create(
            teacher=teacher,
            title=title,
            description='',
            pipeline_type=pipeline_type,
            source_file=SimpleUploadedFile(f'{title}.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name=f'{title}.ogg',
            status=ClassCreationSession.Status.TRANSCRIBED,
            transcript_markdown='hello',
        )

    class_one = make_session('کلاس اول')
    class_two = make_session('کلاس دوم')
    exam = make_session('آمادگی آزمون', ClassCreationSession.PipelineType.EXAM_PREP)
    today = timezone.now()

    def invite(session, phone, code, days_ago):
        invitation = ClassInvitation.objects.create(session=session, phone=phone, invite_code=code)
        ClassInvitation.objects.filter(id=invitation.id).update(
            created_at=today - timedelta(days=days_ago),
        )

    invite(class_one, '09120000011', 'A1', 2)
    invite(class_two, '09120000011', 'A2', 1)
    invite(class_two, '09120000012', 'B1', 1)
    invite(class_one, '09120000013', 'OLD', 10)
    invite(class_one, teacher.phone, 'SELF', 0)
    invite(exam, '09120000014', 'EXAM', 0)

    client = APIClient()
    client.force_authenticate(user=teacher)

    stats = client.get('/api/classes/teacher/analytics/stats/?days=7')
    chart = client.get('/api/classes/teacher/analytics/chart/?days=7')
    distribution = client.get('/api/classes/teacher/analytics/distribution/')

    assert stats.status_code == chart.status_code == distribution.status_code == 200
    student_stat = next(item for item in stats.data if item['title'] == 'کل دانش‌آموزان')
    assert student_stat['value'] == '4'
    assert sum(item['students'] for item in chart.data) == 3
    assert {item['name'] for item in distribution.data} == {'کلاس اول', 'کلاس دوم'}
    assert {item['value'] for item in distribution.data} == {2}
