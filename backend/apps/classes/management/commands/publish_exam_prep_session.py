"""Publish one structured exam-prep session (no SMS, no review lane).

Mirrors the always-allow publish policy for publishable exam-prep sessions:
any ``EXAM_PREP`` session in ``EXAM_STRUCTURED`` status with questions in its
``exam_prep_json`` may be published. This command is the operator-facing twin of
the web publish action used by the grade-9 shared-exam demo — it flips
``is_published`` and stamps ``published_at`` in one transaction and never sends
SMS. The broad display-only issue codes gate nothing here, matching the product
rule that publish is always allowed once structuring finished.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.classes.models import ClassCreationSession


class Command(BaseCommand):
    help = 'Publish an EXAM_STRUCTURED EXAM_PREP session and print its question count.'

    def add_arguments(self, parser):
        parser.add_argument('--session-id', type=int, required=True, help='Structured EXAM_PREP session ID.')

    def handle(self, *args, **options):
        session = self._get_publishable(options['session_id'])
        question_count = self._question_count(session)
        with transaction.atomic():
            session = ClassCreationSession.objects.select_for_update().get(pk=session.pk)
            if session.is_published:
                raise CommandError(f'Exam Prep session {session.pk} is already published.')
            session.is_published = True
            session.published_at = timezone.now()
            session.save(update_fields=['is_published', 'published_at', 'updated_at'])
        self.stdout.write(
            self.style.SUCCESS(
                f'Published Exam Prep session {session.pk} with {question_count} question(s).'
            )
        )

    def _get_publishable(self, session_id: int) -> ClassCreationSession:
        try:
            session = ClassCreationSession.objects.get(pk=session_id)
        except ClassCreationSession.DoesNotExist as exc:
            raise CommandError(f'Exam Prep session {session_id} was not found.') from exc
        if session.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP:
            raise CommandError('--session-id must refer to an EXAM_PREP session.')
        if session.status != ClassCreationSession.Status.EXAM_STRUCTURED:
            raise CommandError('--session-id must be in EXAM_STRUCTURED status before publishing.')
        return session

    @staticmethod
    def _question_count(session: ClassCreationSession) -> int:
        try:
            data = json.loads(session.exam_prep_json or '')
        except (TypeError, json.JSONDecodeError) as exc:
            raise CommandError(f'Exam Prep session {session.pk} has invalid exam_prep_json.') from exc
        questions = data.get('exam_prep', {}).get('questions') if isinstance(data, dict) else None
        if not isinstance(questions, list) or not questions:
            raise CommandError(f'Exam Prep session {session.pk} has no questions in exam_prep_json.')
        return len(questions)
