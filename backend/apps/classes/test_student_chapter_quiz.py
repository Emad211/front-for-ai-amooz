import json

import pytest
from model_bakery import baker
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_student_chapter_quiz_get_requires_auth():
    client = APIClient()
    resp = client.get('/api/classes/student/courses/1/chapters/sec_1/quiz/')
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_student_chapter_quiz_get_and_submit(monkeypatch):
    # Arrange
    student = baker.make('accounts.User', phone='09120000000')
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    section = baker.make('classes.ClassSection', session=session, external_id='sec_1', title='فصل ۱', order=1)
    baker.make('classes.ClassUnit', session=session, section=section, order=1, title='درس ۱', content_markdown='x')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='ABC')

    def fake_generate_section_quiz_questions(*, section_content: str, count: int = 5):
        return (
            {
                'questions': [
                    {
                        'id': 'q1',
                        'type': 'multiple_choice',
                        'question': '1+1؟',
                        'options': ['1', '2', '3', '4'],
                        'correct_answer': '2',
                        'difficulty': 'easy',
                    },
                    {
                        'id': 'q2',
                        'type': 'short_answer',
                        'question': 'تعریف انرژی؟',
                        'options': [],
                        'correct_answer': 'توانایی انجام کار',
                        'difficulty': 'easy',
                    },
                ]
            },
            'gemini',
            'models/fake',
        )

    def fake_grade_open_text_answer(*, question: str, reference_answer: str, student_answer: str):
        # Accept any non-empty answer as 100 for test.
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

    monkeypatch.setattr('apps.classes.views.generate_section_quiz_questions', fake_generate_section_quiz_questions)
    monkeypatch.setattr('apps.classes.views.grade_open_text_answer', fake_grade_open_text_answer)

    client = APIClient()
    client.force_authenticate(user=student)

    # Act: GET quiz
    resp = client.get(f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/')
    assert resp.status_code == 200
    data = resp.json()
    assert data['session_id'] == session.id
    assert data['chapter_id'] == 'sec_1'
    assert data['quiz_id']
    assert len(data['questions']) == 2
    # Ensure correct_answer is not leaked
    assert 'correct_answer' not in data['questions'][0]

    # Act: submit answers
    submit = client.post(
        f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/',
        data=json.dumps({'answers': {'q1': '2', 'q2': 'توانایی انجام کار'}}),
        content_type='application/json',
    )
    assert submit.status_code == 200
    out = submit.json()
    assert out['passed'] is True
    assert out['score_0_100'] == 100
    assert len(out['per_question']) == 2
    # 1 chapter quiz passed out of (1 chapter + final exam)
    assert out['course_progress'] == 50


@pytest.mark.django_db
def test_student_chapter_quiz_denied_without_invite(monkeypatch):
    student = baker.make('accounts.User', phone='09121111111')
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True)
    section = baker.make('classes.ClassSection', session=session, external_id='sec_1', title='فصل ۱', order=1)
    baker.make('classes.ClassUnit', session=session, section=section, order=1, title='درس ۱', content_markdown='x')

    # Even if quiz generator is patched, access should fail first.
    monkeypatch.setattr('apps.classes.views.generate_section_quiz_questions', lambda **_: ({'questions': []}, 'gemini', 'm'))

    client = APIClient()
    client.force_authenticate(user=student)

    resp = client.get(f'/api/classes/student/courses/{session.id}/chapters/sec_1/quiz/')
    assert resp.status_code == 404
