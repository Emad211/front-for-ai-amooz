from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
import pypdfium2 as pdfium
import requests

from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_ENDPOINT,
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRLimits,
    OCRHTTPResponse,
    build_ocr_payload,
    parse_ocr_response,
)


_DEFAULT_PAGES = (4, 10, 13, 17, 20, 31, 39, 40)
_VISUAL_BLOCK_TYPES = {
    'image',
    'figure',
    'illustration',
    'chart',
    'diagram',
    'table',
}


def _parse_pages(raw: str) -> tuple[int, ...]:
    values: list[int] = []
    for part in str(raw or '').split(','):
        token = part.strip()
        if not token:
            continue
        if '-' in token:
            left, right = token.split('-', 1)
            start, end = int(left), int(right)
            if end < start:
                raise CommandError('Page ranges must be ascending.')
            values.extend(range(start, end + 1))
        else:
            values.append(int(token))
    if not values:
        raise CommandError('At least one one-based PDF page is required.')
    if any(value < 1 for value in values):
        raise CommandError('PDF page numbers are one-based and must be positive.')
    if len(values) != len(set(values)):
        raise CommandError('PDF page numbers must be unique.')
    if len(values) > 8:
        raise CommandError('The diagnostic probe is intentionally capped at eight pages.')
    return tuple(values)


