"""Optional AvalAI OCR evidence proposals for Exam Prep V4 block detection.

The adapter is intentionally proposal-only. It never persists OCR output and it
never overrides the confirmed Source Map or the existing SourceBlock validator.
Any incomplete, malformed, low-confidence, or unavailable OCR evidence falls
back to the existing detector for the whole segment.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import time
from typing import Any, Callable, Mapping, Protocol, Sequence

from apps.classes.models_v4 import ExamSourceRole
from apps.classes.models_v4_blocks import ExamSourceBlockKind
from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRError,
    AvalAIOCRLimits,
    AvalAIOCRResult,
    AvalAIOCRTransportError,
    OCRTransport,
    run_ocr_bytes,
)
from apps.classes.services.exam_prep_v4_blocks import normalize_printed_number


_HEADING_RE = re.compile(
    r'^\s*(?:(?:س[ؤو]ال|پاسخ|جواب)\s*)?'
    r'([۰-۹٠-٩0-9]{1,4})(?:\s*[\)\].:،؛\-–—]|\s+)',
    re.IGNORECASE,
)
_IGNORED_BLOCK_TYPES = frozenset(
    {
        'header',
        'footer',
        'page_header',
        'page_footer',
        'page_number',
        'signature',
    }
)
_HEADING_BLOCK_TYPES = frozenset(
    {'title', 'heading', 'section_header', 'text', 'paragraph', 'unknown'}
)


class OCREvidenceFallbackProvider(Protocol):
    provider_calls: int

    def detect_segment_blocks(self, **kwargs) -> Any: ...


@dataclass(frozen=True, slots=True)
class OCREvidenceAdapterConfig:
    enabled: bool = True
    model: str = AVALAI_OCR_PINNED_MODEL
    max_attempts: int = 2
    retry_backoff_seconds: float = 0.25
    min_page_confidence: float = 0.65
    request_bbox_for_diagrams: bool = True
    limits: AvalAIOCRLimits = AvalAIOCRLimits()

    def validate(self) -> None:
        if not self.model.strip():
            raise ValueError('OCR evidence model is required.')
        if isinstance(self.max_attempts, bool) or self.max_attempts < 1:
            raise ValueError('OCR evidence max_attempts must be positive.')
        if self.retry_backoff_seconds < 0:
            raise ValueError('OCR evidence retry backoff may not be negative.')
        if not 0 <= self.min_page_confidence <= 1:
            raise ValueError('OCR evidence confidence must be between zero and one.')
        self.limits.validate()


@dataclass(frozen=True, slots=True)
class OCREvidenceAdapterStats:
    ocr_calls: int
    primary_successes: int
    bbox_calls: int
    retries: int
    fallback_count: int
    fallback_reasons: tuple[str, ...]
    resolved_models: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _NormalizedBlock:
    block_type: str
    content: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class _PageGroup:
    printed_number: str
    bbox: tuple[float, float, float, float]
    continuation: bool = False


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float, *, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def ocr_evidence_config_from_env() -> OCREvidenceAdapterConfig:
    return OCREvidenceAdapterConfig(
        enabled=_bool_env('EXAM_PREP_V4_OCR_EVIDENCE_ENABLED', False),
        model=(
            os.getenv('EXAM_PREP_V4_OCR_EVIDENCE_MODEL')
            or AVALAI_OCR_PINNED_MODEL
        ).strip(),
        max_attempts=_int_env('EXAM_PREP_V4_OCR_EVIDENCE_MAX_ATTEMPTS', 2),
        retry_backoff_seconds=_float_env(
            'EXAM_PREP_V4_OCR_EVIDENCE_RETRY_BACKOFF_SECONDS',
            0.25,
        ),
        min_page_confidence=min(
            1.0,
            _float_env('EXAM_PREP_V4_OCR_EVIDENCE_MIN_CONFIDENCE', 0.65),
        ),
        request_bbox_for_diagrams=_bool_env(
            'EXAM_PREP_V4_OCR_EVIDENCE_BBOX_FOR_DIAGRAMS',
            True,
        ),
    )


def _primary_kind(role: str) -> str | None:
    return {
        ExamSourceRole.QUESTIONS: ExamSourceBlockKind.QUESTION,
        ExamSourceRole.ANSWER_SOLUTIONS: ExamSourceBlockKind.ANSWER_SOLUTION,
        ExamSourceRole.ANSWER_KEY: ExamSourceBlockKind.ANSWER_KEY,
        ExamSourceRole.INLINE_QUESTION_ANSWER: (
            ExamSourceBlockKind.INLINE_QUESTION_ANSWER
        ),
    }.get(role)


def _normalized_bbox(
    bbox: tuple[float, float, float, float] | None,
    *,
    width: int | None,
    height: int | None,
) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    x0, y0, x1, y1 = (float(value) for value in bbox)
    if x1 <= 1 and y1 <= 1:
        normalized = (x0, y0, x1, y1)
    else:
        if not width or not height:
            return None
        normalized = (x0 / width, y0 / height, x1 / width, y1 / height)
    x0, y0, x1, y1 = normalized
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(1.0, x1), min(1.0, y1)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return (x0, y0, x1, y1)


def _union_bbox(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return (
        min(first[0], second[0]),
        min(first[1], second[1]),
        max(first[2], second[2]),
        max(first[3], second[3]),
    )


def _heading_number(block: _NormalizedBlock) -> str:
    if block.block_type not in _HEADING_BLOCK_TYPES:
        return ''
    match = _HEADING_RE.match(block.content)
    return normalize_printed_number(match.group(1)) if match else ''


def _page_blocks(result: AvalAIOCRResult) -> tuple[_NormalizedBlock, ...]:
    if len(result.pages) != 1:
        return ()
    page = result.pages[0]
    normalized: list[_NormalizedBlock] = []
    for block in page.blocks:
        block_type = str(block.block_type or 'unknown').strip().lower()
        if block_type in _IGNORED_BLOCK_TYPES:
            continue
        bbox = _normalized_bbox(
            block.bbox,
            width=page.width,
            height=page.height,
        )
        if bbox is None:
            continue
        content = str(block.content or '').strip()
        if not content and block_type not in {'image', 'figure', 'chart', 'table'}:
            continue
        normalized.append(
            _NormalizedBlock(
                block_type=block_type,
                content=content,
                bbox=bbox,
            )
        )
    return tuple(normalized)


def _group_page(
    result: AvalAIOCRResult,
    *,
    allow_continuation: bool,
    has_previous_primary: bool,
) -> tuple[_PageGroup, ...]:
    blocks = _page_blocks(result)
    if not blocks:
        return ()

    groups: list[_PageGroup] = []
    current_number = ''
    current_bbox: tuple[float, float, float, float] | None = None
    for block in blocks:
        number = _heading_number(block)
        if number:
            if current_number and current_bbox is not None:
                groups.append(
                    _PageGroup(
                        printed_number=current_number,
                        bbox=current_bbox,
                    )
                )
            current_number = number
            current_bbox = block.bbox
            continue
        if current_number and current_bbox is not None:
            current_bbox = _union_bbox(current_bbox, block.bbox)

    if current_number and current_bbox is not None:
        groups.append(
            _PageGroup(
                printed_number=current_number,
                bbox=current_bbox,
            )
        )
    if groups:
        return tuple(groups)

    if allow_continuation and has_previous_primary:
        bbox = blocks[0].bbox
        for block in blocks[1:]:
            bbox = _union_bbox(bbox, block.bbox)
        return (_PageGroup(printed_number='', bbox=bbox, continuation=True),)
    return ()


class AvalAIOCREvidenceAdapter:
    """Wrap an existing provider with fail-closed OCR block proposals."""

    def __init__(
        self,
        *,
        fallback: OCREvidenceFallbackProvider,
        config: OCREvidenceAdapterConfig | None = None,
        api_key: str | None = None,
        transport: OCRTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.fallback = fallback
        self.config = config or ocr_evidence_config_from_env()
        self.config.validate()
        self.api_key = api_key
        self.transport = transport
        self.sleeper = sleeper
        self._ocr_calls = 0
        self._primary_successes = 0
        self._bbox_calls = 0
        self._retries = 0
        self._fallback_count = 0
        self._fallback_reasons: list[str] = []
        self._resolved_models: set[str] = set()

    @property
    def provider_calls(self) -> int:
        return self._ocr_calls + int(getattr(self.fallback, 'provider_calls', 0))

    @property
    def stats(self) -> OCREvidenceAdapterStats:
        return OCREvidenceAdapterStats(
            ocr_calls=self._ocr_calls,
            primary_successes=self._primary_successes,
            bbox_calls=self._bbox_calls,
            retries=self._retries,
            fallback_count=self._fallback_count,
            fallback_reasons=tuple(self._fallback_reasons),
            resolved_models=tuple(sorted(self._resolved_models)),
        )

    def __getattr__(self, name: str):
        return getattr(self.fallback, name)

    def _call(
        self,
        *,
        image: Any,
        mode: str,
    ) -> tuple[AvalAIOCRResult | None, str | None]:
        for attempt in range(self.config.max_attempts):
            self._ocr_calls += 1
            if mode == 'bbox_annotation':
                self._bbox_calls += 1
            try:
                result = run_ocr_bytes(
                    data=image.image,
                    media_type=image.mime_type,
                    mode=mode,
                    model=self.config.model,
                    api_key=self.api_key,
                    limits=self.config.limits,
                    transport=self.transport,
                )
                if result.model:
                    self._resolved_models.add(result.model)
                return result, None
            except AvalAIOCRTransportError:
                if attempt + 1 >= self.config.max_attempts:
                    return None, 'transport_exhausted'
                self._retries += 1
                delay = self.config.retry_backoff_seconds * (attempt + 1)
                if delay:
                    self.sleeper(delay)
            except AvalAIOCRError as exc:
                return None, type(exc).__name__
        return None, 'transport_exhausted'

    def _fallback(self, reason: str, **kwargs):
        self._fallback_count += 1
        self._fallback_reasons.append(reason)
        return self.fallback.detect_segment_blocks(**kwargs)

    def detect_segment_blocks(
        self,
        *,
        document,
        segment,
        pages: Sequence[Any],
        images: Sequence[Any],
    ) -> Any:
        kwargs = {
            'document': document,
            'segment': segment,
            'pages': pages,
            'images': images,
        }
        if not self.config.enabled:
            return self._fallback('disabled', **kwargs)
        primary_kind = _primary_kind(segment.role)
        if primary_kind is None:
            return self._fallback('unsupported_role', **kwargs)
        if len(pages) != len(images) or not pages:
            return self._fallback('page_image_mismatch', **kwargs)

        records: list[dict[str, Any]] = []
        previous_primary_order: int | None = None
        for page, image in zip(pages, images, strict=True):
            result, error = self._call(
                image=image,
                mode='document_annotation',
            )
            if result is None:
                return self._fallback(error or 'primary_ocr_failed', **kwargs)
            if len(result.pages) != 1:
                return self._fallback('unexpected_page_count', **kwargs)
            page_result = result.pages[0]
            if (
                page_result.page_confidence is not None
                and page_result.page_confidence < self.config.min_page_confidence
            ):
                return self._fallback('low_page_confidence', **kwargs)

            groups = _group_page(
                result,
                allow_continuation=(
                    segment.role == ExamSourceRole.ANSWER_SOLUTIONS
                ),
                has_previous_primary=previous_primary_order is not None,
            )
            if not groups:
                return self._fallback('no_numbered_groups', **kwargs)
            self._primary_successes += 1

            annotation = result.document_annotation or {}
            has_diagram = bool(
                isinstance(annotation, Mapping)
                and annotation.get('has_diagram') is True
            )
            if has_diagram and self.config.request_bbox_for_diagrams:
                self._call(image=image, mode='bbox_annotation')

            for group in groups:
                order = len(records)
                x0, y0, x1, y1 = group.bbox
                continuation_parent = (
                    previous_primary_order if group.continuation else None
                )
                kind = (
                    ExamSourceBlockKind.CONTINUATION
                    if group.continuation
                    else primary_kind
                )
                records.append(
                    {
                        'order': order,
                        'kind': kind,
                        'printedNumber': group.printed_number,
                        'confidence': (
                            page_result.page_confidence
                            if page_result.page_confidence is not None
                            else 0.75
                        ),
                        'continuationOfOrder': continuation_parent,
                        'fragments': [
                            {
                                'order': 0,
                                'pageNumber': page.page_number,
                                'x0': x0,
                                'y0': y0,
                                'x1': x1,
                                'y1': y1,
                                'columnIndex': 0,
                                'isContinuation': group.continuation,
                            }
                        ],
                    }
                )
                if not group.continuation:
                    previous_primary_order = order

        if not records:
            return self._fallback('empty_proposals', **kwargs)
        return {'blocks': records}


def wrap_with_optional_ocr_evidence(
    fallback: OCREvidenceFallbackProvider,
    *,
    config: OCREvidenceAdapterConfig | None = None,
    api_key: str | None = None,
    transport: OCRTransport | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> OCREvidenceFallbackProvider:
    selected = config or ocr_evidence_config_from_env()
    if not selected.enabled:
        return fallback
    return AvalAIOCREvidenceAdapter(
        fallback=fallback,
        config=selected,
        api_key=api_key,
        transport=transport,
        sleeper=sleeper,
    )
