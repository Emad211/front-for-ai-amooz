"""Revision-safe teacher source-map mutation and confirmation for Exam Prep V4."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping

from django.db import transaction
from django.utils import timezone

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)
from apps.classes.services.exam_prep_v4_classification import (
    PagePrediction,
    build_segment_proposals,
)
from apps.classes.services.exam_prep_v4_source_map_contract import (
    InvalidSourceMapContract,
    normalize_source_map_pages,
    source_map_fingerprint,
    structural_page_map_from_models,
)


class SourceMapMutationError(ValueError):
    pass


class StaleSourceMapRevision(RuntimeError):
    pass


class SourceMapFingerprintConflict(RuntimeError):
    pass


class SourceMapNotReady(RuntimeError):
    pass


class SourceMapNotConfirmable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SourceMapMutationResult:
    document_id: int
    revision: int
    fingerprint: str
    status: str
    reused: bool
    confirmed: bool


def _owned_document_for_update(
    *,
    teacher,
    project_id: int,
    document_id: int,
) -> tuple[ExamProject, ExamSourceDocument]:
    project = (
        ExamProject.objects.select_for_update()
        .filter(id=project_id, teacher=teacher)
        .first()
    )
    if project is None:
        raise ExamProject.DoesNotExist

    document = (
        ExamSourceDocument.objects.select_for_update()
        .filter(id=document_id, project=project)
        .first()
    )
    if document is None:
        raise ExamSourceDocument.DoesNotExist
    return project, document


def _locked_complete_pages(document: ExamSourceDocument) -> list[ExamSourcePage]:
    pages = list(document.pages.select_for_update().order_by('page_number'))
    if document.page_count < 1:
        raise SourceMapNotReady('Source page count is unavailable.')
    if len(pages) != document.page_count:
        raise SourceMapNotReady('Source page map is incomplete.')
    if [page.page_number for page in pages] != list(
        range(1, document.page_count + 1)
    ):
        raise SourceMapNotReady('Source page map is not a complete one-based sequence.')
    return pages


def _printed_numbers(page: ExamSourcePage) -> tuple[str, ...]:
    metadata = page.classification_metadata
    if not isinstance(metadata, dict):
        return ()
    raw = metadata.get('printedNumbers')
    if not isinstance(raw, list):
        return ()
    return tuple(str(value) for value in raw if value is not None)


def _predictions_for_effective_map(
    *,
    pages: list[ExamSourcePage],
    normalized_map: tuple[dict[str, Any], ...],
) -> tuple[PagePrediction, ...]:
    desired_by_number = {item['pageNumber']: item for item in normalized_map}
    predictions: list[PagePrediction] = []
    for page in pages:
        desired = desired_by_number[page.page_number]
        is_teacher_override = desired['role'] != page.predicted_role
        predictions.append(
            PagePrediction(
                page_number=page.page_number,
                role=desired['role'],
                confidence=(
                    1.0 if is_teacher_override else float(page.predicted_confidence)
                ),
                printed_numbers=_printed_numbers(page),
                reason='',
                source='teacher' if is_teacher_override else 'classifier',
                predicted_role=page.predicted_role,
                predicted_confidence=float(page.predicted_confidence),
            )
        )
    return tuple(predictions)


def _history_entry(
    *,
    document: ExamSourceDocument,
    page_map: tuple[dict[str, Any], ...],
    fingerprint: str,
) -> dict[str, Any]:
    return {
        'revision': document.classification_revision,
        'fingerprint': fingerprint,
        'pages': list(page_map),
        'supersededAt': timezone.now().isoformat(),
    }


def _classification_metadata_after_edit(
    *,
    document: ExamSourceDocument,
    history_entry: dict[str, Any],
    segment_count: int,
) -> dict[str, Any]:
    metadata = (
        dict(document.classification_metadata)
        if isinstance(document.classification_metadata, dict)
        else {}
    )
    history = metadata.get('sourceMapHistory')
    if not isinstance(history, list):
        history = []
    history = [item for item in history if isinstance(item, dict)][-19:]
    history.append(history_entry)
    metadata.update(
        {
            'issues': [],
            'issueCount': 0,
            'segmentCount': segment_count,
            'sourceMapOrigin': 'teacher',
            'sourceMapHistory': history,
        }
    )
    return metadata


def _current_fingerprint(
    *,
    document: ExamSourceDocument,
    page_map: tuple[dict[str, Any], ...],
) -> str:
    fingerprint = document.source_map_fingerprint
    if fingerprint:
        return fingerprint
    fingerprint = source_map_fingerprint(
        page_map,
        page_count=document.page_count,
    )
    document.source_map_fingerprint = fingerprint
    document.save(update_fields=['source_map_fingerprint', 'updated_at'])
    return fingerprint


def _result(
    document: ExamSourceDocument,
    *,
    reused: bool,
) -> SourceMapMutationResult:
    return SourceMapMutationResult(
        document_id=document.id,
        revision=document.classification_revision,
        fingerprint=document.source_map_fingerprint,
        status=document.status,
        reused=reused,
        confirmed=(
            document.teacher_confirmed_revision == document.classification_revision
            and document.teacher_confirmed_fingerprint
            == document.source_map_fingerprint
            and document.status == ExamSourceDocument.Status.CONFIRMED
        ),
    )


@transaction.atomic
def mutate_teacher_source_map(
    *,
    teacher,
    project_id: int,
    document_id: int,
    expected_revision: int,
    pages: Iterable[Mapping[str, Any]],
) -> SourceMapMutationResult:
    """Replace the complete effective source map and create one new revision."""

    project, document = _owned_document_for_update(
        teacher=teacher,
        project_id=project_id,
        document_id=document_id,
    )
    if document.status not in {
        ExamSourceDocument.Status.AWAITING_CONFIRMATION,
        ExamSourceDocument.Status.CONFIRMED,
    }:
        raise SourceMapNotReady('Source map is not ready for teacher editing.')

    model_pages = _locked_complete_pages(document)
    previous_page_map = structural_page_map_from_models(model_pages)
    try:
        normalized = normalize_source_map_pages(
            pages,
            page_count=document.page_count,
        )
    except InvalidSourceMapContract as exc:
        raise SourceMapMutationError(str(exc)) from exc

    desired_fingerprint = source_map_fingerprint(
        normalized,
        page_count=document.page_count,
    )
    current_fingerprint = _current_fingerprint(
        document=document,
        page_map=previous_page_map,
    )

    if desired_fingerprint == current_fingerprint and expected_revision in {
        document.classification_revision,
        document.classification_revision - 1,
    }:
        return _result(document, reused=True)

    if expected_revision != document.classification_revision:
        raise StaleSourceMapRevision(
            'Source map changed after the client loaded it.'
        )

    predictions = _predictions_for_effective_map(
        pages=model_pages,
        normalized_map=normalized,
    )
    proposals = build_segment_proposals(predictions)
    new_revision = document.classification_revision + 1
    history = _history_entry(
        document=document,
        page_map=previous_page_map,
        fingerprint=current_fingerprint,
    )

    old_segments = list(
        document.segments.select_for_update().filter(
            revision=document.classification_revision,
        )
    )
    for segment in old_segments:
        metadata = dict(segment.metadata) if isinstance(segment.metadata, dict) else {}
        metadata['supersededByRevision'] = new_revision
        segment.metadata = metadata
        segment.status = ExamSourceSegment.Status.SUPERSEDED
        segment.teacher_confirmed = False
        segment.save(
            update_fields=[
                'metadata',
                'status',
                'teacher_confirmed',
                'updated_at',
            ]
        )

    desired_by_number = {item['pageNumber']: item for item in normalized}
    for page in model_pages:
        desired = desired_by_number[page.page_number]
        page.teacher_role = (
            '' if desired['role'] == page.predicted_role else desired['role']
        )
        page.orientation = desired['orientation']
        page.save(update_fields=['teacher_role', 'orientation', 'updated_at'])

    ExamSourceSegment.objects.bulk_create(
        [
            ExamSourceSegment(
                document=document,
                revision=new_revision,
                order=proposal.order,
                start_page=proposal.start_page,
                end_page=proposal.end_page,
                role=proposal.role,
                predicted_role=proposal.predicted_role,
                predicted_confidence=Decimal(str(proposal.confidence)),
                teacher_confirmed=False,
                expected_number_start=proposal.expected_number_start,
                expected_number_end=proposal.expected_number_end,
                fingerprint=desired_fingerprint,
                status=ExamSourceSegment.Status.PROPOSED,
                metadata={
                    **proposal.metadata,
                    'sourceMapOrigin': 'teacher',
                },
            )
            for proposal in proposals
        ]
    )

    document.classification_revision = new_revision
    document.classification_fingerprint = ''
    document.source_map_fingerprint = desired_fingerprint
    document.classification_metadata = _classification_metadata_after_edit(
        document=document,
        history_entry=history,
        segment_count=len(proposals),
    )
    document.teacher_confirmed_at = None
    document.teacher_confirmed_by = None
    document.teacher_confirmed_revision = None
    document.teacher_confirmed_fingerprint = ''
    document.status = ExamSourceDocument.Status.AWAITING_CONFIRMATION
    document.error_code = ''
    document.error_detail = ''
    document.save(
        update_fields=[
            'classification_revision',
            'classification_fingerprint',
            'source_map_fingerprint',
            'classification_metadata',
            'teacher_confirmed_at',
            'teacher_confirmed_by',
            'teacher_confirmed_revision',
            'teacher_confirmed_fingerprint',
            'status',
            'error_code',
            'error_detail',
            'updated_at',
        ]
    )

    project.revision += 1
    project.status = ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    project.reviewed_revision = None
    project.reviewed_projection_fingerprint = ''
    project.error_code = ''
    project.error_detail = ''
    project.workflow_state = {
        'stage': 'awaiting_source_confirmation',
        'message': 'نقشهٔ صفحات ویرایش شد و آمادهٔ تأیید است.',
        'progressPercent': 25,
        'warningCount': 0,
    }
    project.save(
        update_fields=[
            'revision',
            'status',
            'reviewed_revision',
            'reviewed_projection_fingerprint',
            'error_code',
            'error_detail',
            'workflow_state',
            'updated_at',
        ]
    )

    document.refresh_from_db()
    return _result(document, reused=False)


def _validate_confirmable_segments(
    *,
    document: ExamSourceDocument,
    pages: list[ExamSourcePage],
) -> list[ExamSourceSegment]:
    if any(page.effective_role == ExamSourceRole.UNKNOWN for page in pages):
        raise SourceMapNotConfirmable(
            'Every page must have a resolved role before confirmation.'
        )

    segments = list(
        document.segments.select_for_update()
        .filter(revision=document.classification_revision)
        .order_by('order', 'id')
    )
    if not segments:
        raise SourceMapNotConfirmable('Current source-map segments are unavailable.')
    expected_start = 1
    for order, segment in enumerate(segments):
        if segment.order != order or segment.start_page != expected_start:
            raise SourceMapNotConfirmable('Current source-map segments are not contiguous.')
        if segment.role == ExamSourceRole.UNKNOWN:
            raise SourceMapNotConfirmable('Unknown source-map segments cannot be confirmed.')
        expected_start = segment.end_page + 1
    if expected_start - 1 != document.page_count:
        raise SourceMapNotConfirmable('Current source-map segments do not cover the document.')
    return segments


@transaction.atomic
def confirm_teacher_source_map(
    *,
    teacher,
    project_id: int,
    document_id: int,
    expected_revision: int,
    expected_fingerprint: str,
) -> SourceMapMutationResult:
    """Confirm exactly the currently visible source-map revision and fingerprint."""

    project, document = _owned_document_for_update(
        teacher=teacher,
        project_id=project_id,
        document_id=document_id,
    )
    if document.status not in {
        ExamSourceDocument.Status.AWAITING_CONFIRMATION,
        ExamSourceDocument.Status.CONFIRMED,
    }:
        raise SourceMapNotReady('Source map is not ready for confirmation.')

    pages = _locked_complete_pages(document)
    current_page_map = structural_page_map_from_models(pages)
    current_fingerprint = _current_fingerprint(
        document=document,
        page_map=current_page_map,
    )

    if expected_revision != document.classification_revision:
        raise StaleSourceMapRevision(
            'Source map changed after the client loaded it.'
        )
    if expected_fingerprint != current_fingerprint:
        raise SourceMapFingerprintConflict(
            'Source-map fingerprint does not match the current revision.'
        )

    if (
        document.status == ExamSourceDocument.Status.CONFIRMED
        and document.teacher_confirmed_revision == document.classification_revision
        and document.teacher_confirmed_fingerprint == current_fingerprint
    ):
        return _result(document, reused=True)

    segments = _validate_confirmable_segments(
        document=document,
        pages=pages,
    )
    confirmed_at = timezone.now()
    for segment in segments:
        segment.status = ExamSourceSegment.Status.CONFIRMED
        segment.teacher_confirmed = True
        if not segment.fingerprint:
            segment.fingerprint = current_fingerprint
        segment.save(
            update_fields=[
                'status',
                'teacher_confirmed',
                'fingerprint',
                'updated_at',
            ]
        )

    document.teacher_confirmed_at = confirmed_at
    document.teacher_confirmed_by = teacher
    document.teacher_confirmed_revision = document.classification_revision
    document.teacher_confirmed_fingerprint = current_fingerprint
    document.status = ExamSourceDocument.Status.CONFIRMED
    document.error_code = ''
    document.error_detail = ''
    document.save(
        update_fields=[
            'teacher_confirmed_at',
            'teacher_confirmed_by',
            'teacher_confirmed_revision',
            'teacher_confirmed_fingerprint',
            'status',
            'error_code',
            'error_detail',
            'updated_at',
        ]
    )

    project.status = ExamProject.Status.SEGMENTING
    project.error_code = ''
    project.error_detail = ''
    project.workflow_state = {
        'stage': 'source_map_confirmed',
        'message': 'نقشهٔ صفحات تأیید شد.',
        'progressPercent': 30,
        'warningCount': 0,
    }
    project.save(
        update_fields=[
            'status',
            'error_code',
            'error_detail',
            'workflow_state',
            'updated_at',
        ]
    )

    document.refresh_from_db()
    return _result(document, reused=False)
