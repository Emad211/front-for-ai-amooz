from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_mistral_layout_analysis import (
    analyze_ocr_document,
    associate_uncovered_graphics,
    detect_uncovered_graphics,
)


_REQUIRED_BUNDLE_FILES = frozenset({'manifest.json', 'response.raw.json'})


def _safe_members(archive: ZipFile) -> set[str]:
    names: set[str] = set()
    for info in archive.infolist():
        raw = info.filename.replace('\\', '/')
        path = Path(raw)
        if path.is_absolute() or '..' in path.parts:
            raise CommandError('Probe ZIP contains an unsafe path.')
        if not info.is_dir():
            names.add(raw)
    return names


def _json_member(archive: ZipFile, name: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(archive.read(name))
    except KeyError as exc:
        raise CommandError(f'Probe ZIP is missing {name}.') from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandError(f'Probe ZIP contains invalid JSON in {name}.') from exc
    if not isinstance(payload, Mapping):
        raise CommandError(f'{name} must contain one JSON object.')
    return payload


def analyze_bundle(bundle_path: Path) -> dict[str, Any]:
    try:
        archive = ZipFile(bundle_path)
    except (OSError, BadZipFile) as exc:
        raise CommandError('The supplied bundle is not a readable ZIP archive.') from exc
    with archive:
        names = _safe_members(archive)
        missing = sorted(_REQUIRED_BUNDLE_FILES - names)
        if missing:
            raise CommandError(
                f'Probe ZIP is missing required files: {", ".join(missing)}'
            )
        manifest = _json_member(archive, 'manifest.json')
        root = _json_member(archive, 'response.raw.json')
        selected = manifest.get('selectedOriginalPages')
        selected_pages = (
            [int(value) for value in selected]
            if isinstance(selected, list)
            else []
        )
        analysis = analyze_ocr_document(
            root,
            original_page_numbers=selected_pages,
        )
        raw_pages = {
            int(page.get('index')): page
            for page in (root.get('pages') or [])
            if isinstance(page, Mapping) and isinstance(page.get('index'), int)
        }
        with tempfile.TemporaryDirectory(
            prefix='exam-prep-mistral-analysis-'
        ) as temp_dir:
            temp = Path(temp_dir)
            uncovered_total = 0
            for page_analysis in analysis.get('pages') or []:
                provider_index = int(page_analysis.get('providerPageIndex') or 0)
                original_page = int(
                    page_analysis.get('originalPageNumber')
                    or provider_index + 1
                )
                image_name = f'page-{original_page:03d}.original.png'
                raw_page = raw_pages.get(provider_index)
                if raw_page is None or image_name not in names:
                    continue
                image_path = temp / image_name
                image_path.write_bytes(archive.read(image_name))
                candidates = detect_uncovered_graphics(
                    image_bytes=image_path.read_bytes(),
                    page=raw_page,
                )
                page_analysis['uncoveredGraphics'] = candidates
                associate_uncovered_graphics(page_analysis, candidates)
                uncovered_total += len(candidates)
        totals = dict(analysis.get('totals') or {})
        totals['uncoveredGraphicCandidates'] = uncovered_total
        totals['pagesWithIssues'] = sum(
            bool(page.get('issues'))
            for page in analysis.get('pages') or []
        )
        analysis['totals'] = totals
        analysis['sourceBundle'] = {
            'providerRequestCount': manifest.get('providerRequestCount'),
            'retryCount': manifest.get('retryCount'),
            'selectedOriginalPages': selected_pages,
            'resolvedModel': manifest.get('resolvedModel'),
        }
        return analysis


class Command(BaseCommand):
    help = (
        'Analyze a private Mistral OCR layout-probe ZIP locally. No provider '
        'request, database write, or production pipeline change is performed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--bundle',
            required=True,
            help='Path to the private probe ZIP.',
        )
        parser.add_argument(
            '--output',
            help='Optional JSON output path. Defaults to <bundle>.analysis.json.',
        )

    def handle(self, *args, **options):
        bundle = Path(options['bundle']).expanduser().resolve()
        if not bundle.is_file():
            raise CommandError('--bundle must point to an existing ZIP file.')
        output = (
            Path(options['output']).expanduser().resolve()
            if options.get('output')
            else bundle.with_suffix('.analysis.json')
        )
        analysis = analyze_bundle(bundle)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        totals = analysis.get('totals') or {}
        self.stdout.write(
            self.style.SUCCESS(
                'Mistral OCR local layout analysis completed: '
                f'pages={analysis.get("pageCount", 0)}, '
                f'rtlDouble={totals.get("rtlDoubleColumnPages", 0)}, '
                f'regions={totals.get("questionRegions", 0) + totals.get("solutionRegions", 0)}, '
                f'uncoveredGraphics={totals.get("uncoveredGraphicCandidates", 0)}, '
                f'output={output}'
            )
        )
