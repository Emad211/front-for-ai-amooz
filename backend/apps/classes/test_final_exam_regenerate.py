"""Endpoint tests for the adaptive FINAL-EXAM loop (mirror of the chapter quiz).

The LLM generator is mocked; weak-point extraction runs for real over the
points-based final-exam attempt shape (score_points / max_points).
"""
import pytest
from model_bakery import baker
from rest_framework.test import APIClient


def _published_course_with_invited_student():
    student = baker.make('accounts.User', phone='09120000000')
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    section = baker.make('classes.ClassSection', session=session, external_id='sec_1', title='ف۱', order=1)
    baker.make('classes.ClassUnit', session=session, section=section, order=1, title='د۱', content_markdown='x')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='ABC')
    return student, session


def _failed_final_exam(session, student):
    exam = baker.make(
        'classes.ClassFinalExam', session=session, student=student,
        exam={'questions': [
            {'id': 'final_q1', 'type': 'multiple_choice', 'question': '؟',
             'options': ['ا', 'ب', 'ج', 'د'], 'correct_answer': 'ا', 'points': 5},
        ], 'exam_title': 'آزمون', 'passing_score': 70},
        last_score_0_100=40, last_passed=False,
    )
    baker.make(
        'classes.ClassFinalExamAttempt', exam=exam, score_0_100=40, passed=False,
        result={'per_question': [
            {'id': 'final_q1', 'label': 'incorrect', 'student_answer': 'ب',
             'score_points': 0, 'max_points': 5},
        ]},
    )
    return exam


@pytest.mark.django_db
def test_final_exam_regenerate_after_fail(monkeypatch):
    student, session = _published_course_with_invited_student()
    exam = _failed_final_exam(session, student)

    captured = {}

    def fake_adaptive_final(*, combined_content, weak_points, pool_size=12, review_count=2):
        captured['weak_points'] = weak_points
        return (
            {'exam_title': 'آزمون نو', 'passing_score': 70, 'questions': [
                {'id': 'naq1', 'type': 'multiple_choice', 'question': 'تمرین تازه؟',
                 'options': ['ا', 'ب', 'ج', 'د'], 'correct_answer': 'ا', 'points': 5},
            ]},
            'g', 'm',
        )

    monkeypatch.setattr('apps.classes.views.generate_adaptive_final_exam', fake_adaptive_final)

    client = APIClient()
    client.force_authenticate(user=student)
    resp = client.post(f'/api/classes/student/courses/{session.id}/final-exam/regenerate/')

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert [q['id'] for q in data['questions']] == ['naq1']
    assert 'correct_answer' not in data['questions'][0]
    assert data['last_passed'] is None

    # weak-point extraction handled the points-based shape (score_points<max_points)
    assert captured['weak_points'][0]['id'] == 'final_q1'
    assert captured['weak_points'][0]['correct_answer'] == 'ا'

    exam.refresh_from_db()
    assert exam.last_passed is None
    assert exam.last_score_0_100 is None
    assert [q['id'] for q in exam.exam['questions']] == ['naq1']
    assert exam.exam.get('adaptive') is True


@pytest.mark.django_db
def test_final_exam_regenerate_blocked_unless_failed(monkeypatch):
    student, session = _published_course_with_invited_student()
    exam = _failed_final_exam(session, student)
    monkeypatch.setattr('apps.classes.views.generate_adaptive_final_exam',
                        lambda **k: ({'questions': []}, 'p', 'm'))
    client = APIClient()
    client.force_authenticate(user=student)

    exam.last_passed = True
    exam.save(update_fields=['last_passed'])
    assert client.post(f'/api/classes/student/courses/{session.id}/final-exam/regenerate/').status_code == 409

    exam.last_passed = None
    exam.save(update_fields=['last_passed'])
    assert client.post(f'/api/classes/student/courses/{session.id}/final-exam/regenerate/').status_code == 409


@pytest.mark.django_db
def test_final_exam_regenerate_without_exam_returns_400():
    student, session = _published_course_with_invited_student()
    client = APIClient()
    client.force_authenticate(user=student)
    resp = client.post(f'/api/classes/student/courses/{session.id}/final-exam/regenerate/')
    assert resp.status_code == 400
