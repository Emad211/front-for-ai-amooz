from __future__ import annotations

import json
import uuid
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_v4_benchmark import (
    BenchmarkConfigurationError,
    BenchmarkManifestError,
    load_benchmark_manifest,
    run_benchmark,
)
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled


class Command(BaseCommand):
    help = (
        'Run the privacy-safe Exam Prep V4 classify-and-segment benchmark. '
        'Source paths and source content are never printed.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument(
            '--stage',
            choices=['classify-and-segment'],
            default='classify-and-segment',
        )
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            '--fake-provider',
            action='store_true',
            help='Use deterministic content-free expected roles; no network call.',
        )
        mode.add_argument(
            '--live-provider',
            action='store_true',
            help='Call the configured provider and record aggregate usage.',
        )
        parser.add_argument('--model', default='')
        parser.add_argument('--teacher-id', type=int)
        parser.add_argument('--keep-projects', action='store_true')
        parser.add_argument('--output', default='')
        parser.add_argument('--indent', type=int, default=2)

    def _resolve_teacher(self, *, teacher_id: int | None, keep_projects: bool):
        User = get_user_model()
        if teacher_id is not None:
            teacher = User.objects.filter(id=teacher_id, role='TEACHER').first()
            if teacher is None:
                raise CommandError('Benchmark teacher is unavailable or is not a teacher.')
            return teacher, False
        if keep_projects:
            raise CommandError('--keep-projects requires --teacher-id.')
        teacher = User.objects.create_user(
            username=f'v4-benchmark-{uuid.uuid4().hex}',
            role='TEACHER',
            is_active=False,
        )
        teacher.set_unusable_password()
        teacher.save(update_fields=['password'])
        return teacher, True

    @staticmethod
    def _write_report(*, output: str, payload: str) -> None:
        destination = Path(output).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(
            f'.{destination.name}.{uuid.uuid4().hex}.tmp'
        )
        try:
            temporary.write_text(payload + '\n', encoding='utf-8')
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()

    def handle(self, *args, **options):
        if not exam_prep_v4_enabled():
            raise CommandError('Exam Prep V4 is disabled.')

        try:
            manifest = load_benchmark_manifest(options['manifest'])
        except BenchmarkManifestError as exc:
            raise CommandError(str(exc)) from exc

        teacher = None
        temporary_teacher = False
        try:
            teacher, temporary_teacher = self._resolve_teacher(
                teacher_id=options.get('teacher_id'),
                keep_projects=bool(options.get('keep_projects')),
            )
            mode = 'live_provider' if options.get('live_provider') else 'fake_provider'
            try:
                report = run_benchmark(
                    manifest=manifest,
                    teacher=teacher,
                    mode=mode,
                    model=(options.get('model') or '').strip() or None,
                    keep_projects=bool(options.get('keep_projects')),
                )
            except BenchmarkConfigurationError as exc:
                raise CommandError(str(exc)) from exc
            except Exception as exc:
                raise CommandError(
                    f'Benchmark execution failed with {type(exc).__name__}.'
                ) from exc

            indent = max(0, min(8, int(options.get('indent') or 0)))
            payload = json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                indent=indent or None,
            )
            if options.get('output'):
                self._write_report(output=options['output'], payload=payload)
            self.stdout.write(payload)

            if report.get('status') != 'passed':
                raise CommandError('Benchmark acceptance failed; aggregate status is failed.')
        finally:
            if temporary_teacher and teacher is not None:
                teacher.delete()