def _selected_pdf_bytes(path: Path, pages: tuple[int, ...]) -> tuple[bytes, int]:
    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # pragma: no cover - provider workstation specific
        raise CommandError('The supplied PDF cannot be opened.') from exc
    total = len(reader.pages)
    invalid = [page for page in pages if page > total]
    if invalid:
        raise CommandError(f'PDF has {total} pages; requested page is out of range.')
    writer = PdfWriter()
    for page_number in pages:
        writer.add_page(reader.pages[page_number - 1])
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue(), total


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bbox(record: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    nested = record.get('bbox')
    source = nested if isinstance(nested, Mapping) else record
    if all(key in source for key in ('x', 'y', 'width', 'height')):
        x = _number(source.get('x'))
        y = _number(source.get('y'))
        width = _number(source.get('width'))
        height = _number(source.get('height'))
        if None not in {x, y, width, height} and width > 0 and height > 0:
            return (x, y, x + width, y + height)
    for keys in (
        ('top_left_x', 'top_left_y', 'bottom_right_x', 'bottom_right_y'),
        ('x0', 'y0', 'x1', 'y1'),
    ):
        if all(key in source for key in keys):
            x0, y0, x1, y1 = (_number(source.get(key)) for key in keys)
            if None not in {x0, y0, x1, y1} and x1 > x0 and y1 > y0:
                return (x0, y0, x1, y1)
    return None


def _dimensions(raw_page: Mapping[str, Any]) -> tuple[float | None, float | None]:
    dimensions = raw_page.get('dimensions')
    if not isinstance(dimensions, Mapping):
        return None, None
    return _number(dimensions.get('width')), _number(dimensions.get('height'))


def _to_pixels(
    bbox: tuple[float, float, float, float],
    *,
    source_width: float | None,
    source_height: float | None,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int] | None:
    x0, y0, x1, y1 = bbox
    if x1 <= 1.0 and y1 <= 1.0:
        x0, x1 = x0 * image_width, x1 * image_width
        y0, y1 = y0 * image_height, y1 * image_height
    elif source_width and source_height:
        x0, x1 = x0 * image_width / source_width, x1 * image_width / source_width
        y0, y1 = y0 * image_height / source_height, y1 * image_height / source_height
    else:
        return None
    x0 = max(0, min(image_width - 1, round(x0)))
    y0 = max(0, min(image_height - 1, round(y0)))
    x1 = max(x0 + 1, min(image_width, round(x1)))
    y1 = max(y0 + 1, min(image_height, round(y1)))
    return x0, y0, x1, y1


def _render_pages(path: Path, pages: tuple[int, ...], dpi: int) -> dict[int, Image.Image]:
    try:
        document = pdfium.PdfDocument(str(path))
    except Exception as exc:  # pragma: no cover - workstation specific
        raise CommandError('The supplied PDF cannot be rendered.') from exc
    rendered: dict[int, Image.Image] = {}
    try:
        scale = dpi / 72.0
        for page_number in pages:
            page = document[page_number - 1]
            try:
                bitmap = page.render(scale=scale)
                try:
                    rendered[page_number] = bitmap.to_pil().convert('RGB')
                finally:
                    bitmap.close()
            finally:
                page.close()
    finally:
        document.close()
    return rendered


def _raw_page_records(root: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    pages = root.get('pages')
    if not isinstance(pages, list):
        raise CommandError('AvalAI OCR response does not contain a pages list.')
    return [page for page in pages if isinstance(page, Mapping)]


def _block_type(record: Mapping[str, Any]) -> str:
    return str(
        record.get('type')
        or record.get('block_type')
        or record.get('label')
        or 'unknown'
    ).strip().lower()


def _block_content(record: Mapping[str, Any]) -> str:
    return str(
        record.get('content')
        or record.get('text')
        or record.get('markdown')
        or ''
    )


def _write_page_bundle(
    *,
    output_dir: Path,
    original_page_number: int,
    raw_page: Mapping[str, Any],
    image: Image.Image,
) -> dict[str, Any]:
    prefix = f'page-{original_page_number:03d}'
    original_path = output_dir / f'{prefix}.original.png'
    overlay_path = output_dir / f'{prefix}.overlay.png'
    records_path = output_dir / f'{prefix}.records.json'
    markdown_path = output_dir / f'{prefix}.md'

    image.save(original_path, format='PNG', optimize=True)
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    source_width, source_height = _dimensions(raw_page)

    raw_blocks = raw_page.get('blocks')
    blocks = raw_blocks if isinstance(raw_blocks, list) else []
    raw_images = raw_page.get('images')
    images = raw_images if isinstance(raw_images, list) else []
    normalized_blocks: list[dict[str, Any]] = []
    normalized_images: list[dict[str, Any]] = []
    bbox_count = 0
    visual_block_count = 0

    for index, raw in enumerate(blocks):
        if not isinstance(raw, Mapping):
            continue
        kind = _block_type(raw)
        box = _bbox(raw)
        if box is not None:
            bbox_count += 1
            pixels = _to_pixels(
                box,
                source_width=source_width,
                source_height=source_height,
                image_width=image.width,
                image_height=image.height,
            )
            if pixels is not None:
                colour = '#e11d48' if kind in _VISUAL_BLOCK_TYPES else '#2563eb'
                draw.rectangle(pixels, outline=colour, width=3)
                draw.text((pixels[0] + 3, pixels[1] + 3), f'B{index}:{kind}', fill=colour)
        if kind in _VISUAL_BLOCK_TYPES:
            visual_block_count += 1
        normalized_blocks.append(
            {
                'index': index,
                'type': kind,
                'bbox': list(box) if box else None,
                'content': _block_content(raw),
                'raw': dict(raw),
            }
        )

    for index, raw in enumerate(images):
        if not isinstance(raw, Mapping):
            continue
        box = _bbox(raw)
        if box is not None:
            bbox_count += 1
            pixels = _to_pixels(
                box,
                source_width=source_width,
                source_height=source_height,
                image_width=image.width,
                image_height=image.height,
            )
            if pixels is not None:
                draw.rectangle(pixels, outline='#16a34a', width=5)
                draw.text((pixels[0] + 3, pixels[1] + 18), f'I{index}', fill='#16a34a')
        normalized_images.append(
            {
                'index': index,
                'bbox': list(box) if box else None,
                'id': raw.get('id') or raw.get('image_id'),
                'hasBase64': bool(raw.get('image_base64')),
                'annotation': raw.get('image_annotation'),
                'rawWithoutBase64': {
                    key: value
                    for key, value in raw.items()
                    if key != 'image_base64'
                },
            }
        )

    overlay.save(overlay_path, format='PNG', optimize=True)
    markdown = str(raw_page.get('markdown') or '')
    markdown_path.write_text(markdown, encoding='utf-8')
    records_path.write_text(
        json.dumps(
            {
                'originalPageNumber': original_page_number,
                'providerPageIndex': raw_page.get('index'),
                'dimensions': raw_page.get('dimensions'),
                'confidenceScores': raw_page.get('confidence_scores'),
                'blocks': normalized_blocks,
                'images': normalized_images,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    return {
        'originalPageNumber': original_page_number,
        'providerPageIndex': raw_page.get('index'),
        'markdownCharacters': len(markdown),
        'blockCount': len(normalized_blocks),
        'blockBBoxCount': sum(item['bbox'] is not None for item in normalized_blocks),
        'visualBlockCount': visual_block_count,
        'imageRecordCount': len(normalized_images),
        'imageBBoxCount': sum(item['bbox'] is not None for item in normalized_images),
        'totalBBoxCount': bbox_count,
        'pageConfidence': (
            raw_page.get('confidence_scores')
            if isinstance(raw_page.get('confidence_scores'), Mapping)
            else None
        ),
        'files': {
            'original': original_path.name,
            'overlay': overlay_path.name,
            'records': records_path.name,
            'markdown': markdown_path.name,
        },
    }


class Command(BaseCommand):
    help = (
        'Send one bounded selected-page PDF request to AvalAI Mistral OCR 4 and '
        'write a private raw/layout/overlay diagnostic bundle. This command is '
        'experimental and is not connected to the production Exam Prep pipeline.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--pdf', required=True, help='Local path to the private PDF.')
        parser.add_argument(
            '--pages',
            default=','.join(map(str, _DEFAULT_PAGES)),
            help='One-based pages, comma/range syntax; maximum eight pages.',
        )
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--model', default=AVALAI_OCR_PINNED_MODEL)
        parser.add_argument('--dpi', type=int, default=200)
        parser.add_argument('--timeout-seconds', type=float, default=300.0)
        parser.add_argument('--max-input-bytes', type=int, default=40 * 1024 * 1024)
        parser.add_argument('--max-response-bytes', type=int, default=80 * 1024 * 1024)
        parser.add_argument('--allow-private-transmission', action='store_true')
        parser.add_argument(
            '--include-image-base64',
            action='store_true',
            help='Diagnostic only; normally leave disabled to keep the response small.',
        )

    def handle(self, *args, **options):
        if not options.get('allow_private_transmission'):
            raise CommandError('Live OCR requires --allow-private-transmission.')
        api_key = (os.getenv('AVALAI_API_KEY') or '').strip()
        if not api_key:
            raise CommandError('AVALAI_API_KEY is required.')

        pdf_path = Path(options['pdf']).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != '.pdf':
            raise CommandError('The --pdf value must be an existing PDF file.')
        pages = _parse_pages(options['pages'])
        dpi = int(options['dpi'])
        if not 96 <= dpi <= 400:
            raise CommandError('--dpi must be between 96 and 400.')

        output_dir = Path(options['output_dir']).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError('Output directory must be absent or empty.')
        output_dir.mkdir(parents=True, exist_ok=True)

        selected_pdf, total_page_count = _selected_pdf_bytes(pdf_path, pages)
        if len(selected_pdf) > int(options['max_input_bytes']):
            raise CommandError('Selected-page PDF exceeds --max-input-bytes.')
        selected_sha = hashlib.sha256(selected_pdf).hexdigest()
        model = str(options['model'] or '').strip()
        limits = AvalAIOCRLimits(
            max_input_bytes=int(options['max_input_bytes']),
            max_response_bytes=int(options['max_response_bytes']),
            max_pages=len(pages),
            timeout_seconds=float(options['timeout_seconds']),
        )
        payload = build_ocr_payload(
            data=selected_pdf,
            media_type='application/pdf',
            model=model,
            mode='blocks',
            pages=None,
            limits=limits,
        )
        payload['include_image_base64'] = bool(options['include_image_base64'])
        payload['extract_header'] = True
        payload['extract_footer'] = True

        endpoint = (os.getenv('AVALAI_OCR_ENDPOINT') or AVALAI_OCR_ENDPOINT).strip()
        safe_request = {
            **payload,
            'document': {
                'type': 'document_url',
                'document_url': '<redacted selected-page PDF data URL>',
                'selectedPdfBytes': len(selected_pdf),
                'selectedPdfSha256': selected_sha,
            },
            'source': {
                'originalPdfPageCount': total_page_count,
                'selectedOriginalPages': list(pages),
                'oneBasedPageMapping': {
                    str(index): page_number
                    for index, page_number in enumerate(pages)
                },
            },
        }
        (output_dir / 'request.safe.json').write_text(
            json.dumps(safe_request, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

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
            raise CommandError('AvalAI OCR request failed; no retry was attempted.') from exc
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
            raise CommandError(
                f'AvalAI OCR returned HTTP {response.status_code}; raw body was saved.'
            )

        try:
            raw_root = response.json()
        except ValueError as exc:
            raise CommandError('AvalAI OCR returned non-JSON; raw body was saved.') from exc
        if not isinstance(raw_root, Mapping):
            raise CommandError('AvalAI OCR root response is not an object.')

        parsed = parse_ocr_response(
            response=OCRHTTPResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.content,
            ),
            expected_pages=tuple(range(len(pages))),
            limits=limits,
            latency_ms=latency_ms,
        )
        raw_pages = _raw_page_records(raw_root)
        raw_by_index = {
            page.get('index'): page
            for page in raw_pages
            if isinstance(page.get('index'), int)
        }
        rendered = _render_pages(pdf_path, pages, dpi)

        page_summaries: list[dict[str, Any]] = []
        for provider_index, original_page_number in enumerate(pages):
            raw_page = raw_by_index.get(provider_index)
            if raw_page is None:
                page_summaries.append(
                    {
                        'originalPageNumber': original_page_number,
                        'providerPageIndex': provider_index,
                        'missingProviderPage': True,
                    }
                )
                continue
            page_summaries.append(
                _write_page_bundle(
                    output_dir=output_dir,
                    original_page_number=original_page_number,
                    raw_page=raw_page,
                    image=rendered[original_page_number],
                )
            )

        total_blocks = sum(int(page.get('blockCount') or 0) for page in page_summaries)
        total_block_bboxes = sum(
            int(page.get('blockBBoxCount') or 0) for page in page_summaries
        )
        total_visual_candidates = sum(
            int(page.get('visualBlockCount') or 0)
            + int(page.get('imageRecordCount') or 0)
            for page in page_summaries
        )
        manifest = {
            'schemaVersion': 1,
            'privateDiagnosticBundle': True,
            'productionPipelineChanged': False,
            'providerRequestCount': 1,
            'retryCount': 0,
            'endpoint': endpoint,
            'requestedModel': model,
            'resolvedModel': parsed.model,
            'requestId': parsed.request_id,
            'latencyMs': latency_ms,
            'selectedOriginalPages': list(pages),
            'selectedPdfBytes': len(selected_pdf),
            'selectedPdfSha256': selected_sha,
            'providerReturnedPageCount': len(parsed.pages),
            'usagePagesProcessed': parsed.usage_pages_processed,
            'usageDocumentBytes': parsed.usage_document_bytes,
            'issues': [
                {'code': issue.code, 'pageIndex': issue.page_index}
                for issue in parsed.issues
            ],
            'pages': page_summaries,
            'totals': {
                'blocks': total_blocks,
                'blockBBoxes': total_block_bboxes,
                'bboxCoverage': (
                    round(total_block_bboxes / total_blocks, 4)
                    if total_blocks
                    else 0.0
                ),
                'visualCandidates': total_visual_candidates,
            },
            'acceptance': {
                'oneRequestOnly': True,
                'allSelectedPagesReturned': len(parsed.pages) == len(pages),
                'includeBlocksReturned': total_blocks > 0,
                'atLeastOneBlockBBoxReturned': total_block_bboxes > 0,
            },
        }
        manifest['acceptance']['passed'] = all(manifest['acceptance'].values())
        (output_dir / 'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        (output_dir / 'README.txt').write_text(
            'PRIVATE OCR DIAGNOSTIC BUNDLE\n'
            'Send the generated ZIP back for architecture analysis.\n'
            'Do not commit this directory or its ZIP to Git.\n'
            'Important files: manifest.json, response.raw.json, page-*.records.json, '
            'page-*.overlay.png, page-*.original.png, page-*.md.\n',
            encoding='utf-8',
        )
        archive = shutil.make_archive(str(output_dir), 'zip', root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                f'Mistral OCR layout probe completed: request=1, '
                f'pages={len(pages)}, blocks={total_blocks}, bundle={archive}'
            )
        )
        if not manifest['acceptance']['passed']:
            raise CommandError(
                'Probe bundle was written, but include_blocks/bbox acceptance failed.'
            )
