"""Import the real grade-9 shared-exam result file into published attempts.

Production adapter for the external shape: a **top-level JSON array** of ten
students, each with ``counter``, ``first_name``, ``last_name``, ``group`` and
``courses[{id,name,answers[{q_no,rankq,answer,result}]}]`` where ``result`` is
``correct`` | ``wrong`` | ``white`` and ``answer`` ``'0'`` means white
(unanswered) while ``'1'``..``'4'`` is the selected option label.

The file has no phones: identity comes from the roster. By default the ten
array positions map to the deterministic demo phones (``09129090001``..
``09129090010``); ``--roster-json`` overrides name/phone/password.

Each external ``q_no`` is mapped to the session question id from
``exam_prep_json`` (accepted when the question id ends with ``-<q_no>`` or its
``source_question_number`` equals ``q_no``); rows then delegate to
``import_exam_prep_results`` unchanged in semantics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.classes.models import ClassCreationSession, StudentExamPrepAttempt
from apps.classes.services.exam_prep_result_import import (
    ResultImportError,
    import_exam_prep_results,
)
from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone

DEFAULT_ROSTER_PHONES = [f'091290900{index:02d}' for index in range(1, 11)]
_RESULT_STATES = {'correct', 'wrong', 'white'}
_DIGIT_MAP = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def _digits(value: object) -> str:
    text = str(value or '').strip().translate(_DIGIT_MAP)
    return ''.join(ch for ch in text if ch in '0123456789')


def _number(value: object) -> int | None:
    digits = _digits(value)
    return int(digits) if digits else None


class Command(BaseCommand):
    help = (
        'Import the real grade-9 shared-exam results file (array of ten students '
        'with courses/answers) into published attempts via import_exam_prep_results.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--session-id', type=int, required=True, help='Published EXAM_PREP session ID.')
        parser.add_argument('--results-json', required=True, help='Path to the real external exam-result.json.')
        parser.add_argument(
            '--roster-json',
            help='Optional 10-row JSON roster (array or {"students": [...]}) with name/phone/password.',
        )
        parser.add_argument('--dry-run', action='store_true', help='Validate without writing attempts.')
        parser.add_argument('--force', action='store_true', help='Replace existing attempts for these students.')

    def handle(self, *args, **options):
        session = self._get_session(options['session_id'])
        question_index = self._question_index(session)
        entries = self._read_results(options['results_json'])
        roster_phones = self._load_roster(options.get('roster_json'), len(entries))
        existing_phones = set(
            StudentExamPrepAttempt.objects.filter(session=session).values_list('student__phone', flat=True)
        )
        payload, summary = self._map_payload(entries, roster_phones, question_index, existing_phones)
        try:
            with transaction.atomic():
                result = import_exam_prep_results(session, {'results': payload}, force=options['force'])
                if options['dry_run']:
                    transaction.set_rollback(True)
        except ResultImportError as exc:
            raise CommandError(str(exc)) from exc

        for phone, action in summary:
            self.stdout.write(f'{action}\t{phone}')
        if options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run validated {result['imported']} result(s) across "
                    f"{result['total_questions']} question(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {result['imported']} result(s) across "
                    f"{result['total_questions']} question(s)."
                )
            )

    def _get_session(self, session_id: int) -> ClassCreationSession:
        try:
            session = ClassCreationSession.objects.get(pk=session_id)
        except ClassCreationSession.DoesNotExist as exc:
            raise CommandError(f'Exam Prep session {session_id} was not found.') from exc
        if session.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP or not session.is_published:
            raise CommandError('--session-id must refer to a published EXAM_PREP session.')
        return session

    def _question_index(self, session: ClassCreationSession) -> dict[int, str]:
        """Map canonical printed question numbers to one session question id."""
        try:
            data = json.loads(session.exam_prep_json or '')
        except (TypeError, json.JSONDecodeError) as exc:
            raise CommandError(f'Exam Prep session {session.pk} has invalid exam_prep_json.') from exc
        questions = data.get('exam_prep', {}).get('questions') if isinstance(data, dict) else None
        if not isinstance(questions, list) or not questions:
            raise CommandError(f'Exam Prep session {session.pk} has no questions in exam_prep_json.')
        by_number: dict[int, set[str]] = {}
        for item in questions:
            if not isinstance(item, dict):
                continue
            qid = str(item.get('question_id') or '').strip()
            if not qid:
                continue
            for key in (item.get('source_question_number'), qid.rsplit('-', 1)[-1]):
                number = _number(key)
                if number is not None:
                    by_number.setdefault(number, set()).add(qid)
        index: dict[int, str] = {}
        for number, qids in by_number.items():
            unique = sorted(qids)
            if len(unique) > 1:
                raise CommandError(
                    f'question number {number} maps to multiple session question ids: {", ".join(unique)}.'
                )
            index[number] = unique[0]
        return index

    def _map_payload(
        self,
        entries: list[dict[str, Any]],
        roster_phones: list[str],
        question_index: dict[int, str],
        existing_phones: set[str],
    ) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
        payload: list[dict[str, Any]] = []
        summary: list[tuple[str, str]] = []
        unknowns: set[str] = set()
        for position, (entry, phone) in enumerate(zip(entries, roster_phones), start=1):
            if not isinstance(entry, dict):
                raise CommandError(f'Result row {position} must be an object.')
            records = self._answer_records(entry, position, question_index, unknowns)
            payload.append({'phone': phone, 'questions': records})
            summary.append((phone, 'updated' if phone in existing_phones else 'created'))
        if unknowns:
            listed = ', '.join(sorted(unknowns)[:20])
            raise CommandError(f'unknown question numbers: {listed}')
        return payload, summary

    def _answer_records(
        self,
        entry: dict[str, Any],
        position: int,
        question_index: dict[int, str],
        unknowns: set[str],
    ) -> list[dict[str, str]]:
        courses = entry.get('courses')
        if courses is None:
            return []
        if not isinstance(courses, list):
            raise CommandError(f'Result row {position} courses must be a list.')
        seen: dict[str, tuple[str, str]] = {}
        for course_index, course in enumerate(courses, start=1):
            if not isinstance(course, dict) or not isinstance(course.get('answers'), list):
                raise CommandError(f'Result row {position} course {course_index} answers must be a list.')
            for answer in course['answers']:
                if not isinstance(answer, dict):
                    raise CommandError(f'Result row {position} contains a malformed answer entry.')
                q_no = str(answer.get('q_no') or '').strip()
                result = str(answer.get('result') or '').strip().lower()
                selected = _digits(answer.get('answer'))
                if result not in _RESULT_STATES:
                    raise CommandError(
                        f'Result row {position} question {q_no or "?"} has invalid result: {result!r}.'
                    )
                if not q_no or not selected:
                    raise CommandError(f'Result row {position} contains an answer without q_no/answer.')
                if q_no in seen and seen[q_no] != (selected, result):
                    raise CommandError(f'Result row {position} has conflicting answers for question {q_no}.')
                seen[q_no] = (selected, result)
        records: list[dict[str, str]] = []
        for q_no in sorted(seen, key=lambda value: (len(value), value)):
            selected, result = seen[q_no]
            number = _number(q_no)
            qid = question_index.get(number) if number is not None else None
            if qid is None:
                unknowns.add(q_no)
                continue
            if result == 'white' or selected == '0':
                records.append({'question_id': qid, 'status': 'unanswered'})
            else:
                if selected not in {'1', '2', '3', '4'}:
                    raise CommandError(
                        f'Result row {position} question {q_no} has invalid option answer: {selected!r}.'
                    )
                records.append({'question_id': qid, 'status': result, 'answer': selected})
        return records

    def _read_results(self, json_path: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(Path(json_path).read_text(encoding='utf-8-sig'))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f'Could not read JSON file {json_path}: {exc}') from exc
        if not isinstance(payload, list) or not payload:
            raise CommandError('Results JSON must contain a non-empty array of students.')
        return payload

    def _load_roster(self, roster_path: str | None, student_count: int) -> list[str]:
        if roster_path is None:
            phones = list(DEFAULT_ROSTER_PHONES)
        else:
            try:
                rows = json.loads(Path(roster_path).read_text(encoding='utf-8'))
            except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CommandError(f'Could not read roster JSON file {roster_path}: {exc}') from exc
            if isinstance(rows, dict):
                rows = rows.get('students')
            if not isinstance(rows, list) or not rows:
                raise CommandError('Roster JSON must contain a non-empty array or a students array.')
            phones = [self._roster_phone(row, index) for index, row in enumerate(rows, start=1)]
        if len(phones) != student_count:
            raise CommandError(
                f'Roster has {len(phones)} phone(s) but the results file has {student_count} student(s).'
            )
        if len(set(phones)) != len(phones):
            raise CommandError('Roster phones must be unique.')
        for phone in phones:
            if not is_valid_iran_mobile(phone):
                raise CommandError(f'Roster phone {phone} is not a valid Iranian mobile number.')
        return phones

    @staticmethod
    def _roster_phone(row: Any, index: int) -> str:
        if not isinstance(row, dict) or not str(row.get('phone') or '').strip():
            raise CommandError(f'Roster row {index} requires a phone.')
        return normalize_phone(row['phone'])
