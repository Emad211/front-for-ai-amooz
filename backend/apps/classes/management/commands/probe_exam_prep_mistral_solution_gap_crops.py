from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
from PIL import Image
import pypdfium2 as pdfium
import requests

from apps.classes.services.exam_prep_mistral_solution_headings import (
    normalize_solution_option_label,
    parse_solution_heading,
)
from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_ENDPOINT,
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRLimits,
    OCRHTTPResponse,
    build_ocr_payload,
    parse_ocr_response,
)

_DEFAULT_SPECS = (
    (33, 'left'),
    (34, 'left'),
    (35, 'right'),
    (36, 'left'),
    (37, 'right'),
    (40, 'left'),
    (43, 'left'),
)


def _parse_specs(raw: str) -> tuple[tuple[int, str], ...]:
    specs: list[tuple[int, str]] = []
    for part in str(raw or '').split(','):
        token = part.strip()
        if not token:
            continue
        if ':' not in token:
            raise CommandError('Each crop spec must be PAGE:left or PAGE:right.')
        page_text, side = token.split(':', 1)
        try:
            page = int(page_text.strip())
        except ValueError as exc:
            raise CommandError('Crop page numbers must be integers.') from exc
        side = side.strip().lower()
        if page < 1 or side not in {'left', 'right'}:
            raise CommandError('Each crop spec must be a positive PAGE:left/right value.')
        item = (page, side)
        if item not in specs:
            specs.append(item)
    if not specs:
        raise CommandError('At least one crop spec is required.')
    if len(specs) > 12:
        raise CommandError('Targeted gap probe is capped at 12 column crops.')
    return tuple(specs)


def _render_column_crops(
    pdf_path: Path,
    specs: tuple[tuple[int, str], ...],
    *,
    dpi: int,
) -> list[Image.Image]:
    try:
        document = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:
        raise CommandError('The supplied PDF cannot be rendered.') from exc
    output: list[Image.Image] = []
    try:
        page_count = len(document)
        scale = dpi / 72.0
        for page_number, side in specs:
            if page_number > page_count:
                raise CommandError(
                    f'PDF has {page_count} pages; requested page {page_number} is out of range.'
                )
            page = document[page_number - 1]
            try:
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil().convert('RGB')
                finally:
                    bitmap.close()
            finally:
                page.close()
            width, height = image.size
            # Keep a small overlap around the center rule and strip the repeated
            # outer header/footer. This enlarges the worked-solution text while
            # preserving every separator and heading in the selected column.
            x0 = int(width * (0.02 if side == 'left' else 0.49))
            x1 = int(width * (0.51 if side == 'left' else 0.98))
            y0 = int(height * 0.075)
            y1 = int(height * 0.965)
            crop = image.crop((x0, y0, x1, y1))
            image.close()
            output.append(crop)
    finally:
        document.close()
    return output


def _multi_page_pdf(images: list[Image.Image], *, dpi: int) -> bytes:
    if not images:
        raise CommandError('No crop images were rendered.')
    buffer = io.BytesIO()
    first, *rest = images
    first.save(
        buffer,
        format='PDF',
        save_all=True,
        append_images=rest,
        resolution=float(dpi),
    )
    return buffer.getvalue()


