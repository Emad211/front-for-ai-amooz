"""Endpoint tests for the adaptive chapter-quiz loop.

Covers: the new regenerate endpoint (fail → weak-point-targeted quiz), its
guards (only after a fail), and the reveal of correct answers on submit. The
LLM generator is mocked; weak-point extraction runs for real over stored
attempt data.
"""
import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient


def _published_course_with_invited_student():
    student = baker.make('accounts.User', phone='09120000000')
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    section = baker.make('classes.ClassSection', session=session, external_id='sec_1', title='فصل ۱', order=1)
    baker.make('classes.ClassUnit', session=session, section=section, order=1, title='درس ۱', content_markdown='x')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='ABC')
    return student, session, section


def _failed_quiz(session, section, student):
    """A quiz the student has FAILED, with one wrong question on record."""
    quiz = baker.make(
        'classes.ClassSectionQuiz',
        session=session, section=section, student=student,
        questions={'questions': [
            {'id': 'q1', 'type': 'multiple_choice', 'question': '۱+۱؟',
             'options': ['۱', '۲', '۳', '۴'], 'correct_answer': '۲', 'difficulty': 'easy'},
        ]},
        last_score_0_100=40, last_passed=False,
    )
    baker.make(
        'classes.ClassSectionQuizAttempt',
        quiz=quiz, score_0_100=40, passed=False,
        result={'per_question': [
            {'id': 'q1', 'label': 'incorrect', 'student_answer': '۳', 'score_0_100': 0},
        ], 'passing_score': 70},
    )
    return quiz


@pytest.mark.django_db
def test_regenerate_after_fail_builds_weakpoint_quiz(monkeypatch):
    student, session, section = _published_course_with_invited_student()
    quiz = _failed_quiz(session, section, student)

    captured = {}

    def fake_adaptive(*, section_content, weak_points, count=5, review_count=1):
        captured['weak_points'] = weak_points
        captured['count'] = count
        return (
            {'questions': [
                {'id': 'aq1', 'type': 'multiple_choice', 'question': 'تمرین تازه؟',
                 'options': ['الف', 'ب', 'ج', 'د'], 'correct_answer': 'الف', 'difficulty': 'medium'},
            ]},
            'gemini', 'models/fake',
        )

    monkeypatch.setattr('apps.classes.views.generate_adaptive_section_quiz', fake_adaptive)

    client = APIClient()
    client.force_authenticate(user=student)
    resp = client.post(f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/regenerate/')

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert [q['id'] for q in data['questions']] == ['aq1']
    assert 'correct_answer' not in data['questions'][0]   # never leaked before answering
    assert data['last_passed'] is None                    # reset → must take the new quiz

    # Real weak-point extraction fed the generator the failed question + its answer.
    assert captured['weak_points'][0]['id'] == 'q1'
    assert captured['weak_points'][0]['correct_answer'] == '۲'

    # Stored quiz overwritten + reset + tagged adaptive.
    quiz.refresh_from_db()
    assert quiz.last_passed is None
    assert quiz.last_score_0_100 is None
    assert [q['id'] for q in quiz.questions['questions']] == ['aq1']
    assert quiz.questions.get('adaptive') is True


@pytest.mark.django_db
def test_regenerate_blocked_unless_failed(monkeypatch):
    student, session, section = _published_course_with_invited_student()
    quiz = _failed_quiz(session, section, student)
    monkeypatch.setattr('apps.classes.views.generate_adaptive_section_quiz',
                        lambda **k: ({'questions': []}, 'p', 'm'))
    client = APIClient()
    client.force_authenticate(user=student)

    # Passed → 409 (no need for a new quiz)
    quiz.last_passed = True
    quiz.save(update_fields=['last_passed'])
    assert client.post(f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/regenerate/').status_code == 409

    # Not yet attempted (None) → 409 too
    quiz.last_passed = None
    quiz.save(update_fields=['last_passed'])
    assert client.post(f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/regenerate/').status_code == 409


@pytest.mark.django_db
def test_regenerate_without_quiz_returns_400():
    student, session, section = _published_course_with_invited_student()
    client = APIClient()
    client.force_authenticate(user=student)
    resp = client.post(f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/regenerate/')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_submit_reveals_correct_answer(monkeypatch):
    student, session, section = _published_course_with_invited_student()

    def fake_gen(*, section_content, count=5):
        return ({'questions': [
            {'id': 'q1', 'type': 'multiple_choice', 'question': '۱+۱؟',
             'options': ['۱', '۲', '۳', '۴'], 'correct_answer': '۲', 'difficulty': 'easy'},
        ]}, 'gemini', 'models/fake')

    monkeypatch.setattr('apps.classes.views.generate_section_quiz_questions', fake_gen)
    client = APIClient()
    client.force_authenticate(user=student)

    client.get(f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/')
    submit = client.post(
        f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/',
        data=json.dumps({'answers': {'q1': '۳'}}),  # wrong
        content_type='application/json',
    )
    assert submit.status_code == 200
    pq = submit.json()['per_question'][0]
    assert pq['label'] == 'incorrect'
    assert pq['correct_answer'] == '۲'   # revealed after submission
