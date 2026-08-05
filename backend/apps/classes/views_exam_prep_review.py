"""Teacher detail view for reviewable page-first exam-prep drafts.

The public URL remains unchanged. This narrow override preserves the legacy
view's DELETE behavior, permits PATCH for a completed page-first draft, and
keeps legacy drafts self-healing when review rules become more accurate.
"""
from __future__ import annotations

import json
from typing import Any

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from .models import ClassCreationSession, ExamPrepExtractionArtifact
from .serializers import (
    ExamPrepSessionDetailSerializer,
    ExamPrepSessionUpdateSerializer,
)
from .services.exam_prep_inventory import rebuild_audit_after_teacher_review
from .services.exam_prep_page_review import (
    audit_page_first_projection,
    parse_projection,
    render_projection_transcript,
    retain_failed_page_evidence,
)
from .services.exam_prep_utils import normalize_exam_prep_json
from .views import (
    ExamPrepSessionDetailView,
    _teacher_exam_prep_sessions,
)


def _workflow(session: ClassCreationSession) -> dict[str, Any]:
    value = session.workflow_state
    return dict(value) if isinstance(value, dict) else {}


def _is_reviewable_page_first_session(session: ClassCreationSession) -> bool:
    """Use durable workflow completion, not stale task metadata, as the gate."""

    workflow = _workflow(session)
    return bool(
        session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
        and workflow.get('engine') == 'page_first'
        and workflow.get('readyForReview') is True
        and not session.is_published
    )


def _normalise_page_numbers(values: object) -> list[int]:
    pages: list[int] = []
    if not isinstance(values, (list, tuple, set)):
        return pages
    for value in values:
        try:
            page = int(value)
        except (TypeError, ValueError):
            continue
        if page > 0 and page not in pages:
            pages.append(page)
    return sorted(pages)


def _failed_pages_that_still_contain_content(
    session: ClassCreationSession,
    failed_page_numbers: object,
) -> list[int]:
    """Drop stale cover/blank failures using the zero-cost local classifier.

    Older drafts may have recorded a cover as ``failed_chunk`` before the local
    non-content router existed. Keep every page fail-closed when source reading
    or classification fails; only a confident non-content result is removed.
    """

    pages = _normalise_page_numbers(failed_page_numbers)
    if not pages or not session.source_file:
        return pages

    try:
        from .services.exam_prep_page_layout import classify_exam_page
        from .services.exam_prep_pipeline import render_exam_prep_pdf

        session.source_file.open('rb')
        try:
            data = session.source_file.read()
        finally:
            session.source_file.close()
        source = render_exam_prep_pdf(data)
        rendered = source.render_selected_pages(set(pages))
    except Exception:
        return pages

    remaining: list[int] = []
    for page_number in pages:
        page = rendered.get(page_number)
        if page is None:
            remaining.append(page_number)
            continue
        try:
            decision = classify_exam_page(
                image=page.image,
                native_text=page.native_text,
                right_native_text=page.right_column_native_text,
                left_native_text=page.left_column_native_text,
            )
        except Exception:
            remaining.append(page_number)
            continue
        if not decision.skipped_non_content:
            remaining.append(page_number)
    return remaining


def _downgrade_intentional_number_gaps(audit: dict[str, Any]) -> dict[str, Any]:
    """A teacher-curated exam may intentionally omit source question numbers.

    Extraction-time gaps remain strict in the original pipeline audit. After a
    teacher edits or deletes questions, the current question list is canonical;
    gaps stay visible as warnings but must not block publication.
    """

    updated = dict(audit)
    issues = [
        dict(item)
        for item in (audit.get('issues') or [])
        if isinstance(item, dict)
    ]
    for issue in issues:
        if issue.get('code') == 'missing_question_number':
            issue['severity'] = 'warning'
    critical_count = sum(item.get('severity') == 'critical' for item in issues)
    critical_question_keys = {
        (
            str(item.get('scopeKey') or 'default'),
            int(item.get('questionNumber') or 0),
        )
        for item in issues
        if item.get('severity') == 'critical'
        and int(item.get('questionNumber') or 0) > 0
    }
    question_count = int(updated.get('questionCount') or 0)
    updated.update(
        {
            'issues': issues,
            'criticalIssueCount': critical_count,
            'questionsNeedingReview': len(critical_question_keys),
            'usableQuestionCount': max(0, question_count - len(critical_question_keys)),
            'status': (
                'passed'
                if question_count > 0 and critical_count == 0
                else 'needs_review'
            ),
        }
    )
    return updated


