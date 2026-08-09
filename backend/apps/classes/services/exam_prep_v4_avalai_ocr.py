"""Bounded, privacy-safe AvalAI Mistral OCR client for V4 feasibility tests.

This module is intentionally isolated from the production extraction runner.
It accepts local private bytes, encodes them as data URLs, validates the OCR
response, and exposes private in-memory results plus aggregate-only metrics.
No source path, filename, source text, annotation payload, or image bytes are
included in the aggregate report contract.
"""
from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass
import json
import os
import re
import time
from typing import Any, Callable, Literal, Mapping, Sequence

try:  # Keep pure response/parser tests usable without the optional HTTP client.
    import requests
except ImportError:  # pragma: no cover - live environments install requests
    requests = None  # type: ignore[assignment]


AVALAI_OCR_ENDPOINT = 'https://api.avalai.ir/v1/ocr'
AVALAI_OCR_PINNED_MODEL = 'mistral-ocr-4-0'
OCRSmokeMode = Literal[
    'markdown',
    'blocks',
    'document_annotation',
    'bbox_annotation',
]

_ALLOWED_MEDIA_TYPES = {
    'application/pdf': 'document_url',
    'image/png': 'image_url',
    'image/jpeg': 'image_url',
}
_ARABIC_RTL_RE = re.compile(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]')
_FORMULA_SIGNALS = (
    '$',
    '\\(',
    '\\[',
    '\\frac',
    '\\sqrt',
    '\\begin{equation',
    '<math',
)
_TABLE_SIGNALS = ('<table', '|---', '| ---', '<tr', '<td')


class AvalAIOCRError(RuntimeError):
    pass


class AvalAIOCRConfigurationError(AvalAIOCRError):
    pass


class AvalAIOCRTransportError(AvalAIOCRError):
    pass


class AvalAIOCRResponseError(AvalAIOCRError):
    pass


class AvalAIOCRPrivacyError(AvalAIOCRError):
    pass


@dataclass(frozen=True, slots=True)
class OCRHTTPResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


OCRTransport = Callable[[str, Mapping[str, str], Mapping[str, Any], float], OCRHTTPResponse]


@dataclass(frozen=True, slots=True)
class AvalAIOCRLimits:
    max_input_bytes: int = 12 * 1024 * 1024
    max_response_bytes: int = 24 * 1024 * 1024
    max_pages: int = 8
    max_markdown_chars_per_page: int = 500_000
    max_annotation_chars: int = 500_000
    timeout_seconds: float = 180.0

    def validate(self) -> None:
        values = (
            self.max_input_bytes,
            self.max_response_bytes,
            self.max_pages,
            self.max_markdown_chars_per_page,
            self.max_annotation_chars,
        )
        if any(isinstance(value, bool) or int(value) < 1 for value in values):
            raise AvalAIOCRConfigurationError('OCR limits must be positive integers.')
        if float(self.timeout_seconds) < 1:
            raise AvalAIOCRConfigurationError('OCR timeout must be at least one second.')


@dataclass(frozen=True, slots=True)
class AvalAIOCRIssue:
    code: str
    page_index: int | None = None


@dataclass(frozen=True, slots=True)
class AvalAIOCRBlock:
    block_type: str
    bbox: tuple[float, float, float, float] | None
    content: str


@dataclass(frozen=True, slots=True)
class AvalAIOCRImage:
    bbox: tuple[float, float, float, float] | None
    annotation: Mapping[str, Any] | None
    has_base64: bool


@dataclass(frozen=True, slots=True)
class AvalAIOCRPage:
    index: int
    markdown: str
    width: int | None
    height: int | None
    dpi: int | None
    blocks: tuple[AvalAIOCRBlock, ...]
    images: tuple[AvalAIOCRImage, ...]
    page_confidence: float | None


@dataclass(frozen=True, slots=True)
class AvalAIOCRResult:
    model: str
    request_id: str
    pages: tuple[AvalAIOCRPage, ...]
    document_annotation: Mapping[str, Any] | None
    usage_pages_processed: int | None
    usage_document_bytes: int | None
    issues: tuple[AvalAIOCRIssue, ...]
    latency_ms: float


