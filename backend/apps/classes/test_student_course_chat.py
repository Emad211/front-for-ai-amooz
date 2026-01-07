import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentCourseChatMessage


@pytest.mark.django_db
def test_student_course_chat_requires_student_role(monkeypatch):
    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='T')
    baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-1')

    client = APIClient()
    client.force_authenticate(user=teacher)

    resp = client.post(f'/api/classes/student/courses/{session.id}/chat/', {'message': 'hi'}, format='json')
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_student_course_chat_returns_payload(monkeypatch):
    monkeypatch.setattr(
        'apps.classes.views.handle_student_message',
        lambda **_kwargs: {'type': 'text', 'content': 'ok', 'suggestions': ['a', 'b', 'c']},
    )

    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='Course')
    baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-1')

    client = APIClient()
    client.force_authenticate(user=student)

    resp = client.post(
        f'/api/classes/student/courses/{session.id}/chat/',
        {'message': 'سلام', 'lesson_id': None},
        format='json',
    )

    assert resp.status_code == 200
    assert resp.data['type'] == 'text'
    assert resp.data['content'] == 'ok'
    assert resp.data['suggestions'] == ['a', 'b', 'c']


@pytest.mark.django_db
def test_student_course_chat_persists_and_history_returns(monkeypatch):
    monkeypatch.setattr(
        'apps.classes.views.handle_student_message',
        lambda **_kwargs: {'type': 'text', 'content': 'ok', 'suggestions': []},
    )

    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='Course')
    baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-1')

    client = APIClient()
    client.force_authenticate(user=student)

    resp = client.post(
        f'/api/classes/student/courses/{session.id}/chat/',
        {'message': 'سلام', 'lesson_id': '1', 'page_context': '', 'page_material': ''},
        format='json',
    )
    assert resp.status_code == 200

    assert StudentCourseChatMessage.objects.filter(thread__session=session, thread__student=student).count() == 2

    hist = client.get(f'/api/classes/student/courses/{session.id}/chat-history/?lesson_id=1')
    assert hist.status_code == 200
    assert len(hist.data['items']) == 2
    assert hist.data['items'][0]['role'] == 'user'
    assert hist.data['items'][0]['content'] == 'سلام'
    assert hist.data['items'][1]['role'] == 'assistant'
    assert hist.data['items'][1]['content'] == 'ok'


@pytest.mark.django_db
def test_student_course_chat_media_routes_image(monkeypatch):
    monkeypatch.setattr(
        'apps.classes.views.handle_student_image_upload',
        lambda **_kwargs: {'type': 'text', 'content': 'image ok', 'suggestions': []},
    )

    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')

    session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='Course')
    baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-1')

    client = APIClient()
    client.force_authenticate(user=student)

    file = SimpleUploadedFile('x.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')

    resp = client.post(
        f'/api/classes/student/courses/{session.id}/chat-media/',
        {'file': file, 'message': 'این چیه؟'},
        format='multipart',
    )

    assert resp.status_code == 200
    assert resp.data['type'] == 'text'
    assert resp.data['content'] == 'image ok'
