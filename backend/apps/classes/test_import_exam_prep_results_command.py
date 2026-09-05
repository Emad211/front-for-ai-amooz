import json

import pytest
from django.core.management import CommandError, call_command
from model_bakery import baker

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentExamPrepAttempt


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
        ]}}),
    )
    ClassInvitation.objects.create(session=session, phone=phone, invite_code='code')
    return session, student


def _write_payload(tmp_path, payload: dict, name: str = 'results.json') -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding='utf-8')
    return str(path)


@pytest.mark.django_db
def test_import_command_imports_results_and_reports_count(tmp_path, capsys):
    session, student = _session()
    results_path = _write_payload(tmp_path, {
        'results': [{'student': {'phone': '+98 912 000 0001'}, 'answers': {'q1': 'الف'}}]
    })

    call_command('import_exam_prep_results', '--session-id', session.pk, '--results-json', results_path)

    attempt = StudentExamPrepAttempt.objects.get(session=session, student=student)
    assert attempt.correct_count == 1
    assert 'Imported 1 result(s)' in capsys.readouterr().out


@pytest.mark.django_db
def test_import_command_dry_run_validates_without_writing_attempt(tmp_path, capsys):
    session, _student = _session()
    results_path = _write_payload(tmp_path, {
        'results': [{'phone': '09120000001', 'answers': {'q1': 'الف'}}]
    })

    call_command(
        'import_exam_prep_results', '--session-id', session.pk, '--results-json', results_path, '--dry-run'
    )

    assert not StudentExamPrepAttempt.objects.filter(session=session).exists()
    assert 'Dry run validated 1 result(s)' in capsys.readouterr().out


@pytest.mark.django_db
def test_import_command_force_replaces_existing_attempt(tmp_path):
    session, student = _session()
    results_path = _write_payload(tmp_path, {
        'results': [{'phone': student.phone, 'answers': {'q1': 'ب'}}]
    }, name='replacement.json')
    first_path = _write_payload(tmp_path, {
        'results': [{'phone': student.phone, 'answers': {'q1': 'الف'}}]
    }, name='initial.json')
    call_command('import_exam_prep_results', '--session-id', session.pk, '--results-json', first_path)

    call_command(
        'import_exam_prep_results', '--session-id', session.pk, '--results-json', results_path, '--force'
    )

    assert StudentExamPrepAttempt.objects.get(session=session, student=student).answers['q1']['is_correct'] is False


@pytest.mark.django_db
def test_import_command_rejects_conflict_and_malformed_json(tmp_path):
    session, student = _session()
    valid_path = _write_payload(tmp_path, {'results': [{'phone': student.phone, 'answers': {'q1': 'الف'}}]})
    call_command('import_exam_prep_results', '--session-id', session.pk, '--results-json', valid_path)

    with pytest.raises(CommandError, match='conflicting attempt'):
        call_command('import_exam_prep_results', '--session-id', session.pk, '--results-json', valid_path)

    malformed_path = tmp_path / 'malformed.json'
    malformed_path.write_text('{', encoding='utf-8')
    with pytest.raises(CommandError, match='Could not read JSON'):
        call_command('import_exam_prep_results', '--session-id', session.pk, '--results-json', str(malformed_path))