def _detected_headings(root: Mapping[str, Any], specs: tuple[tuple[int, str], ...]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    pages = [page for page in (root.get('pages') or []) if isinstance(page, Mapping)]
    pages.sort(key=lambda page: int(page.get('index') or 0))
    for page in pages:
        index = int(page.get('index') or 0)
        if not 0 <= index < len(specs):
            continue
        physical_page, side = specs[index]
        for block_index, block in enumerate(page.get('blocks') or []):
            if not isinstance(block, Mapping):
                continue
            parsed = parse_solution_heading(str(block.get('content') or ''))
            if not parsed:
                continue
            raw_option = int(parsed['rawOptionLabel'])
            option, normalized, valid = normalize_solution_option_label(raw_option)
            output.append(
                {
                    'providerCropIndex': index,
                    'physicalPageNumber': physical_page,
                    'column': side,
                    'providerBlockIndex': block_index,
                    'rawQuestionNumber': int(parsed['rawQuestionNumber']),
                    'rawOptionLabel': raw_option,
                    'optionLabel': option,
                    'optionLabelNormalized': normalized,
                    'optionLabelValid': valid,
                    'headingFormat': parsed['format'],
                }
            )
    return output


class Command(BaseCommand):
    help = (
        'Re-OCR only selected worked-solution columns in one bounded OCR4 request. '
        'Used to test whether local column crops recover headings missed by full-page OCR.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--pdf', required=True)
        parser.add_argument(
            '--specs',
            default=','.join(f'{page}:{side}' for page, side in _DEFAULT_SPECS),
        )
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--model', default=AVALAI_OCR_PINNED_MODEL)
        parser.add_argument('--dpi', type=int, default=250)
        parser.add_argument('--timeout-seconds', type=float, default=300.0)
        parser.add_argument('--max-input-bytes', type=int, default=30 * 1024 * 1024)
        parser.add_argument('--max-response-bytes', type=int, default=80 * 1024 * 1024)
        parser.add_argument('--allow-private-transmission', action='store_true')

    def handle(self, *args, **options):
        if not options.get('allow_private_transmission'):
            raise CommandError('Live OCR requires --allow-private-transmission.')
        api_key = (os.getenv('AVALAI_API_KEY') or '').strip()
        if not api_key:
            raise CommandError('AVALAI_API_KEY is required.')
        pdf_path = Path(options['pdf']).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != '.pdf':
            raise CommandError('--pdf must point to an existing PDF file.')
        specs = _parse_specs(options['specs'])
        dpi = int(options['dpi'])
        if not 150 <= dpi <= 350:
            raise CommandError('--dpi must be between 150 and 350.')
        output_dir = Path(options['output_dir']).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError('Output directory must be absent or empty.')
        output_dir.mkdir(parents=True, exist_ok=True)

        images = _render_column_crops(pdf_path, specs, dpi=dpi)
        try:
            for index, image in enumerate(images):
                image.save(output_dir / f'crop-{index + 1:02d}.png', format='PNG', optimize=True)
            crop_pdf = _multi_page_pdf(images, dpi=dpi)
        finally:
            for image in images:
                image.close()
        if len(crop_pdf) > int(options['max_input_bytes']):
            raise CommandError('Targeted crop PDF exceeds --max-input-bytes.')

        limits = AvalAIOCRLimits(
            max_input_bytes=int(options['max_input_bytes']),
            max_response_bytes=int(options['max_response_bytes']),
            max_pages=len(specs),
            timeout_seconds=float(options['timeout_seconds']),
        )
        model = str(options['model'] or '').strip()
        payload = build_ocr_payload(
            data=crop_pdf,
            media_type='application/pdf',
            model=model,
            mode='blocks',
            pages=None,
            limits=limits,
        )
        payload.update(
            {
                'include_image_base64': False,
                'extract_header': False,
                'extract_footer': False,
                'table_format': 'html',
                'confidence_scores_granularity': 'word',
            }
        )
        crop_sha = hashlib.sha256(crop_pdf).hexdigest()
        (output_dir / 'request.safe.json').write_text(
            json.dumps(
                {
                    **payload,
                    'document': {
                        'type': 'document_url',
                        'document_url': '<redacted targeted crop PDF data URL>',
                        'selectedPdfBytes': len(crop_pdf),
                        'selectedPdfSha256': crop_sha,
                    },
                    'source': {
                        'cropSpecs': [
                            {'physicalPageNumber': page, 'column': side}
                            for page, side in specs
                        ]
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )

        endpoint = (os.getenv('AVALAI_OCR_ENDPOINT') or AVALAI_OCR_ENDPOINT).strip()
        started = time.monotonic()
        try:
            response = requests.post(
                endpoint,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=limits.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise CommandError('Targeted solution-gap OCR transport failed; no retry was attempted.') from exc
        latency_ms = round((time.monotonic() - started) * 1000, 2)
        (output_dir / 'response.raw.json').write_bytes(response.content)
        (output_dir / 'response.headers.safe.json').write_text(
            json.dumps(
                {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in {'set-cookie', 'authorization'}
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
        if not response.ok:
            archive = shutil.make_archive(str(output_dir), 'zip', root_dir=output_dir)
            raise CommandError(
                f'Targeted solution-gap OCR returned HTTP {response.status_code}; '
                f'bundle={archive}'
            )
        try:
            root = response.json()
        except ValueError as exc:
            raise CommandError('Targeted solution-gap OCR returned non-JSON.') from exc
        if not isinstance(root, Mapping):
            raise CommandError('Targeted solution-gap OCR root is not an object.')
        parsed = parse_ocr_response(
            response=OCRHTTPResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.content,
            ),
            expected_pages=tuple(range(len(specs))),
            limits=limits,
            latency_ms=latency_ms,
        )
        headings = _detected_headings(root, specs)
        report = {
            'schemaVersion': 1,
            'privateDiagnosticBundle': True,
            'productionPipelineChanged': False,
            'providerRequestCount': 1,
            'retryCount': 0,
            'cropCount': len(specs),
            'cropSpecs': [
                {'physicalPageNumber': page, 'column': side}
                for page, side in specs
            ],
            'requestedModel': model,
            'resolvedModel': parsed.model,
            'requestId': parsed.request_id,
            'latencyMs': latency_ms,
            'cropPdfBytes': len(crop_pdf),
            'cropPdfSha256': crop_sha,
            'usagePagesProcessed': parsed.usage_pages_processed,
            'estimatedCost': root.get('estimated_cost'),
            'detectedHeadings': headings,
            'invalidDetectedOptions': [
                item for item in headings if not item['optionLabelValid']
            ],
        }
        (output_dir / 'manifest.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        archive = shutil.make_archive(str(output_dir), 'zip', root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                'Mistral OCR solution-gap crop probe completed: '
                f'request=1, crops={len(specs)}, headings={len(headings)}, '
                f'bundle={archive}'
            )
        )
