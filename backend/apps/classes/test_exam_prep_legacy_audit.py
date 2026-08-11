import io
import json

import pytest
from django.core.management import call_command
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes import tasks_exam_prep
from apps.classes.models import (
    ClassCreationSession,
    ExamPrepExtractionArtifact,
    ExamPrepExtractionUnit,
    ExamPrepVisualAsset,
)
from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.models_v4_bridge import ExamV4SessionBridge
from apps.classes.models_v4_projection import ExamV4Projection
from apps.classes.services.exam_prep_legacy_audit import (
    PAGE_FIRST_ENGINE,
    build_exam_prep_legacy_audit,
)
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE
from apps.classes.views_exam_prep import _mistral_workflow_state


pytestmark = pytest.mark.django_db


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _valid_exam_json(number=1):
    return json.dumps(
        {
            'exam_prep': {
                'title': 'آزمون',
                'questions': [
                    {
                        'question_id': f'q-{number}',
                        'question_text_markdown': f'متن سؤال {number}',
                        'options': [
                            {'label': '1', 'text_markdown': 'گزینه یک'},
                            {'label': '2', 'text_markdown': 'گزینه دو'},
                        ],
                        'correct_option_label': '2',
                        'teacher_solution_markdown': 'حل',
                    }
                ],
            }
        },
        ensure_ascii=False,
    )


def _session(
    teacher,
    *,
    status,
    task_id='',
    workflow_state=None,
    exam_prep_json='',
    is_published=False,
):
    return ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=status,
        celery_task_id=task_id,
        workflow_state=workflow_state or {},
        exam_prep_json=exam_prep_json,
        is_published=is_published,
    )


def _build_inventory():
    teacher = _teacher()

    current = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
        task_id='current-mistral-task',
        workflow_state={'engine': PRODUCTION_ENGINE, 'stage': 'extracting_questions'},
    )
    v1_active = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
        task_id='v1-session-task',
    )
    v1_ready = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        exam_prep_json=_valid_exam_json(1),
    )
    v1_failed = _session(
        teacher,
        status=ClassCreationSession.Status.FAILED,
    )
    published_invalid = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        exam_prep_json='{}',
        is_published=True,
    )

    v2_session = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_STRUCTURING,
        task_id='v2-session-task',
    )
    v2_artifact = ExamPrepExtractionArtifact.objects.create(
        session=v2_session,
        pipeline_version=2,
        status=ExamPrepExtractionArtifact.Status.EXTRACTING,
        active_task_id='v2-artifact-task',
    )
    ExamPrepExtractionUnit.objects.create(
        artifact=v2_artifact,
        stage=ExamPrepExtractionUnit.Stage.QUESTIONS,
        unit_key='questions-page-1',
        revision=1,
        status=ExamPrepExtractionUnit.Status.PROCESSING,
        input_fingerprint='a' * 64,
        processing_task_id='v2-unit-task',
    )
    ExamPrepVisualAsset.objects.create(
        artifact=v2_artifact,
        asset_key='visual-1',
        role=ExamPrepVisualAsset.Role.QUESTION,
        source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
        source_file='exam-prep/visuals/source/visual-1.png',
        source_sha256='b' * 64,
        fingerprint='c' * 64,
        status=ExamPrepVisualAsset.Status.GENERATING,
    )

    v3_session = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
        task_id='v3-session-task',
    )
    ExamPrepExtractionArtifact.objects.create(
        session=v3_session,
        pipeline_version=3,
        status=ExamPrepExtractionArtifact.Status.MATCHING,
        active_task_id='v3-artifact-task',
    )

    v4_active_session = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
        task_id='v4-session-task',
    )
    v4_active_project = ExamProject.objects.create(
        teacher=teacher,
        title='V4 active',
        status=ExamProject.Status.EXTRACTING_QUESTIONS,
        workflow_state={'taskId': 'v4-project-task'},
    )
    ExamV4SessionBridge.objects.create(
        project=v4_active_project,
        session=v4_active_session,
    )
    ExamSourceDocument.objects.create(
        project=v4_active_project,
        original_name='active.pdf',
        status=ExamSourceDocument.Status.CLASSIFYING,
    )

    v4_retained_session = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        exam_prep_json=_valid_exam_json(2),
    )
    v4_retained_project = ExamProject.objects.create(
        teacher=teacher,
        title='V4 retained',
        status=ExamProject.Status.AWAITING_REVIEW,
    )
    ExamV4SessionBridge.objects.create(
        project=v4_retained_project,
        session=v4_retained_session,
    )
    ExamSourceDocument.objects.create(
        project=v4_retained_project,
        original_name='retained.pdf',
        status=ExamSourceDocument.Status.CONFIRMED,
    )
    ExamV4Projection.objects.create(
        project=v4_retained_project,
        session=v4_retained_session,
        revision=1,
        question_set_fingerprint='d' * 64,
        answer_set_fingerprint='e' * 64,
        review_set_fingerprint='f' * 64,
        projection_fingerprint='1' * 64,
        question_count=1,
        status=ExamV4Projection.Status.READY,
    )

    v4_reupload_project = ExamProject.objects.create(
        teacher=teacher,
        title='V4 incomplete',
        status=ExamProject.Status.AWAITING_SOURCE_CONFIRMATION,
    )
    ExamSourceDocument.objects.create(
        project=v4_reupload_project,
        original_name='incomplete.pdf',
        status=ExamSourceDocument.Status.AWAITING_CONFIRMATION,
    )

    return {
        'teacher': teacher,
        'current': current,
        'v1_active': v1_active,
        'v1_ready': v1_ready,
        'v1_failed': v1_failed,
        'published_invalid': published_invalid,
        'v2_session': v2_session,
        'v3_session': v3_session,
        'v4_active_session': v4_active_session,
        'v4_active_project': v4_active_project,
        'v4_retained_session': v4_retained_session,
        'v4_retained_project': v4_retained_project,
        'v4_reupload_project': v4_reupload_project,
    }


