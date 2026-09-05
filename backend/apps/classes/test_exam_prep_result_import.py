import json

import pytest
from model_bakery import baker

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentExamPrepAttempt
from apps.classes.services.exam_prep_result_import import (
    ResultImportError,
    import_exam_prep_results,
)


def _session(phone: str = '09120000001'):
    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone=phone)
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        is_published=True,
        exam_prep_json=json.dumps({'exam_prep': {'questions': [
            {'question_id': 'q1', 'correct_option_label': 'الف'},
            {'question_id': 'q2', 'correct_option_label': 'ب'},
            {'question_id': 'q3', 'correct_option_label': 'ج'},
        ]}}),
    )
    ClassInvitation.objects.create(session=session, phone=phone, invite_code='code')
    return session, student


@pytest.mark.django_db
def test_imports_flexible_status_buckets_and_computes_result():
    session, student = _session()

    result = import_exam_prep_results(session, {
        'results': [{
            'student': {'phone': '+98 912 000 0001'},
            'answers': {'q1': 'الف', 'q2': 'الف'},
            'unanswered': ['q3'],
        }]
    })

    attempt = StudentExamPrepAttempt.objects.get(session=session, student=student)
    assert attempt.answers['q1']['is_correct'] is True
    assert attempt.answers['q2']['is_correct'] is False
    assert 'q3' not in attempt.answers
    assert (attempt.total_questions, attempt.correct_count, attempt.score_0_100) == (3, 1, 33)
    assert result['imported'] == 1


@pytest.mark.django_db
def test_import_rejects_unknown_question_and_uninvited_student_atomically():
    session, _student = _session()
    with pytest.raises(ResultImportError, match='unknown question IDs'):
        import_exam_prep_results(session, {
            'results': [{'phone': '09120000001', 'answers': {'unknown': 'الف'}}]
        })
    with pytest.raises(ResultImportError, match='not invited'):
        import_exam_prep_results(session, {
            'results': [{'phone': '09120000099', 'answers': {'q1': 'الف'}}]
        })
    assert not StudentExamPrepAttempt.objects.filter(session=session).exists()


@pytest.mark.django_db
def test_import_rejects_conflict_unless_force():
    session, student = _session()
    payload = {'results': [{'phone': student.phone, 'answers': {'q1': 'الف'}}]}
    import_exam_prep_results(session, payload)
    with pytest.raises(ResultImportError, match='conflicting attempt'):
        import_exam_prep_results(session, {'results': [{'phone': student.phone, 'answers': {'q1': 'ب'}}]})
    import_exam_prep_results(session, {'results': [{'phone': student.phone, 'answers': {'q1': 'ب'}}]}, force=True)
    assert StudentExamPrepAttempt.objects.get(session=session, student=student).answers['q1']['is_correct'] is False


@pytest.mark.django_db
def test_import_rejects_answer_status_contradiction():
    session, student = _session()

    with pytest.raises(ResultImportError, match='contradictory status'):
        import_exam_prep_results(session, {
            'results': [{
                'phone': student.phone,
                'questions': [{'question_id': 'q1', 'status': 'wrong', 'answer': 'الف'}],
            }],
        })

    assert not StudentExamPrepAttempt.objects.filter(session=session).exists()


@pytest.mark.django_db
def test_imports_status_only_correctness_claims_without_selected_answers():
    session, student = _session()

    import_exam_prep_results(session, {
        'results': [{'phone': student.phone, 'correct': ['q1'], 'wrong': ['q2'], 'unanswered': ['q3']}],
    })

    attempt = StudentExamPrepAttempt.objects.get(session=session, student=student)
    assert attempt.answers['q1'] == {
        'current_answer': '', 'attempts': 1, 'is_correct': True, 'score': 100,
    }
    assert attempt.answers['q2']['is_correct'] is False
    assert 'q3' not in attempt.answers


@pytest.mark.django_db
def test_import_requires_published_exam_prep_session():
    session, student = _session()
    session.is_published = False
    session.save(update_fields=['is_published'])

    with pytest.raises(ResultImportError, match='session must be published'):
        import_exam_prep_results(session, {
            'results': [{'phone': student.phone, 'answers': {'q1': 'الف'}}],
        })
