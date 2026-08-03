"""Tolerant, revision-bound source block contracts for Exam Prep V4."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Iterable, Mapping

from django.db import transaction
from django.db.models import Max, Prefetch
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)
from apps.classes.models_v4_blocks import (
    ExamSourceBlock,
    ExamSourceBlockFragment,
    ExamSourceBlockKind,
)


BLOCK_SCHEMA_VERSION = 1
_PERSIAN_DIGITS = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
    '01234567890123456789',
)
_ALLOWED_KINDS = frozenset(ExamSourceBlockKind.values)


class InvalidBlockInput(ValueError):
    pass


class SourceMapNotConfirmed(RuntimeError):
    pass


class StaleBlockSourceMap(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BlockFragmentProposal:
    order: int
    page_number: int
    x0: Decimal
    y0: Decimal
    x1: Decimal
    y1: Decimal
    column_index: int | None = None
    is_continuation: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceBlockProposal:
    order: int
    segment_order: int
    kind: str
    fragments: tuple[BlockFragmentProposal, ...]
    printed_number: str = ''
    confidence: float = 0.0
    continuation_of_order: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BlockParseIssue:
    code: str
    record_index: int | None = None
    block_order: int | None = None
    detail: str = ''

    def as_dict(self) -> dict[str, Any]:
        return {
            'code': self.code,
            'recordIndex': self.record_index,
            'blockOrder': self.block_order,
            'detail': self.detail,
        }


@dataclass(frozen=True, slots=True)
class BlockParseResult:
    blocks: tuple[SourceBlockProposal, ...]
    issues: tuple[BlockParseIssue, ...]


@dataclass(frozen=True, slots=True)
class PersistedBlockSet:
    document_id: int
    revision: int
    source_map_fingerprint: str
    set_fingerprint: str
    block_count: int
    fragment_count: int
    reused: bool = False


class BlockFragmentPayload(BaseModel):
    model_config = ConfigDict(extra='ignore', populate_by_name=True)

    order: int = Field(ge=0)
    page_number: int = Field(alias='pageNumber', ge=1)
    x0: Decimal = Field(ge=0, le=1)
    y0: Decimal = Field(ge=0, le=1)
    x1: Decimal = Field(gt=0, le=1)
    y1: Decimal = Field(gt=0, le=1)
    column_index: int | None = Field(default=None, alias='columnIndex', ge=0)
    is_continuation: bool = Field(default=False, alias='isContinuation')

    @field_validator('x1')
    @classmethod
    def positive_width(cls, value: Decimal, info):
        x0 = info.data.get('x0')
        if x0 is not None and value <= x0:
            raise ValueError('x1 must be greater than x0')
        return value

    @field_validator('y1')
    @classmethod
    def positive_height(cls, value: Decimal, info):
        y0 = info.data.get('y0')
        if y0 is not None and value <= y0:
            raise ValueError('y1 must be greater than y0')
        return value


class SourceBlockPayload(BaseModel):
    model_config = ConfigDict(extra='ignore', populate_by_name=True)

    order: int = Field(ge=0)
    segment_order: int = Field(alias='segmentOrder', ge=0)
    kind: str = ExamSourceBlockKind.UNKNOWN
    printed_number: str = Field(default='', alias='printedNumber', max_length=64)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    continuation_of_order: int | None = Field(
        default=None,
        alias='continuationOfOrder',
        ge=0,
    )
    fragments: list[BlockFragmentPayload] = Field(min_length=1)

    @field_validator('kind')
    @classmethod
    def validate_kind(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_KINDS:
            raise ValueError(f'unsupported block kind: {value}')
        return normalized


def normalize_printed_number(value: Any) -> str:
    return ''.join(str(value or '').translate(_PERSIAN_DIGITS).split())[:64]


def _quantize(value: Decimal | float | str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal('0.000001'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidBlockInput('Invalid normalized bounding-box coordinate.') from exc


def _records_from_payload(raw_output: Any) -> list[Any]:
    if isinstance(raw_output, list):
        return raw_output
    if isinstance(raw_output, dict) and isinstance(raw_output.get('blocks'), list):
        return raw_output['blocks']
    raise InvalidBlockInput(
        'Block detector output must be a list or an object with a blocks list.'
    )


def parse_block_detector_output(raw_output: Any) -> BlockParseResult:
    """Validate each detector block independently and retain valid siblings."""

    records = _records_from_payload(raw_output)
    by_order: dict[int, SourceBlockPayload] = {}
    issues: list[BlockParseIssue] = []

    for index, raw_record in enumerate(records):
        try:
            parsed = SourceBlockPayload.model_validate(raw_record)
        except ValidationError as exc:
            issues.append(
                BlockParseIssue(
                    code='invalid_block_record',
                    record_index=index,
                    detail=str(exc.errors(include_url=False))[:1200],
                )
            )
            continue

        previous = by_order.get(parsed.order)
        if previous is not None:
            issues.append(
                BlockParseIssue(
                    code='duplicate_block_order',
                    record_index=index,
                    block_order=parsed.order,
                    detail='The higher-confidence record was retained.',
                )
            )
            if previous.confidence >= parsed.confidence:
                continue
        by_order[parsed.order] = parsed

    proposals: list[SourceBlockProposal] = []
    for parsed in sorted(by_order.values(), key=lambda item: item.order):
        fragments = tuple(
            BlockFragmentProposal(
                order=fragment.order,
                page_number=fragment.page_number,
                x0=_quantize(fragment.x0),
                y0=_quantize(fragment.y0),
                x1=_quantize(fragment.x1),
                y1=_quantize(fragment.y1),
                column_index=fragment.column_index,
                is_continuation=fragment.is_continuation,
            )
            for fragment in sorted(parsed.fragments, key=lambda item: item.order)
        )
        proposals.append(
            SourceBlockProposal(
                order=parsed.order,
                segment_order=parsed.segment_order,
                kind=parsed.kind,
                printed_number=normalize_printed_number(parsed.printed_number),
                confidence=parsed.confidence,
                continuation_of_order=parsed.continuation_of_order,
                fragments=fragments,
            )
        )

    return BlockParseResult(blocks=tuple(proposals), issues=tuple(issues))


_ROLE_KIND_COMPATIBILITY: dict[str, frozenset[str]] = {
    ExamSourceRole.COVER: frozenset(
        {ExamSourceBlockKind.IGNORED, ExamSourceBlockKind.UNKNOWN}
    ),
    ExamSourceRole.QUESTIONS: frozenset(
        {
            ExamSourceBlockKind.QUESTION,
            ExamSourceBlockKind.IGNORED,
            ExamSourceBlockKind.UNKNOWN,
        }
    ),
    ExamSourceRole.ANSWER_SOLUTIONS: frozenset(
        {
            ExamSourceBlockKind.ANSWER_SOLUTION,
            ExamSourceBlockKind.CONTINUATION,
            ExamSourceBlockKind.IGNORED,
            ExamSourceBlockKind.UNKNOWN,
        }
    ),
    ExamSourceRole.ANSWER_KEY: frozenset(
        {
            ExamSourceBlockKind.ANSWER_KEY,
            ExamSourceBlockKind.IGNORED,
            ExamSourceBlockKind.UNKNOWN,
        }
    ),
    ExamSourceRole.INLINE_QUESTION_ANSWER: frozenset(
        {
            ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
            ExamSourceBlockKind.IGNORED,
            ExamSourceBlockKind.UNKNOWN,
        }
    ),
    ExamSourceRole.IGNORED: frozenset({ExamSourceBlockKind.IGNORED}),
    ExamSourceRole.UNKNOWN: frozenset(_ALLOWED_KINDS),
}


def _segment_page_numbers(
    segment: ExamSourceSegment,
    ordered_pages: tuple[ExamSourcePage, ...],
) -> tuple[int, ...]:
    raw = (segment.metadata or {}).get('pageNumbers')
    if isinstance(raw, list) and raw:
        try:
            numbers = tuple(int(value) for value in raw)
        except (TypeError, ValueError):
            numbers = ()
        if numbers:
            return numbers

    positions = {page.page_number: index for index, page in enumerate(ordered_pages)}
    if segment.start_page not in positions or segment.end_page not in positions:
        raise InvalidBlockInput('Segment boundary pages are missing from the document.')
    start = positions[segment.start_page]
    end = positions[segment.end_page]
    low, high = sorted((start, end))
    sequence = tuple(page.page_number for page in ordered_pages[low : high + 1])
    if start > end:
        sequence = tuple(reversed(sequence))
    return sequence


def _fragment_payload(fragment: BlockFragmentProposal) -> dict[str, Any]:
    return {
        'order': fragment.order,
        'pageNumber': fragment.page_number,
        'bbox': [
            str(fragment.x0),
            str(fragment.y0),
            str(fragment.x1),
            str(fragment.y1),
        ],
        'columnIndex': fragment.column_index,
        'isContinuation': fragment.is_continuation,
    }


def _block_payload(block: SourceBlockProposal) -> dict[str, Any]:
    return {
        'order': block.order,
        'segmentOrder': block.segment_order,
        'kind': block.kind,
        'printedNumber': block.printed_number,
        'confidence': round(float(block.confidence), 6),
        'continuationOfOrder': block.continuation_of_order,
        'fragments': [_fragment_payload(fragment) for fragment in block.fragments],
    }


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    ).hexdigest()


def source_block_fingerprint(
    block: SourceBlockProposal,
    *,
    source_map_fingerprint: str,
) -> str:
    return _hash_payload(
        {
            'schemaVersion': BLOCK_SCHEMA_VERSION,
            'sourceMapFingerprint': source_map_fingerprint,
            'block': _block_payload(block),
        }
    )


def source_block_set_fingerprint(
    blocks: Iterable[SourceBlockProposal],
    *,
    source_map_fingerprint: str,
) -> str:
    return _hash_payload(
        {
            'schemaVersion': BLOCK_SCHEMA_VERSION,
            'sourceMapFingerprint': source_map_fingerprint,
            'blocks': [_block_payload(block) for block in blocks],
        }
    )


def _validate_and_normalize_proposals(
    *,
    proposals: Iterable[SourceBlockProposal],
    segments_by_order: Mapping[int, ExamSourceSegment],
    ordered_pages: tuple[ExamSourcePage, ...],
) -> tuple[SourceBlockProposal, ...]:
    blocks = tuple(sorted(proposals, key=lambda item: item.order))
    if not blocks:
        raise InvalidBlockInput('At least one source block is required.')
    if [block.order for block in blocks] != list(range(len(blocks))):
        raise InvalidBlockInput('Block order must be a complete zero-based sequence.')

    pages_by_number = {page.page_number: page for page in ordered_pages}
    block_orders = {block.order for block in blocks}
    normalized: list[SourceBlockProposal] = []

    for block in blocks:
        segment = segments_by_order.get(block.segment_order)
        if segment is None:
            raise InvalidBlockInput('Block references a non-current source segment.')
        if block.kind not in _ROLE_KIND_COMPATIBILITY.get(segment.role, frozenset()):
            raise InvalidBlockInput(
                f'Block kind {block.kind} is incompatible with segment role {segment.role}.'
            )
        if block.continuation_of_order is not None:
            if block.continuation_of_order not in block_orders:
                raise InvalidBlockInput('Continuation parent block does not exist.')
            if block.continuation_of_order >= block.order:
                raise InvalidBlockInput('Continuation parent must precede the continuation.')

        fragments = tuple(sorted(block.fragments, key=lambda item: item.order))
        if not fragments:
            raise InvalidBlockInput('Every source block requires at least one fragment.')
        if [fragment.order for fragment in fragments] != list(range(len(fragments))):
            raise InvalidBlockInput(
                'Fragment order must be a complete zero-based sequence per block.'
            )

        allowed_pages = set(_segment_page_numbers(segment, ordered_pages))
        display_orders: list[int] = []
        normalized_fragments: list[BlockFragmentProposal] = []
        for fragment in fragments:
            page = pages_by_number.get(fragment.page_number)
            if page is None or fragment.page_number not in allowed_pages:
                raise InvalidBlockInput(
                    'Block fragment page must belong to the referenced current segment.'
                )
            coordinates = tuple(
                _quantize(value)
                for value in (fragment.x0, fragment.y0, fragment.x1, fragment.y1)
            )
            x0, y0, x1, y1 = coordinates
            if not (
                Decimal('0') <= x0 < x1 <= Decimal('1')
                and Decimal('0') <= y0 < y1 <= Decimal('1')
            ):
                raise InvalidBlockInput('Fragment bounding box must be normalized and positive.')
            display_orders.append(page.display_order)
            normalized_fragments.append(
                BlockFragmentProposal(
                    order=fragment.order,
                    page_number=fragment.page_number,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    column_index=fragment.column_index,
                    is_continuation=fragment.is_continuation,
                    metadata=dict(fragment.metadata),
                )
            )
        if display_orders != sorted(display_orders):
            raise InvalidBlockInput(
                'Block fragments must follow the document virtual page order.'
            )

        normalized.append(
            SourceBlockProposal(
                order=block.order,
                segment_order=block.segment_order,
                kind=block.kind,
                printed_number=normalize_printed_number(block.printed_number),
                confidence=float(block.confidence),
                continuation_of_order=block.continuation_of_order,
                fragments=tuple(normalized_fragments),
                metadata=dict(block.metadata),
            )
        )
    return tuple(normalized)


def _current_accepted_blocks(
    document: ExamSourceDocument,
) -> tuple[ExamSourceBlock, ...]:
    current_revision = (
        ExamSourceBlock.objects.filter(
            document=document,
            source_map_fingerprint=document.source_map_fingerprint,
            status=ExamSourceBlock.Status.ACCEPTED,
        ).aggregate(value=Max('revision'))['value']
    )
    if current_revision is None:
        return ()
    return tuple(
        ExamSourceBlock.objects.filter(
            document=document,
            source_map_fingerprint=document.source_map_fingerprint,
            revision=current_revision,
            status=ExamSourceBlock.Status.ACCEPTED,
        ).order_by('order')
    )


@transaction.atomic
def persist_source_blocks(
    *,
    document_id: int,
    expected_source_map_revision: int,
    expected_source_map_fingerprint: str,
    proposals: Iterable[SourceBlockProposal],
) -> PersistedBlockSet:
    """Atomically persist one complete block set for a confirmed Source Map."""

    document = (
        ExamSourceDocument.objects.select_for_update()
        .select_related('project')
        .get(id=document_id)
    )
    project = ExamProject.objects.select_for_update().get(id=document.project_id)

    if (
        document.classification_revision != expected_source_map_revision
        or document.source_map_fingerprint != expected_source_map_fingerprint
    ):
        raise StaleBlockSourceMap('The confirmed Source Map changed before block persistence.')
    if not (
        document.status == ExamSourceDocument.Status.CONFIRMED
        and document.teacher_confirmed_revision == document.classification_revision
        and document.teacher_confirmed_fingerprint == document.source_map_fingerprint
        and document.teacher_confirmed_at is not None
    ):
        raise SourceMapNotConfirmed(
            'Source blocks may only be created from the exact confirmed Source Map.'
        )

    segments = tuple(
        ExamSourceSegment.objects.select_for_update()
        .filter(
            document=document,
            revision=document.classification_revision,
            teacher_confirmed=True,
            status=ExamSourceSegment.Status.CONFIRMED,
        )
        .order_by('order')
    )
    if not segments:
        raise SourceMapNotConfirmed('No confirmed current-revision segments exist.')
    segments_by_order = {segment.order: segment for segment in segments}
    ordered_pages = tuple(
        ExamSourcePage.objects.select_for_update()
        .filter(document=document)
        .order_by('display_order', 'page_number')
    )
    if len(ordered_pages) != document.page_count:
        raise InvalidBlockInput('The source page map is incomplete.')

    blocks = _validate_and_normalize_proposals(
        proposals=proposals,
        segments_by_order=segments_by_order,
        ordered_pages=ordered_pages,
    )
    set_fingerprint = source_block_set_fingerprint(
        blocks,
        source_map_fingerprint=document.source_map_fingerprint,
    )

    current = _current_accepted_blocks(document)
    if current and all(block.set_fingerprint == set_fingerprint for block in current):
        return PersistedBlockSet(
            document_id=document.id,
            revision=current[0].revision,
            source_map_fingerprint=document.source_map_fingerprint,
            set_fingerprint=set_fingerprint,
            block_count=len(current),
            fragment_count=sum(block.fragments.count() for block in current),
            reused=True,
        )

    if current:
        ExamSourceBlock.objects.filter(id__in=[block.id for block in current]).update(
            status=ExamSourceBlock.Status.SUPERSEDED,
        )
    revision = (
        ExamSourceBlock.objects.filter(document=document).aggregate(value=Max('revision'))[
            'value'
        ]
        or 0
    ) + 1

    created_by_order: dict[int, ExamSourceBlock] = {}
    all_fragments: list[ExamSourceBlockFragment] = []
    for proposal in blocks:
        block = ExamSourceBlock.objects.create(
            document=document,
            segment=segments_by_order[proposal.segment_order],
            revision=revision,
            order=proposal.order,
            kind=proposal.kind,
            printed_number=proposal.printed_number,
            confidence=Decimal(str(proposal.confidence)),
            source_map_fingerprint=document.source_map_fingerprint,
            set_fingerprint=set_fingerprint,
            fingerprint=source_block_fingerprint(
                proposal,
                source_map_fingerprint=document.source_map_fingerprint,
            ),
            metadata=dict(proposal.metadata),
        )
        created_by_order[proposal.order] = block
        for fragment in proposal.fragments:
            all_fragments.append(
                ExamSourceBlockFragment(
                    block=block,
                    page=next(
                        page
                        for page in ordered_pages
                        if page.page_number == fragment.page_number
                    ),
                    order=fragment.order,
                    x0=fragment.x0,
                    y0=fragment.y0,
                    x1=fragment.x1,
                    y1=fragment.y1,
                    column_index=fragment.column_index,
                    is_continuation=fragment.is_continuation,
                    metadata=dict(fragment.metadata),
                )
            )
    ExamSourceBlockFragment.objects.bulk_create(all_fragments)

    continuation_updates: list[ExamSourceBlock] = []
    for proposal in blocks:
        if proposal.continuation_of_order is None:
            continue
        block = created_by_order[proposal.order]
        block.continuation_of = created_by_order[proposal.continuation_of_order]
        continuation_updates.append(block)
    if continuation_updates:
        ExamSourceBlock.objects.bulk_update(continuation_updates, ['continuation_of'])

    project.status = ExamProject.Status.EXTRACTING_QUESTIONS
    project.workflow_state = {
        'stage': 'blocks_ready',
        'progressPercent': 35,
        'blockCount': len(blocks),
        'fragmentCount': len(all_fragments),
    }
    project.error_code = ''
    project.error_detail = ''
    project.save(
        update_fields=[
            'status',
            'workflow_state',
            'error_code',
            'error_detail',
            'updated_at',
        ]
    )

    return PersistedBlockSet(
        document_id=document.id,
        revision=revision,
        source_map_fingerprint=document.source_map_fingerprint,
        set_fingerprint=set_fingerprint,
        block_count=len(blocks),
        fragment_count=len(all_fragments),
        reused=False,
    )


def get_teacher_source_blocks(
    *,
    teacher,
    project_id: int,
    document_id: int,
) -> dict[str, Any]:
    """Return a content-free owner-scoped summary of the current block set."""

    document = (
        ExamSourceDocument.objects.filter(
            id=document_id,
            project_id=project_id,
            project__teacher=teacher,
        )
        .only(
            'id',
            'classification_revision',
            'source_map_fingerprint',
            'teacher_confirmed_revision',
        )
        .first()
    )
    if document is None:
        raise ExamSourceDocument.DoesNotExist

    revision = (
        ExamSourceBlock.objects.filter(
            document=document,
            source_map_fingerprint=document.source_map_fingerprint,
            status=ExamSourceBlock.Status.ACCEPTED,
        ).aggregate(value=Max('revision'))['value']
    )
    if revision is None:
        return {
            'documentId': document.id,
            'sourceMapRevision': document.classification_revision,
            'blockRevision': None,
            'blockCount': 0,
            'blocks': [],
        }

    fragments = Prefetch(
        'fragments',
        queryset=ExamSourceBlockFragment.objects.select_related('page').order_by(
            'order'
        ),
    )
    blocks = list(
        ExamSourceBlock.objects.filter(
            document=document,
            source_map_fingerprint=document.source_map_fingerprint,
            revision=revision,
            status=ExamSourceBlock.Status.ACCEPTED,
        )
        .select_related('segment', 'continuation_of')
        .prefetch_related(fragments)
        .order_by('order')
    )
    return {
        'documentId': document.id,
        'sourceMapRevision': document.classification_revision,
        'blockRevision': revision,
        'blockCount': len(blocks),
        'blocks': [
            {
                'id': block.id,
                'order': block.order,
                'kind': block.kind,
                'printedNumber': block.printed_number or None,
                'confidence': float(block.confidence),
                'segmentOrder': block.segment.order,
                'segmentRole': block.segment.role,
                'continuationOfOrder': (
                    block.continuation_of.order if block.continuation_of_id else None
                ),
                'fragments': [
                    {
                        'order': fragment.order,
                        'pageNumber': fragment.page.page_number,
                        'displayOrder': fragment.page.display_order,
                        'bbox': [
                            float(fragment.x0),
                            float(fragment.y0),
                            float(fragment.x1),
                            float(fragment.y1),
                        ],
                        'columnIndex': fragment.column_index,
                        'isContinuation': fragment.is_continuation,
                    }
                    for fragment in block.fragments.all()
                ],
            }
            for block in blocks
        ],
    }
