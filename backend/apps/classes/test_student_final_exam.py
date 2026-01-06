import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_student_final_exam_get_requires_auth():
    client = APIClient()
    resp = client.get('/api/classes/student/courses/1/final-exam/')
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_student_final_exam_get_and_submit(monkeypatch):
    # Arrange
    student = baker.make('accounts.User', phone='09120000000')
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    section = baker.make('classes.ClassSection', session=session, external_id='sec_1', title='فصل ۱', order=1)
    baker.make('classes.ClassUnit', session=session, section=section, order=1, title='درس ۱', content_markdown='x')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='ABC')

    def fake_generate_final_exam_pool(*, combined_content: str, pool_size: int = 12):
        assert combined_content
        assert pool_size == 12
        return (
            {
                'exam_title': 'آزمون نهایی دوره',
                'time_limit': 45,
                'passing_score': 70,
                'questions': [
                    {
                        'id': 'q1',
                        'type': 'multiple_choice',
                        'question': '1+1؟',
                        'options': ['1', '2', '3', '4'],
                        'correct_answer': '2',
                        'points': 10,
                        'chapter': 'فصل ۱',
                    },
                    {
                        'id': 'q2',
                        'type': 'short_answer',
                        'question': 'تعریف انرژی؟',
                        'options': [],
                        'correct_answer': 'توانایی انجام کار',
                        'points': 10,
                        'chapter': 'فصل ۱',
                    },
                ],
            },
            'gemini',
            'models/fake',
        )

    def fake_grade_open_text_answer(*, question: str, reference_answer: str, student_answer: str):
        score = 100 if (student_answer or '').strip() else 0
        return (
            {
                'score_0_100': score,
                'label': 'correct' if score else 'incorrect',
                'feedback': 'ok',
                'missing_points': [],
            },
            'gemini',
            'models/fake',
        )

    monkeypatch.setattr('apps.classes.views.generate_final_exam_pool', fake_generate_final_exam_pool)
    monkeypatch.setattr('apps.classes.views.grade_open_text_answer', fake_grade_open_text_answer)

    client = APIClient()
    client.force_authenticate(user=student)

    # Act: GET exam
    resp = client.get(f'/api/classes/student/courses/{session.id}/final-exam/')
    assert resp.status_code == 200
    data = resp.json()
    assert data['session_id'] == session.id
    assert data['exam_id']
    assert data['exam_title'] == 'آزمون نهایی دوره'
    assert data['passing_score'] == 70
    assert len(data['questions']) == 2
    # Ensure correct_answer is not leaked
    assert 'correct_answer' not in data['questions'][0]

    # Act: submit answers
    submit = client.post(
        f'/api/classes/student/courses/{session.id}/final-exam/',
        data=json.dumps({'answers': {'q1': '2', 'q2': 'توانایی انجام کار'}}),
        content_type='application/json',
    )
    assert submit.status_code == 200
    out = submit.json()
    assert out['passed'] is True
    assert out['score_0_100'] == 100
    assert len(out['per_question']) == 2
    # Final exam passed out of (1 chapter + final exam)
    assert out['course_progress'] == 50


@pytest.mark.django_db
def test_student_final_exam_submit_before_get_returns_400():
    student = baker.make('accounts.User', phone='09120000000')
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True)
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='ABC')

    client = APIClient()
    client.force_authenticate(user=student)

    submit = client.post(
        f'/api/classes/student/courses/{session.id}/final-exam/',
        data=json.dumps({'answers': {'q1': '2'}}),
        content_type='application/json',
    )
    assert submit.status_code == 400


@pytest.mark.django_db
def test_student_final_exam_denied_without_invite(monkeypatch):
    student = baker.make('accounts.User', phone='09121111111')
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True)
    baker.make('classes.ClassSection', session=session, external_id='sec_1', title='فصل ۱', order=1)

    monkeypatch.setattr('apps.classes.views.generate_final_exam_pool', lambda **_: ({'questions': []}, 'gemini', 'm'))

    client = APIClient()
    client.force_authenticate(user=student)

    resp = client.get(f'/api/classes/student/courses/{session.id}/final-exam/')
    assert resp.status_code == 404