def test_production_workflow_states_have_explicit_engine_marker():
    intake_state = _mistral_workflow_state('queued', message='queued')
    task_state = tasks_exam_prep._workflow_state(
        'reading_source',
        message='reading',
        progress=10,
    )

    assert intake_state['engine'] == PRODUCTION_ENGINE
    assert task_state['engine'] == PRODUCTION_ENGINE


def test_audit_classifies_current_and_legacy_families_without_task_leakage():
    data = _build_inventory()

    report = build_exam_prep_legacy_audit(include_ids=True)

    assert report['dryRun'] is True
    assert report['writesPerformed'] == 0
    assert report['sessions']['total'] == 9
    assert report['sessions']['familyCounts'] == {
        PRODUCTION_ENGINE: 1,
        'v1': 4,
        'v2': 1,
        'v3': 1,
        'v4': 2,
    }
    assert report['sessions']['actionCounts'] == {
        'current': 1,
        'drain': 4,
        'retain': 3,
        'reupload': 1,
    }
    assert report['sessions']['publishableCount'] == 2
    assert report['sessions']['invalidPublishedCount'] == 1

    ids = report['ids']['sessionIdsByAction']
    assert ids['current'] == [data['current'].id]
    assert data['v1_active'].id in ids['drain']
    assert data['v2_session'].id in ids['drain']
    assert data['v3_session'].id in ids['drain']
    assert data['v4_active_session'].id in ids['drain']
    assert data['v1_ready'].id in ids['retain']
    assert data['v4_retained_session'].id in ids['retain']
    assert data['published_invalid'].id in ids['retain']
    assert ids['reupload'] == [data['v1_failed'].id]

    task_ids = report['ids']['taskIdsByFamily']
    assert task_ids == {
        'v1': ['v1-session-task'],
        'v2': ['v2-artifact-task', 'v2-session-task', 'v2-unit-task'],
        'v3': ['v3-artifact-task', 'v3-session-task'],
        'v4': ['v4-project-task'],
    }
    assert 'current-mistral-task' not in json.dumps(task_ids)
    assert report['drain']['taskCount'] == 7


