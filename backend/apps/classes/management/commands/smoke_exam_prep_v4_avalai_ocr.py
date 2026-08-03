from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_ENDPOINT,
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRConfigurationError,
    AvalAIOCRError,
    AvalAIOCRLimits,
    OCRHTTPResponse,
    OCRSmokeMode,
    aggregate_ocr_result,
    assert_aggregate_ocr_report,
    infer_media_type,
    run_ocr_bytes,
)


_SUPPORTED_MODES: tuple[OCRSmokeMode, ...] = (
    'markdown',
    'blocks',
    'document_annotation',
    'bbox_annotation',
)


def _fake_transport(*, fixture_id: str, mode: OCRSmokeMode):
    role = 'question' if fixture_id == 'question-page' else 'answer_solution'

    def transport(url, headers, payload, timeout):
        del url, headers, timeout
        markdown = (
            'سؤال ۱: مقدار $x^2$ را بررسی کنید.\n\n'
            '<table><tr><td>گزینه ۱</td><td>گزینه ۲</td></tr></table>'
            if role == 'question'
            else 'پاسخ ۱: گزینه ۲\n\nراه‌حل: $x=2$ و ادامهٔ استدلال.'
        )
        page: dict[str, Any] = {
            'index': 0,
            'markdown': markdown,
            'dimensions': {'dpi': 200, 'width': 1200, 'height': 1600},
            'images': [],
        }
        root: dict[str, Any] = {
            'pages': [page],
            'model': payload['model'],
            'object': 'ocr',
            'usage_info': {
                'pages_processed': 1,
                'doc_size_bytes': 1024,
            },
            'document_annotation': None,
        }
        if mode == 'blocks':
            page['confidence_scores'] = {
                'average_page_confidence_score': 0.97,
            }
            page['blocks'] = [
                {
                    'type': 'text',
                    'bbox': {'x': 10, 'y': 20, 'width': 500, 'height': 220},
                    'content': markdown,
                },
                {
                    'type': 'equation',
                    'bbox': {'x': 50, 'y': 260, 'width': 240, 'height': 100},
                    'content': '$x^2$',
                },
            ]
        elif mode == 'document_annotation':
            root['document_annotation'] = json.dumps(
                {
                    'document_role': role,
                    'rtl': True,
                    'has_formula': True,
                    'has_table': role == 'question',
                    'has_diagram': False,
                    'printed_numbers': ['1'],
                },
                ensure_ascii=False,
            )
        elif mode == 'bbox_annotation':
            page['images'] = [
                {
                    'bbox': {'x': 100, 'y': 300, 'width': 420, 'height': 260},
                    'image_annotation': json.dumps(
                        {
                            'image_type': 'diagram',
                            'contains_text': True,
                            'reading_order_relevant': True,
                        }
                    ),
                }
            ]
        body = json.dumps(root, ensure_ascii=False).encode('utf-8')
        return OCRHTTPResponse(
            status_code=200,
            headers={'x-request-id': f'fake-{fixture_id}-{mode}'},
            body=body,
        )

    return transport


def _parse_modes(raw: str) -> tuple[OCRSmokeMode, ...]:
    requested = tuple(
        value.strip()
        for value in str(raw or '').split(',')
        if value.strip()
    )
    if not requested:
        raise CommandError('At least one OCR smoke mode is required.')
    unknown = sorted(set(requested) - set(_SUPPORTED_MODES))
    if unknown:
        raise CommandError('Unsupported OCR smoke mode.')
    if len(requested) != len(set(requested)):
        raise CommandError('OCR smoke modes must be unique.')
    return requested  # type: ignore[return-value]


