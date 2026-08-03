from __future__ import annotations

import json

import pytest

from apps.classes.models_v4 import ExamSourceRole
from apps.classes.models_v4_blocks import ExamSourceBlockKind
from apps.classes.services.exam_prep_v4_avalai_ocr import OCRHTTPResponse
from apps.classes.services.exam_prep_v4_live_pipeline import (
    PreparedVisionImage,
    run_document_extraction_pipeline,
)
from apps.classes.services.exam_prep_v4_ocr_evidence import (
    AvalAIOCREvidenceAdapter,
    OCREvidenceAdapterConfig,
)
from apps.classes.test_exam_prep_v4_full_pipeline import (
    FakeFullPipelineProvider,
    _confirmed_document,
)


pytestmark = pytest.mark.django_db


def _annotation(*, role: str, has_diagram: bool = False) -> str:
    return json.dumps(
        {
            'document_role': role,
            'rtl': True,
            'has_formula': False,
            'has_table': False,
            'has_diagram': has_diagram,
            'printed_numbers': ['1'],
        },
        ensure_ascii=False,
    )


def _ocr_response(
    *,
    blocks,
    role='question',
    confidence=0.95,
    has_diagram=False,
    status=200,
    model='mistral-ocr-4-0',
):
    if status != 200:
        return OCRHTTPResponse(
            status_code=status,
            headers={'x-request-id': 'failed-request'},
            body=b'{}',
        )
    body = {
        'pages': [
            {
                'index': 0,
                'markdown': 'متن خصوصی صفحه',
                'dimensions': {'dpi': 200, 'width': 1000, 'height': 1400},
                'confidence_scores': {
                    'average_page_confidence_score': confidence,
                },
                'blocks': blocks,
                'images': [],
            }
        ],
        'model': model,
        'usage_info': {'pages_processed': 1, 'doc_size_bytes': 1024},
        'document_annotation': _annotation(
            role=role,
            has_diagram=has_diagram,
        ),
    }
    return OCRHTTPResponse(
        status_code=200,
        headers={'x-request-id': 'request-id'},
        body=json.dumps(body, ensure_ascii=False).encode('utf-8'),
    )


def _question_blocks():
    return [
        {
            'type': 'title',
            'bbox': {'x': 50, 'y': 80, 'width': 900, 'height': 100},
            'content': 'سؤال ۱: متن سؤال',
        },
        {
            'type': 'list',
            'bbox': {'x': 70, 'y': 200, 'width': 850, 'height': 500},
            'content': '۱) گزینه یک ۲) گزینه دو',
        },
    ]


def _answer_blocks():
    return [
        {
            'type': 'title',
            'bbox': {'x': 50, 'y': 80, 'width': 900, 'height': 100},
            'content': 'پاسخ ۱: گزینه دوم',
        },
        {
            'type': 'text',
            'bbox': {'x': 60, 'y': 200, 'width': 880, 'height': 650},
            'content': 'راه‌حل کامل',
        },
    ]


def _continuation_blocks():
    return [
        {
            'type': 'text',
            'bbox': {'x': 60, 'y': 40, 'width': 880, 'height': 500},
            'content': 'ادامهٔ راه‌حل صفحهٔ قبل',
        }
    ]


class _Fallback:
    def __init__(self, value=None):
        self.value = value or {'blocks': [{'order': 0, 'kind': 'unknown'}]}
        self.provider_calls = 0
        self.detect_calls = 0

    def detect_segment_blocks(self, **kwargs):
        self.provider_calls += 1
        self.detect_calls += 1
        return self.value


class _NoDetectFallback(FakeFullPipelineProvider):
    def detect_segment_blocks(self, **kwargs):
        raise AssertionError('fallback detector must not run')


def _image(page_number=1):
    return PreparedVisionImage(
        image=b'private-jpeg-bytes',
        mime_type='image/jpeg',
        page_number=page_number,
        label=f'PAGE {page_number}',
    )


def _page(page_number=1):
    return type('Page', (), {'page_number': page_number})()


def _segment(role=ExamSourceRole.QUESTIONS):
    return type('Segment', (), {'role': role})()


def _document():
    return type('Document', (), {'id': 1, 'project_id': 1})()


def _config(**overrides):
    values = {
        'enabled': True,
        'model': 'mistral-ocr-4-0',
        'max_attempts': 2,
        'retry_backoff_seconds': 0,
        'min_page_confidence': 0.65,
        'request_bbox_for_diagrams': True,
    }
    values.update(overrides)
    return OCREvidenceAdapterConfig(**values)