def test_audit_reports_v4_project_plan_and_intermediate_counts():
    data = _build_inventory()

    report = build_exam_prep_legacy_audit(include_ids=True)

    assert report['legacyArtifacts']['total'] == 2
    assert report['legacyArtifacts']['activeCount'] == 2
    assert report['legacyUnits']['total'] == 1
    assert report['legacyUnits']['activeCount'] == 1
    assert report['legacyVisuals']['total'] == 1
    assert report['legacyVisuals']['activeCount'] == 1

    assert report['v4']['projectCount'] == 3
    assert report['v4']['documentCount'] == 3
    assert report['v4']['bridgeCount'] == 2
    assert report['v4']['projectionCount'] == 1
    assert report['v4']['projectActionCounts'] == {
        'drain': 1,
        'retain': 1,
        'reupload': 1,
    }
    project_ids = report['ids']['v4ProjectIdsByAction']
    assert project_ids['drain'] == [data['v4_active_project'].id]
    assert project_ids['retain'] == [data['v4_retained_project'].id]
    assert project_ids['reupload'] == [data['v4_reupload_project'].id]


def test_audit_is_strictly_read_only():
    data = _build_inventory()
    before_counts = {
        'sessions': ClassCreationSession.objects.count(),
        'artifacts': ExamPrepExtractionArtifact.objects.count(),
        'units': ExamPrepExtractionUnit.objects.count(),
        'visuals': ExamPrepVisualAsset.objects.count(),
        'projects': ExamProject.objects.count(),
        'documents': ExamSourceDocument.objects.count(),
        'bridges': ExamV4SessionBridge.objects.count(),
        'projections': ExamV4Projection.objects.count(),
    }
    before_session = ClassCreationSession.objects.values(
        'status',
        'workflow_state',
        'exam_prep_json',
        'is_published',
        'celery_task_id',
        'cancel_requested',
    ).get(id=data['v1_active'].id)
    before_project = ExamProject.objects.values(
        'status',
        'workflow_state',
        'cancel_requested',
        'is_published',
    ).get(id=data['v4_active_project'].id)

    build_exam_prep_legacy_audit(include_ids=True)

    assert before_counts == {
        'sessions': ClassCreationSession.objects.count(),
        'artifacts': ExamPrepExtractionArtifact.objects.count(),
        'units': ExamPrepExtractionUnit.objects.count(),
        'visuals': ExamPrepVisualAsset.objects.count(),
        'projects': ExamProject.objects.count(),
        'documents': ExamSourceDocument.objects.count(),
        'bridges': ExamV4SessionBridge.objects.count(),
        'projections': ExamV4Projection.objects.count(),
    }
    assert before_session == ClassCreationSession.objects.values(
        'status',
        'workflow_state',
        'exam_prep_json',
        'is_published',
        'celery_task_id',
        'cancel_requested',
    ).get(id=data['v1_active'].id)
    assert before_project == ExamProject.objects.values(
        'status',
        'workflow_state',
        'cancel_requested',
        'is_published',
    ).get(id=data['v4_active_project'].id)


def test_management_command_prints_json_only_and_performs_no_writes():
    _build_inventory()
    output = io.StringIO()

    call_command(
        'audit_exam_prep_legacy',
        '--include-ids',
        '--compact',
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload['dryRun'] is True
    assert payload['writesPerformed'] == 0
    assert payload['drain']['taskCount'] == 7
    assert 'ids' in payload


def test_valid_legacy_exam_json_remains_publishable_through_existing_api():
    teacher = _teacher()
    session = _session(
        teacher,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        exam_prep_json=_valid_exam_json(8),
    )
    client = APIClient()
    client.force_authenticate(user=teacher)

    response = client.post(
        f'/api/classes/exam-prep-sessions/{session.id}/publish/'
    )

    assert response.status_code == 200
    session.refresh_from_db()
    assert session.is_published is True
    assert session.published_at is not None
