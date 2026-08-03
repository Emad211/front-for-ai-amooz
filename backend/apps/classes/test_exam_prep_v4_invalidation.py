from decimal import Decimal

import pytest
from django.db import transaction

from apps.classes import test_exam_prep_v4_records_and_matching as fixture_helpers
from apps.classes.models_v4_blocks import (
    ExamSourceBlock,
    ExamSourceBlockFragment,
    ExamSourceBlockKind,
)
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamMatchDecision,
    ExamQuestionRecord,
)
from apps.classes.services import exam_prep_v4_blocks as blocks_service
from apps.classes.services.exam_prep_v4_blocks import (
    SourceBlockProposal,
    persist_source_blocks,
)
from apps.classes.services.exam_prep_v4_records import build_deterministic_matches


pytestmark = pytest.mark.django_db


def _completed_fixture():
    teacher, project, document, blocks, block_set = fixture_helpers._pipeline_fixture()
    fixture_helpers._persist_questions(
        document,
        block_set,
        fixture_helpers._question_proposals(blocks),
    )
    fixture_helpers._persist_answers(
        document,
        block_set,
        fixture_helpers._answer_proposals(blocks),
    )
    build_deterministic_matches(project_id=project.id)
    return teacher, project, document, blocks, block_set


def _block_proposals(*, changed: bool = False):
    return (
        SourceBlockProposal(
            order=0,
            segment_order=1,
            kind=ExamSourceBlockKind.QUESTION,
            printed_number='1',
            confidence=0.88 if changed else 0.98,
            fragments=(fixture_helpers._fragment(0, 2),),
        ),
        SourceBlockProposal(
            order=1,
            segment_order=1,
            kind=ExamSourceBlockKind.QUESTION,
            printed_number='2',
            confidence=0.97,
            fragments=(fixture_helpers._fragment(0, 3),),
        ),
        SourceBlockProposal(
            order=2,
            segment_order=2,
            kind=ExamSourceBlockKind.ANSWER_SOLUTION,
            printed_number='1',
            confidence=0.96,
            fragments=(fixture_helpers._fragment(0, 4),),
        ),
        SourceBlockProposal(
            order=3,
            segment_order=2,
            kind=ExamSourceBlockKind.ANSWER_SOLUTION,
            printed_number='99',
            confidence=0.95,
            fragments=(fixture_helpers._fragment(0, 5),),
        ),
        SourceBlockProposal(
            order=4,
            segment_order=2,
            kind=ExamSourceBlockKind.CONTINUATION,
            confidence=0.90,
            continuation_of_order=2,
            fragments=(fixture_helpers._fragment(0, 6, continuation=True),),
        ),
    )


def _accepted_counts(project):
    return (
        ExamQuestionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).count(),
        ExamAnswerSolutionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).count(),
        ExamMatchDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).count(),
    )


def test_source_map_revision_invalidates_only_its_document_and_project():
    _teacher_a, project_a, document_a, _blocks_a, _set_a = _completed_fixture()
    _teacher_b, project_b, _document_b, _blocks_b, _set_b = _completed_fixture()

    document_a.classification_revision = 2
    document_a.source_map_fingerprint = 'b' * 64
    document_a.save(
        update_fields=[
            'classification_revision',
            'source_map_fingerprint',
            'updated_at',
        ]
    )

    assert _accepted_counts(project_a) == (0, 0, 0)
    assert _accepted_counts(project_b) == (2, 2, 2)
    assert ExamQuestionRecord.objects.filter(
        project=project_a,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2
    assert ExamAnswerSolutionRecord.objects.filter(
        project=project_a,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2
    assert ExamMatchDecision.objects.filter(
        project=project_a,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2


def test_changed_block_set_supersedes_all_dependent_semantics_and_matches():
    _teacher, project, document, _blocks, _block_set = _completed_fixture()

    result = persist_source_blocks(
        document_id=document.id,
        expected_source_map_revision=document.classification_revision,
        expected_source_map_fingerprint=document.source_map_fingerprint,
        proposals=_block_proposals(changed=True),
    )

    assert result.reused is False
    assert result.revision == 2
    assert _accepted_counts(project) == (0, 0, 0)
    assert ExamQuestionRecord.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2
    assert ExamAnswerSolutionRecord.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2
    assert ExamMatchDecision.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2
    assert ExamSourceBlock.objects.filter(
        document=document,
        revision=2,
        status=ExamSourceBlock.Status.ACCEPTED,
    ).count() == 5


def test_failed_block_replacement_rolls_back_blocks_records_and_matches(
    monkeypatch,
):
    _teacher, project, document, _blocks, _block_set = _completed_fixture()

    def fail_fragment_write(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError('simulated fragment persistence failure')

    monkeypatch.setattr(
        blocks_service.ExamSourceBlockFragment.objects,
        'bulk_create',
        fail_fragment_write,
    )

    with pytest.raises(RuntimeError, match='fragment persistence failure'):
        persist_source_blocks(
            document_id=document.id,
            expected_source_map_revision=document.classification_revision,
            expected_source_map_fingerprint=document.source_map_fingerprint,
            proposals=_block_proposals(changed=True),
        )

    assert _accepted_counts(project) == (2, 2, 2)
    assert ExamQuestionRecord.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 0
    assert ExamAnswerSolutionRecord.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 0
    assert ExamMatchDecision.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 0
    assert ExamSourceBlock.objects.filter(
        document=document,
        revision=1,
        status=ExamSourceBlock.Status.ACCEPTED,
    ).count() == 5
    assert not ExamSourceBlock.objects.filter(document=document, revision=2).exists()


def test_new_question_revision_supersedes_matches_but_keeps_answers_current():
    _teacher, project, document, blocks, block_set = _completed_fixture()

    fixture_helpers._persist_questions(
        document,
        block_set,
        fixture_helpers._question_proposals(blocks, changed=True),
    )

    assert _accepted_counts(project) == (2, 2, 0)
    assert ExamQuestionRecord.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2
    assert ExamMatchDecision.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2


def test_new_answer_revision_supersedes_matches_but_keeps_questions_current():
    _teacher, project, document, blocks, block_set = _completed_fixture()

    fixture_helpers._persist_answers(
        document,
        block_set,
        fixture_helpers._answer_proposals(blocks, option='1'),
    )

    assert _accepted_counts(project) == (2, 2, 0)
    assert ExamAnswerSolutionRecord.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2
    assert ExamMatchDecision.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).count() == 2


def test_unchanged_block_set_reuse_keeps_current_records_and_matches():
    _teacher, project, document, _blocks, _block_set = _completed_fixture()

    result = persist_source_blocks(
        document_id=document.id,
        expected_source_map_revision=document.classification_revision,
        expected_source_map_fingerprint=document.source_map_fingerprint,
        proposals=_block_proposals(changed=False),
    )

    assert result.reused is True
    assert result.revision == 1
    assert _accepted_counts(project) == (2, 2, 2)
    assert not ExamQuestionRecord.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).exists()
    assert not ExamAnswerSolutionRecord.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).exists()
    assert not ExamMatchDecision.objects.filter(
        project=project,
        lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
    ).exists()
