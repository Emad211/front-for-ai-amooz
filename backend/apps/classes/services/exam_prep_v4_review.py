"""Revision-bound exception review for Exam Prep V4."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.classes.models_v4 import ExamProject
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamMatchDecision,
    ExamQuestionRecord,
)
from apps.classes.models_v4_review import ExamReviewDecision


class ReviewNotReady(RuntimeError):
    pass


class StaleReviewSet(RuntimeError):
    pass


class InvalidReviewDecision(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PersistedReviewDecision:
    review_id: int
    revision: int
    action: str
    question_record_id: int | None
    remaining_count: int
    ready_to_finalize: bool
    reused: bool = False


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    ).hexdigest()


def _owned_project(*, teacher, project_id: int, for_update: bool = False) -> ExamProject:
    queryset = ExamProject.objects
    if for_update:
        queryset = queryset.select_for_update()
    project = queryset.filter(id=project_id, teacher=teacher).first()
    if project is None:
        raise ExamProject.DoesNotExist
    return project


def _current_questions(project: ExamProject) -> tuple[ExamQuestionRecord, ...]:
    return tuple(
        ExamQuestionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).order_by('document__upload_order', 'order', 'id')
    )


def _current_answers(project: ExamProject) -> tuple[ExamAnswerSolutionRecord, ...]:
    return tuple(
        ExamAnswerSolutionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).order_by('document__upload_order', 'order', 'id')
    )


def _current_matches(project: ExamProject) -> tuple[ExamMatchDecision, ...]:
    matches = tuple(
        ExamMatchDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
        .select_related('answer_record', 'question_record')
        .order_by('order', 'id')
    )
    if not matches:
        raise ReviewNotReady('Current match decisions are unavailable.')
    question_sets = {item.question_set_fingerprint for item in matches}
    answer_sets = {item.answer_set_fingerprint for item in matches}
    match_sets = {item.set_fingerprint for item in matches}
    if len(question_sets) != 1 or len(answer_sets) != 1 or len(match_sets) != 1:
        raise ReviewNotReady('Current match decisions do not share one fingerprint set.')
    return matches


def _exception_matches(matches: tuple[ExamMatchDecision, ...]) -> tuple[ExamMatchDecision, ...]:
    return tuple(
        item
        for item in matches
        if item.decision != ExamMatchDecision.Decision.MATCHED
    )


def _accepted_reviews(
    project: ExamProject,
    *,
    question_set_fingerprint: str,
    answer_set_fingerprint: str,
) -> tuple[ExamReviewDecision, ...]:
    return tuple(
        ExamReviewDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
            question_set_fingerprint=question_set_fingerprint,
            answer_set_fingerprint=answer_set_fingerprint,
        )
        .select_related('match_decision', 'answer_record', 'question_record')
        .order_by('answer_record_id', '-revision', '-id')
    )


def _safe_warnings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:500] for item in value[:50] if str(item).strip()]


def _question_payload(record: ExamQuestionRecord) -> dict[str, Any]:
    options = []
    if isinstance(record.options, list):
        for item in record.options[:20]:
            if not isinstance(item, dict):
                continue
            label = str(item.get('label') or '').strip()[:32]
            if not label:
                continue
            options.append(
                {
                    'label': label,
                    'text': str(item.get('text') or '').strip()[:50_000],
                }
            )
    return {
        'id': record.id,
        'printedNumber': record.printed_number or None,
        'sectionKey': record.section_key or None,
        'questionText': record.question_text,
        'options': options,
        'confidence': float(record.confidence),
        'warnings': _safe_warnings(record.warnings),
    }


def _answer_payload(record: ExamAnswerSolutionRecord) -> dict[str, Any]:
    return {
        'id': record.id,
        'printedNumber': record.printed_number or None,
        'sectionKey': record.section_key or None,
        'correctOption': record.correct_option or None,
        'finalAnswer': record.final_answer or None,
        'solutionText': record.solution_text or None,
        'confidence': float(record.confidence),
        'warnings': _safe_warnings(record.warnings),
    }


def _review_payload(review: ExamReviewDecision | None) -> dict[str, Any] | None:
    if review is None:
        return None
    return {
        'id': review.id,
        'revision': review.revision,
        'action': review.action,
        'questionRecordId': review.question_record_id,
        'note': review.note,
        'updatedAt': review.updated_at,
    }


def _review_index(
    reviews: tuple[ExamReviewDecision, ...],
) -> dict[int, ExamReviewDecision]:
    result: dict[int, ExamReviewDecision] = {}
    for review in reviews:
        result.setdefault(review.answer_record_id, review)
    return result


def get_teacher_review_queue(*, teacher, project_id: int) -> dict[str, Any]:
    project = _owned_project(teacher=teacher, project_id=project_id)
    matches = _current_matches(project)
    exceptions = _exception_matches(matches)
    questions = _current_questions(project)
    question_set_fingerprint = matches[0].question_set_fingerprint
    answer_set_fingerprint = matches[0].answer_set_fingerprint
    match_set_fingerprint = matches[0].set_fingerprint
    reviews = _accepted_reviews(
        project,
        question_set_fingerprint=question_set_fingerprint,
        answer_set_fingerprint=answer_set_fingerprint,
    )
    review_by_answer = _review_index(reviews)
    exception_answer_ids = {item.answer_record_id for item in exceptions}
    resolved_count = len(exception_answer_ids & set(review_by_answer))
    remaining_count = max(0, len(exception_answer_ids) - resolved_count)

    return {
        'projectId': project.id,
        'projectStatus': project.status,
        'questionSetFingerprint': question_set_fingerprint,
        'answerSetFingerprint': answer_set_fingerprint,
        'matchSetFingerprint': match_set_fingerprint,
        'totalCount': len(exceptions),
        'resolvedCount': resolved_count,
        'remainingCount': remaining_count,
        'canFinalize': remaining_count == 0,
        'questions': [_question_payload(item) for item in questions],
        'items': [
            {
                'matchDecisionId': item.id,
                'automaticDecision': item.decision,
                'method': item.method,
                'reasonCode': item.reason_code,
                'printedNumber': item.normalized_number or None,
                'sectionKey': item.normalized_section or None,
                'answer': _answer_payload(item.answer_record),
                'review': _review_payload(review_by_answer.get(item.answer_record_id)),
            }
            for item in exceptions
        ],
        'updatedAt': project.updated_at,
    }


def _review_counts(project: ExamProject) -> tuple[int, int, str, str]:
    matches = _current_matches(project)
    exceptions = _exception_matches(matches)
    question_set = matches[0].question_set_fingerprint
    answer_set = matches[0].answer_set_fingerprint
    reviews = _accepted_reviews(
        project,
        question_set_fingerprint=question_set,
        answer_set_fingerprint=answer_set,
    )
    reviewed_answers = {item.answer_record_id for item in reviews}
    exception_answers = {item.answer_record_id for item in exceptions}
    resolved = len(reviewed_answers & exception_answers)
    remaining = max(0, len(exception_answers) - resolved)
    return resolved, remaining, question_set, answer_set


@transaction.atomic
def persist_teacher_review_decision(
    *,
    teacher,
    project_id: int,
    match_decision_id: int,
    action: str,
    question_record_id: int | None = None,
    note: str = '',
) -> PersistedReviewDecision:
    project = _owned_project(
        teacher=teacher,
        project_id=project_id,
        for_update=True,
    )
    matches = _current_matches(project)
    current_by_id = {item.id: item for item in matches}
    source = current_by_id.get(match_decision_id)
    if source is None:
        raise StaleReviewSet('The match decision is no longer current.')
    if source.decision == ExamMatchDecision.Decision.MATCHED:
        raise InvalidReviewDecision('Automatically matched records are not exceptions.')

    selected_action = str(action or '').strip()
    if selected_action not in ExamReviewDecision.Action.values:
        raise InvalidReviewDecision('Unsupported review action.')

    question = None
    if selected_action == ExamReviewDecision.Action.MATCH:
        if not question_record_id:
            raise InvalidReviewDecision('Manual match requires a question record.')
        question = ExamQuestionRecord.objects.filter(
            id=question_record_id,
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).first()
        if question is None:
            raise InvalidReviewDecision('Selected question is unavailable.')
    elif question_record_id is not None:
        raise InvalidReviewDecision('Only manual match may select a question.')

    question_set = matches[0].question_set_fingerprint
    answer_set = matches[0].answer_set_fingerprint
    normalized_note = str(note or '').strip()[:500]
    payload = {
        'projectId': project.id,
        'sourceMatchFingerprint': source.fingerprint,
        'answerFingerprint': source.answer_record.fingerprint,
        'questionFingerprint': question.fingerprint if question else None,
        'action': selected_action,
        'note': normalized_note,
        'questionSetFingerprint': question_set,
        'answerSetFingerprint': answer_set,
    }
    fingerprint = _hash_payload(payload)
    current = tuple(
        ExamReviewDecision.objects.select_for_update().filter(
            answer_record=source.answer_record,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
    )
    if current and all(item.fingerprint == fingerprint for item in current):
        resolved, remaining, _question_set, _answer_set = _review_counts(project)
        selected = max(current, key=lambda item: (item.revision, item.id))
        return PersistedReviewDecision(
            review_id=selected.id,
            revision=selected.revision,
            action=selected.action,
            question_record_id=selected.question_record_id,
            remaining_count=remaining,
            ready_to_finalize=remaining == 0,
            reused=True,
        )

    if current:
        ExamReviewDecision.objects.filter(id__in=[item.id for item in current]).update(
            lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
        )
    revision = (
        ExamReviewDecision.objects.filter(answer_record=source.answer_record).aggregate(
            value=Max('revision')
        )['value']
        or 0
    ) + 1
    review = ExamReviewDecision(
        project=project,
        match_decision=source,
        answer_record=source.answer_record,
        question_record=question,
        created_by=teacher,
        revision=revision,
        action=selected_action,
        note=normalized_note,
        question_set_fingerprint=question_set,
        answer_set_fingerprint=answer_set,
        source_match_fingerprint=source.fingerprint,
        fingerprint=fingerprint,
    )
    review.full_clean()
    review.save()

    resolved, remaining, _question_set, _answer_set = _review_counts(project)
    state = dict(project.workflow_state) if isinstance(project.workflow_state, dict) else {}
    state.update(
        {
            'stage': 'exception_review',
            'progressPercent': 85,
            'reviewTotalCount': resolved + remaining,
            'reviewResolvedCount': resolved,
            'reviewRemainingCount': remaining,
            'lastEventAt': timezone.now().isoformat(),
        }
    )
    project.status = ExamProject.Status.AWAITING_REVIEW
    project.workflow_state = state
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
    return PersistedReviewDecision(
        review_id=review.id,
        revision=review.revision,
        action=review.action,
        question_record_id=review.question_record_id,
        remaining_count=remaining,
        ready_to_finalize=remaining == 0,
        reused=False,
    )


@transaction.atomic
def finalize_teacher_exception_review(
    *,
    teacher,
    project_id: int,
    expected_question_set_fingerprint: str,
    expected_answer_set_fingerprint: str,
) -> dict[str, Any]:
    project = _owned_project(
        teacher=teacher,
        project_id=project_id,
        for_update=True,
    )
    resolved, remaining, question_set, answer_set = _review_counts(project)
    if (
        question_set != expected_question_set_fingerprint
        or answer_set != expected_answer_set_fingerprint
    ):
        raise StaleReviewSet('The extraction record set changed during review.')
    if remaining:
        raise ReviewNotReady('All exception records must be reviewed first.')

    state = dict(project.workflow_state) if isinstance(project.workflow_state, dict) else {}
    state.update(
        {
            'stage': 'review_complete',
            'progressPercent': 90,
            'reviewTotalCount': resolved,
            'reviewResolvedCount': resolved,
            'reviewRemainingCount': 0,
            'reviewCompletedAt': timezone.now().isoformat(),
            'lastEventAt': timezone.now().isoformat(),
        }
    )
    project.status = ExamProject.Status.READY_TO_PUBLISH
    project.workflow_state = state
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
    return {
        'projectId': project.id,
        'status': project.status,
        'resolvedCount': resolved,
        'remainingCount': 0,
        'questionSetFingerprint': question_set,
        'answerSetFingerprint': answer_set,
    }
