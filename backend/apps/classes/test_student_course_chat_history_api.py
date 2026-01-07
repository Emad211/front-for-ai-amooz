import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentCourseChatMessage


@pytest.mark.django_db
class TestStudentChatHistoryApi:
    def _make_student_client(self, *, student_phone: str = '09920000000'):
        student = baker.make(User, role=User.Role.STUDENT, phone=student_phone)
        client = APIClient()
        client.force_authenticate(user=student)
        return student, client

    def _make_published_session_for_student(self, student_phone: str):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='Course')
        baker.make(ClassInvitation, session=session, phone=student_phone, invite_code='INV-1')
        return session

    def test_history_requires_phone(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='Course')

        student = baker.make(User, role=User.Role.STUDENT, phone='')
        client = APIClient()
        client.force_authenticate(user=student)

        resp = client.get(f'/api/classes/student/courses/{session.id}/chat-history/')
        assert resp.status_code == 400

    def test_history_requires_invite_access(self):
        student, client = self._make_student_client(student_phone='09920000000')
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='Course')

        resp = client.get(f'/api/classes/student/courses/{session.id}/chat-history/')
        assert resp.status_code in (404, 403)

    def test_history_returns_only_requested_lesson(self, monkeypatch):
        # Keep assistant deterministic.
        monkeypatch.setattr(
            'apps.classes.views.handle_student_message',
            lambda **_kwargs: {'type': 'text', 'content': 'ok', 'suggestions': []},
        )

        student, client = self._make_student_client(student_phone='09920000000')
        session = self._make_published_session_for_student(student_phone=student.phone)

        # Send two lessons.
        client.post(f'/api/classes/student/courses/{session.id}/chat/', {'message': 'm1', 'lesson_id': '1'}, format='json')
        client.post(f'/api/classes/student/courses/{session.id}/chat/', {'message': 'm2', 'lesson_id': '2'}, format='json')

        resp1 = client.get(f'/api/classes/student/courses/{session.id}/chat-history/?lesson_id=1')
        assert resp1.status_code == 200
        assert len(resp1.data['items']) == 2
        assert resp1.data['items'][0]['content'] == 'm1'

        resp2 = client.get(f'/api/classes/student/courses/{session.id}/chat-history/?lesson_id=2')
        assert resp2.status_code == 200
        assert len(resp2.data['items']) == 2
        assert resp2.data['items'][0]['content'] == 'm2'

        # Sanity: total stored messages is 4.
        assert StudentCourseChatMessage.objects.filter(thread__session=session, thread__student=student).count() == 4

    def test_history_returns_widgets_payload(self, monkeypatch):
        monkeypatch.setattr(
            'apps.classes.views.handle_student_message',
            lambda **_kwargs: {'type': 'widget', 'widget_type': 'quiz', 'data': {'questions': []}, 'text': 'ready', 'suggestions': ['s']},
        )

        student, client = self._make_student_client(student_phone='09920000000')
        session = self._make_published_session_for_student(student_phone=student.phone)

        resp = client.post(f'/api/classes/student/courses/{session.id}/chat/', {'message': 'SYSTEM_TOOL:fetch_quizzes', 'lesson_id': '1'}, format='json')
        assert resp.status_code == 200
        assert resp.data['type'] == 'widget'

        hist = client.get(f'/api/classes/student/courses/{session.id}/chat-history/?lesson_id=1')
        assert hist.status_code == 200

        items = hist.data['items']
        assert len(items) == 2
        assert items[1]['type'] == 'widget'
        assert items[1]['payload']['widget_type'] == 'quiz'
        assert items[1]['payload']['data'] == {'questions': []}
        assert items[1]['suggestions'] == ['s']
