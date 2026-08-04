"""Print the read-only exam-prep legacy drain inventory."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.classes.services.exam_prep_legacy_audit import (
    build_exam_prep_legacy_audit,
)


class Command(BaseCommand):
    help = (
        'Read-only inventory of legacy exam-prep sessions, task IDs, V4 projects, '
        'and the retain/drain/re-upload plan. This command performs no writes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-ids',
            action='store_true',
            help='Include session, project, and Celery task IDs in the output.',
        )
        parser.add_argument(
            '--compact',
            action='store_true',
            help='Print compact JSON instead of indented JSON.',
        )

    def handle(self, *args, **options):
        report = build_exam_prep_legacy_audit(
            include_ids=bool(options['include_ids']),
        )
        self.stdout.write(
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                indent=None if options['compact'] else 2,
            )
        )
