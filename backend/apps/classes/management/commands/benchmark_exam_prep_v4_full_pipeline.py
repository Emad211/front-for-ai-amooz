import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_v4_benchmark import (
    BenchmarkMode,
    load_benchmark_manifest,
)
from apps.classes.services.exam_prep_v4_full_benchmark import (
    FullBenchmarkError,
    run_full_pipeline_benchmark,
)


class Command(BaseCommand):
    help = (
        'Run the private Exam Prep V4 cold/warm full extraction benchmark and '
        'write an aggregate-only report.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument(
            '--mode',
            required=True,
            choices=[BenchmarkMode.FAKE_PROVIDER, BenchmarkMode.LIVE_PROVIDER],
        )
        parser.add_argument(
            '--model',
            default='',
            help='Use one explicit live model for classifier, block, question, and answer stages.',
        )
        parser.add_argument('--classifier-model', default='')
        parser.add_argument('--block-model', default='')
        parser.add_argument('--question-model', default='')
        parser.add_argument('--answer-model', default='')
        parser.add_argument('--report', required=True)
        parser.add_argument('--keep-projects', action='store_true')

    def handle(self, *args, **options):
        common_model = str(options.get('model') or '').strip()
        classifier_model = str(options.get('classifier_model') or '').strip() or common_model
        block_model = str(options.get('block_model') or '').strip() or common_model
        question_model = str(options.get('question_model') or '').strip() or common_model
        answer_model = str(options.get('answer_model') or '').strip() or common_model

        try:
            manifest = load_benchmark_manifest(options['manifest'])
            result = run_full_pipeline_benchmark(
                manifest=manifest,
                mode=options['mode'],
                classifier_model=classifier_model or None,
                block_model=block_model or None,
                question_model=question_model or None,
                answer_model=answer_model or None,
                keep_projects=bool(options.get('keep_projects')),
            )
        except (FullBenchmarkError, ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        report_path = Path(options['report']).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding='utf-8',
        )
        self.stdout.write(
            self.style.SUCCESS(
                'Exam Prep V4 full-pipeline benchmark completed. '
                f'aggregate_report={report_path} '
                f'passed={result.report["acceptance"]["passed"]}'
            )
        )
