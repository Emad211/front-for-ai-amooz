import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_PINNED_MODEL,
)
from apps.classes.services.exam_prep_v4_benchmark_guard import (
    calculate_required_external_request_ceiling,
    run_bounded_full_pipeline_benchmark,
)
from apps.classes.services.exam_prep_v4_full_benchmark import (
    FullBenchmarkError,
    FullBenchmarkManifestError,
    load_full_benchmark_manifest,
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
            choices=['fake_provider', 'live_provider'],
        )
        parser.add_argument(
            '--model',
            default='',
            help=(
                'Use one explicit live model for classifier, block, question, '
                'and answer stages.'
            ),
        )
        parser.add_argument('--classifier-model', default='')
        parser.add_argument('--block-model', default='')
        parser.add_argument('--question-model', default='')
        parser.add_argument('--answer-model', default='')
        parser.add_argument(
            '--ocr-evidence',
            action='store_true',
            help=(
                'Use the optional AvalAI OCR evidence adapter for block '
                'proposals; existing structured detector remains fallback.'
            ),
        )
        parser.add_argument(
            '--ocr-model',
            default=AVALAI_OCR_PINNED_MODEL,
        )
        parser.add_argument(
            '--ocr-max-attempts',
            type=int,
            default=2,
        )
        parser.add_argument(
            '--ocr-bbox-for-diagrams',
            action='store_true',
            help='Allow one bounded bbox-annotation path for diagram pages.',
        )
        parser.add_argument(
            '--max-provider-calls',
            type=int,
            default=None,
            help=(
                'Mandatory hard ceiling for all live external calls, including '
                'structured fallbacks/repairs and direct OCR requests.'
            ),
        )
        parser.add_argument(
            '--show-required-ceiling',
            action='store_true',
            help=(
                'Print the deterministic manifest/config ceiling and exit '
                'without creating projects or calling providers.'
            ),
        )
        parser.add_argument('--report', required=True)
        parser.add_argument('--keep-projects', action='store_true')

    def handle(self, *args, **options):
        common_model = str(options.get('model') or '').strip()
        classifier_model = (
            str(options.get('classifier_model') or '').strip() or common_model
        )
        block_model = str(options.get('block_model') or '').strip() or common_model
        question_model = (
            str(options.get('question_model') or '').strip() or common_model
        )
        answer_model = str(options.get('answer_model') or '').strip() or common_model
        ocr_enabled = bool(options.get('ocr_evidence'))
        ocr_model = str(options.get('ocr_model') or '').strip()
        ocr_attempts = options.get('ocr_max_attempts')
        ocr_bbox = bool(options.get('ocr_bbox_for_diagrams'))

        try:
            manifest = load_full_benchmark_manifest(options['manifest'])
            ceiling_plan = calculate_required_external_request_ceiling(
                manifest=manifest,
                ocr_evidence_enabled=ocr_enabled,
                ocr_max_attempts=ocr_attempts,
                ocr_bbox_for_diagrams=ocr_bbox,
            )
            if options.get('show_required_ceiling'):
                self.stdout.write(
                    json.dumps(
                        ceiling_plan,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                return
            result = run_bounded_full_pipeline_benchmark(
                manifest=manifest,
                mode=options['mode'],
                classifier_model=classifier_model or None,
                block_model=block_model or None,
                question_model=question_model or None,
                answer_model=answer_model or None,
                keep_projects=bool(options.get('keep_projects')),
                max_provider_calls=options.get('max_provider_calls'),
                ocr_evidence_enabled=ocr_enabled,
                ocr_model=ocr_model,
                ocr_max_attempts=ocr_attempts,
                ocr_bbox_for_diagrams=ocr_bbox,
            )
        except (
            FullBenchmarkError,
            FullBenchmarkManifestError,
            ValueError,
            OSError,
        ) as exc:
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
