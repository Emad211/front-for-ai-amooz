import io
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_ENDPOINT,
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRConfigurationError,
    AvalAIOCRLimits,
    AvalAIOCRPrivacyError,
    AvalAIOCRResponseError,
    OCRHTTPResponse,
    aggregate_ocr_result,
    assert_aggregate_ocr_report,
    build_ocr_payload,
    parse_ocr_response,
    run_ocr_bytes,
)


def _response(payload, *, request_id='req-1', status=200):
    return OCRHTTPResponse(
        status_code=status,
        headers={'x-request-id': request_id},
        body=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
    )


def _page_payload(*, index=0):
    return {
        'index': index,
        'markdown': 'سؤال ۱ با فرمول $x^2$\n<table><tr><td>گزینه</td></tr></table>',
        'dimensions': {'dpi': 200, 'width': 1000, 'height': 1400},
        'confidence_scores': {'average_page_confidence_score': 0.95},
        'blocks': [
            {
                'type': 'text',
                'bbox': {'x': 10, 'y': 20, 'width': 400, 'height': 200},
                'content': 'متن خصوصی سؤال',
            },
            {
                'type': 'equation',
                'bbox': {'x0': 50, 'y0': 240, 'x1': 300, 'y1': 360},
                'content': '$x^2$',
            },
        ],
        'images': [
            {
                'bbox': {'x': 100, 'y': 400, 'width': 300, 'height': 220},
                'image_annotation': json.dumps(
                    {
                        'image_type': 'diagram',
                        'contains_text': True,
                        'reading_order_relevant': True,
                    }
                ),
            }
        ],
    }


def test_payload_pins_endpoint_uses_private_data_url_and_mode_contracts():
    limits = AvalAIOCRLimits(max_input_bytes=100)
    data = b'PRIVATE-PNG-BYTES'

    markdown = build_ocr_payload(
        data=data,
        media_type='image/png',
        model=AVALAI_OCR_PINNED_MODEL,
        mode='markdown',
        pages=None,
        limits=limits,
    )
    blocks = build_ocr_payload(
        data=data,
        media_type='image/png',
        model=AVALAI_OCR_PINNED_MODEL,
        mode='blocks',
        pages=None,
        limits=limits,
    )
    document = build_ocr_payload(
        data=data,
        media_type='image/png',
        model=AVALAI_OCR_PINNED_MODEL,
        mode='document_annotation',
        pages=None,
        limits=limits,
    )
    bbox = build_ocr_payload(
        data=data,
        media_type='image/png',
        model=AVALAI_OCR_PINNED_MODEL,
        mode='bbox_annotation',
        pages=None,
        limits=limits,
    )

    assert AVALAI_OCR_ENDPOINT == 'https://api.avalai.ir/v1/ocr'
    assert markdown['model'] == 'mistral-ocr-4-0'
    assert markdown['document']['type'] == 'image_url'
    assert markdown['document']['image_url'].startswith('data:image/png;base64,')
    assert 'PRIVATE-PNG-BYTES' not in json.dumps(markdown)
    assert markdown['include_image_base64'] is False
    assert markdown['table_format'] == 'html'
    assert blocks['include_blocks'] is True
    assert blocks['confidence_scores_granularity'] == 'page'
    assert document['document_annotation_format']['type'] == 'json_schema'
    assert bbox['bbox_annotation_format']['type'] == 'json_schema'


def test_pdf_page_selection_is_zero_based_unique_and_bounded():
    limits = AvalAIOCRLimits(max_pages=2)
    payload = build_ocr_payload(
        data=b'%PDF-1.7',
        media_type='application/pdf',
        model=AVALAI_OCR_PINNED_MODEL,
        mode='markdown',
        pages=[0, 2],
        limits=limits,
    )
    assert payload['document']['type'] == 'document_url'
    assert payload['pages'] == [0, 2]

    with pytest.raises(AvalAIOCRConfigurationError, match='unique'):
        build_ocr_payload(
            data=b'%PDF-1.7',
            media_type='application/pdf',
            model=AVALAI_OCR_PINNED_MODEL,
            mode='markdown',
            pages=[0, 0],
            limits=limits,
        )
    with pytest.raises(AvalAIOCRConfigurationError, match='bounded'):
        build_ocr_payload(
            data=b'%PDF-1.7',
            media_type='application/pdf',
            model=AVALAI_OCR_PINNED_MODEL,
            mode='markdown',
            pages=[0, 1, 2],
            limits=limits,
        )


