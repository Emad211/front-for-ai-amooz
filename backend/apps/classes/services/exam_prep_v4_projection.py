"""Backward-compatible projection and publication for Exam Prep V4."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.classes.models import ClassCreationSession
from apps.classes.models_v4 import ExamProject
from apps.classes.models_v4_blocks import ExamSourceBlock
from apps.classes.models_v4_projection import ExamV4Projection
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamMatchDecision,
    ExamQuestionRecord,
)
from apps.classes.models_v4_review import ExamReviewDecision
from apps.classes.services.exam_prep_v4_observability import emit_v4_event
from apps.classes.services.exam_prep_v4_source_crops import source_crop_url


class ProjectionNotReady(RuntimeError):
    pass


class StaleProjection(RuntimeError):
    pass


class ProjectionIntegrityError(ValueError):
    pass


def _hash_payload(payload: Any) -> str:
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
    records = tuple(
        ExamQuestionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
        .select_related('source_block')
        .prefetch_related('source_block__fragments')
        .order_by('document__upload_order', 'order', 'id')
    )
    if not records:
        raise ProjectionNotReady('No accepted question inventory exists.')
    return records


def _current_answers(project: ExamProject) -> tuple[ExamAnswerSolutionRecord, ...]:
    records = tuple(
        ExamAnswerSolutionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
        .select_related('source_block')
        .prefetch_related('source_block__fragments')
        .order_by('document__upload_order', 'order', 'id')
    )
    if not records:
        raise ProjectionNotReady('No accepted answer inventory exists.')
    return records


def _current_matches(project: ExamProject) -> tuple[ExamMatchDecision, ...]:
    records = tuple(
        ExamMatchDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
        .select_related('answer_record', 'question_record')
        .order_by('order', 'id')
    )
    if not records:
        raise ProjectionNotReady('No accepted match set exists.')
    if len({item.question_set_fingerprint for item in records}) != 1:
        raise ProjectionNotReady('Question set fingerprints are inconsistent.')
    if len({item.answer_set_fingerprint for item in records}) != 1:
        raise ProjectionNotReady('Answer set fingerprints are inconsistent.')
    return records


def _current_reviews(project: ExamProject) -> tuple[ExamReviewDecision, ...]:
    return tuple(
        ExamReviewDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
        .select_related('question_record', 'match_decision', 'answer_record')
        .order_by('answer_record_id', '-revision', '-id')
    )


def _review_by_answer(
    reviews: tuple[ExamReviewDecision, ...],
) -> dict[int, ExamReviewDecision]:
    result: dict[int, ExamReviewDecision] = {}
    for review in reviews:
        result.setdefault(review.answer_record_id, review)
    return result


def _normalized_option_labels(question: ExamQuestionRecord) -> set[str]:
    result: set[str] = set()
    if isinstance(question.options, list):
        for item in question.options:
            if isinstance(item, dict):
                label = str(item.get('label') or '').strip().lower()
                if label:
                    result.add(label)
    return result


def _resolved_answer_map(
    *,
    project: ExamProject,
    questions: tuple[ExamQuestionRecord, ...],
    answers: tuple[ExamAnswerSolutionRecord, ...],
    matches: tuple[ExamMatchDecision, ...],
    reviews: tuple[ExamReviewDecision, ...],
) -> tuple[dict[int, ExamAnswerSolutionRecord], str]:
    questions_by_id = {item.id: item for item in questions}
    answers_by_id = {item.id: item for item in answers}
    reviews_by_answer = _review_by_answer(reviews)
    resolved: dict[int, ExamAnswerSolutionRecord] = {}
    used_answers: set[int] = set()

    for match in matches:
        answer = answers_by_id.get(match.answer_record_id)
        if answer is None:
            raise StaleProjection('A match references a non-current answer record.')
        question = None
        if match.decision == ExamMatchDecision.Decision.MATCHED:
            question = questions_by_id.get(match.question_record_id)
            if question is None:
                raise StaleProjection('A matched question is no longer current.')
        else:
            review = reviews_by_answer.get(answer.id)
            if review is None:
                raise ProjectionNotReady('All match exceptions must be reviewed first.')
            if (
                review.question_set_fingerprint != match.question_set_fingerprint
                or review.answer_set_fingerprint != match.answer_set_fingerprint
                or review.source_match_fingerprint != match.fingerprint
            ):
                raise StaleProjection('A review decision is bound to a stale match set.')
            if review.action == ExamReviewDecision.Action.MATCH:
                question = questions_by_id.get(review.question_record_id)
                if question is None:
                    raise StaleProjection('A manually selected question is no longer current.')
            elif review.action in {
                ExamReviewDecision.Action.OUT_OF_SCOPE,
                ExamReviewDecision.Action.IGNORE,
            }:
                continue
            else:
                raise ProjectionIntegrityError('Unsupported teacher review action.')

        if question.id in resolved:
            raise ProjectionIntegrityError(
                'Multiple answer records resolve to the same question.'
            )
        option_labels = _normalized_option_labels(question)
        correct_option = str(answer.correct_option or '').strip().lower()
        if option_labels and correct_option and correct_option not in option_labels:
            raise ProjectionIntegrityError(
                'Correct option is not present in the selected question options.'
            )
        if option_labels and not correct_option:
            raise ProjectionIntegrityError(
                'A question with options requires a correct option label.'
            )
        resolved[question.id] = answer
        used_answers.add(answer.id)

    missing_question_ids = [item.id for item in questions if item.id not in resolved]
    if missing_question_ids:
        raise ProjectionIntegrityError(
            f'{len(missing_question_ids)} questions do not have a publishable answer.'
        )
    review_fingerprint = _hash_payload(
        sorted(
            review.fingerprint
            for review in reviews
            if review.answer_record_id in used_answers
            or review.action in {
                ExamReviewDecision.Action.OUT_OF_SCOPE,
                ExamReviewDecision.Action.IGNORE,
            }
        )
    )
    return resolved, review_fingerprint


def _legacy_options(question: ExamQuestionRecord) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    if not isinstance(question.options, list):
        return result
    for item in question.options[:20]:
        if not isinstance(item, dict):
            continue
        label = str(item.get('label') or '').strip()[:32]
        if not label:
            continue
        result.append(
            {
                'label': label,
                'text_markdown': str(item.get('text') or '').strip()[:50_000],
            }
        )
    return result


def _question_type(options: list[dict[str, str]]) -> str:
    if not options:
        return 'short_answer'
    values = {
        item['text_markdown'].strip().lower()
        for item in options
        if item['text_markdown'].strip()
    }
    if len(options) == 2 and values & {
        'صحیح',
        'غلط',
        'درست',
        'نادرست',
        'true',
        'false',
    }:
        return 'true_false'
    return 'multiple_choice'


def _source_visual_ref(
    *,
    project: ExamProject,
    record: ExamQuestionRecord | ExamAnswerSolutionRecord,
    role: str,
    alt_text: str,
) -> dict[str, Any] | None:
    """Expose a protected crop URL, never a storage key or raw OCR payload.

    The URL contains the record id for routing, but the view enforces project
    ancestry and (for students) exact projection membership before streaming.
    """

    block = getattr(record, 'source_block', None)
    if block is None or not getattr(record, 'source_block_id', None):
        return None
    if block.status != ExamSourceBlock.Status.ACCEPTED:
        return None
    # A record without fragments is not renderable; omitting the ref lets the
    # existing review/legacy UI fall back cleanly instead of showing a broken
    # image.  Accepted V4 records normally always have at least one fragment.
    if not block.fragments.all():
        return None
    return {
        'id': f'v4-{role}-{record.id}',
        'role': role,
        'optionLabel': None,
        'altText': alt_text,
        'selectedVariant': 'source',
        'url': source_crop_url(
            project_id=project.id,
            record_kind='question' if role == 'question' else 'solution',
            record_id=record.id,
        ),
    }


def _legacy_question(
    *,
    project: ExamProject,
    question: ExamQuestionRecord,
    answer: ExamAnswerSolutionRecord,
) -> dict[str, Any]:
    options = _legacy_options(question)
    correct_label = str(answer.correct_option or '').strip()
    correct_text = ''
    for option in options:
        if option['label'].strip().lower() == correct_label.lower():
            correct_text = option['text_markdown']
            break
    opaque_id = _hash_payload(
        {
            'projectId': project.id,
            'questionFingerprint': question.fingerprint,
        }
    )[:24]
    visuals: list[dict[str, Any]] = []
    question_visual = _source_visual_ref(
        project=project,
        record=question,
        role='question',
        alt_text='برش اصلی صورت سؤال و گزینه‌ها',
    )
    if question_visual is not None:
        visuals.append(question_visual)
    solution_visual = _source_visual_ref(
        project=project,
        record=answer,
        role='solution',
        alt_text='برش اصلی راه‌حل و پاسخ تشریحی',
    )
    if solution_visual is not None:
        visuals.append(solution_visual)
    return {
        'question_id': f'v4-{opaque_id}',
        'question_text_markdown': question.question_text,
        'type': _question_type(options),
        'options': options,
        'correct_option_label': correct_label,
        'correct_option_text_markdown': correct_text,
        'teacher_solution_markdown': answer.solution_text,
        'final_answer_markdown': answer.final_answer,
        'visuals': visuals,
    }


def _projection_payload(
    *,
    project: ExamProject,
    questions: tuple[ExamQuestionRecord, ...],
    resolved_answers: dict[int, ExamAnswerSolutionRecord],
) -> dict[str, Any]:
    return {
        'exam_prep': {
            'title': project.title,
            'questions': [
                _legacy_question(
                    project=project,
                    question=question,
                    answer=resolved_answers[question.id],
                )
                for question in questions
            ],
        }
    }


def _session_defaults(project: ExamProject, payload_json: str, page_count: int) -> dict[str, Any]:
    return {
        'teacher': project.teacher,
        'organization': project.organization,
        'study_group': project.study_group,
        'title': project.title,
        'description': project.description,
        'pipeline_type': ClassCreationSession.PipelineType.EXAM_PREP,
        'source_type': ClassCreationSession.SourceType.PDF,
        'source_file': '',
        'source_mime_type': 'application/pdf',
        'source_original_name': '',
        'source_page_count': page_count,
        'status': ClassCreationSession.Status.EXAM_STRUCTURED,
        'transcript_markdown': '',
        'exam_prep_json': payload_json,
        'workflow_state': {
            'stage': 'v4_projection_ready',
            'v4ProjectId': project.id,
            'progressPercent': 100,
        },
        'is_published': False,
    }


@transaction.atomic
def build_legacy_projection(*, teacher, project_id: int) -> dict[str, Any]:
    project = _owned_project(teacher=teacher, project_id=project_id, for_update=True)
    if project.status not in {
        ExamProject.Status.READY_TO_PUBLISH,
        ExamProject.Status.PUBLISHED,
    }:
        raise ProjectionNotReady('Teacher review must be completed first.')
    questions = _current_questions(project)
    answers = _current_answers(project)
    matches = _current_matches(project)
    reviews = _current_reviews(project)
    resolved_answers, review_set_fingerprint = _resolved_answer_map(
        project=project,
        questions=questions,
        answers=answers,
        matches=matches,
        reviews=reviews,
    )
    payload = _projection_payload(
        project=project,
        questions=questions,
        resolved_answers=resolved_answers,
    )
    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    projection_fingerprint = _hash_payload(payload)
    question_set = matches[0].question_set_fingerprint
    answer_set = matches[0].answer_set_fingerprint
    page_count = sum(project.source_documents.values_list('page_count', flat=True))

    projection = (
        ExamV4Projection.objects.select_for_update()
        .select_related('session')
        .filter(project=project)
        .first()
    )
    if projection is not None and (
        projection.projection_fingerprint == projection_fingerprint
        and projection.question_set_fingerprint == question_set
        and projection.answer_set_fingerprint == answer_set
        and projection.review_set_fingerprint == review_set_fingerprint
    ):
        return {
            'projectId': project.id,
            'sessionId': projection.session_id,
            'projectionId': projection.id,
            'projectionFingerprint': projection.projection_fingerprint,
            'questionCount': projection.question_count,
            'status': projection.status,
            'published': projection.session.is_published,
            'reused': True,
        }
    if projection is not None and projection.session.is_published:
        raise StaleProjection('Published projection cannot be replaced.')

    if projection is None:
        session = ClassCreationSession.objects.create(
            **_session_defaults(project, payload_json, page_count)
        )
        projection = ExamV4Projection.objects.create(
            project=project,
            session=session,
            revision=1,
            question_set_fingerprint=question_set,
            answer_set_fingerprint=answer_set,
            review_set_fingerprint=review_set_fingerprint,
            projection_fingerprint=projection_fingerprint,
            question_count=len(questions),
            status=ExamV4Projection.Status.READY,
        )
    else:
        session = projection.session
        defaults = _session_defaults(project, payload_json, page_count)
        for field, value in defaults.items():
            setattr(session, field, value)
        session.save(
            update_fields=[
                'teacher',
                'organization',
                'study_group',
                'title',
                'description',
                'pipeline_type',
                'source_type',
                'source_file',
                'source_mime_type',
                'source_original_name',
                'source_page_count',
                'status',
                'transcript_markdown',
                'exam_prep_json',
                'workflow_state',
                'is_published',
                'updated_at',
            ]
        )
        projection.revision += 1
        projection.question_set_fingerprint = question_set
        projection.answer_set_fingerprint = answer_set
        projection.review_set_fingerprint = review_set_fingerprint
        projection.projection_fingerprint = projection_fingerprint
        projection.question_count = len(questions)
        projection.status = ExamV4Projection.Status.READY
        projection.published_at = None
        projection.save()

    state = dict(project.workflow_state) if isinstance(project.workflow_state, dict) else {}
    state.update(
        {
            'stage': 'projection_ready',
            'progressPercent': 95,
            'legacySessionId': projection.session_id,
            'projectionFingerprintPrefix': projection_fingerprint[:12],
            'projectionQuestionCount': len(questions),
            'lastEventAt': timezone.now().isoformat(),
        }
    )
    project.status = ExamProject.Status.READY_TO_PUBLISH
    project.workflow_state = state
    project.reviewed_revision = project.revision
    project.reviewed_projection_fingerprint = projection_fingerprint
    project.save(
        update_fields=[
            'status',
            'workflow_state',
            'reviewed_revision',
            'reviewed_projection_fingerprint',
            'updated_at',
        ]
    )
    emit_v4_event(
        'exam_prep_v4.projection.ready',
        projectId=project.id,
        sessionId=projection.session_id,
        projectionFingerprintPrefix=projection_fingerprint[:12],
        questionCount=len(questions),
    )
    return {
        'projectId': project.id,
        'sessionId': projection.session_id,
        'projectionId': projection.id,
        'projectionFingerprint': projection.projection_fingerprint,
        'questionCount': projection.question_count,
        'status': projection.status,
        'published': False,
        'reused': False,
    }


@transaction.atomic
def publish_legacy_projection(*, teacher, project_id: int) -> dict[str, Any]:
    projection_payload = build_legacy_projection(
        teacher=teacher,
        project_id=project_id,
    )
    project = _owned_project(teacher=teacher, project_id=project_id, for_update=True)
    projection = (
        ExamV4Projection.objects.select_for_update()
        .select_related('session')
        .get(project=project)
    )
    session = ClassCreationSession.objects.select_for_update().get(
        id=projection.session_id,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
    )
    if session.is_published:
        # A legacy teacher publish request can predate the V4 publication
        # endpoint and set only ``session.is_published``.  Repair all three
        # linked lifecycle records idempotently so protected source crops and
        # the V4 project agree with the public session boundary.
        now = session.published_at or projection.published_at or timezone.now()
        if session.published_at is None:
            session.published_at = now
            session.save(update_fields=['published_at', 'updated_at'])
        projection_updates: list[str] = []
        if projection.status != ExamV4Projection.Status.PUBLISHED:
            projection.status = ExamV4Projection.Status.PUBLISHED
            projection_updates.append('status')
        if projection.published_at is None:
            projection.published_at = now
            projection_updates.append('published_at')
        if projection_updates:
            projection.save(update_fields=[*projection_updates, 'updated_at'])

        project_updates: list[str] = []
        if project.status != ExamProject.Status.PUBLISHED:
            project.status = ExamProject.Status.PUBLISHED
            project_updates.append('status')
        if not project.is_published:
            project.is_published = True
            project_updates.append('is_published')
        if project.published_at is None:
            project.published_at = now
            project_updates.append('published_at')
        state = dict(project.workflow_state) if isinstance(project.workflow_state, dict) else {}
        state_changed = state.get('stage') != 'published' or state.get('legacySessionId') != session.id
        if state_changed:
            state.update(
                {
                    'stage': 'published',
                    'progressPercent': 100,
                    'legacySessionId': session.id,
                    'publishedAt': now.isoformat(),
                    'lastEventAt': now.isoformat(),
                }
            )
            project.workflow_state = state
            project_updates.append('workflow_state')
        if project_updates:
            project.save(update_fields=[*project_updates, 'updated_at'])
        return {
            **projection_payload,
            'status': ExamV4Projection.Status.PUBLISHED,
            'published': True,
            'reused': True,
        }
    if (
        project.reviewed_revision != project.revision
        or project.reviewed_projection_fingerprint
        != projection.projection_fingerprint
    ):
        raise StaleProjection('Projection is no longer bound to the reviewed project revision.')

    now = timezone.now()
    session.is_published = True
    session.published_at = now
    session.save(update_fields=['is_published', 'published_at', 'updated_at'])
    projection.status = ExamV4Projection.Status.PUBLISHED
    projection.published_at = now
    projection.save(update_fields=['status', 'published_at', 'updated_at'])
    project.status = ExamProject.Status.PUBLISHED
    project.is_published = True
    project.published_at = now
    state = dict(project.workflow_state) if isinstance(project.workflow_state, dict) else {}
    state.update(
        {
            'stage': 'published',
            'progressPercent': 100,
            'legacySessionId': session.id,
            'publishedAt': now.isoformat(),
            'lastEventAt': now.isoformat(),
        }
    )
    project.workflow_state = state
    project.save(
        update_fields=[
            'status',
            'is_published',
            'published_at',
            'workflow_state',
            'updated_at',
        ]
    )

    def _after_commit() -> None:
        try:
            from apps.classes.services.org_roster import sync_org_class_roster

            sync_org_class_roster(session)
        except Exception:
            emit_v4_event(
                'exam_prep_v4.projection.roster_sync_failed',
                level=30,
                projectId=project.id,
                sessionId=session.id,
                errorCode='roster_sync_failed',
            )
        try:
            from apps.classes.tasks import send_publish_sms_task

            send_publish_sms_task.delay(session.id)
        except Exception:
            emit_v4_event(
                'exam_prep_v4.projection.publish_sms_dispatch_failed',
                level=30,
                projectId=project.id,
                sessionId=session.id,
                errorCode='publish_sms_dispatch_failed',
            )

    transaction.on_commit(_after_commit)
    emit_v4_event(
        'exam_prep_v4.projection.published',
        projectId=project.id,
        sessionId=session.id,
        projectionFingerprintPrefix=projection.projection_fingerprint[:12],
        questionCount=projection.question_count,
    )
    return {
        'projectId': project.id,
        'sessionId': session.id,
        'projectionId': projection.id,
        'projectionFingerprint': projection.projection_fingerprint,
        'questionCount': projection.question_count,
        'status': projection.status,
        'published': True,
        'reused': False,
    }
