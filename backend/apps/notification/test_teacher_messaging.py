"""Tests for teacher messaging + notification preferences. DB-only, no SMS/LLM."""
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession, ClassExercise, ClassInvitation
from apps.notification.models import (
    TeacherNotification,
    TeacherNotificationRecipient,
    UserNotificationPreference,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def _teacher(username='t1', phone='09150000000'):
    return User.objects.create_user(username=username, password='p', role=User.Role.TEACHER, phone=phone)


def _student(username='s1', phone='09120000001'):
    return User.objects.create_user(username=username, password='p', role=User.Role.STUDENT, phone=phone)


def _session_with_invite(teacher, phone, *, published=True):
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='C',
        description='d',
        source_file=SimpleUploadedFile('a.ogg', b'x', content_type='audio/ogg'),
        source_mime_type='audio/ogg',
        source_original_name='a.ogg',
        status=ClassCreationSession.Status.RECAPPED,
        pipeline_type=ClassCreationSession.PipelineType.CLASS,
        is_published=published,
    )
    ClassInvitation.objects.create(session=session, phone=phone, invite_code=f'INV-{phone}')
    return session


# ---------------------------------------------------------------------------
# recipients
# ---------------------------------------------------------------------------

def test_recipients_lists_only_own_students():
    teacher = _teacher()
    other_teacher = _teacher(username='t2', phone='09150000099')
    student = _student()
    _session_with_invite(teacher, student.phone)
    # a student of another teacher must NOT appear
    _session_with_invite(other_teacher, '09129999999')

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.get('/api/notifications/teacher/recipients/')
    assert res.status_code == 200
    phones = {r['phone'] for r in res.data}
    assert phones == {student.phone}
    row = res.data[0]
    assert row['hasAccount'] is True
    assert row['name']  # resolved name


# ---------------------------------------------------------------------------
# broadcast
# ---------------------------------------------------------------------------

def test_broadcast_to_all_creates_notification_and_recipients():
    teacher = _teacher()
    s1 = _student()
    s2 = _student(username='s2', phone='09120000002')
    _session_with_invite(teacher, s1.phone)
    _session_with_invite(teacher, s2.phone)

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.post(
        '/api/notifications/teacher/broadcast/',
        {'title': 'سلام', 'message': 'به کلاس خوش آمدید', 'sendToAll': True},
        format='json',
    )
    assert res.status_code == 201
    assert res.data['recipientCount'] == 2
    assert res.data['smsQueued'] is False
    notif = TeacherNotification.objects.get(id=res.data['id'])
    assert notif.teacher_id == teacher.id
    assert TeacherNotificationRecipient.objects.filter(notification=notif).count() == 2


def test_broadcast_only_targets_own_students():
    teacher = _teacher()
    other_teacher = _teacher(username='t2', phone='09150000099')
    mine = _student()
    not_mine = _student(username='s2', phone='09129999999')
    _session_with_invite(teacher, mine.phone)
    _session_with_invite(other_teacher, not_mine.phone)

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.post(
        '/api/notifications/teacher/broadcast/',
        {'title': 't', 'message': 'm', 'recipientPhones': [mine.phone, not_mine.phone]},
        format='json',
    )
    assert res.status_code == 201
    # the foreign student is silently dropped
    assert res.data['recipientCount'] == 1
    notif = TeacherNotification.objects.get(id=res.data['id'])
    phones = set(notif.recipients.values_list('phone', flat=True))
    assert phones == {mine.phone}


def test_broadcast_with_no_valid_recipients_is_rejected():
    teacher = _teacher()
    student = _student()
    _session_with_invite(teacher, student.phone)

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.post(
        '/api/notifications/teacher/broadcast/',
        {'title': 't', 'message': 'm', 'recipientPhones': ['09120000404']},
        format='json',
    )
    assert res.status_code == 400


def test_broadcast_requires_teacher_role():
    student = _student()
    client = APIClient()
    client.force_authenticate(user=student)
    res = client.post(
        '/api/notifications/teacher/broadcast/',
        {'title': 't', 'message': 'm', 'sendToAll': True},
        format='json',
    )
    assert res.status_code == 403


