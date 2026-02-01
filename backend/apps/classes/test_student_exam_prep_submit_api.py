import json
import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentExamPrepAttempt


@pytest.mark.django_db
class TestStudentExamPrepSubmitApi:
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
        baker.make(ClassInvitation, session=session, phone=student_phone, invite_code='INV-EXAM-1')
        session.exam_prep_json = json.dumps({'exam_prep': {'questions': questions}}, ensure_ascii=False)
        session.save(update_fields=['exam_prep_json'])
        return session

    def test_submit_does_not_score_until_finalize(self):
        student, client = self._make_student_client(student_phone='09920000000')
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

        resp = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'ب'}, 'finalize': False},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['total_questions'] == 1
        assert resp.data['finalized'] is False
        assert resp.data['correct_count'] == 0
        assert resp.data['score_0_100'] == 0

        attempt = StudentExamPrepAttempt.objects.filter(session=session, student=student).first()
        assert attempt is not None
        assert attempt.finalized is False
        assert attempt.answers == {'q1': 'ب'}

    def test_finalize_scores_with_labels(self):
        student, client = self._make_student_client(student_phone='09920000000')
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

        resp = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'ب'}, 'finalize': True},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['finalized'] is True
        assert resp.data['total_questions'] == 1
        assert resp.data['correct_count'] == 1
        assert resp.data['score_0_100'] == 100

    def test_finalize_prevents_resubmit(self):
        student, client = self._make_student_client(student_phone='09920000000')
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
                }
            ],
        )

        resp = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'الف'}, 'finalize': True},
            format='json',
        )
        assert resp.status_code == 200

        attempt = StudentExamPrepAttempt.objects.filter(session=session, student=student).first()
        assert attempt is not None
        assert attempt.finalized is True

        resp2 = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'ب'}, 'finalize': False},
            format='json',
        )
        assert resp2.status_code == 400

    def test_submit_merges_draft_and_finalize(self):
        student, client = self._make_student_client(student_phone='09920000010')
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

        # Draft: answer only q1.
        draft = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': 'ب'}, 'finalize': False},
            format='json',
        )
        assert draft.status_code == 200
        assert draft.data['finalized'] is False

        # Finalize: answer only q2; should merge q1 from draft.
        fin = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q2': 'الف'}, 'finalize': True},
            format='json',
        )
        assert fin.status_code == 200
        assert fin.data['finalized'] is True
        assert fin.data['total_questions'] == 2
        assert fin.data['correct_count'] == 2
        assert fin.data['score_0_100'] == 100

        attempt = StudentExamPrepAttempt.objects.filter(session=session, student=student).first()
        assert attempt is not None
        assert attempt.answers == {'q1': 'ب', 'q2': 'الف'}

    def test_submit_trims_values_and_ignores_empty_question_ids(self):
        student, client = self._make_student_client(student_phone='09920000011')
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

        resp = client.post(
            f'/api/classes/student/exam-preps/{session.id}/submit/',
            {'answers': {'q1': '  الف  ', '': 'ب', '   ': 'ج'}, 'finalize': False},
            format='json',
        )
        assert resp.status_code == 200

        attempt = StudentExamPrepAttempt.objects.filter(session=session, student=student).first()
        assert attempt is not None
        assert attempt.answers == {'q1': 'الف'}