def test_parser_keeps_private_content_in_memory_but_aggregate_is_content_free():
    root = {
        'pages': [_page_payload()],
        'model': AVALAI_OCR_PINNED_MODEL,
        'usage_info': {'pages_processed': 1, 'doc_size_bytes': 1234},
        'document_annotation': json.dumps(
            {
                'document_role': 'question',
                'rtl': True,
                'has_formula': True,
                'has_table': True,
                'has_diagram': True,
                'printed_numbers': ['1'],
            },
            ensure_ascii=False,
        ),
    }
    result = parse_ocr_response(
        response=_response(root),
        expected_pages=[0],
        limits=AvalAIOCRLimits(),
        latency_ms=12.5,
    )
    aggregate = aggregate_ocr_result(
        fixture_id='question-page',
        mode='blocks',
        input_bytes=100,
        result=result,
    )
    rendered = json.dumps(aggregate, ensure_ascii=False)

    assert result.pages[0].markdown.startswith('سؤال')
    assert result.pages[0].blocks[0].content == 'متن خصوصی سؤال'
    assert aggregate['returnedPageIndexes'] == [0]
    assert aggregate['rtlCharacterCount'] > 0
    assert aggregate['formulaSignalCount'] > 0
    assert aggregate['tableSignalCount'] > 0
    assert aggregate['blockCount'] == 2
    assert aggregate['blockTypeCounts'] == {'equation': 1, 'text': 1}
    assert aggregate['bboxCount'] == 3
    assert aggregate['bboxAnnotationCount'] == 1
    assert aggregate['documentAnnotationPresent'] is True
    assert aggregate['usagePagesProcessed'] == 1
    assert 'متن خصوصی سؤال' not in rendered
    assert 'سؤال ۱' not in rendered
    assert 'printed_numbers' not in rendered
    assert_aggregate_ocr_report(aggregate)


def test_malformed_annotations_are_content_free_issues_not_sibling_loss():
    page = _page_payload()
    page['images'].append(
        {
            'bbox': {'x': 1, 'y': 1, 'width': 2, 'height': 2},
            'image_annotation': '{broken-json',
        }
    )
    root = {
        'pages': [page],
        'model': AVALAI_OCR_PINNED_MODEL,
        'document_annotation': '{broken-json',
    }

    result = parse_ocr_response(
        response=_response(root),
        expected_pages=[0],
        limits=AvalAIOCRLimits(),
        latency_ms=1,
    )

    assert len(result.pages) == 1
    assert len(result.pages[0].images) == 2
    assert result.document_annotation is None
    assert sorted(issue.code for issue in result.issues) == [
        'invalid_bbox_annotation',
        'invalid_document_annotation',
    ]


def test_duplicate_or_missing_page_coverage_fails_closed():
    duplicate = {
        'pages': [_page_payload(index=0), _page_payload(index=0)],
        'model': AVALAI_OCR_PINNED_MODEL,
    }
    with pytest.raises(AvalAIOCRResponseError, match='duplicate'):
        parse_ocr_response(
            response=_response(duplicate),
            expected_pages=[0],
            limits=AvalAIOCRLimits(),
            latency_ms=1,
        )

    missing = {
        'pages': [_page_payload(index=1)],
        'model': AVALAI_OCR_PINNED_MODEL,
    }
    with pytest.raises(AvalAIOCRResponseError, match='coverage'):
        parse_ocr_response(
            response=_response(missing),
            expected_pages=[0, 1],
            limits=AvalAIOCRLimits(),
            latency_ms=1,
        )


def test_input_response_markdown_and_unexpected_image_bytes_are_bounded():
    with pytest.raises(AvalAIOCRConfigurationError, match='input exceeds'):
        build_ocr_payload(
            data=b'x' * 11,
            media_type='image/png',
            model=AVALAI_OCR_PINNED_MODEL,
            mode='markdown',
            pages=None,
            limits=AvalAIOCRLimits(max_input_bytes=10),
        )

    with pytest.raises(AvalAIOCRResponseError, match='response exceeds'):
        parse_ocr_response(
            response=OCRHTTPResponse(200, {}, b'x' * 11),
            expected_pages=[0],
            limits=AvalAIOCRLimits(max_response_bytes=10),
            latency_ms=1,
        )

    oversized_markdown = {
        'pages': [{'index': 0, 'markdown': 'x' * 11, 'images': []}],
        'model': AVALAI_OCR_PINNED_MODEL,
    }
    with pytest.raises(AvalAIOCRResponseError, match='markdown exceeds'):
        parse_ocr_response(
            response=_response(oversized_markdown),
            expected_pages=[0],
            limits=AvalAIOCRLimits(max_markdown_chars_per_page=10),
            latency_ms=1,
        )

    private_image = _page_payload()
    private_image['images'][0]['image_base64'] = 'SECRET-BASE64'
    with pytest.raises(AvalAIOCRPrivacyError, match='image base64'):
        parse_ocr_response(
            response=_response(
                {'pages': [private_image], 'model': AVALAI_OCR_PINNED_MODEL}
            ),
            expected_pages=[0],
            limits=AvalAIOCRLimits(),
            latency_ms=1,
        )


