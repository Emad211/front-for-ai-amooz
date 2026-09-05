from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_result_import import (
    ResultImportError,
    import_exam_prep_results,
)


class Command(BaseCommand):
    help = 'Import finalized shared Exam Prep results without invoking an LLM.'

    def add_arguments(self, parser):
        parser.add_argument('--session-id', type=int, required=True, help='Published EXAM_PREP session ID.')
        parser.add_argument('--results-json', required=True, help='Path to the JSON results payload.')
        parser.add_argument('--dry-run', action='store_true', help='Validate the payload without writing attempts.')
        parser.add_argument('--force', action='store_true', help='Replace existing attempts for these students.')

    def handle(self, *args, **options):
        session = self._get_session(options['session_id'])
        payload = self._read_payload(options['results_json'])
        try:
            with transaction.atomic():
                result = import_exam_prep_results(session, payload, force=options['force'])
                if options['dry_run']:
                    transaction.set_rollback(True)
        except ResultImportError as exc:
            raise CommandError(str(exc)) from exc

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f"Dry run validated {result['imported']} result(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Imported {result['imported']} result(s)."))

    def _get_session(self, session_id: int) -> ClassCreationSession:
        try:
            session = ClassCreationSession.objects.get(pk=session_id)
        except ClassCreationSession.DoesNotExist as exc:
            raise CommandError(f'Exam Prep session {session_id} was not found.') from exc
        if session.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP or not session.is_published:
            raise CommandError('--session-id must refer to a published EXAM_PREP session.')
        return session

    def _read_payload(self, json_path: str) -> dict[str, Any]:
        try:
            payload = json.loads(Path(json_path).read_text(encoding='utf-8'))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f'Could not read JSON file {json_path}: {exc}') from exc
        if not isinstance(payload, dict):
            raise CommandError('Results JSON must contain an object payload.')
        return payload
