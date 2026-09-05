"""Focused tests for the three grade-9 shared-exam production commands."""
from __future__ import annotations

import json
from io import StringIO
from unittest import mock
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from model_bakery import baker

from apps.classes.models import ClassCreationSession, ClassInvitation, StudentExamPrepAttempt

User = get_user_model()

pytestmark = pytest.mark.django_db

DEMO_PHONES = [f'091290900{index:02d}' for index in range(1, 11)]
PDF_BYTES = b'%PDF-1.4\n1 0 obj\n%%EOF'


def _run(command: str, *args: str) -> str:
    output = StringIO()
    call_command(command, *args, stdout=output)
    return output.getvalue()


def _questions() -> tuple[list[dict], dict[int, str]]:
    """Three questions; number 3 is mapped only via source_question_number."""
    qid_by_number = {
        1: f'grade9-exam-{uuid4().hex[:8]}-1',
        2: f'grade9-exam-{uuid4().hex[:8]}-2',
        3: f'grade9-exam-{uuid4().hex[:8]}-final',
    }
    keys = {1: '1', 2: '3', 3: '2'}
    questions = [
        {
            'question_id': qid_by_number[number],
            'question_text_markdown': f'Question {number}',
            'options': ['1', '2', '3', '4'],
            'correct_option_label': keys[number],
            'source_question_number': str(number),
        }
        for number in (1, 2, 3)
    ]
    return questions, qid_by_number


def _session() -> tuple[ClassCreationSession, dict[int, str], list[User]]:
    teacher = baker.make(User, role=User.Role.TEACHER)
    questions, qid_by_number = _questions()
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        is_published=True,
        source_file='',
        exam_prep_json=json.dumps({'exam_prep': {'title': 'Grade 9', 'questions': questions}}),
    )
    students: list[User] = []
    for index, phone in enumerate(DEMO_PHONES, start=1):
        student = User.objects.create_user(
            username=f'grade9_student_{index:02d}',
            password='grade9-demo-123',
            role=User.Role.STUDENT,
            phone=phone,
            first_name=f'Student{index}',
        )
        ClassInvitation.objects.create(session=session, phone=phone, invite_code=f'inv-{index:02d}')
        students.append(student)
    return session, qid_by_number, students


def _write_results(tmp_path, students: list[dict], name: str = 'exam-result.json') -> str:
    path = tmp_path / name
    path.write_bytes(b'\xef\xbb\xbf' + json.dumps(students, ensure_ascii=False).encode('utf-8'))
    return str(path)


def _student_entry(index: int, answers: list[dict]) -> dict:
    return {
        'counter': index,
        'first_name': f'Student{index}',
        'last_name': 'Last',
        'group': {'code': 'g9', 'name': 'نهم'},
        'courses': [{'id': 1, 'name': 'علوم', 'answers': answers}],
    }


def _answer(q_no: str, answer: str, result: str) -> dict:
    return {'q_no': q_no, 'rankq': q_no, 'answer': answer, 'result': result}


def _real_file(answers_by_index: dict[int, list[dict]], student_count: int = 10) -> list[dict]:
    return [
        _student_entry(index, answers_by_index.get(index, []))
        for index in range(1, student_count + 1)
    ]


# ---------------------------------------------------------------------------
# ingest_exam_prep_pdf
# ---------------------------------------------------------------------------
@override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
def test_ingest_creates_session_and_dispatches_to_pipeline_queue(tmp_path):
    pdf = tmp_path / 'exam.pdf'
    pdf.write_bytes(PDF_BYTES)
    target = 'apps.classes.management.commands.ingest_exam_prep_pdf.process_exam_prep_pdf_session.apply_async'
    with mock.patch(target) as apply_async:
        output = _run('ingest_exam_prep_pdf', '--pdf', str(pdf), '--title', 'Grade 9 Exam')

    apply_async.assert_called_once()
    call = apply_async.call_args
    session = ClassCreationSession.objects.get()
    assert call.kwargs['args'] == [session.pk]
    assert call.kwargs['queue'] == 'pipeline'
    assert call.kwargs['task_id'] == session.celery_task_id
    assert session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
    assert session.source_type == ClassCreationSession.SourceType.PDF
    assert session.source_mime_type == 'application/pdf'
    assert session.source_original_name == 'exam.pdf'
    assert session.status == ClassCreationSession.Status.EXAM_TRANSCRIBING
    assert session.workflow_state.get('stage') == 'queued'
    assert session.client_request_id is not None
    teacher = session.teacher
    assert teacher.role == User.Role.TEACHER
    assert teacher.check_password('grade9-teacher-123')
    assert f'Queued exam-prep session {session.pk}' in output