def test_run_ocr_bytes_uses_injected_transport_without_live_key():
    captured = {}

    def transport(url, headers, payload, timeout):
        captured.update(
            {'url': url, 'headers': headers, 'payload': payload, 'timeout': timeout}
        )
        return _response(
            {'pages': [_page_payload()], 'model': AVALAI_OCR_PINNED_MODEL}
        )

    result = run_ocr_bytes(
        data=b'private-image',
        media_type='image/png',
        mode='markdown',
        transport=transport,
    )

    assert result.pages[0].index == 0
    assert captured['url'] == AVALAI_OCR_ENDPOINT
    assert captured['headers']['Authorization'] == 'Bearer '
    assert captured['payload']['document']['image_url'].startswith(
        'data:image/png;base64,'
    )


def _private_inputs(tmp_path: Path):
    question = tmp_path / 'SECRET_QUESTION_PAGE.png'
    answer = tmp_path / 'SECRET_ANSWER_PAGE.png'
    question.write_bytes(b'private-question-image')
    answer.write_bytes(b'private-answer-image')
    return question, answer


def test_fake_command_runs_eight_requests_and_writes_aggregate_only_report(tmp_path):
    question, answer = _private_inputs(tmp_path)
    report_path = tmp_path / 'ocr-smoke-report.json'
    stdout = io.StringIO()

    call_command(
        'smoke_exam_prep_v4_avalai_ocr',
        question_page=str(question),
        answer_page=str(answer),
        report=str(report_path),
        mode='fake_provider',
        stdout=stdout,
    )

    report = json.loads(report_path.read_text(encoding='utf-8'))
    rendered = json.dumps(report, ensure_ascii=False)
    terminal = stdout.getvalue()
    assert report['model'] == 'mistral-ocr-4-0'
    assert report['plannedRequestCount'] == 8
    assert report['executedRequestCount'] == 8
    assert report['totals']['passed'] == 8
    assert report['totals']['failed'] == 0
    assert report['acceptance']['passed'] is True
    assert report['totals']['rtlCharacters'] > 0
    assert report['totals']['formulaSignals'] > 0
    assert report['totals']['blocks'] > 0
    assert 'requests=8; passed=True' in terminal
    for private_path in (question, answer):
        assert str(private_path) not in rendered
        assert private_path.name not in rendered
        assert str(private_path) not in terminal
        assert private_path.name not in terminal
    assert 'سؤال ۱' not in rendered
    assert 'راه‌حل' not in rendered
    assert 'private-question-image' not in rendered
    assert_aggregate_ocr_report(report)


def test_live_command_fails_before_read_or_network_without_explicit_approvals(
    tmp_path,
    monkeypatch,
):
    question, answer = _private_inputs(tmp_path)
    report_path = tmp_path / 'report.json'
    monkeypatch.delenv('AVALAI_API_KEY', raising=False)

    with pytest.raises(CommandError, match='allow-private-transmission'):
        call_command(
            'smoke_exam_prep_v4_avalai_ocr',
            question_page=str(question),
            answer_page=str(answer),
            report=str(report_path),
            mode='live_provider',
            max_requests=8,
        )
    assert not report_path.exists()

    with pytest.raises(CommandError, match='AVALAI_API_KEY'):
        call_command(
            'smoke_exam_prep_v4_avalai_ocr',
            question_page=str(question),
            answer_page=str(answer),
            report=str(report_path),
            mode='live_provider',
            max_requests=8,
            allow_private_transmission=True,
        )
    assert not report_path.exists()

    monkeypatch.setenv('AVALAI_API_KEY', 'secret-key')
    with pytest.raises(CommandError, match='below the planned'):
        call_command(
            'smoke_exam_prep_v4_avalai_ocr',
            question_page=str(question),
            answer_page=str(answer),
            report=str(report_path),
            mode='live_provider',
            max_requests=7,
            allow_private_transmission=True,
        )
    assert not report_path.exists()
