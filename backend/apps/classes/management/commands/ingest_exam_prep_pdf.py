"""Queue a shared grade-9 exam PDF into the production exam-prep pipeline.

Production-safe CLI twin of ``ExamPrepPdfStep1View``: create (or reuse) one
``EXAM_PREP`` ``ClassCreationSession`` exactly like the web intake —
``pipeline_type=EXAM_PREP``, ``source_type=PDF``, ``status=EXAM_TRANSCRIBING``,
``workflow_state`` stage ``queued`` with the Mistral OCR engine stamp — then
dispatch ``process_exam_prep_pdf_session`` on the ``pipeline`` Celery queue.

Never runs OCR synchronously and never blocks on the worker.

Storage note: the local PDF is copied into ``source_file`` using the Django
storage configured for this process. The worker must read from the *same*
storage, so run this inside the backend container/production where the storage
env matches the Celery workers (typically the ``backend`` service).
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE
from apps.classes.services.session_workflow import build_session_workflow_state
from apps.classes.tasks_exam_prep import process_exam_prep_pdf_session

User = get_user_model()

TEACHER_PASSWORD = 'grade9-teacher-123'
_ID_NAMESPACE = uuid.UUID('8f7e92c4-3a5d-4c1b-9e6a-2b4d0f1a7c33')


def _workflow_state(stage: str, *, message: str) -> dict:
    """Match ``views_exam_prep._mistral_workflow_state`` byte-for-byte."""
    state = build_session_workflow_state(stage, message=message)
    state['engine'] = PRODUCTION_ENGINE
    return state


class Command(BaseCommand):
    help = (
        'Create-or-reuse one EXAM_PREP session from a local PDF and queue the '
        'async production OCR pipeline task (queue=pipeline). Run inside the '
        'backend container so source_file storage matches the worker storage.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--pdf', required=True, help='Path to the local exam PDF file.')
        parser.add_argument('--title', required=True, help='Exam title stored on the session.')
        parser.add_argument(
            '--teacher-username',
            default='teacher',
            help='Username of the owning TEACHER; created with a usable password if missing.',
        )
        parser.add_argument(
            '--client-request-id',
            help='Idempotency key (UUID). Defaults to a UUID v5 derived from the PDF sha256.',
        )

    def handle(self, *args, **options):
        pdf_bytes, pdf_name = self._read_pdf(options['pdf'])
        teacher = self._get_teacher(options['teacher_username'])
        client_request_id = self._request_id(pdf_bytes, options.get('client_request_id'))

        existing = ClassCreationSession.objects.filter(
            teacher=teacher,
            client_request_id=client_request_id,
        ).first()
        if existing is not None:
            if (
                existing.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP
                or not self._same_source(existing, pdf_name, len(pdf_bytes))
            ):
                raise CommandError(
                    f'client_request_id {client_request_id} is already attached to session '
                    f'{existing.pk} with a different source; pass a fresh --client-request-id.'
                )
            self.stdout.write(self.style.SUCCESS(f'Reused exam-prep session {existing.pk} (already queued/processed).'))
            return

        session = self._create_session(
            teacher=teacher,
            title=options['title'],
            client_request_id=client_request_id,
            pdf_bytes=pdf_bytes,
            pdf_name=pdf_name,
        )
        task_id = uuid.uuid4().hex
        session.celery_task_id = task_id
        session.save(update_fields=['celery_task_id', 'updated_at'])
        try:
            process_exam_prep_pdf_session.apply_async(
                args=[session.pk],
                task_id=task_id,
                queue='pipeline',
                retry=False,
            )
        except Exception:
            session.status = ClassCreationSession.Status.FAILED
            session.celery_task_id = ''
            session.error_detail = 'Queueing the exam-prep pipeline task failed.'
            session.workflow_state = _workflow_state(
                'failed',
                message='Queueing the exam-prep pipeline task failed; re-run the command.',
            )
            session.save(
                update_fields=['status', 'celery_task_id', 'error_detail', 'workflow_state', 'updated_at']
            )
            raise CommandError(
                f'PDF stored as session {session.pk} but queueing failed; fix the broker and re-run '
                'with a fresh --client-request-id.'
            ) from None

        self.stdout.write(self.style.SUCCESS(f'Queued exam-prep session {session.pk} (title: {session.title}).'))

    def _read_pdf(self, raw_path: str) -> tuple[bytes, str]:
        path = Path(raw_path)
        if not path.is_file():
            raise CommandError(f'PDF file does not exist: {raw_path}')
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise CommandError(f'Could not read PDF file {raw_path}: {exc}') from exc
        if not data.lstrip().startswith(b'%PDF'):
            raise CommandError(f'{raw_path} is not a PDF file (missing %PDF magic bytes).')
        return data, path.name

    def _get_teacher(self, username: str):
        teacher, created = User.objects.get_or_create(
            username=username,
            defaults={
                'role': User.Role.TEACHER,
                'email': f'{username}@example.com',
            },
        )
        if created or teacher.role != User.Role.TEACHER or not teacher.has_usable_password():
            teacher.role = User.Role.TEACHER
            teacher.set_password(TEACHER_PASSWORD)
            teacher.save(update_fields=['password', 'role'])
        return teacher

    def _request_id(self, pdf_bytes: bytes, provided: str | None) -> uuid.UUID:
        if provided:
            try:
                return uuid.UUID(str(provided))
            except (ValueError, AttributeError, TypeError) as exc:
                raise CommandError(f'--client-request-id must be a valid UUID: {provided}') from exc
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        return uuid.uuid5(_ID_NAMESPACE, digest)

    @staticmethod
    def _same_source(session: ClassCreationSession, pdf_name: str, byte_size: int) -> bool:
        old_name = str(session.source_original_name or '').strip()
        if pdf_name and old_name and pdf_name != old_name:
            return False
        try:
            old_size = int(session.source_file.size) if session.source_file else 0
        except Exception:
            old_size = 0
        return not (byte_size and old_size and byte_size != old_size)

    def _create_session(self, *, teacher, title: str, client_request_id: uuid.UUID, pdf_bytes: bytes, pdf_name: str) -> ClassCreationSession:
        with transaction.atomic():
            return ClassCreationSession.objects.create(
                teacher=teacher,
                title=title,
                description='Grade 9 shared exam imported from PDF.',
                pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                source_type=ClassCreationSession.SourceType.PDF,
                source_file=ContentFile(pdf_bytes, name=pdf_name),
                source_mime_type='application/pdf',
                source_original_name=pdf_name,
                status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
                client_request_id=client_request_id,
                workflow_state=_workflow_state(
                    'queued',
                    message='PDF is queued for processing.',
                ),
            )
