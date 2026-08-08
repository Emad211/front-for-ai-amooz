from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
import requests

from apps.classes.management.commands.probe_exam_prep_mistral_layout import (
    _parse_pages,
    _selected_pdf_bytes,
)
from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_ENDPOINT,
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRLimits,
    OCRHTTPResponse,
    build_ocr_payload,
    parse_ocr_response,
)

_DEFAULT_PAGES = (20, 39, 40)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _confidence_aggregate(root: Mapping[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for page in root.get('pages') or []:
        if not isinstance(page, Mapping):
            continue
        confidence = page.get('confidence_scores')
        confidence = confidence if isinstance(confidence, Mapping) else {}
        words = confidence.get('word_confidence_scores')
        words = words if isinstance(words, list) else []
        scores: list[float] = []
        for item in words:
            if not isinstance(item, Mapping):
                continue
            score = _number(
                item.get('confidence')
                or item.get('score')
                or item.get('confidence_score')
            )
            if score is not None and 0 <= score <= 1:
                scores.append(score)
        output.append(
            {
                'providerPageIndex': page.get('index'),
                'averagePageConfidence': _number(
                    confidence.get('average_page_confidence_score')
                ),
                'minimumPageConfidence': _number(
                    confidence.get('minimum_page_confidence_score')
                ),
                'wordScoreCount': len(scores),
                'below60': sum(score < 0.60 for score in scores),
                'below80': sum(score < 0.80 for score in scores),
                'below95': sum(score < 0.95 for score in scores),
            }
        )
    return output


class Command(BaseCommand):
    help = (
        'Send one selected-page Mistral OCR 4 request with word confidence enabled. '
        'This is a private diagnostic only; it does not touch production data.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--pdf', required=True)
        parser.add_argument(
            '--pages',
            default=','.join(map(str, _DEFAULT_PAGES)),
            help='One-based pages; maximum eight pages for this diagnostic.',
        )
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--model', default=AVALAI_OCR_PINNED_MODEL)
        parser.add_argument('--timeout-seconds', type=float, default=300.0)
        parser.add_argument('--max-input-bytes', type=int, default=40 * 1024 * 1024)
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
        pages = _parse_pages(options['pages'])
        output_dir = Path(options['output_dir']).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError('Output directory must be absent or empty.')
        output_dir.mkdir(parents=True, exist_ok=True)

        selected_pdf, total_page_count = _selected_pdf_bytes(pdf_path, pages)
        limits = AvalAIOCRLimits(
            max_input_bytes=int(options['max_input_bytes']),
            max_response_bytes=int(options['max_response_bytes']),
            max_pages=len(pages),
            timeout_seconds=float(options['timeout_seconds']),
        )
        model = str(options['model'] or '').strip()
        payload = build_ocr_payload(
            data=selected_pdf,
            media_type='application/pdf',
            model=model,
            mode='blocks',
            pages=None,
            limits=limits,
        )
        payload.update(
            {
                'include_image_base64': False,
                'extract_header': True,
                'extract_footer': True,
                'table_format': 'html',
                'confidence_scores_granularity': 'word',
            }
        )
        selected_sha = hashlib.sha256(selected_pdf).hexdigest()
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
            },
        }
        (output_dir / 'request.safe.json').write_text(
            json.dumps(safe_request, ensure_ascii=False, indent=2),
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
            raise CommandError('AvalAI OCR request failed; no retry was attempted.') from exc
        latency_ms = round((time.monotonic() - started) * 1000, 2)
        (output_dir / 'response.raw.json').write_bytes(response.content)
        if not response.ok:
            raise CommandError(
                f'AvalAI OCR returned HTTP {response.status_code}; raw body was saved.'
            )
        try:
            root = response.json()
        except ValueError as exc:
            raise CommandError('AvalAI OCR returned non-JSON; raw body was saved.') from exc
        if not isinstance(root, Mapping):
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
        summary = {
            'privateDiagnosticBundle': True,
            'providerRequestCount': 1,
            'retryCount': 0,
            'confidenceGranularity': 'word',
            'requestedModel': model,
            'resolvedModel': parsed.model,
            'latencyMs': latency_ms,
            'selectedOriginalPages': list(pages),
            'usagePagesProcessed': parsed.usage_pages_processed,
            'pages': _confidence_aggregate(root),
        }
        (output_dir / 'summary.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        archive = shutil.make_archive(str(output_dir), 'zip', root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                f'Mistral OCR word-confidence probe completed: request=1, '
                f'pages={len(pages)}, bundle={archive}'
            )
        )