def _refresh_page_first_review_state(
    session: ClassCreationSession,
) -> ClassCreationSession:
    """Recompute a completed page-first draft and persist only real blockers."""

    if not _is_reviewable_page_first_session(session):
        return session

    workflow = _workflow(session)
    projection = parse_projection(session.exam_prep_json)
    audit = _downgrade_intentional_number_gaps(
        audit_page_first_projection(projection)
    )
    remaining_failed_pages = _failed_pages_that_still_contain_content(
        session,
        workflow.get('failedPageNumbers') or [],
    )
    audit = retain_failed_page_evidence(audit, remaining_failed_pages)
    passed = audit.get('status') == 'passed'

    warnings: list[str] = []
    critical_count = int(audit.get('criticalIssueCount') or 0)
    if critical_count:
        warnings.append(
            f'{critical_count} مورد بحرانی در محتوای ویرایش‌شده باقی مانده است.'
        )
    gap_count = sum(
        len(values)
        for values in (audit.get('questionNumberGaps') or {}).values()
        if isinstance(values, list)
    )
    if gap_count:
        warnings.append(
            f'{gap_count} شماره سؤال عمداً یا در اثر ویرایش از توالی حذف شده است.'
        )
    if remaining_failed_pages:
        pages = '، '.join(map(str, remaining_failed_pages))
        warnings.append(
            f'صفحه‌های {pages} هنوز محتوای پردازش‌نشده دارند.'
        )

    new_workflow = {
        **workflow,
        'stage': 'ready_for_review',
        'message': (
            'محتوای ویرایش‌شده کنترل شد و آماده انتشار است.'
            if passed
            else 'محتوای ویرایش‌شده هنوز خطای بحرانی دارد و قابل انتشار نیست.'
        ),
        'progressPercent': 100,
        'warnings': warnings,
        'readyForReview': True,
        'failedPageNumbers': remaining_failed_pages,
        'extractionAudit': audit,
        'publicationBlocked': not passed,
    }
    new_status = (
        ClassCreationSession.Status.EXAM_STRUCTURED
        if passed
        else ClassCreationSession.Status.EXAM_TRANSCRIBED
    )
    new_transcript = render_projection_transcript(projection, audit)
    now = timezone.now()

    changed = (
        session.status != new_status
        or session.workflow_state != new_workflow
        or session.transcript_markdown != new_transcript
    )
    session.status = new_status
    session.workflow_state = new_workflow
    session.transcript_markdown = new_transcript
    session.updated_at = now
    if changed:
        ClassCreationSession.objects.filter(pk=session.pk).update(
            status=new_status,
            workflow_state=new_workflow,
            transcript_markdown=new_transcript,
            updated_at=now,
        )
    return session


class PageFirstExamPrepSessionDetailSerializer(ExamPrepSessionDetailSerializer):
    """Expose the durable page-first audit when no legacy artifact exists."""

    def get_extractionAudit(self, obj):
        artifact = self._artifact(obj)
        if artifact is not None:
            return artifact.audit
        audit = _workflow(obj).get('extractionAudit')
        return dict(audit) if isinstance(audit, dict) else None


