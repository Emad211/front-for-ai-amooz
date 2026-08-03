"""Transaction-safe invalidation of evidence-bound Exam Prep V4 outputs.

The V4 pipeline keeps every historical row for audit. When a Source Map, block
set, question set, or answer-solution set changes, dependent accepted rows are
made non-current by moving only their lifecycle status to ``superseded``.

Callers may already be inside a larger atomic source/block/record replacement.
The nested atomic blocks below intentionally participate in that transaction,
so a later failure restores the previous accepted state together with the
failed replacement.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q

from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamMatchDecision,
    ExamQuestionRecord,
)


@dataclass(frozen=True, slots=True)
class SemanticInvalidationResult:
    question_count: int = 0
    answer_solution_count: int = 0
    match_decision_count: int = 0


def _locked_ids(queryset) -> tuple[int, ...]:
    """Lock the exact current rows that will be superseded."""

    return tuple(
        queryset.select_for_update().order_by('id').values_list('id', flat=True)
    )


def _accepted_match_decisions_for_document(*, document_id: int):
    """Select accepted decisions without joining the nullable question relation.

    ``question_record`` is nullable for unresolved and out-of-scope decisions.
    Filtering through ``question_record__document_id`` makes Django emit an
    outer join, and PostgreSQL rejects ``SELECT ... FOR UPDATE`` when a nullable
    join side is present. FK-id subqueries keep the lock on MatchDecision rows
    only while preserving the exact same document dependency boundary.
    """

    answer_record_ids = ExamAnswerSolutionRecord.objects.filter(
        document_id=document_id,
    ).values('id')
    question_record_ids = ExamQuestionRecord.objects.filter(
        document_id=document_id,
    ).values('id')
    return ExamMatchDecision.objects.filter(
        lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
    ).filter(
        Q(answer_record_id__in=answer_record_ids)
        | Q(question_record_id__in=question_record_ids)
    )


@transaction.atomic
def supersede_match_decisions_for_document(
    *,
    document_id: int,
) -> SemanticInvalidationResult:
    """Supersede accepted matches that depend on either record side of a document."""

    match_ids = _locked_ids(
        _accepted_match_decisions_for_document(document_id=document_id)
    )
    if match_ids:
        ExamMatchDecision.objects.filter(id__in=match_ids).update(
            lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
        )
    return SemanticInvalidationResult(match_decision_count=len(match_ids))


@transaction.atomic
def supersede_document_semantic_outputs(
    *,
    document_id: int,
) -> SemanticInvalidationResult:
    """Supersede every accepted semantic output dependent on one source document.

    The project boundary is reached only through record foreign keys. Unrelated
    documents, including equal or duplicate PDFs in independent projects, are
    never selected.
    """

    question_ids = _locked_ids(
        ExamQuestionRecord.objects.filter(
            document_id=document_id,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
    )
    answer_ids = _locked_ids(
        ExamAnswerSolutionRecord.objects.filter(
            document_id=document_id,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
    )
    match_result = supersede_match_decisions_for_document(
        document_id=document_id,
    )

    if question_ids:
        ExamQuestionRecord.objects.filter(id__in=question_ids).update(
            lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
        )
    if answer_ids:
        ExamAnswerSolutionRecord.objects.filter(id__in=answer_ids).update(
            lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
        )

    return SemanticInvalidationResult(
        question_count=len(question_ids),
        answer_solution_count=len(answer_ids),
        match_decision_count=match_result.match_decision_count,
    )