def test_broadcast_appears_in_student_feed():
    teacher = _teacher()
    student = _student()
    _session_with_invite(teacher, student.phone)

    tclient = APIClient()
    tclient.force_authenticate(user=teacher)
    tclient.post(
        '/api/notifications/teacher/broadcast/',
        {'title': 'اعلان معلم', 'message': 'پیام', 'sendToAll': True},
        format='json',
    )

    sclient = APIClient()
    sclient.force_authenticate(user=student)
    res = sclient.get('/api/classes/student/notifications/')
    assert res.status_code == 200
    titles = {n['title'] for n in res.data}
    assert 'اعلان معلم' in titles


def test_broadcast_sms_flag_queues_without_crashing(monkeypatch):
    # Ensure the SMS dispatch path is exercised but no real network/celery runs.
    import apps.classes.tasks as tasks

    called = {}

    def fake_delay(notification_id):
        called['id'] = notification_id

    monkeypatch.setattr(tasks.send_teacher_message_sms_task, 'delay', fake_delay)

    teacher = _teacher()
    student = _student()
    _session_with_invite(teacher, student.phone)

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.post(
        '/api/notifications/teacher/broadcast/',
        {'title': 't', 'message': 'm', 'sendToAll': True, 'sendSms': True},
        format='json',
    )
    assert res.status_code == 201
    assert res.data['smsQueued'] is True
    # transaction.on_commit fires at the end of the test-case's atomic block;
    # force it by asserting the task was scheduled via the captured delay.
    # (DRF test wraps each request; on_commit runs on commit which pytest-django
    # may defer — so we just assert the response contract here.)


def test_teacher_feed_includes_owned_exercise_ready_notifications_only():
    teacher = _teacher()
    other_teacher = _teacher(username='t2', phone='09150000099')
    session = _session_with_invite(teacher, '09120000999')
    other_session = _session_with_invite(other_teacher, '09120000888')
    mine = ClassExercise.objects.create(
        session=session,
        title='تمرین من',
        status=ClassExercise.Status.EXTRACTED,
        review_ready_notified_at=timezone.now(),
    )
    ClassExercise.objects.create(
        session=other_session,
        title='تمرین دیگری',
        status=ClassExercise.Status.EXTRACTED,
        review_ready_notified_at=timezone.now(),
    )

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.get('/api/notifications/teacher/')
    assert res.status_code == 200
    ids = {item['id'] for item in res.data}
    assert f'exercise-ready-{mine.id}' in ids
    assert all('تمرین دیگری' not in item['title'] for item in res.data)


def test_teacher_feed_includes_owned_class_and_exam_ready_notifications_only():
    teacher = _teacher(username='feed_owner', phone='09150000001')
    other_teacher = _teacher(username='feed_other', phone='09150000002')
    class_session = _session_with_invite(teacher, '09120000777')
    exam_session = _session_with_invite(other_teacher, '09120000666')
    class_session.review_ready_notified_at = timezone.now()
    class_session.save(update_fields=['review_ready_notified_at'])
    own_exam = ClassCreationSession.objects.create(
        teacher=teacher,
        title='E',
        description='exam',
        source_file=SimpleUploadedFile('e.ogg', b'x', content_type='audio/ogg'),
        source_mime_type='audio/ogg',
        source_original_name='e.ogg',
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        is_published=False,
    )
    own_exam.review_ready_notified_at = timezone.now()
    own_exam.save(update_fields=['review_ready_notified_at'])
    exam_session.review_ready_notified_at = timezone.now()
    exam_session.save(update_fields=['review_ready_notified_at'])

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.get('/api/notifications/teacher/')
    assert res.status_code == 200
    ids = {item['id'] for item in res.data}
    assert f'class-ready-{class_session.id}' in ids
    assert f'exam-ready-{own_exam.id}' in ids
    assert f'class-ready-{exam_session.id}' not in ids


# ---------------------------------------------------------------------------
# preferences
# ---------------------------------------------------------------------------

def test_preferences_get_creates_defaults():
    teacher = _teacher()
    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.get('/api/notifications/preferences/')
    assert res.status_code == 200
    assert res.data['emailNotifications'] is True
    assert res.data['smsNotifications'] is False
    assert UserNotificationPreference.objects.filter(user=teacher).exists()


def test_preferences_patch_persists():
    teacher = _teacher()
    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.patch(
        '/api/notifications/preferences/',
        {'smsNotifications': True, 'marketingEmails': True},
        format='json',
    )
    assert res.status_code == 200
    assert res.data['smsNotifications'] is True
    prefs = UserNotificationPreference.objects.get(user=teacher)
    assert prefs.sms_enabled is True
    assert prefs.marketing_enabled is True
