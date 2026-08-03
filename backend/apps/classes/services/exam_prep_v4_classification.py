"""Tolerant page classification and virtual-split persistence for Exam Prep V4.

The LLM adapter is deliberately not part of this module. It accepts an
untrusted structured payload, validates every page independently, fills every
missing source page with ``unknown``, applies teacher overrides, and converts
the result into deterministic contiguous segments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable

from django.db import transaction
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)


_PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
_ALLOWED_ROLES = frozenset(ExamSourceRole.values)


class InvalidClassificationInput(ValueError):
    pass


class StaleClassificationRevision(RuntimeError):
    pass


class ClassificationFingerprintConflict(RuntimeError):
    pass


class PagePredictionPayload(BaseModel):
    """One permissive page record returned by a fast classifier."""

    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)

    page_number: int = Field(ge=1)
    role: str = ExamSourceRole.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    printed_numbers: list[str] = Field(default_factory=list)
    reason: str = ''

    @field_validator('role')
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_ROLES:
            raise ValueError(f'unsupported page role: {value}')
        return normalized

    @field_validator('printed_numbers', mode='before')
    @classmethod
    def coerce_printed_numbers(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (str, int)):
            return [str(value)]
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        raise ValueError('printed_numbers must be a list, string, integer, or null')


@dataclass(frozen=True, slots=True)
class PagePrediction:
    page_number: int
    role: str
    confidence: float
    display_order: int = 0
    printed_numbers: tuple[str, ...] = ()
    reason: str = ''
    source: str = 'classifier'
    predicted_role: str = ExamSourceRole.UNKNOWN
    predicted_confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class ClassificationIssue:
    code: str
    record_index: int | None = None
    page_number: int | None = None
    detail: str = ''

    def as_dict(self) -> dict[str, Any]:
        return {
            'code': self.code,
            'recordIndex': self.record_index,
            'pageNumber': self.page_number,
            'detail': self.detail,
        }


@dataclass(frozen=True, slots=True)
class ClassificationParseResult:
    pages: tuple[PagePrediction, ...]
    issues: tuple[ClassificationIssue, ...]


@dataclass(frozen=True, slots=True)
class SegmentProposal:
    order: int
    start_page: int
    end_page: int
    role: str
    predicted_role: str
    confidence: float
    expected_number_start: int | None
    expected_number_end: int | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PersistedClassification:
    document_id: int
    revision: int
    fingerprint: str
    pages: tuple[PagePrediction, ...]
    segments: tuple[SegmentProposal, ...]
    issues: tuple[ClassificationIssue, ...]
    reused: bool = False


def normalize_printed_number(value: str) -> str:
    return ''.join(str(value).translate(_PERSIAN_DIGITS).split())


def _records_from_payload(raw_output: Any) -> list[Any]:
    if isinstance(raw_output, list):
        return raw_output
    if isinstance(raw_output, dict):
        records = raw_output.get('pages')
        if isinstance(records, list):
            return records
    raise InvalidClassificationInput(
        'Classification output must be a list or an object with a pages list.'
    )


def _normalize_display_orders(
    display_orders: dict[int, int] | None,
    *,
    page_count: int,
) -> dict[int, int]:
    if not display_orders:
        return {number: number for number in range(1, page_count + 1)}
    normalized: dict[int, int] = {}
    for page_number, display_order in display_orders.items():
        try:
            page_number = int(page_number)
            display_order = int(display_order)
        except (TypeError, ValueError) as exc:
            raise InvalidClassificationInput('Invalid virtual page order.') from exc
        normalized[page_number] = display_order
    expected = set(range(1, page_count + 1))
    if set(normalized) != expected or set(normalized.values()) != expected:
        raise InvalidClassificationInput(
            'Virtual page order must be a complete one-based sequence.'
        )
    return normalized


def parse_page_predictions(
    *,
    raw_output: Any,
    page_count: int,
    teacher_roles: dict[int, str] | None = None,
    display_orders: dict[int, int] | None = None,
) -> ClassificationParseResult:
    """Validate page records independently and preserve a total page map."""

    if page_count < 1:
        raise InvalidClassificationInput('A classified PDF must have at least one page.')

    virtual_orders = _normalize_display_orders(
        display_orders,
        page_count=page_count,
    )
    records = _records_from_payload(raw_output)
    by_page: dict[int, PagePredictionPayload] = {}
    issues: list[ClassificationIssue] = []

    for index, raw_record in enumerate(records):
        try:
            parsed = PagePredictionPayload.model_validate(raw_record)
        except ValidationError as exc:
            issues.append(
                ClassificationIssue(
                    code='invalid_page_record',
                    record_index=index,
                    detail=str(exc.errors(include_url=False))[:1000],
                )
            )
            continue

        if parsed.page_number > page_count:
            issues.append(
                ClassificationIssue(
                    code='page_out_of_range',
                    record_index=index,
                    page_number=parsed.page_number,
                )
            )
            continue

        previous = by_page.get(parsed.page_number)
        if previous is not None:
            issues.append(
                ClassificationIssue(
                    code='duplicate_page_prediction',
                    record_index=index,
                    page_number=parsed.page_number,
                    detail='The higher-confidence record was retained.',
                )
            )
            if previous.confidence >= parsed.confidence:
                continue
        by_page[parsed.page_number] = parsed

    normalized_teacher_roles: dict[int, str] = {}
    for page_number, role in (teacher_roles or {}).items():
        normalized = str(role).strip().lower()
        if page_number < 1 or page_number > page_count or normalized not in _ALLOWED_ROLES:
            issues.append(
                ClassificationIssue(
                    code='invalid_teacher_role',
                    page_number=page_number,
                    detail=str(role),
                )
            )
            continue
        normalized_teacher_roles[page_number] = normalized

    pages: list[PagePrediction] = []
    for page_number in range(1, page_count + 1):
        predicted = by_page.get(page_number)
        if predicted is None:
            predicted_role = ExamSourceRole.UNKNOWN
            predicted_confidence = 0.0
            printed_numbers: tuple[str, ...] = ()
            reason = ''
            issues.append(
                ClassificationIssue(
                    code='missing_page_prediction',
                    page_number=page_number,
                )
            )
        else:
            predicted_role = predicted.role
            predicted_confidence = float(predicted.confidence)
            printed_numbers = tuple(
                normalized
                for number in predicted.printed_numbers
                if (normalized := normalize_printed_number(number))
            )
            reason = predicted.reason

        teacher_role = normalized_teacher_roles.get(page_number)
        pages.append(
            PagePrediction(
                page_number=page_number,
                display_order=virtual_orders[page_number],
                role=teacher_role or predicted_role,
                confidence=1.0 if teacher_role else predicted_confidence,
                printed_numbers=printed_numbers,
                reason=reason,
                source='teacher' if teacher_role else (
                    'fallback' if predicted is None else 'classifier'
                ),
                predicted_role=predicted_role,
                predicted_confidence=predicted_confidence,
            )
        )

    return ClassificationParseResult(pages=tuple(pages), issues=tuple(issues))


def _numeric_bounds(pages: Iterable[PagePrediction]) -> tuple[int | None, int | None]:
    values: list[int] = []
    for page in pages:
        for number in page.printed_numbers:
            if number.isdigit():
                values.append(int(number))
    if not values:
        return None, None
    return min(values), max(values)


def _physically_contiguous(page_numbers: list[int]) -> bool:
    return all(
        abs(current - previous) == 1
        for previous, current in zip(page_numbers, page_numbers[1:])
    )


def build_segment_proposals(
    pages: Iterable[PagePrediction],
) -> tuple[SegmentProposal, ...]:
    """Group equal-role pages that are adjacent in virtual display order."""

    source_pages = tuple(pages)
    if not source_pages:
        return ()
    page_count = len(source_pages)
    expected = set(range(1, page_count + 1))
    if {page.page_number for page in source_pages} != expected:
        raise InvalidClassificationInput('Page predictions must form a complete 1-based map.')
    if {page.display_order for page in source_pages} != expected:
        raise InvalidClassificationInput(
            'Virtual page order must form a complete 1-based map.'
        )

    ordered = tuple(
        sorted(
            source_pages,
            key=lambda item: (item.display_order, item.page_number),
        )
    )
    groups: list[list[PagePrediction]] = []
    for page in ordered:
        if not groups or groups[-1][-1].role != page.role:
            groups.append([page])
        else:
            groups[-1].append(page)

    proposals: list[SegmentProposal] = []
    for order, group in enumerate(groups):
        number_start, number_end = _numeric_bounds(group)
        average_confidence = sum(page.confidence for page in group) / len(group)
        predicted_roles = {page.predicted_role for page in group}
        predicted_role = (
            next(iter(predicted_roles))
            if len(predicted_roles) == 1
            else ExamSourceRole.UNKNOWN
        )
        page_numbers = [page.page_number for page in group]
        proposals.append(
            SegmentProposal(
                order=order,
                start_page=group[0].page_number,
                end_page=group[-1].page_number,
                role=group[0].role,
                predicted_role=predicted_role,
                confidence=average_confidence,
                expected_number_start=number_start,
                expected_number_end=number_end,
                metadata={
                    'minimumConfidence': min(page.confidence for page in group),
                    'pageSources': [page.source for page in group],
                    'pageNumbers': page_numbers,
                    'displayOrderStart': group[0].display_order,
                    'displayOrderEnd': group[-1].display_order,
                    'physicalContiguous': _physically_contiguous(page_numbers),
                },
            )
        )
    return tuple(proposals)


def _persisted_result(document: ExamSourceDocument, *, reused: bool) -> PersistedClassification:
    pages = tuple(
        PagePrediction(
            page_number=page.page_number,
            display_order=page.display_order,
            role=page.effective_role,
            confidence=(
                1.0 if page.teacher_role else float(page.predicted_confidence)
            ),
            source='teacher' if page.teacher_role else 'classifier',
            predicted_role=page.predicted_role,
            predicted_confidence=float(page.predicted_confidence),
        )
        for page in document.pages.order_by('display_order', 'page_number')
    )
    proposals = tuple(
        SegmentProposal(
            order=segment.order,
            start_page=segment.start_page,
            end_page=segment.end_page,
            role=segment.role,
            predicted_role=segment.predicted_role,
            confidence=float(segment.predicted_confidence),
            expected_number_start=segment.expected_number_start,
            expected_number_end=segment.expected_number_end,
            metadata=segment.metadata,
        )
        for segment in document.segments.filter(
            revision=document.classification_revision,
        ).order_by('order')
    )
    issues = tuple(
        ClassificationIssue(
            code=str(issue.get('code') or 'unknown'),
            record_index=issue.get('recordIndex'),
            page_number=issue.get('pageNumber'),
            detail=str(issue.get('detail') or ''),
        )
        for issue in (document.classification_metadata or {}).get('issues', [])
        if isinstance(issue, dict)
    )
    return PersistedClassification(
        document_id=document.id,
        revision=document.classification_revision,
        fingerprint=document.classification_fingerprint,
        pages=pages,
        segments=proposals,
        issues=issues,
        reused=reused,
    )


@transaction.atomic
def persist_classification_result(
    *,
    document_id: int,
    expected_revision: int,
    fingerprint: str,
    raw_output: Any,
) -> PersistedClassification:
    """Persist one immutable classification result for the active revision."""

    if not fingerprint or len(fingerprint) != 64:
        raise InvalidClassificationInput('Classification fingerprint must be SHA-256.')

    document = (
        ExamSourceDocument.objects.select_for_update()
        .select_related('project')
        .get(id=document_id)
    )
    if document.classification_revision != expected_revision:
        raise StaleClassificationRevision(
            f'Expected revision {expected_revision}, current revision is '
            f'{document.classification_revision}.'
        )
    if document.page_count < 1:
        raise InvalidClassificationInput('Source page count must be known before classification.')

    if document.classification_fingerprint:
        if document.classification_fingerprint == fingerprint:
            return _persisted_result(document, reused=True)
        raise ClassificationFingerprintConflict(
            'This classification revision already has a different accepted fingerprint.'
        )

    existing_pages = {
        page.page_number: page
        for page in document.pages.select_for_update().order_by('page_number')
    }
    teacher_roles = {
        number: page.teacher_role
        for number, page in existing_pages.items()
        if page.teacher_role
    }
    display_orders = {
        number: page.display_order
        for number, page in existing_pages.items()
    }
    parsed = parse_page_predictions(
        raw_output=raw_output,
        page_count=document.page_count,
        teacher_roles=teacher_roles,
        display_orders=display_orders or None,
    )
    proposals = build_segment_proposals(parsed.pages)

    for prediction in parsed.pages:
        page = existing_pages.get(prediction.page_number)
        if page is None:
            page = ExamSourcePage(
                document=document,
                page_number=prediction.page_number,
                display_order=prediction.display_order,
            )
        page.predicted_role = prediction.predicted_role
        page.predicted_confidence = Decimal(str(prediction.predicted_confidence))
        page.classification_metadata = {
            'reason': prediction.reason,
            'printedNumbers': list(prediction.printed_numbers),
            'source': prediction.source,
        }
        page.save()

    document.segments.filter(revision=expected_revision).delete()
    ExamSourceSegment.objects.bulk_create(
        [
            ExamSourceSegment(
                document=document,
                revision=expected_revision,
                order=proposal.order,
                start_page=proposal.start_page,
                end_page=proposal.end_page,
                role=proposal.role,
                predicted_role=proposal.predicted_role,
                predicted_confidence=Decimal(str(proposal.confidence)),
                teacher_confirmed=False,
                expected_number_start=proposal.expected_number_start,
                expected_number_end=proposal.expected_number_end,
                status=ExamSourceSegment.Status.PROPOSED,
                metadata=proposal.metadata,
            )
            for proposal in proposals
        ]
    )

    issue_payload = [issue.as_dict() for issue in parsed.issues]
    document.classification_fingerprint = fingerprint
    document.classification_metadata = {
        'issues': issue_payload,
        'issueCount': len(issue_payload),
        'segmentCount': len(proposals),
    }
    document.status = ExamSourceDocument.Status.AWAITING_CONFIRMATION
    document.save(
        update_fields=[
            'classification_fingerprint',
            'classification_metadata',
            'status',
            'updated_at',
        ]
    )
    ExamProject.objects.filter(id=document.project_id).update(
        status=ExamProject.Status.AWAITING_SOURCE_CONFIRMATION,
        workflow_state={
            'stage': 'awaiting_source_confirmation',
            'message': 'تقسیم‌بندی پیشنهادی صفحات آماده بررسی است.',
            'progressPercent': 20,
            'warningCount': len(issue_payload),
        },
    )

    document.refresh_from_db()
    return _persisted_result(document, reused=False)