def test_ocr_adapter_runs_real_pipeline_and_warm_reuse_makes_zero_calls():
    _teacher, _project, document, _pages = _confirmed_document()
    fallback = _NoDetectFallback()
    responses = iter(
        [
            _ocr_response(blocks=_question_blocks(), role='question'),
            _ocr_response(blocks=_answer_blocks(), role='answer_solution'),
            _ocr_response(blocks=_continuation_blocks(), role='answer_solution'),
        ]
    )

    def transport(url, headers, payload, timeout):
        del url, headers, payload, timeout
        return next(responses)

    adapter = AvalAIOCREvidenceAdapter(
        fallback=fallback,
        config=_config(),
        transport=transport,
        sleeper=lambda _seconds: None,
    )
    cold = run_document_extraction_pipeline(
        document_id=document.id,
        provider=adapter,
    )

    assert cold.block_set.block_count == 3
    assert cold.question_set.record_count == 1
    assert cold.answer_set.record_count == 1
    assert cold.matches.matched_count == 1
    assert adapter.stats.ocr_calls == 3
    assert adapter.stats.primary_successes == 3
    assert adapter.stats.fallback_count == 0
    assert fallback.provider_calls == 2
    assert adapter.provider_calls == 5

    warm_fallback = _NoDetectFallback()

    def forbidden_transport(*args, **kwargs):
        raise AssertionError('warm reuse must not call OCR')

    warm_adapter = AvalAIOCREvidenceAdapter(
        fallback=warm_fallback,
        config=_config(),
        transport=forbidden_transport,
    )
    warm = run_document_extraction_pipeline(
        document_id=document.id,
        provider=warm_adapter,
    )

    assert warm.block_set.reused is True
    assert warm.question_set.reused is True
    assert warm.answer_set.reused is True
    assert warm.matches.reused is True
    assert warm_adapter.provider_calls == 0
    assert warm_adapter.stats.ocr_calls == 0


def test_transient_transport_failure_retries_then_succeeds_without_fallback():
    fallback = _Fallback()
    calls = 0

    def transport(url, headers, payload, timeout):
        nonlocal calls
        del url, headers, payload, timeout
        calls += 1
        if calls == 1:
            return _ocr_response(blocks=[], status=503)
        return _ocr_response(blocks=_question_blocks())

    adapter = AvalAIOCREvidenceAdapter(
        fallback=fallback,
        config=_config(),
        transport=transport,
        sleeper=lambda _seconds: None,
    )
    result = adapter.detect_segment_blocks(
        document=_document(),
        segment=_segment(),
        pages=(_page(),),
        images=(_image(),),
    )

    assert len(result['blocks']) == 1
    assert result['blocks'][0]['kind'] == ExamSourceBlockKind.QUESTION
    assert adapter.stats.ocr_calls == 2
    assert adapter.stats.retries == 1
    assert adapter.stats.fallback_count == 0
    assert fallback.detect_calls == 0


def test_exhausted_transport_retries_fall_back_exactly_once():
    fallback = _Fallback({'blocks': ['fallback']})

    def transport(url, headers, payload, timeout):
        del url, headers, payload, timeout
        return _ocr_response(blocks=[], status=503)

    adapter = AvalAIOCREvidenceAdapter(
        fallback=fallback,
        config=_config(max_attempts=2),
        transport=transport,
        sleeper=lambda _seconds: None,
    )
    result = adapter.detect_segment_blocks(
        document=_document(),
        segment=_segment(),
        pages=(_page(),),
        images=(_image(),),
    )

    assert result == {'blocks': ['fallback']}
    assert adapter.stats.ocr_calls == 2
    assert adapter.stats.retries == 1
    assert adapter.stats.fallback_count == 1
    assert adapter.stats.fallback_reasons == ('transport_exhausted',)
    assert fallback.detect_calls == 1


def test_response_error_does_not_retry_and_falls_back_safely():
    fallback = _Fallback({'blocks': ['fallback']})
    calls = 0

    def transport(url, headers, payload, timeout):
        nonlocal calls
        del url, headers, payload, timeout
        calls += 1
        return OCRHTTPResponse(200, {}, b'not-json')

    adapter = AvalAIOCREvidenceAdapter(
        fallback=fallback,
        config=_config(max_attempts=3),
        transport=transport,
    )
    result = adapter.detect_segment_blocks(
        document=_document(),
        segment=_segment(),
        pages=(_page(),),
        images=(_image(),),
    )

    assert result == {'blocks': ['fallback']}
    assert calls == 1
    assert adapter.stats.retries == 0
    assert adapter.stats.fallback_count == 1
    assert fallback.detect_calls == 1