class Command(BaseCommand):
    help = (
        'Run an aggregate-only two-page AvalAI OCR feasibility smoke test. '
        'The command never prints OCR text, annotations, input paths, or bytes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--question-page', required=True)
        parser.add_argument('--answer-page', required=True)
        parser.add_argument('--report', required=True)
        parser.add_argument(
            '--mode',
            required=True,
            choices=['fake_provider', 'live_provider'],
        )
        parser.add_argument('--model', default=AVALAI_OCR_PINNED_MODEL)
        parser.add_argument(
            '--smoke-modes',
            default=','.join(_SUPPORTED_MODES),
            help='Comma-separated: markdown,blocks,document_annotation,bbox_annotation',
        )
        parser.add_argument('--max-requests', type=int)
        parser.add_argument('--allow-private-transmission', action='store_true')
        parser.add_argument('--max-input-bytes', type=int, default=12 * 1024 * 1024)
        parser.add_argument('--max-response-bytes', type=int, default=24 * 1024 * 1024)
        parser.add_argument('--timeout-seconds', type=float, default=180.0)

    @staticmethod
    def _read_input(path_value: str, limits: AvalAIOCRLimits) -> tuple[bytes, str]:
        path = Path(path_value).expanduser().resolve()
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise CommandError('A private OCR smoke input is unavailable.') from exc
        if size < 1 or size > limits.max_input_bytes:
            raise CommandError('A private OCR smoke input violates the byte limit.')
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise CommandError('A private OCR smoke input is unreadable.') from exc
        return data, infer_media_type(path.suffix)

    def handle(self, *args, **options):
        modes = _parse_modes(options['smoke_modes'])
        limits = AvalAIOCRLimits(
            max_input_bytes=options['max_input_bytes'],
            max_response_bytes=options['max_response_bytes'],
            timeout_seconds=options['timeout_seconds'],
        )
        try:
            limits.validate()
        except AvalAIOCRConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        model = str(options.get('model') or '').strip()
        if not model:
            raise CommandError('An explicit OCR model is required.')
        planned_requests = 2 * len(modes)
        live = options['mode'] == 'live_provider'
        max_requests = options.get('max_requests')
        if live:
            if not options.get('allow_private_transmission'):
                raise CommandError(
                    'Live OCR requires --allow-private-transmission.'
                )
            if not (os.getenv('AVALAI_API_KEY') or '').strip():
                raise CommandError('Live OCR requires AVALAI_API_KEY.')
            if isinstance(max_requests, bool) or not isinstance(max_requests, int):
                raise CommandError('Live OCR requires an explicit --max-requests.')
            if max_requests < planned_requests:
                raise CommandError(
                    'Live OCR max-requests is below the planned request count.'
                )
        elif max_requests is not None and max_requests < planned_requests:
            raise CommandError('Fake OCR max-requests is below the planned request count.')

        fixtures = (
            ('question-page', options['question_page']),
            ('answer-page', options['answer_page']),
        )
        prepared: list[tuple[str, bytes, str]] = []
        for fixture_id, path_value in fixtures:
            data, media_type = self._read_input(path_value, limits)
            prepared.append((fixture_id, data, media_type))

        results: list[dict[str, Any]] = []
        started = time.monotonic()
        request_count = 0
        for fixture_id, data, media_type in prepared:
            for smoke_mode in modes:
                request_count += 1
                if max_requests is not None and request_count > max_requests:
                    raise CommandError('OCR smoke request ceiling exhausted.')
                try:
                    result = run_ocr_bytes(
                        data=data,
                        media_type=media_type,
                        mode=smoke_mode,
                        model=model,
                        api_key=(os.getenv('AVALAI_API_KEY') if live else 'fake-key'),
                        limits=limits,
                        transport=(
                            None
                            if live
                            else _fake_transport(
                                fixture_id=fixture_id,
                                mode=smoke_mode,
                            )
                        ),
                    )
                    results.append(
                        {
                            'status': 'passed',
                            **aggregate_ocr_result(
                                fixture_id=fixture_id,
                                mode=smoke_mode,
                                input_bytes=len(data),
                                result=result,
                            ),
                        }
                    )
                except AvalAIOCRError as exc:
                    results.append(
                        {
                            'fixtureId': fixture_id,
                            'mode': smoke_mode,
                            'status': 'failed',
                            'errorCode': type(exc).__name__,
                        }
                    )

        all_passed = all(item['status'] == 'passed' for item in results)
        report: dict[str, Any] = {
            'schemaVersion': 1,
            'endpoint': AVALAI_OCR_ENDPOINT,
            'mode': options['mode'],
            'model': model,
            'fixtureCount': len(prepared),
            'smokeModes': list(modes),
            'plannedRequestCount': planned_requests,
            'executedRequestCount': request_count,
            'maxRequests': max_requests,
            'totalLatencyMs': round((time.monotonic() - started) * 1000, 2),
            'results': results,
            'totals': {
                'passed': sum(item['status'] == 'passed' for item in results),
                'failed': sum(item['status'] != 'passed' for item in results),
                'returnedPages': sum(
                    int(item.get('returnedPageCount') or 0) for item in results
                ),
                'blocks': sum(int(item.get('blockCount') or 0) for item in results),
                'bboxes': sum(int(item.get('bboxCount') or 0) for item in results),
                'rtlCharacters': sum(
                    int(item.get('rtlCharacterCount') or 0) for item in results
                ),
                'formulaSignals': sum(
                    int(item.get('formulaSignalCount') or 0) for item in results
                ),
                'tableSignals': sum(
                    int(item.get('tableSignalCount') or 0) for item in results
                ),
            },
            'acceptance': {
                'allRequestsPassed': all_passed,
                'requestCountExact': request_count == planned_requests,
                'privateTransmissionExplicit': (
                    bool(options.get('allow_private_transmission')) if live else True
                ),
                'requestCeilingRespected': (
                    max_requests is None or request_count <= max_requests
                ),
            },
        }
        report['acceptance']['passed'] = all(report['acceptance'].values())
        try:
            assert_aggregate_ocr_report(report)
        except AvalAIOCRError as exc:
            raise CommandError(str(exc)) from exc

        report_path = Path(options['report']).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding='utf-8',
        )
        self.stdout.write(
            f'Exam Prep V4 AvalAI OCR smoke completed; '
            f'requests={request_count}; passed={report["acceptance"]["passed"]}'
        )
        if not report['acceptance']['passed']:
            raise CommandError('AvalAI OCR smoke acceptance failed.')
