from __future__ import annotations

import json
from pathlib import Path
import zipfile
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_mistral_booklet_ranges import (
    extract_booklet_ranges,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import (
    analyze_ocr_document,
)
from apps.classes.services.exam_prep_mistral_solution_headings import (
    audit_solution_headings,
)


def _member(archive: zipfile.ZipFile, name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(archive.read(name).decode('utf-8'))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandError(f'Bundle is missing valid {name}.') from exc
    if not isinstance(value, Mapping):
        raise CommandError(f'{name} must contain one JSON object.')
    return value


def _load_success_bundle(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise CommandError('The supplied bundle is not a readable ZIP.') from exc
    with archive:
        names = set(archive.namelist())
        if 'failure.json' in names and 'response.raw.json' not in names:
            failure = _member(archive, 'failure.json')
            raise CommandError(
                'Cannot audit a failed OCR bundle: '
                f"chunk={failure.get('failedChunkIndex')}, "
                f"httpStatus={failure.get('httpStatus')}, "
                f"reason={failure.get('reason')}."
            )
        return _member(archive, 'response.raw.json'), _member(archive, 'manifest.json')


def _page_mapping(manifest: Mapping[str, Any]) -> list[int] | None:
    selected = manifest.get('selectedOriginalPages')
    if not isinstance(selected, list):
        return None
    try:
        return [int(value) for value in selected]
    except (TypeError, ValueError):
        return None


def build_document_contract(
    root: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    expected_last_question: int = 155,
) -> dict[str, Any]:
    mapping = _page_mapping(manifest)
    ranges = extract_booklet_ranges(root, original_page_numbers=mapping)
    layout = analyze_ocr_document(root, original_page_numbers=mapping)
    solutions = audit_solution_headings(
        root,
        original_page_numbers=mapping,
        first_expected_question=1,
        last_expected_question=expected_last_question,
    )

    question_numbers = sorted(
        int(region['questionNumber'])
        for page in layout.get('pages') or []
        if page.get('pageRole') == 'question'
        for region in page.get('regions') or []
        if region.get('kind') == 'question'
        and isinstance(region.get('questionNumber'), int)
    )
    unique_questions = sorted(set(question_numbers))
    expected = list(range(1, expected_last_question + 1))
    question_duplicates = sorted(
        number
        for number in unique_questions
        if question_numbers.count(number) > 1
    )
    question_missing = sorted(set(expected) - set(unique_questions))
    question_exact = (
        question_numbers == expected
        and not question_duplicates
        and not question_missing
    )

    declared_exact = bool(
        ranges.get('overallStart') == 1
        and ranges.get('overallEnd') == expected_last_question
        and ranges.get('declaredQuestionCount') == expected_last_question
        and not ranges.get('gaps')
        and not ranges.get('overlaps')
        and ranges.get('allCountsMatchRanges') is True
    )
    solution_missing = list(solutions.get('missingSolutionHeadingNumbers') or [])
    invalid_options = list(solutions.get('invalidOptionLabels') or [])
    solution_anchor_coverage = int(solutions.get('acceptedHeadingCount') or 0)

    return {
        'schemaVersion': 1,
        'contentFree': True,
        'providerRequestCount': manifest.get('providerRequestCount'),
        'pageCount': manifest.get('pageCount'),
        'declaredRanges': {
            'exact': declared_exact,
            'rangeCount': ranges.get('rangeCount'),
            'declaredQuestionCount': ranges.get('declaredQuestionCount'),
            'overallStart': ranges.get('overallStart'),
            'overallEnd': ranges.get('overallEnd'),
            'gaps': ranges.get('gaps'),
            'overlaps': ranges.get('overlaps'),
        },
        'questions': {
            'exact': question_exact,
            'anchorCount': len(question_numbers),
            'uniqueCount': len(unique_questions),
            'missing': question_missing,
            'duplicates': question_duplicates,
        },
        'solutions': {
            'rawCandidateCount': solutions.get('rawCandidateCount'),
            'acceptedHeadingCount': solution_anchor_coverage,
            'uniqueAcceptedQuestionCount': solutions.get('uniqueAcceptedQuestionCount'),
            'missingHeadings': solution_missing,
            'recoveredQuestionNumbers': solutions.get('recoveredQuestionNumbers'),
            'duplicateCandidateCount': solutions.get('duplicateCandidateCount'),
            'normalizedOptionLabelCount': solutions.get('normalizedOptionLabelCount'),
            'invalidOptionLabels': invalid_options,
        },
        'readyForRegionBoundaryBenchmark': bool(
            declared_exact and question_exact
        ),
        'solutionBoundaryGapsRemain': bool(solution_missing),
        'invalidSolutionAnswerLabelsRemain': bool(invalid_options),
    }


class Command(BaseCommand):
    help = (
        'Build a content-free structural contract report from a completed Mistral OCR '
        'diagnostic bundle. No provider request or production write is performed.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--bundle', required=True)
        parser.add_argument('--output', required=True)
        parser.add_argument('--expected-last-question', type=int, default=155)

    def handle(self, *args, **options):
        bundle = Path(options['bundle']).expanduser().resolve()
        if not bundle.is_file():
            raise CommandError('--bundle must point to an existing ZIP file.')
        root, manifest = _load_success_bundle(bundle)
        report = build_document_contract(
            root,
            manifest,
            expected_last_question=max(1, int(options['expected_last_question'])),
        )
        output = Path(options['output']).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        self.stdout.write(
            self.style.SUCCESS(
                'Mistral OCR document contract audit completed: '
                f"questionsExact={report['questions']['exact']}, "
                f"declaredRangesExact={report['declaredRanges']['exact']}, "
                f"solutionMissing={len(report['solutions']['missingHeadings'])}, "
                f"invalidSolutionOptions={len(report['solutions']['invalidOptionLabels'])}, "
                f'output={output}'
            )
        )
