import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation


@pytest.mark.django_db
class TestStudentExamPrepResultApi:
    def _make_student_client(self, *, student_phone: str = '09920000000'):
        student = baker.make(User, role=User.Role.STUDENT, phone=student_phone)
        client = APIClient()
        client.force_authenticate(user=student)
        return student, client

    def _make_exam_for_student(self, student_phone: str, *, questions: list[dict]):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            is_published=True,
            title='Exam Prep',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )
        baker.make(ClassInvitation, session=session, phone=student_phone, invite_code='INV-EXAM-RES-1')
        session.exam_prep_json = json.dumps({'exam_prep': {'questions': questions}}, ensure_ascii=False)
        session.save(update_fields=['exam_prep_json'])
        return session

    def test_result_requires_attempt(self):
        student, client = self._make_student_client(student_phone='09920000001')
        session = self._make_exam_for_student(
            student.phone,
            questions=[
                {
                    'question_id': 'q1',
                    'question_text_markdown': 'Q1',
                    'options': [
                        {'label': 'الف', 'text_markdown': '1'},
                        {'label': 'ب', 'text_markdown': '2'},
                    ],
                    'correct_option_label': 'ب',
                }
            ],
        )

        resp = client.get(f'/api/classes/student/exam-preps/{session.id}/result/')
        assert resp.status_code == 404

    def test_result_after_finalize(self):
        student, client = self._make_student_client(student_phone='09920000002')
        session = self._make_exam_for_student(
            student.phone,
            questions=[
                {
                    'question_id': 'q1',
                    'question_text_markdown': 'Q1',
                    'options': [
                        {'label': 'الف', 'text_markdown': '1'},
                        {'label': 'ب', 'text_markdown': '2'},
                    ],
                    'correct_option_label': 'ب',
                },
                {
                    'question_id': 'q2',
                    'question_text_markdown': 'Q2',
                    'options': [
                        {'label': 'الف', 'text_markdown': '1'},
                        {'label': 'ب', 'text_markdown': '2'},
                    ],
                    'correct_option_label': 'الف',
                },
            ],
        )

        # Finalize with one correct and one wrong.
        submit = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'ب', 'q2': 'ب'}, 'finalize': True},
            format='json',
        )
        assert submit.status_code == 200

        resp = client.get(f'/api/classes/student/exam-preps/{session.id}/result/')
        assert resp.status_code == 200
        assert resp.data['finalized'] is True
        assert resp.data['total_questions'] == 2
        assert resp.data['correct_count'] == 1
        assert resp.data['score_0_100'] == 50

        items = {it['question_id']: it for it in resp.data['items']}
        # Never expose correct answers to students
        assert 'correct_label' not in items['q1']
        assert items['q1']['is_correct'] is True
        assert items['q2']['is_correct'] is False

    def test_result_before_finalize_does_not_reveal_correctness(self):
        student, client = self._make_student_client(student_phone='09920000003')
        session = self._make_exam_for_student(
            student.phone,
            questions=[
                {
                    'question_id': 'q1',
                    'question_text_markdown': 'Q1',
                    'options': [
                        {'label': 'الف', 'text_markdown': '1'},
                        {'label': 'ب', 'text_markdown': '2'},
                    ],
                    'correct_option_label': 'ب',
                }
            ],
        )

        # Save a correct draft answer but do NOT finalize.
        submit = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'ب'}, 'finalize': False},
            format='json',
        )
        assert submit.status_code == 200
        assert submit.data['finalized'] is False

        resp = client.get(f'/api/classes/student/exam-preps/{session.id}/result/')
        assert resp.status_code == 200
        assert resp.data['finalized'] is False
        assert resp.data['score_0_100'] == 0
        assert resp.data['correct_count'] == 0

        items = resp.data['items']
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]['question_id'] == 'q1'
        assert items[0]['selected_label'] == 'ب'
        assert items[0]['is_correct'] is False
        assert 'correct_label' not in items[0]

    def test_result_is_404_when_student_not_invited(self):
        # Session is invited for a different phone.
        _student, _client = self._make_student_client(student_phone='09920000004')
        session = self._make_exam_for_student(
            '09920009999',
            questions=[
                {
                    'question_id': 'q1',
                    'question_text_markdown': 'Q1',
                    'options': [{'label': 'الف', 'text_markdown': '1'}],
                    'correct_option_label': 'الف',
                }
            ],
        )

        student2, client2 = self._make_student_client(student_phone='09920000005')
        resp = client2.get(f'/api/classes/student/exam-preps/{session.id}/result/')
        assert resp.status_code == 404

    def test_result_handles_invalid_exam_json_safely(self):
        student, client = self._make_student_client(student_phone='09920000006')

        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            is_published=True,
            title='Exam Prep',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            exam_prep_json='not-json',
        )
        baker.make(ClassInvitation, session=session, phone=student.phone, invite_code='INV-EXAM-RES-INVALID')

        # Create an attempt by submitting draft answers.
        submit = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'الف'}, 'finalize': False},
            format='json',
        )
        assert submit.status_code == 200

        resp = client.get(f'/api/classes/student/exam-preps/{session.id}/result/')
        assert resp.status_code == 200
        assert resp.data['total_questions'] == 0
        assert resp.data['items'] == []
