import pytest
from django.urls import resolve

from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE
from apps.classes.views_exam_prep_review import (
    ExamPrepReviewSessionDetailView,
    _is_reviewable_exam_session,
)


pytestmark = pytest.mark.unit


def test_detail_url_resolves_to_generic_review_view():
    match = resolve('/api/classes/exam-prep-sessions/123/')
    assert match.func.view_class is ExamPrepReviewSessionDetailView


def test_completed_page_first_draft_is_reviewable():
    session = ClassCreationSession(
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
        workflow_state={
            'engine': 'page_first',
            'readyForReview': True,
        },
        celery_task_id='',
        cancel_requested=False,
    )

    assert _is_reviewable_exam_session(session) is True


def test_incomplete_mistral_stage5_workflow_is_not_reviewable():
    session = ClassCreationSession(
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
        workflow_state={
            'engine': PRODUCTION_ENGINE,
            'readyForReview': True,
        },
        celery_task_id='',
        cancel_requested=False,
    )

    assert _is_reviewable_exam_session(session) is False


def test_running_or_legacy_draft_is_not_reviewable():
    running = ClassCreationSession(
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
        workflow_state={'engine': 'page_first', 'readyForReview': False},
    )
    legacy = ClassCreationSession(
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
        workflow_state={'readyForReview': True},
    )

    assert _is_reviewable_exam_session(running) is False
    assert _is_reviewable_exam_session(legacy) is False
