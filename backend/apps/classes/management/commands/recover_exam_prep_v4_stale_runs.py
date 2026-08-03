from django.core.management.base import BaseCommand, CommandError

from apps.classes.tasks_v4_recovery import recover_exam_prep_v4_stale_runs


class Command(BaseCommand):
    help = (
        'Mark stale active Exam Prep V4 extraction runs failed and request '
        'cooperative worker cancellation.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-age-minutes',
            type=int,
            default=None,
            help='Override EXAM_PREP_V4_STALE_RUN_MINUTES for this execution.',
        )
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, *args, **options):
        max_age = options.get('max_age_minutes')
        limit = options.get('limit')
        if max_age is not None and max_age < 1:
            raise CommandError('--max-age-minutes must be positive.')
        if limit < 1:
            raise CommandError('--limit must be positive.')
        result = recover_exam_prep_v4_stale_runs.run(
            max_age_minutes=max_age,
            limit=limit,
        )
        self.stdout.write(
            self.style.SUCCESS(
                'Exam Prep V4 stale-run recovery completed. '
                f'candidates={result["candidateCount"]} '
                f'recovered={result["recoveredCount"]} '
                f'max_age_minutes={result["maxAgeMinutes"]}'
            )
        )
