import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentCourseChatMessage


@pytest.mark.django_db
class TestStudentExamPrepChatHistoryApi:
    def _make_student_client(self, *, student_phone: str = '09920000000'):
        student = baker.make(User, role=User.Role.STUDENT, phone=student_phone)
        client = APIClient()
        client.force_authenticate(user=student)
        return student, client

    def _make_published_exam_for_student(self, student_phone: str):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            is_published=True,
            title='Exam Prep',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )
        baker.make(ClassInvitation, session=session, phone=student_phone, invite_code='INV-EXAM-1')
        return session

    def test_history_requires_phone(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            is_published=True,
            title='Exam Prep',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )

        student = baker.make(User, role=User.Role.STUDENT, phone='')
        client = APIClient()
        client.force_authenticate(user=student)

        resp = client.get(f'/api/classes/student/exam-preps/{session.id}/chat-history/')
        assert resp.status_code == 400

    def test_history_requires_invite_access(self):
        student, client = self._make_student_client(student_phone='09920000000')
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            is_published=True,
            title='Exam Prep',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )

        resp = client.get(f'/api/classes/student/exam-preps/{session.id}/chat-history/')
        assert resp.status_code in (404, 403)

    def test_history_returns_only_requested_question(self, monkeypatch):
        monkeypatch.setattr(
            'apps.classes.views.handle_exam_prep_message',
            lambda **_kwargs: {'type': 'text', 'content': 'ok', 'suggestions': []},
        )

        student, client = self._make_student_client(student_phone='09920000000')
        session = self._make_published_exam_for_student(student_phone=student.phone)

        client.post(
            f'/api/classes/student/exam-preps/{session.id}/chat/',
            {'message': 'm1', 'question_id': 'q1'},
            format='json',
        )
        client.post(
            f'/api/classes/student/exam-preps/{session.id}/chat/',
            {'message': 'm2', 'question_id': 'q2'},
            format='json',
        )

        resp1 = client.get(f'/api/classes/student/exam-preps/{session.id}/chat-history/?question_id=q1')
        assert resp1.status_code == 200
        assert len(resp1.data['items']) == 2
        assert resp1.data['items'][0]['content'] == 'm1'

        resp2 = client.get(f'/api/classes/student/exam-preps/{session.id}/chat-history/?question_id=q2')
        assert resp2.status_code == 200
        assert len(resp2.data['items']) == 2
        assert resp2.data['items'][0]['content'] == 'm2'

        assert StudentCourseChatMessage.objects.filter(thread__session=session, thread__student=student).count() == 4