@override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
def test_ingest_is_idempotent_and_never_runs_ocr_synchronously(tmp_path):
    pdf = tmp_path / 'exam.pdf'
    pdf.write_bytes(PDF_BYTES)
    target = 'apps.classes.management.commands.ingest_exam_prep_pdf.process_exam_prep_pdf_session.apply_async'
    with mock.patch(target) as apply_async:
        first = _run('ingest_exam_prep_pdf', '--pdf', str(pdf), '--title', 'Grade 9 Exam')
        second = _run('ingest_exam_prep_pdf', '--pdf', str(pdf), '--title', 'Grade 9 Exam')

    assert ClassCreationSession.objects.count() == 1
    apply_async.assert_called_once()  # OCR task dispatched exactly once
    session = ClassCreationSession.objects.get()
    assert f'Queued exam-prep session {session.pk}' in first
    assert f'Reused exam-prep session {session.pk}' in second


@override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
def test_ingest_creates_default_teacher_and_rejects_missing_pdf(tmp_path):
    pdf = tmp_path / 'exam.pdf'
    pdf.write_bytes(PDF_BYTES)
    target = 'apps.classes.management.commands.ingest_exam_prep_pdf.process_exam_prep_pdf_session.apply_async'
    with mock.patch(target):
        _run('ingest_exam_prep_pdf', '--pdf', str(pdf), '--title', 'Grade 9 Exam')

    assert User.objects.get(username='teacher').role == User.Role.TEACHER
    with pytest.raises(CommandError, match='does not exist'):
        _run('ingest_exam_prep_pdf', '--pdf', str(tmp_path / 'missing.pdf'), '--title', 'Grade 9 Exam')


# ---------------------------------------------------------------------------
# publish_exam_prep_session
# ---------------------------------------------------------------------------
def _structured_session(status: str = ClassCreationSession.Status.EXAM_STRUCTURED) -> ClassCreationSession:
    teacher = baker.make(User, role=User.Role.TEACHER)
    return baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=status,
        source_file='',
        exam_prep_json=json.dumps({'exam_prep': {'questions': [{'question_id': 'q1'}] * 3}}),
    )


def test_publish_rejects_unstructured_and_missing_questions():
    session = _structured_session(status=ClassCreationSession.Status.EXAM_TRANSCRIBING)
    with pytest.raises(CommandError, match='must be in EXAM_STRUCTURED'):
        _run('publish_exam_prep_session', '--session-id', str(session.pk))

    empty = baker.make(
        ClassCreationSession,
        teacher=baker.make(User, role=User.Role.TEACHER),
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        source_file='',
        exam_prep_json=json.dumps({'exam_prep': {'questions': []}}),
    )
    with pytest.raises(CommandError, match='no questions'):
        _run('publish_exam_prep_session', '--session-id', str(empty.pk))


def test_publish_publishes_once_with_question_count():
    session = _structured_session()
    output = _run('publish_exam_prep_session', '--session-id', str(session.pk))
    session.refresh_from_db()
    assert session.is_published is True
    assert session.published_at is not None
    assert '3 question(s)' in output

    with pytest.raises(CommandError, match='already published'):
        _run('publish_exam_prep_session', '--session-id', str(session.pk))


