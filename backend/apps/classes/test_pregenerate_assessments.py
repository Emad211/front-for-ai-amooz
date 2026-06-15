"""Tests for the pre-generation Celery task.

Generators are mocked (no LLM); the task's own branching/idempotency runs for
real. Run synchronously via ``.apply()``.
"""
import pytest
from model_bakery import baker

from apps.classes.tasks import pregenerate_student_assessments


def _course_with_two_sections():
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    s1 = baker.make('classes.ClassSection', session=session, external_id='sec_1', title='ف۱', order=1)
    baker.make('classes.ClassUnit', session=session, section=s1, order=1, title='د۱', content_markdown='alpha')
    s2 = baker.make('classes.ClassSection', session=session, external_id='sec_2', title='ف۲', order=2)
    baker.make('classes.ClassUnit', session=session, section=s2, order=1, title='د۲', content_markdown='beta')
    student = baker.make('accounts.User', phone='09120000000')
    return session, student, s1, s2


def _mock_generators(monkeypatch, calls):
    def fake_quiz(*, section_content, count=5):
        calls['quiz'] += 1
        return ({'questions': [{'id': 'q1', 'type': 'multiple_choice', 'question': '?',
                                'options': ['a', 'b', 'c', 'd'], 'correct_answer': 'a', 'difficulty': 'easy'}]},
                'p', 'm')

    def fake_exam(*, combined_content, pool_size=12):
        calls['exam'] += 1
        return ({'questions': [{'id': 'e1', 'type': 'multiple_choice', 'question': '?',
                                'options': ['a', 'b', 'c', 'd'], 'correct_answer': 'a', 'points': 10}]},
                'p', 'm')

    # The task imports these names inside the function body, so patch them at
    # the source module (not on apps.classes.tasks).
    monkeypatch.setattr('apps.classes.services.quizzes.generate_section_quiz_questions', fake_quiz)
    monkeypatch.setattr('apps.classes.services.quizzes.generate_final_exam_pool', fake_exam)


@pytest.mark.django_db
def test_pregenerate_creates_all_quizzes_and_final_exam(monkeypatch):
    from apps.classes.models import ClassSectionQuiz, ClassFinalExam

    session, student, s1, s2 = _course_with_two_sections()
    calls = {'quiz': 0, 'exam': 0}
    _mock_generators(monkeypatch, calls)

    result = pregenerate_student_assessments.apply(args=[session.id, student.id]).result

    assert result['status'] == 'success'
    assert result['quizzes_created'] == 2
    assert result['final_exam_created'] is True
    assert calls == {'quiz': 2, 'exam': 1}
    assert ClassSectionQuiz.objects.filter(session=session, student=student).count() == 2
    assert ClassFinalExam.objects.filter(session=session, student=student).exists()


@pytest.mark.django_db
def test_pregenerate_is_idempotent(monkeypatch):
    session, student, s1, s2 = _course_with_two_sections()
    calls = {'quiz': 0, 'exam': 0}
    _mock_generators(monkeypatch, calls)

    pregenerate_student_assessments.apply(args=[session.id, student.id])
    # Second run: everything exists → nothing regenerated.
    result2 = pregenerate_student_assessments.apply(args=[session.id, student.id]).result

    assert result2['quizzes_created'] == 0
    assert result2['final_exam_created'] is False
    assert calls == {'quiz': 2, 'exam': 1}  # unchanged from the first run


@pytest.mark.django_db
def test_pregenerate_skips_section_without_content(monkeypatch):
    from apps.classes.models import ClassSectionQuiz

    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    s1 = baker.make('classes.ClassSection', session=session, external_id='sec_1', order=1)
    baker.make('classes.ClassUnit', session=session, section=s1, order=1, content_markdown='alpha')
    # Section with an empty unit → no content → skipped.
    s2 = baker.make('classes.ClassSection', session=session, external_id='sec_2', order=2)
    baker.make('classes.ClassUnit', session=session, section=s2, order=1, content_markdown='')
    student = baker.make('accounts.User', phone='09120000000')

    calls = {'quiz': 0, 'exam': 0}
    _mock_generators(monkeypatch, calls)

    result = pregenerate_student_assessments.apply(args=[session.id, student.id]).result
    assert result['quizzes_created'] == 1   # only the section with content
    assert ClassSectionQuiz.objects.filter(session=session, student=student).count() == 1


@pytest.mark.django_db
def test_pregenerate_missing_session_is_safe():
    result = pregenerate_student_assessments.apply(args=[999999, 999999]).result
    assert result['status'] == 'skipped'