DOCUMENT_ANNOTATION_SCHEMA: dict[str, Any] = {
    'type': 'json_schema',
    'json_schema': {
        'name': 'exam_prep_v4_ocr_smoke_document',
        'schema': {
            'type': 'object',
            'properties': {
                'document_role': {
                    'type': 'string',
                    'enum': ['question', 'answer_solution', 'mixed', 'other'],
                },
                'rtl': {'type': 'boolean'},
                'has_formula': {'type': 'boolean'},
                'has_table': {'type': 'boolean'},
                'has_diagram': {'type': 'boolean'},
                'printed_numbers': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'maxItems': 200,
                },
            },
            'required': [
                'document_role',
                'rtl',
                'has_formula',
                'has_table',
                'has_diagram',
                'printed_numbers',
            ],
            'additionalProperties': False,
        },
    },
}


BBOX_ANNOTATION_SCHEMA: dict[str, Any] = {
    'type': 'json_schema',
    'json_schema': {
        'name': 'exam_prep_v4_ocr_smoke_image',
        'schema': {
            'type': 'object',
            'properties': {
                'image_type': {
                    'type': 'string',
                    'enum': [
                        'diagram',
                        'chart',
                        'table',
                        'formula',
                        'illustration',
                        'photo',
                        'other',
                    ],
                },
                'contains_text': {'type': 'boolean'},
                'reading_order_relevant': {'type': 'boolean'},
            },
            'required': [
                'image_type',
                'contains_text',
                'reading_order_relevant',
            ],
            'additionalProperties': False,
        },
    },
}


