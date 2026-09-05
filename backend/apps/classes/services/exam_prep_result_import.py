"""Import finalized shared exam results without invoking an LLM.

Adapter contract:
``{'results': [{'student': {'phone': '+98...'}, 'answers': {'q1': 'الف'},
'unanswered': ['q2']}]}``. ``student_phone`` or ``phone`` may replace the
student object. An optional ``questions`` list accepts records with
``question_id``, ``status`` (``correct``, ``wrong``, or ``unanswered``), and
``answer``. Status buckets (``correct``/``wrong``/``unanswered``) are also
accepted. Phone is the only identity key; names and row order are ignored.
When an answer is supplied, the published exam key is authoritative and a
supplied ``correct``/``wrong`` status must agree with it. Status-only
correct/wrong records are accepted as authoritative imported outcomes and are
stored with one attempt and an empty selected answer. Unanswered questions are
deliberately omitted from ``answers``.
"""

from __future__ import annotations

import json
from typing import Any

from django.db import transaction

from apps.accounts.models import User
from apps.commons.phone_utils import normalize_phone

from ..models import ClassCreationSession, ClassInvitation, StudentExamPrepAttempt


class ResultImportError(ValueError):
    """Raised when an external result cannot be mapped safely."""


def _questions(session: ClassCreationSession) -> dict[str, str]:
    try:
        data = json.loads(session.exam_prep_json or '')
    except (TypeError, json.JSONDecodeError) as exc:
        raise ResultImportError('session exam JSON is invalid') from exc
    raw = data.get('exam_prep', {}).get('questions', []) if isinstance(data, dict) else []
    if not isinstance(raw, list):
        raise ResultImportError('session exam questions are invalid')
    out: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        qid = str(item.get('question_id') or '').strip()
        if qid:
            out[qid] = str(item.get('correct_option_label') or '').strip()
    if not out:
        raise ResultImportError('session has no importable questions')
    return out


def _phone(row: dict[str, Any]) -> str:
    identity = row.get('student')
    if isinstance(identity, dict):
        raw = identity.get('phone')
    elif isinstance(identity, str):
        raw = identity
    else:
        raw = row.get('phone') or row.get('student_phone')
    phone = normalize_phone(raw)
    if not phone:
        raise ResultImportError('each result requires student.phone')
    return phone


def _statuses(row: dict[str, Any], question_map: dict[str, str]) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    answers = row.get('answers', {})
    if answers is not None and not isinstance(answers, dict):
        raise ResultImportError('answers must be an object keyed by question ID')
    for qid, answer in (answers or {}).items():
        key = str(qid).strip()
        if key:
            entries[key] = ('answered', str(answer).strip())
    records = row.get('questions', [])
    if records and not isinstance(records, list):
        raise ResultImportError('questions must be a list')
    for item in records:
        if not isinstance(item, dict) or not str(item.get('question_id') or '').strip():
            raise ResultImportError('question records require question_id')
        qid = str(item['question_id']).strip()
        status = str(item.get('status') or '').strip().lower()
        if status not in {'correct', 'wrong', 'unanswered'}:
            raise ResultImportError(f'invalid status for question {qid}')
        if status == 'unanswered':
            entries.pop(qid, None)
        else:
            entries[qid] = (status, str(item.get('answer') or '').strip())
    bucket_values: dict[str, Any] = {}
    for bucket, status in (('correct', 'correct'), ('wrong', 'wrong')):
        values = row.get(bucket, [])
        if not isinstance(values, list):
            raise ResultImportError(f'{bucket} must be a list of question IDs')
        bucket_values[bucket] = values
        for qid in values:
            key = str(qid).strip()
            entries[key] = (status, entries.get(key, ('', ''))[1])
    unanswered = row.get('unanswered', [])
    if not isinstance(unanswered, list):
        raise ResultImportError('unanswered must be a list of question IDs')
    for qid in unanswered:
        entries.pop(str(qid).strip(), None)
    unknown = sorted(set(entries) - set(question_map))
    listed = (
        {str(q).strip() for q in unanswered}
        | {str(q).strip() for q in bucket_values['correct']}
        | {str(q).strip() for q in bucket_values['wrong']}
    )
    unknown += sorted(listed - set(question_map))
    if unknown:
        raise ResultImportError(f'unknown question IDs: {", ".join(unknown)}')
    for qid, (status, answer) in entries.items():
        derived = bool(question_map[qid]) and answer == question_map[qid]
        if answer and status in {'correct', 'wrong'} and (status == 'correct') != derived:
            raise ResultImportError(
                f'contradictory status for question {qid}: exam key derives '
                f'{"correct" if derived else "wrong"}'
            )
    return entries


@transaction.atomic
def import_exam_prep_results(session: ClassCreationSession, payload: dict[str, Any], *, force: bool = False) -> dict[str, int]:
    """Atomically import all rows, returning counts and score totals."""
    # Lock the aggregate: a missing child attempt cannot be locked, so the
    # session row serializes concurrent first creates for this session.
    session = ClassCreationSession.objects.select_for_update().get(pk=session.pk)
    if session.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP:
        raise ResultImportError('session must be an EXAM_PREP session')
    if not session.is_published:
        raise ResultImportError('session must be published')
    if not isinstance(payload, dict) or not isinstance(payload.get('results'), list):
        raise ResultImportError('payload.results must be a list')
    question_map = _questions(session)
    invited = {
        normalize_phone(phone)
        for phone in ClassInvitation.objects.filter(session=session).values_list('phone', flat=True)
    }
    rows: list[tuple[User, dict[str, Any]]] = []
    seen: set[str] = set()
    for row in payload['results']:
        if not isinstance(row, dict):
            raise ResultImportError('each result must be an object')
        phone = _phone(row)
        if phone not in invited:
            raise ResultImportError(f'student {phone} is not invited')
        if phone in seen:
            raise ResultImportError(f'duplicate result for student {phone}')
        seen.add(phone)
        student = User.objects.filter(phone=phone, role=User.Role.STUDENT).first()
        if student is None:
            raise ResultImportError(f'invited student {phone} has no account')
        rows.append((student, row))
    imported = 0
    for student, row in rows:
        answers = _statuses(row, question_map)
        attempt = StudentExamPrepAttempt.objects.select_for_update().filter(session=session, student=student).first()
        if attempt is not None and not force:
            raise ResultImportError(f'conflicting attempt for student {student.phone}')
        stored: dict[str, dict[str, Any]] = {}
        correct = 0
        for qid, (state, answer) in answers.items():
            is_correct = state == 'correct' if not answer else bool(question_map[qid]) and answer == question_map[qid]
            stored[qid] = {'current_answer': answer, 'attempts': 1, 'is_correct': is_correct, 'score': 100 if is_correct else 0}
            correct += int(is_correct)
        values = {'answers': stored, 'score_0_100': round(correct * 100 / len(question_map)), 'total_questions': len(question_map), 'correct_count': correct, 'finalized': True}
        if attempt is None:
            StudentExamPrepAttempt.objects.create(session=session, student=student, **values)
        else:
            for key, value in values.items():
                setattr(attempt, key, value)
            attempt.save(update_fields=[*values, 'updated_at'])
        imported += 1
    return {'imported': imported, 'total_questions': len(question_map)}
