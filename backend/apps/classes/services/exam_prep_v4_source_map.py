"""Privacy-safe read models for Exam Prep V4 source maps.

Private filenames, object keys, hashes, native text, raw model payloads, model
reasons, and error details are intentionally absent.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from django.db.models import Count, Q, QuerySet

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceSegment,
)
from apps.classes.services.exam_prep_v4_source_map_contract import (
    source_map_fingerprint,
    structural_page_map_from_models,
)


_SAFE_ISSUE_CODE = re.compile(r'^[a-z0-9_]{1,64}$')


def teacher_project_list_queryset(teacher) -> QuerySet[ExamProject]:
    return (
        ExamProject.objects.filter(teacher=teacher)
        .annotate(document_count=Count('source_documents'))
        .only(
            'id',
            'title',
            'description',
            'engine_version',
            'revision',
            'status',
            'workflow_state',
            'error_code',
            'is_published',
            'published_at',
            'created_at',
            'updated_at',
        )
        .order_by('-updated_at', '-id')
    )


def _safe_nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _safe_progress(raw: Any) -> dict[str, Any]:
    state = raw if isinstance(raw, dict) else {}
    stage = str(state.get('stage') or '').strip().lower()[:64]
    return {
        'stage': stage,
        'progressPercent': min(
            100,
            _safe_nonnegative_int(state.get('progressPercent')),
        ),
        'warningCount': _safe_nonnegative_int(state.get('warningCount')),
    }


def serialize_project_summary(project: ExamProject) -> dict[str, Any]:
    return {
        'id': project.id,
        'title': project.title,
        'description': project.description,
        'engineVersion': project.engine_version,
        'revision': project.revision,
        'status': project.status,
        'progress': _safe_progress(project.workflow_state),
        'errorCode': project.error_code or None,
        'documentCount': int(getattr(project, 'document_count', 0)),
        'isPublished': project.is_published,
        'publishedAt': project.published_at,
        'createdAt': project.created_at,
        'updatedAt': project.updated_at,
    }


def _safe_issue(issue: Any, *, page_count: int) -> dict[str, Any] | None:
    if not isinstance(issue, dict):
        return None
    code = str(issue.get('code') or '').strip().lower()
    if not _SAFE_ISSUE_CODE.fullmatch(code):
        code = 'unknown'

    page_number = issue.get('pageNumber')
    try:
        page_number = int(page_number) if page_number is not None else None
    except (TypeError, ValueError):
        page_number = None
    if page_number is not None and not (1 <= page_number <= page_count):
        page_number = None

    return {
        'code': code,
        'pageNumber': page_number,
    }


def _safe_document_issues(document: ExamSourceDocument) -> list[dict[str, Any]]:
    metadata = (
        document.classification_metadata
        if isinstance(document.classification_metadata, dict)
        else {}
    )
    raw_issues = metadata.get('issues')
    if not isinstance(raw_issues, list):
        return []
    issues: list[dict[str, Any]] = []
    for issue in raw_issues[:500]:
        safe = _safe_issue(issue, page_count=document.page_count)
        if safe is not None:
            issues.append(safe)
    return issues


def _serialize_page(page: ExamSourcePage) -> dict[str, Any]:
    return {
        'pageNumber': page.page_number,
        'displayOrder': page.display_order,
        'predictedRole': page.predicted_role,
        'predictedConfidence': float(page.predicted_confidence),
        'teacherRole': page.teacher_role or None,
        'effectiveRole': page.effective_role,
        'orientation': page.orientation,
        'width': page.width,
        'height': page.height,
        'hasThumbnail': bool(page.thumbnail_file),
        'isDuplicate': page.duplicate_of_id is not None,
    }


def _safe_segment_page_numbers(
    segment: ExamSourceSegment,
    *,
    page_count: int,
) -> list[int]:
    metadata = segment.metadata if isinstance(segment.metadata, dict) else {}
    raw = metadata.get('pageNumbers')
    if not isinstance(raw, list):
        return [segment.start_page] if segment.start_page == segment.end_page else [
            segment.start_page,
            segment.end_page,
        ]
    result: list[int] = []
    for value in raw:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= page_count and number not in result:
            result.append(number)
    return result


def _safe_segment_display_bound(
    segment: ExamSourceSegment,
    key: str,
    *,
    page_count: int,
) -> int | None:
    metadata = segment.metadata if isinstance(segment.metadata, dict) else {}
    try:
        value = int(metadata.get(key))
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= page_count else None


def _serialize_segment(
    segment: ExamSourceSegment,
    *,
    page_count: int,
) -> dict[str, Any]:
    return {
        'id': segment.id,
        'revision': segment.revision,
        'order': segment.order,
        'startPage': segment.start_page,
        'endPage': segment.end_page,
        'displayOrderStart': _safe_segment_display_bound(
            segment,
            'displayOrderStart',
            page_count=page_count,
        ),
        'displayOrderEnd': _safe_segment_display_bound(
            segment,
            'displayOrderEnd',
            page_count=page_count,
        ),
        'pageNumbers': _safe_segment_page_numbers(
            segment,
            page_count=page_count,
        ),
        'role': segment.role,
        'predictedRole': segment.predicted_role,
        'predictedConfidence': float(segment.predicted_confidence),
        'teacherConfirmed': segment.teacher_confirmed,
        'expectedNumberStart': segment.expected_number_start,
        'expectedNumberEnd': segment.expected_number_end,
        'status': segment.status,
    }


def _safe_source_map_fingerprint(
    *,
    document: ExamSourceDocument,
    pages: list[ExamSourcePage],
) -> str | None:
    if document.source_map_fingerprint:
        return document.source_map_fingerprint
    if document.page_count < 1 or len(pages) != document.page_count:
        return None
    expected = list(range(1, document.page_count + 1))
    if sorted(page.page_number for page in pages) != expected:
        return None
    if sorted(page.display_order for page in pages) != expected:
        return None
    return source_map_fingerprint(
        structural_page_map_from_models(pages),
        page_count=document.page_count,
    )


def get_teacher_project_source_map(*, teacher, project_id: int) -> dict[str, Any]:
    """Fetch one owner-scoped project with its current safe source map."""

    project = (
        ExamProject.objects.filter(teacher=teacher, id=project_id)
        .only(
            'id',
            'title',
            'description',
            'engine_version',
            'revision',
            'status',
            'workflow_state',
            'error_code',
            'is_published',
            'published_at',
            'created_at',
            'updated_at',
        )
        .first()
    )
    if project is None:
        raise ExamProject.DoesNotExist

    documents = list(
        ExamSourceDocument.objects.filter(project=project)
        .only(
            'id',
            'project_id',
            'upload_order',
            'page_count',
            'status',
            'classification_revision',
            'classification_fingerprint',
            'source_map_fingerprint',
            'classification_metadata',
            'teacher_confirmed_at',
            'teacher_confirmed_revision',
            'teacher_confirmed_fingerprint',
            'error_code',
            'created_at',
            'updated_at',
        )
        .order_by('upload_order', 'id')
    )
    document_ids = [document.id for document in documents]

    pages_by_document: dict[int, list[ExamSourcePage]] = defaultdict(list)
    if document_ids:
        pages = ExamSourcePage.objects.filter(document_id__in=document_ids).only(
            'id',
            'document_id',
            'page_number',
            'display_order',
            'thumbnail_file',
            'width',
            'height',
            'predicted_role',
            'predicted_confidence',
            'teacher_role',
            'orientation',
            'duplicate_of_id',
        ).order_by('document_id', 'display_order', 'page_number')
        for page in pages:
            pages_by_document[page.document_id].append(page)

    current_segment_filter = Q(pk__in=[])
    for document in documents:
        current_segment_filter |= Q(
            document_id=document.id,
            revision=document.classification_revision,
        )

    segments_by_document: dict[int, list[ExamSourceSegment]] = defaultdict(list)
    if documents:
        segments = (
            ExamSourceSegment.objects.filter(current_segment_filter)
            .only(
                'id',
                'document_id',
                'revision',
                'order',
                'start_page',
                'end_page',
                'role',
                'predicted_role',
                'predicted_confidence',
                'teacher_confirmed',
                'expected_number_start',
                'expected_number_end',
                'status',
                'metadata',
            )
            .order_by('document_id', 'order', 'id')
        )
        for segment in segments:
            segments_by_document[segment.document_id].append(segment)

    project.document_count = len(documents)
    payload = serialize_project_summary(project)
    payload['documents'] = []

    for document in documents:
        issues = _safe_document_issues(document)
        document_pages = pages_by_document.get(document.id, [])
        fingerprint = _safe_source_map_fingerprint(
            document=document,
            pages=document_pages,
        )
        is_confirmed = bool(
            fingerprint
            and document.status == ExamSourceDocument.Status.CONFIRMED
            and document.teacher_confirmed_revision
            == document.classification_revision
            and document.teacher_confirmed_fingerprint == fingerprint
        )
        payload['documents'].append(
            {
                'id': document.id,
                'uploadOrder': document.upload_order,
                'status': document.status,
                'pageCount': document.page_count,
                'classificationRevision': document.classification_revision,
                'hasClassification': bool(document.classification_fingerprint),
                'hasSourceMap': fingerprint is not None,
                'sourceMapFingerprint': fingerprint,
                'isTeacherConfirmed': is_confirmed,
                'teacherConfirmedRevision': (
                    document.teacher_confirmed_revision if is_confirmed else None
                ),
                'issueCount': len(issues),
                'issues': issues,
                'teacherConfirmedAt': (
                    document.teacher_confirmed_at if is_confirmed else None
                ),
                'errorCode': document.error_code or None,
                'createdAt': document.created_at,
                'updatedAt': document.updated_at,
                'pages': [_serialize_page(page) for page in document_pages],
                'segments': [
                    _serialize_segment(
                        segment,
                        page_count=document.page_count,
                    )
                    for segment in segments_by_document.get(document.id, [])
                ],
            }
        )

    return payload
