import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentExamPrepAttempt


@pytest.mark.django_db
class TestStudentExamPrepResetApi:
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
        baker.make(ClassInvitation, session=session, phone=student_phone, invite_code='INV-EXAM-RESET-1')
        session.exam_prep_json = json.dumps({'exam_prep': {'questions': questions}}, ensure_ascii=False)
        session.save(update_fields=['exam_prep_json'])
        return session

    def test_reset_is_404_when_no_attempt_exists(self):
        student, client = self._make_student_client(student_phone='09920001001')
        session = self._make_exam_for_student(
            student.phone,
            questions=[
                {
                    'question_id': 'q1',
                    'question_text_markdown': 'Q1',
                    'options': [{'label': 'الف', 'text_markdown': '1'}],
                    'correct_option_label': 'الف',
                }
            ],
        )

        resp = client.post(f'/api/classes/student/exam-preps/{session.id}/reset/', format='json')
        assert resp.status_code == 404

    def test_reset_clears_attempt_and_allows_retake(self):
        student, client = self._make_student_client(student_phone='09920001002')
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
                    'correct_option_label': 'الف',
                },
                {
                    'question_id': 'q2',
                    'question_text_markdown': 'Q2',
                    'options': [
                        {'label': 'الف', 'text_markdown': '1'},
                        {'label': 'ب', 'text_markdown': '2'},
                    ],
                    'correct_option_label': 'ب',
                },
            ],
        )

        fin = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'الف', 'q2': 'الف'}, 'finalize': True},
            format='json',
        )
        assert fin.status_code == 200
        assert fin.data['finalized'] is True

        attempt = StudentExamPrepAttempt.objects.filter(session=session, student=student).first()
        assert attempt is not None
        assert attempt.finalized is True
        assert attempt.answers == {'q1': 'الف', 'q2': 'الف'}

        reset = client.post(f'/api/classes/student/exam-preps/{session.id}/reset/', format='json')
        assert reset.status_code == 200
        assert reset.data['finalized'] is False
        assert reset.data['score_0_100'] == 0
        assert reset.data['correct_count'] == 0
        assert reset.data['total_questions'] == 2

        attempt.refresh_from_db()
        assert attempt.finalized is False
        assert attempt.answers == {}
        assert attempt.score_0_100 == 0
        assert attempt.correct_count == 0

        res = client.get(f'/api/classes/student/exam-preps/{session.id}/result/')
        assert res.status_code == 200
        assert res.data['finalized'] is False
        assert res.data['score_0_100'] == 0
        assert res.data['correct_count'] == 0
        assert res.data['answers'] == {}
        assert {it['question_id'] for it in res.data['items']} == {'q1', 'q2'}
        assert all(it['selected_label'] == '' for it in res.data['items'])
        assert all(it['is_correct'] is False for it in res.data['items'])

        # Retake should be possible now.
        fin2 = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'الف', 'q2': 'ب'}, 'finalize': True},
            format='json',
        )
        assert fin2.status_code == 200
        assert fin2.data['finalized'] is True
        assert fin2.data['correct_count'] == 2
        assert fin2.data['score_0_100'] == 100
