import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentCourseChatMessage


@pytest.mark.django_db
class TestStudentExamPrepChatApi:
    def _make_student_client(self, *, student_phone: str = '09920000000'):
        student = baker.make(User, role=User.Role.STUDENT, phone=student_phone)
        client = APIClient()
        client.force_authenticate(user=student)
        return student, client

    def _make_exam_for_student(self, student_phone: str):
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

    def test_chat_requires_phone(self):
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

        resp = client.post(f'/api/classes/student/exam-preps/{session.id}/chat/', {'message': 'hi'}, format='json')
        assert resp.status_code == 400

    def test_chat_requires_invite_access(self):
        student, client = self._make_student_client(student_phone='09920000000')
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            is_published=True,
            title='Exam Prep',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )

        resp = client.post(f'/api/classes/student/exam-preps/{session.id}/chat/', {'message': 'hi'}, format='json')
        assert resp.status_code in (404, 403)

    def test_chat_persists_user_and_assistant(self, monkeypatch):
        monkeypatch.setattr(
            'apps.classes.views.handle_exam_prep_message',
            lambda **_kwargs: {'type': 'text', 'content': 'ok', 'suggestions': ['s1']},
        )

        student, client = self._make_student_client(student_phone='09920000000')
        session = self._make_exam_for_student(student_phone=student.phone)

        resp = client.post(
            f'/api/classes/student/exam-preps/{session.id}/chat/',
            {'message': 'سلام', 'question_id': 'q1'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['type'] == 'text'
        assert resp.data['content'] == 'ok'

        msgs = StudentCourseChatMessage.objects.filter(thread__session=session, thread__student=student).order_by('created_at')
        assert msgs.count() == 2
        assert msgs[0].role == 'user'
        assert msgs[0].content == 'سلام'
        assert msgs[0].lesson_id == 'q1'
        assert msgs[1].role == 'assistant'
        assert msgs[1].content == 'ok'
        assert msgs[1].lesson_id == 'q1'