def test_low_confidence_or_empty_numbered_evidence_falls_back():
    for response, reason in (
        (
            _ocr_response(
                blocks=_question_blocks(),
                confidence=0.2,
            ),
            'low_page_confidence',
        ),
        (
            _ocr_response(
                blocks=[
                    {
                        'type': 'text',
                        'bbox': {
                            'x': 10,
                            'y': 20,
                            'width': 400,
                            'height': 200,
                        },
                        'content': 'متن بدون شماره',
                    }
                ]
            ),
            'no_numbered_groups',
        ),
    ):
        fallback = _Fallback({'blocks': ['fallback']})
        adapter = AvalAIOCREvidenceAdapter(
            fallback=fallback,
            config=_config(),
            transport=lambda *_args, response=response: response,
        )
        result = adapter.detect_segment_blocks(
            document=_document(),
            segment=_segment(),
            pages=(_page(),),
            images=(_image(),),
        )
        assert result == {'blocks': ['fallback']}
        assert adapter.stats.fallback_reasons == (reason,)
        assert fallback.detect_calls == 1


def test_bbox_annotation_is_requested_only_for_diagram_pages():
    fallback = _Fallback()
    payloads = []

    def transport(url, headers, payload, timeout):
        del url, headers, timeout
        payloads.append(payload)
        if 'bbox_annotation_format' in payload:
            return _ocr_response(blocks=_question_blocks(), has_diagram=True)
        return _ocr_response(
            blocks=_question_blocks(),
            has_diagram=True,
        )

    adapter = AvalAIOCREvidenceAdapter(
        fallback=fallback,
        config=_config(),
        transport=transport,
    )
    adapter.detect_segment_blocks(
        document=_document(),
        segment=_segment(),
        pages=(_page(),),
        images=(_image(),),
    )

    assert len(payloads) == 2
    assert 'document_annotation_format' in payloads[0]
    assert 'bbox_annotation_format' in payloads[1]
    assert adapter.stats.bbox_calls == 1

    payloads.clear()
    adapter = AvalAIOCREvidenceAdapter(
        fallback=_Fallback(),
        config=_config(),
        transport=lambda url, headers, payload, timeout: (
            payloads.append(payload)
            or _ocr_response(blocks=_question_blocks(), has_diagram=False)
        ),
    )
    adapter.detect_segment_blocks(
        document=_document(),
        segment=_segment(),
        pages=(_page(),),
        images=(_image(),),
    )
    assert len(payloads) == 1


def test_disabled_adapter_is_byte_stable_and_never_calls_ocr():
    expected = {
        'blocks': [
            {
                'order': 0,
                'kind': 'question',
                'printedNumber': '1',
            }
        ]
    }
    fallback = _Fallback(expected)
    adapter = AvalAIOCREvidenceAdapter(
        fallback=fallback,
        config=_config(enabled=False),
        transport=lambda *_args: pytest.fail('disabled adapter called OCR'),
    )

    result = adapter.detect_segment_blocks(
        document=_document(),
        segment=_segment(),
        pages=(_page(),),
        images=(_image(),),
    )

    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert adapter.stats.ocr_calls == 0
    assert adapter.stats.fallback_reasons == ('disabled',)
    assert fallback.detect_calls == 1


def test_adapter_stats_are_content_free():
    fallback = _Fallback({'blocks': ['fallback']})
    adapter = AvalAIOCREvidenceAdapter(
        fallback=fallback,
        config=_config(),
        transport=lambda *_args: OCRHTTPResponse(200, {}, b'not-json'),
    )
    adapter.detect_segment_blocks(
        document=_document(),
        segment=_segment(),
        pages=(_page(),),
        images=(_image(),),
    )

    rendered = json.dumps(adapter.stats.__dict__ if hasattr(adapter.stats, '__dict__') else {
        'ocrCalls': adapter.stats.ocr_calls,
        'fallbackReasons': adapter.stats.fallback_reasons,
        'resolvedModels': adapter.stats.resolved_models,
    }, ensure_ascii=False)
    assert 'متن خصوصی' not in rendered
    assert 'private-jpeg-bytes' not in rendered
    assert 'data:image/' not in rendered
