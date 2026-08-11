"""Read-only inventory for draining legacy exam-preparation pipelines.

The audit intentionally performs no updates, deletes, revokes, or file access.
It reports only operational identifiers, statuses, counts, and a deterministic
retain/drain/re-upload plan.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any

from django.db.models import QuerySet

from apps.classes.models import (
    ClassCreationSession,
    ExamPrepExtractionArtifact,
    ExamPrepExtractionUnit,
    ExamPrepVisualAsset,
)
from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.models_v4_bridge import ExamV4SessionBridge
from apps.classes.models_v4_projection import ExamV4Projection
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE


PAGE_FIRST_ENGINE = 'page_first'
CURRENT_ENGINES = frozenset({PAGE_FIRST_ENGINE, PRODUCTION_ENGINE})
SCHEMA_VERSION = 1

_SESSION_ACTIVE = {
    ClassCreationSession.Status.EXAM_TRANSCRIBING,
    ClassCreationSession.Status.EXAM_TRANSCRIBED,
    ClassCreationSession.Status.EXAM_STRUCTURING,
}
_ARTIFACT_ACTIVE = {
    ExamPrepExtractionArtifact.Status.COLLECTING_PAGES,
    ExamPrepExtractionArtifact.Status.INVENTORY,
    ExamPrepExtractionArtifact.Status.EXTRACTING,
    ExamPrepExtractionArtifact.Status.MATCHING,
    ExamPrepExtractionArtifact.Status.VISUALS,
}
_UNIT_ACTIVE = {
    ExamPrepExtractionUnit.Status.PENDING,
    ExamPrepExtractionUnit.Status.PROCESSING,
    ExamPrepExtractionUnit.Status.RETRYABLE,
}
_VISUAL_ACTIVE = {
    ExamPrepVisualAsset.Status.GENERATING,
}
_V4_ACTIVE = {
    ExamProject.Status.UPLOADING,
    ExamProject.Status.CLASSIFYING,
    ExamProject.Status.SEGMENTING,
    ExamProject.Status.EXTRACTING_QUESTIONS,
    ExamProject.Status.EXTRACTING_ANSWERS,
    ExamProject.Status.MATCHING,
}


def _status_counts(queryset: QuerySet, field: str = 'status') -> dict[str, int]:
    result: Counter[str] = Counter()
    for value in queryset.values_list(field, flat=True):
        result[str(value or '')] += 1
    return dict(sorted(result.items()))


def _clean_id(value: Any) -> str | None:
    text = str(value or '').strip()
    return text[:255] if text else None


def _valid_question_count(raw: object) -> int:
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return 0
    else:
        return 0

    exam = payload.get('exam_prep') if isinstance(payload, dict) else None
    questions = exam.get('questions') if isinstance(exam, dict) else None
    if not isinstance(questions, list):
        return 0
    return sum(
        1
        for question in questions
        if isinstance(question, dict)
        and str(question.get('question_text_markdown') or '').strip()
        and isinstance(question.get('options'), list)
        and len(question['options']) >= 2
    )


def _session_family(
    session: ClassCreationSession,
    *,
    v4_session_ids: set[int],
    artifact_versions: dict[int, int],
) -> str:
    state = session.workflow_state if isinstance(session.workflow_state, dict) else {}
    engine = str(state.get('engine') or '')
    if engine in CURRENT_ENGINES:
        return engine
    if session.id in v4_session_ids:
        return 'v4'
    version = artifact_versions.get(session.id)
    if version is not None:
        return f'v{version}'
    return 'v1'


def _session_action(
    session: ClassCreationSession,
    *,
    family: str,
    valid_question_count: int,
) -> str:
    if family in CURRENT_ENGINES:
        return 'current'
    if session.is_published or valid_question_count > 0:
        return 'retain'
    if session.status in _SESSION_ACTIVE:
        return 'drain'
    return 'reupload'


def _append_task(
    target: dict[str, set[str]],
    family: str,
    value: Any,
) -> None:
    task_id = _clean_id(value)
    if task_id:
        target[family].add(task_id)


def build_exam_prep_legacy_audit(*, include_ids: bool = False) -> dict[str, Any]:
    """Build a deterministic read-only drain plan from current database state."""

    sessions = list(
        ClassCreationSession.objects.filter(
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).only(
            'id',
            'status',
            'workflow_state',
            'exam_prep_json',
            'is_published',
            'celery_task_id',
            'cancel_requested',
        ).order_by('id')
    )
    artifacts = list(
        ExamPrepExtractionArtifact.objects.only(
            'id',
            'session_id',
            'pipeline_version',
            'status',
            'active_task_id',
        ).order_by('id')
    )
    units = list(
        ExamPrepExtractionUnit.objects.only(
            'id',
            'artifact_id',
            'status',
            'processing_task_id',
        ).order_by('id')
    )
    visuals = list(
        ExamPrepVisualAsset.objects.only(
            'id',
            'artifact_id',
            'status',
        ).order_by('id')
    )
    bridges = list(
        ExamV4SessionBridge.objects.only('id', 'project_id', 'session_id').order_by('id')
    )
    projects = list(
        ExamProject.objects.only(
            'id',
            'status',
            'workflow_state',
            'is_published',
            'cancel_requested',
        ).order_by('id')
    )
    documents = list(
        ExamSourceDocument.objects.only('id', 'project_id', 'status').order_by('id')
    )
    projections = list(
        ExamV4Projection.objects.only(
            'id',
            'project_id',
            'session_id',
            'status',
        ).order_by('id')
    )

    sessions_by_id = {session.id: session for session in sessions}
    artifact_by_id = {artifact.id: artifact for artifact in artifacts}
    artifact_versions = {
        artifact.session_id: int(artifact.pipeline_version)
        for artifact in artifacts
    }
    v4_session_ids = {bridge.session_id for bridge in bridges}
    v4_project_to_session = {
        bridge.project_id: bridge.session_id
        for bridge in bridges
    }

    family_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    status_by_family: dict[str, Counter[str]] = defaultdict(Counter)
    session_ids_by_action: dict[str, list[int]] = defaultdict(list)
    task_ids: dict[str, set[str]] = defaultdict(set)
    invalid_published_session_ids: list[int] = []
    publishable_session_ids: list[int] = []

    for session in sessions:
        family = _session_family(
            session,
            v4_session_ids=v4_session_ids,
            artifact_versions=artifact_versions,
        )
        question_count = _valid_question_count(session.exam_prep_json)
        action = _session_action(
            session,
            family=family,
            valid_question_count=question_count,
        )
        family_counts[family] += 1
        action_counts[action] += 1
        status_by_family[family][session.status] += 1
        session_ids_by_action[action].append(session.id)

        if question_count > 0:
            publishable_session_ids.append(session.id)
        if session.is_published and question_count < 1:
            invalid_published_session_ids.append(session.id)
        if family not in CURRENT_ENGINES and session.status in _SESSION_ACTIVE:
            _append_task(task_ids, family, session.celery_task_id)

    for artifact in artifacts:
        family = f'v{int(artifact.pipeline_version)}'
        if artifact.status in _ARTIFACT_ACTIVE:
            _append_task(task_ids, family, artifact.active_task_id)

    for unit in units:
        artifact = artifact_by_id.get(unit.artifact_id)
        family = f'v{int(artifact.pipeline_version)}' if artifact else 'legacy_unknown'
        if unit.status in _UNIT_ACTIVE:
            _append_task(task_ids, family, unit.processing_task_id)

    v4_project_actions: Counter[str] = Counter()
    v4_project_ids_by_action: dict[str, list[int]] = defaultdict(list)
    for project in projects:
        session_id = v4_project_to_session.get(project.id)
        linked_session = sessions_by_id.get(session_id)
        linked_question_count = (
            _valid_question_count(linked_session.exam_prep_json)
            if linked_session is not None
            else 0
        )
        if project.is_published or linked_question_count > 0:
            action = 'retain'
        elif project.status in _V4_ACTIVE:
            action = 'drain'
        else:
            action = 'reupload'
        v4_project_actions[action] += 1
        v4_project_ids_by_action[action].append(project.id)
        if action == 'drain':
            state = project.workflow_state if isinstance(project.workflow_state, dict) else {}
            _append_task(task_ids, 'v4', state.get('taskId'))

    report: dict[str, Any] = {
        'schemaVersion': SCHEMA_VERSION,
        'dryRun': True,
        'writesPerformed': 0,
        'pageFirstEngine': PAGE_FIRST_ENGINE,
        'productionEngine': PRODUCTION_ENGINE,
        'sessions': {
            'total': len(sessions),
            'familyCounts': dict(sorted(family_counts.items())),
            'actionCounts': dict(sorted(action_counts.items())),
            'statusCounts': _status_counts(
                ClassCreationSession.objects.filter(
                    pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                )
            ),
            'statusByFamily': {
                family: dict(sorted(counter.items()))
                for family, counter in sorted(status_by_family.items())
            },
            'publishableCount': len(publishable_session_ids),
            'invalidPublishedCount': len(invalid_published_session_ids),
        },
        'legacyArtifacts': {
            'total': len(artifacts),
            'statusCounts': _status_counts(ExamPrepExtractionArtifact.objects.all()),
            'activeCount': sum(artifact.status in _ARTIFACT_ACTIVE for artifact in artifacts),
        },
        'legacyUnits': {
            'total': len(units),
            'statusCounts': _status_counts(ExamPrepExtractionUnit.objects.all()),
            'activeCount': sum(unit.status in _UNIT_ACTIVE for unit in units),
        },
        'legacyVisuals': {
            'total': len(visuals),
            'statusCounts': _status_counts(ExamPrepVisualAsset.objects.all()),
            'activeCount': sum(visual.status in _VISUAL_ACTIVE for visual in visuals),
        },
        'v4': {
            'projectCount': len(projects),
            'projectStatusCounts': _status_counts(ExamProject.objects.all()),
            'projectActionCounts': dict(sorted(v4_project_actions.items())),
            'documentCount': len(documents),
            'documentStatusCounts': _status_counts(ExamSourceDocument.objects.all()),
            'bridgeCount': len(bridges),
            'projectionCount': len(projections),
            'projectionStatusCounts': _status_counts(ExamV4Projection.objects.all()),
        },
        'drain': {
            'taskCount': sum(len(values) for values in task_ids.values()),
            'taskCountByFamily': {
                family: len(values)
                for family, values in sorted(task_ids.items())
            },
        },
    }

    if include_ids:
        report['ids'] = {
            'sessionIdsByAction': {
                action: sorted(values)
                for action, values in sorted(session_ids_by_action.items())
            },
            'v4ProjectIdsByAction': {
                action: sorted(values)
                for action, values in sorted(v4_project_ids_by_action.items())
            },
            'publishableSessionIds': sorted(publishable_session_ids),
            'invalidPublishedSessionIds': sorted(invalid_published_session_ids),
            'taskIdsByFamily': {
                family: sorted(values)
                for family, values in sorted(task_ids.items())
            },
        }

    return report