class PageFirstExamPrepSessionDetailView(ExamPrepSessionDetailView):
    """Keep the existing endpoint while permitting completed blocked drafts."""

    serializer_class = PageFirstExamPrepSessionDetailSerializer

    def get(self, request, session_id: int):
        session = _teacher_exam_prep_sessions(request.user).filter(id=session_id).first()
        if session is None:
            return Response(
                {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        session = _refresh_page_first_review_state(session)
        return Response(PageFirstExamPrepSessionDetailSerializer(session).data)

    @extend_schema(
        tags=['Exam Prep'],
        summary='Update Exam Prep Session',
        request=ExamPrepSessionUpdateSerializer,
        responses={200: PageFirstExamPrepSessionDetailSerializer},
    )
    def patch(self, request, session_id: int):
        session = _teacher_exam_prep_sessions(request.user).filter(id=session_id).first()
        if session is None:
            return Response(
                {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ExamPrepSessionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        normalized_json = None
        if 'exam_prep_json' in data:
            normalized_json, _changed = normalize_exam_prep_json(data['exam_prep_json'])

        updated_fields = [
            field_name
            for field_name in ('title', 'description', 'level', 'duration', 'exam_prep_json')
            if field_name in data
        ]
        if not updated_fields:
            session = _refresh_page_first_review_state(session)
            return Response(PageFirstExamPrepSessionDetailSerializer(session).data)

        with transaction.atomic():
            session = ClassCreationSession.objects.select_for_update().get(
                id=session.id,
                teacher=request.user,
            )
            if 'exam_prep_json' in data and (
                session.is_published
                or (
                    session.is_active_pipeline
                    and not _is_reviewable_page_first_session(session)
                )
            ):
                return Response(
                    {
                        'detail': (
                            'ویرایش محتوای آزمون هنگام پردازش یا پس از انتشار '
                            'امکان‌پذیر نیست.'
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            for field_name in ('title', 'description', 'level', 'duration'):
                if field_name in data:
                    setattr(session, field_name, data[field_name])
            if 'exam_prep_json' in data:
                session.exam_prep_json = normalized_json or ''
            session.save(update_fields=[*updated_fields, 'updated_at'])

            # Preserve the existing V2/V3 review behavior. Page-first sessions
            # have no artifact and are revalidated by the dedicated post-save
            # signal, then normalized once more below with teacher-curation rules.
            artifact = ExamPrepExtractionArtifact.objects.select_for_update().filter(
                session=session
            ).first()
            if 'exam_prep_json' in data and artifact and artifact.pipeline_version >= 2:
                parsed_projection = json.loads(session.exam_prep_json or '{}')
                projection = parsed_projection if isinstance(parsed_projection, dict) else {}
                artifact.audit = rebuild_audit_after_teacher_review(
                    projection=projection,
                    previous_audit=artifact.audit or {},
                    available_visual_ids={
                        visual.id for visual in artifact.visual_assets.all()
                    },
                )
                if artifact.pipeline_version >= 3:
                    from .services.exam_prep_v3 import clone_units_to_revision

                    previous_revision = artifact.revision
                    artifact.revision += 1
                    clone_units_to_revision(
                        artifact=artifact,
                        source_revision=previous_revision,
                        target_revision=artifact.revision,
                    )
                    artifact.teacher_reviewed_at = None
                    artifact.teacher_reviewed_by = None
                    artifact.reviewed_revision = None
                    artifact.reviewed_projection_fingerprint = ''
                    artifact.save(
                        update_fields=[
                            'audit',
                            'revision',
                            'teacher_reviewed_at',
                            'teacher_reviewed_by',
                            'reviewed_revision',
                            'reviewed_projection_fingerprint',
                            'updated_at',
                        ]
                    )
                else:
                    artifact.audit['teacherReviewedAt'] = timezone.now().isoformat()
                    artifact.save(update_fields=['audit', 'updated_at'])

        session = _teacher_exam_prep_sessions(request.user).get(id=session_id)
        session = _refresh_page_first_review_state(session)
        return Response(PageFirstExamPrepSessionDetailSerializer(session).data)