def _default_transport(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> OCRHTTPResponse:
    http = requests
    if http is None:  # pragma: no cover - exercised only in dependency failures
        try:
            import requests as http  # type: ignore[no-redef]
        except ImportError as exc:
            raise AvalAIOCRConfigurationError(
                "The 'requests' package is required for live OCR."
            ) from exc
    try:
        response = http.post(
            url,
            headers=dict(headers),
            json=dict(payload),
            timeout=timeout,
        )
    except http.RequestException as exc:
        raise AvalAIOCRTransportError('AvalAI OCR request failed.') from exc
    return OCRHTTPResponse(
        status_code=response.status_code,
        headers=dict(response.headers),
        body=response.content,
    )


def infer_media_type(path_suffix: str) -> str:
    suffix = str(path_suffix or '').lower().strip()
    if suffix == '.pdf':
        return 'application/pdf'
    if suffix == '.png':
        return 'image/png'
    if suffix in {'.jpg', '.jpeg'}:
        return 'image/jpeg'
    raise AvalAIOCRConfigurationError('Smoke input must be PDF, PNG, or JPEG.')


def _data_url(data: bytes, media_type: str, limits: AvalAIOCRLimits) -> str:
    if media_type not in _ALLOWED_MEDIA_TYPES:
        raise AvalAIOCRConfigurationError('Unsupported OCR media type.')
    if not data:
        raise AvalAIOCRConfigurationError('OCR input bytes may not be empty.')
    if len(data) > limits.max_input_bytes:
        raise AvalAIOCRConfigurationError('OCR input exceeds the bounded byte limit.')
    encoded = base64.b64encode(data).decode('ascii')
    return f'data:{media_type};base64,{encoded}'


def _validate_pages(pages: Sequence[int] | None, limits: AvalAIOCRLimits) -> tuple[int, ...] | None:
    if pages is None:
        return None
    normalized = tuple(int(value) for value in pages)
    if not normalized or len(normalized) > limits.max_pages:
        raise AvalAIOCRConfigurationError('OCR page selection exceeds the bounded limit.')
    if any(value < 0 for value in normalized):
        raise AvalAIOCRConfigurationError('OCR page indexes must be zero-based and non-negative.')
    if len(normalized) != len(set(normalized)):
        raise AvalAIOCRConfigurationError('OCR page indexes must be unique.')
    return normalized


def build_ocr_payload(
    *,
    data: bytes,
    media_type: str,
    model: str,
    mode: OCRSmokeMode,
    pages: Sequence[int] | None,
    limits: AvalAIOCRLimits,
) -> dict[str, Any]:
    limits.validate()
    selected_model = str(model or '').strip()
    if not selected_model:
        raise AvalAIOCRConfigurationError('An explicit OCR model is required.')
    document_type = _ALLOWED_MEDIA_TYPES.get(media_type)
    if document_type is None:
        raise AvalAIOCRConfigurationError('Unsupported OCR media type.')
    selected_pages = _validate_pages(pages, limits)
    url_field = 'document_url' if document_type == 'document_url' else 'image_url'
    payload: dict[str, Any] = {
        'model': selected_model,
        'document': {
            'type': document_type,
            url_field: _data_url(data, media_type, limits),
        },
        'include_image_base64': False,
        'extract_header': False,
        'extract_footer': False,
        'table_format': 'html',
    }
    if selected_pages is not None:
        payload['pages'] = list(selected_pages)
    if mode == 'blocks':
        # OCR 4 capability from current Mistral Document AI docs. AvalAI support
        # is intentionally treated as a smoke-tested capability, not assumed.
        payload['include_blocks'] = True
        payload['confidence_scores_granularity'] = 'page'
    elif mode == 'document_annotation':
        payload['document_annotation_format'] = DOCUMENT_ANNOTATION_SCHEMA
    elif mode == 'bbox_annotation':
        payload['bbox_annotation_format'] = BBOX_ANNOTATION_SCHEMA
    elif mode != 'markdown':
        raise AvalAIOCRConfigurationError('Unsupported OCR smoke mode.')
    return payload


def _parse_json_annotation(
    value: Any,
    *,
    max_chars: int,
) -> tuple[Mapping[str, Any] | None, bool]:
    if value is None or value == '':
        return None, True
    if isinstance(value, Mapping):
        rendered = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        if len(rendered) > max_chars:
            return None, False
        return dict(value), True
    if isinstance(value, str):
        if len(value) > max_chars:
            return None, False
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None, False
        if not isinstance(parsed, Mapping):
            return None, False
        return dict(parsed), True
    return None, False


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bbox_from_record(record: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    nested = record.get('bbox')
    source = nested if isinstance(nested, Mapping) else record
    if all(key in source for key in ('x', 'y', 'width', 'height')):
        x = _number(source.get('x'))
        y = _number(source.get('y'))
        width = _number(source.get('width'))
        height = _number(source.get('height'))
        if None not in {x, y, width, height} and width > 0 and height > 0:
            return (x, y, x + width, y + height)
    aliases = (
        ('top_left_x', 'top_left_y', 'bottom_right_x', 'bottom_right_y'),
        ('x0', 'y0', 'x1', 'y1'),
    )
    for x0_key, y0_key, x1_key, y1_key in aliases:
        if all(key in source for key in (x0_key, y0_key, x1_key, y1_key)):
            x0 = _number(source.get(x0_key))
            y0 = _number(source.get(y0_key))
            x1 = _number(source.get(x1_key))
            y1 = _number(source.get(y1_key))
            if None not in {x0, y0, x1, y1} and x1 > x0 and y1 > y0:
                return (x0, y0, x1, y1)
    return None


def _parse_block(record: Any) -> AvalAIOCRBlock | None:
    if not isinstance(record, Mapping):
        return None
    block_type = str(
        record.get('type')
        or record.get('block_type')
        or record.get('label')
        or 'unknown'
    ).strip()[:100]
    content = str(record.get('content') or record.get('text') or record.get('markdown') or '')
    return AvalAIOCRBlock(
        block_type=block_type or 'unknown',
        bbox=_bbox_from_record(record),
        content=content,
    )


def _parse_image(
    record: Any,
    *,
    limits: AvalAIOCRLimits,
) -> tuple[AvalAIOCRImage | None, bool]:
    if not isinstance(record, Mapping):
        return None, False
    has_base64 = bool(record.get('image_base64'))
    annotation, valid = _parse_json_annotation(
        record.get('image_annotation'),
        max_chars=limits.max_annotation_chars,
    )
    return (
        AvalAIOCRImage(
            bbox=_bbox_from_record(record),
            annotation=annotation,
            has_base64=has_base64,
        ),
        valid,
    )


def _page_confidence(record: Mapping[str, Any]) -> float | None:
    confidence = record.get('confidence_scores')
    if not isinstance(confidence, Mapping):
        return None
    value = _number(
        confidence.get('average_page_confidence_score')
        or confidence.get('page_confidence')
    )
    if value is None or not 0 <= value <= 1:
        return None
    return value


def parse_ocr_response(
    *,
    response: OCRHTTPResponse,
    expected_pages: Sequence[int] | None,
    limits: AvalAIOCRLimits,
    latency_ms: float,
) -> AvalAIOCRResult:
    if response.status_code < 200 or response.status_code >= 300:
        raise AvalAIOCRTransportError(
            f'AvalAI OCR returned HTTP {response.status_code}.'
        )
    if len(response.body) > limits.max_response_bytes:
        raise AvalAIOCRResponseError('OCR response exceeds the bounded byte limit.')
    try:
        root = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AvalAIOCRResponseError('OCR response is not valid JSON.') from exc
    if not isinstance(root, Mapping) or not isinstance(root.get('pages'), list):
        raise AvalAIOCRResponseError('OCR response does not contain a pages list.')

    issues: list[AvalAIOCRIssue] = []
    pages: list[AvalAIOCRPage] = []
    seen: set[int] = set()
    for raw_page in root['pages']:
        if not isinstance(raw_page, Mapping):
            issues.append(AvalAIOCRIssue('invalid_page_record'))
            continue
        index = raw_page.get('index')
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            issues.append(AvalAIOCRIssue('invalid_page_index'))
            continue
        if index in seen:
            raise AvalAIOCRResponseError('OCR response contains a duplicate page index.')
        seen.add(index)
        markdown = raw_page.get('markdown')
        if not isinstance(markdown, str):
            issues.append(AvalAIOCRIssue('invalid_page_markdown', index))
            markdown = ''
        if len(markdown) > limits.max_markdown_chars_per_page:
            raise AvalAIOCRResponseError('OCR page markdown exceeds the bounded limit.')

        dimensions = raw_page.get('dimensions')
        dimensions = dimensions if isinstance(dimensions, Mapping) else {}
        width = dimensions.get('width') if isinstance(dimensions.get('width'), int) else None
        height = dimensions.get('height') if isinstance(dimensions.get('height'), int) else None
        dpi = dimensions.get('dpi') if isinstance(dimensions.get('dpi'), int) else None

        blocks: list[AvalAIOCRBlock] = []
        for raw_block in raw_page.get('blocks') or []:
            block = _parse_block(raw_block)
            if block is None:
                issues.append(AvalAIOCRIssue('invalid_block_record', index))
            else:
                blocks.append(block)

        images: list[AvalAIOCRImage] = []
        for raw_image in raw_page.get('images') or []:
            image, annotation_valid = _parse_image(raw_image, limits=limits)
            if image is None:
                issues.append(AvalAIOCRIssue('invalid_image_record', index))
                continue
            if image.has_base64:
                raise AvalAIOCRPrivacyError(
                    'OCR response unexpectedly contains image base64.'
                )
            if not annotation_valid:
                issues.append(AvalAIOCRIssue('invalid_bbox_annotation', index))
            images.append(image)

        pages.append(
            AvalAIOCRPage(
                index=index,
                markdown=markdown,
                width=width,
                height=height,
                dpi=dpi,
                blocks=tuple(blocks),
                images=tuple(images),
                page_confidence=_page_confidence(raw_page),
            )
        )

    returned_indexes = tuple(page.index for page in pages)
    if expected_pages is not None and set(returned_indexes) != set(expected_pages):
        raise AvalAIOCRResponseError('OCR response page coverage does not match the request.')
    if not pages:
        raise AvalAIOCRResponseError('OCR response contains no valid pages.')

    document_annotation, annotation_valid = _parse_json_annotation(
        root.get('document_annotation'),
        max_chars=limits.max_annotation_chars,
    )
    if not annotation_valid:
        issues.append(AvalAIOCRIssue('invalid_document_annotation'))

    usage = root.get('usage_info')
    usage = usage if isinstance(usage, Mapping) else {}
    processed = usage.get('pages_processed')
    doc_bytes = usage.get('doc_size_bytes')
    return AvalAIOCRResult(
        model=str(root.get('model') or '')[:200],
        request_id=str(response.headers.get('x-request-id') or '')[:200],
        pages=tuple(sorted(pages, key=lambda page: page.index)),
        document_annotation=document_annotation,
        usage_pages_processed=(processed if isinstance(processed, int) else None),
        usage_document_bytes=(doc_bytes if isinstance(doc_bytes, int) else None),
        issues=tuple(issues),
        latency_ms=round(float(latency_ms), 2),
    )


def run_ocr_bytes(
    *,
    data: bytes,
    media_type: str,
    mode: OCRSmokeMode,
    model: str = AVALAI_OCR_PINNED_MODEL,
    pages: Sequence[int] | None = None,
    api_key: str | None = None,
    limits: AvalAIOCRLimits | None = None,
    transport: OCRTransport | None = None,
) -> AvalAIOCRResult:
    selected_limits = limits or AvalAIOCRLimits()
    selected_limits.validate()
    selected_pages = _validate_pages(pages, selected_limits)
    key = str(api_key or os.getenv('AVALAI_API_KEY') or '').strip()
    if transport is None and not key:
        raise AvalAIOCRConfigurationError('AVALAI_API_KEY is required for live OCR.')
    payload = build_ocr_payload(
        data=data,
        media_type=media_type,
        model=model,
        mode=mode,
        pages=selected_pages,
        limits=selected_limits,
    )
    headers = {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }
    selected_transport = transport or _default_transport
    started = time.monotonic()
    response = selected_transport(
        AVALAI_OCR_ENDPOINT,
        headers,
        payload,
        selected_limits.timeout_seconds,
    )
    latency_ms = (time.monotonic() - started) * 1000
    expected = selected_pages
    if expected is None and media_type.startswith('image/'):
        expected = (0,)
    return parse_ocr_response(
        response=response,
        expected_pages=expected,
        limits=selected_limits,
        latency_ms=latency_ms,
    )


def aggregate_ocr_result(
    *,
    fixture_id: str,
    mode: OCRSmokeMode,
    input_bytes: int,
    result: AvalAIOCRResult,
) -> dict[str, Any]:
    markdown = '\n'.join(page.markdown for page in result.pages)
    block_types = Counter(
        block.block_type
        for page in result.pages
        for block in page.blocks
    )
    annotated_images = sum(
        image.annotation is not None
        for page in result.pages
        for image in page.images
    )
    bbox_count = sum(
        block.bbox is not None
        for page in result.pages
        for block in page.blocks
    ) + sum(
        image.bbox is not None
        for page in result.pages
        for image in page.images
    )
    confidences = [
        page.page_confidence
        for page in result.pages
        if page.page_confidence is not None
    ]
    return {
        'fixtureId': fixture_id,
        'mode': mode,
        'model': result.model or AVALAI_OCR_PINNED_MODEL,
        'requestId': result.request_id,
        'inputBytes': int(input_bytes),
        'returnedPageCount': len(result.pages),
        'returnedPageIndexes': [page.index for page in result.pages],
        'markdownCharCount': len(markdown),
        'rtlCharacterCount': len(_ARABIC_RTL_RE.findall(markdown)),
        'formulaSignalCount': sum(markdown.count(signal) for signal in _FORMULA_SIGNALS),
        'tableSignalCount': sum(markdown.lower().count(signal) for signal in _TABLE_SIGNALS),
        'blockCount': sum(len(page.blocks) for page in result.pages),
        'blockTypeCounts': dict(sorted(block_types.items())),
        'imageCount': sum(len(page.images) for page in result.pages),
        'bboxCount': bbox_count,
        'bboxAnnotationCount': annotated_images,
        'documentAnnotationPresent': result.document_annotation is not None,
        'issueCodes': sorted(issue.code for issue in result.issues),
        'pageConfidenceAverage': (
            round(sum(confidences) / len(confidences), 6)
            if confidences
            else None
        ),
        'usagePagesProcessed': result.usage_pages_processed,
        'usageDocumentBytes': result.usage_document_bytes,
        'latencyMs': result.latency_ms,
    }


def assert_aggregate_ocr_report(report: Mapping[str, Any]) -> None:
    forbidden_keys = {
        'path',
        'filename',
        'markdown',
        'content',
        'annotation',
        'image_base64',
        'document_url',
        'image_url',
        'questionText',
        'solutionText',
        'finalAnswer',
        'rawPayload',
    }

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            if forbidden_keys & set(value):
                raise AvalAIOCRPrivacyError('Aggregate OCR report contains a private key.')
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(report)
    rendered = json.dumps(report, ensure_ascii=False, default=str)
    if 'data:application/' in rendered or 'data:image/' in rendered:
        raise AvalAIOCRPrivacyError('Aggregate OCR report contains a data URL.')