# ---------------------------------------------------------------------------
# import_grade9_exam_results
# ---------------------------------------------------------------------------
def test_adapter_maps_real_rows_to_question_ids_and_white_to_unanswered(tmp_path):
    session, qid_by_number, _students = _session()
    results = _real_file({
        1: [
            _answer('1', '2', 'wrong'),
            _answer('2', '3', 'correct'),
            _answer('3', '0', 'white'),
        ]
    })
    results_path = _write_results(tmp_path, results)

    output = _run('import_grade9_exam_results', '--session-id', str(session.pk), '--results-json', results_path)

    attempt = StudentExamPrepAttempt.objects.get(session=session, student__phone='09129090001')
    assert set(attempt.answers) == {qid_by_number[1], qid_by_number[2]}
    assert attempt.answers[qid_by_number[1]]['is_correct'] is False
    assert attempt.answers[qid_by_number[1]]['current_answer'] == '2'
    assert attempt.answers[qid_by_number[2]]['is_correct'] is True
    assert qid_by_number[3] not in attempt.answers
    assert attempt.correct_count == 1
    assert StudentExamPrepAttempt.objects.filter(session=session).count() == 10
    assert 'created\t09129090001' in output
    assert 'Imported 10 result(s) across 3 question(s)' in output


def test_adapter_rejects_unknown_q_no_without_writing(tmp_path):
    session, _qid_by_number, _students = _session()
    results = _real_file({1: [_answer('999', '1', 'correct')]})
    results_path = _write_results(tmp_path, results)

    with pytest.raises(CommandError, match='unknown question numbers: 999'):
        _run('import_grade9_exam_results', '--session-id', str(session.pk), '--results-json', results_path)
    assert not StudentExamPrepAttempt.objects.filter(session=session).exists()


def test_adapter_rejects_uninvited_roster_phone(tmp_path):
    session, _qid_by_number, _students = _session()
    results = _real_file({1: [_answer('1', '2', 'wrong')]})
    results_path = _write_results(tmp_path, results)
    roster = tmp_path / 'roster.json'
    rows = [{'name': f'Student {i}', 'phone': phone, 'password': 'demo-pass'} for i, phone in enumerate(DEMO_PHONES, start=1)]
    rows[-1]['phone'] = '09129999999'  # never invited
    roster.write_text(json.dumps(rows), encoding='utf-8')

    with pytest.raises(CommandError, match='not invited'):
        _run(
            'import_grade9_exam_results',
            '--session-id', str(session.pk),
            '--results-json', results_path,
            '--roster-json', str(roster),
        )
    assert not StudentExamPrepAttempt.objects.filter(session=session).exists()


def test_adapter_dry_run_validates_without_writing_attempts(tmp_path):
    session, _qid_by_number, _students = _session()
    results = _real_file({1: [_answer('1', '1', 'correct'), _answer('2', '0', 'white')]})
    results_path = _write_results(tmp_path, results)

    output = _run(
        'import_grade9_exam_results',
        '--session-id', str(session.pk),
        '--results-json', results_path,
        '--dry-run',
    )

    assert not StudentExamPrepAttempt.objects.filter(session=session).exists()
    assert 'Dry run validated 10 result(s)' in output


def test_adapter_force_replaces_existing_attempt_and_normalizes_roster_phones(tmp_path):
    session, qid_by_number, _students = _session()
    results = _real_file({1: [_answer('1', '1', 'correct')]})
    results_path = _write_results(tmp_path, results)
    roster = tmp_path / 'roster.json'
    roster.write_text(
        json.dumps([
            {'name': f'Student {i}', 'phone': '+98 912 909 0001' if i == 1 else phone, 'password': 'demo-pass'}
            for i, phone in enumerate(DEMO_PHONES, start=1)
        ]),
        encoding='utf-8',
    )
    _run('import_grade9_exam_results', '--session-id', str(session.pk), '--results-json', results_path, '--roster-json', str(roster))
    assert StudentExamPrepAttempt.objects.get(session=session, student__phone='09129090001').answers[qid_by_number[1]]['is_correct'] is True

    _run(
        'import_grade9_exam_results',
        '--session-id', str(session.pk),
        '--results-json', results_path,
        '--roster-json', str(roster),
        '--force',
    )
    assert StudentExamPrepAttempt.objects.filter(session=session).count() == 10
    assert 'updated\t09129090001' in _run(
        'import_grade9_exam_results',
        '--session-id', str(session.pk),
        '--results-json', results_path,
        '--roster-json', str(roster),
        '--force',
    )
