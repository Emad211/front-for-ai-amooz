import json
from decimal import Decimal

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)
from apps.organizations.models import Organization, StudyGroup


pytestmark = pytest.mark.django_db
LIST_URL = '/api/classes/exam-prep-v4/projects/'


def _detail_url(project_id: int) -> str:
    return f'/api/classes/exam-prep-v4/projects/{project_id}/'


def _user(role='TEACHER'):
    return baker.make('accounts.User', role=role)


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _project(teacher, **kwargs):
    return ExamProject.objects.create(
        teacher=teacher,
        title=kwargs.pop('title', 'آزمون امن'),
        description=kwargs.pop('description', 'توضیح مجاز'),
        **kwargs,
    )


def _build_sensitive_source_map(teacher):
    owner = _user()
    organization = Organization.objects.create(
        owner=owner,
        name='PRIVATE_ORGANIZATION_NAME',
        slug='private-org-name',
    )
    group = StudyGroup.objects.create(
        organization=organization,
        name='PRIVATE_STUDY_GROUP_NAME',
    )
    project = _project(
        teacher,
        organization=organization,
        study_group=group,
        status=ExamProject.Status.AWAITING_SOURCE_CONFIRMATION,
        revision=3,
        workflow_state={
            'stage': 'awaiting_source_confirmation',
            'progressPercent': 20,
            'warningCount': 2,
            'message': 'PRIVATE_WORKFLOW_MESSAGE',
            'rawPayload': 'PRIVATE_WORKFLOW_RAW',
        },
        error_code='safe_project_code',
        error_detail='PRIVATE_PROJECT_ERROR_DETAIL',
    )
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='PRIVATE_SOURCE_FILENAME.pdf',
        source_file='exam-prep-v4/source/documents/PRIVATE_STORAGE_KEY.pdf',
        source_sha256='a' * 64,
        byte_size=987654,
        page_count=3,
        status=ExamSourceDocument.Status.AWAITING_CONFIRMATION,
        classification_revision=2,
        classification_fingerprint='b' * 64,
        classification_metadata={
            'issues': [
                {
                    'code': 'missing_page_prediction',
                    'recordIndex': 7,
                    'pageNumber': 2,
                    'detail': 'PRIVATE_ISSUE_DETAIL',
                },
                {
                    'code': 'INVALID CODE WITH PRIVATE DATA',
                    'pageNumber': 999,
                    'detail': 'PRIVATE_INVALID_ISSUE_DETAIL',
                },
            ],
            'rawPayload': 'PRIVATE_DOCUMENT_RAW_PAYLOAD',
            'model': 'PRIVATE_MODEL_NAME',
        },
        error_code='safe_document_code',
        error_detail='PRIVATE_DOCUMENT_ERROR_DETAIL',
    )
    ExamSourcePage.objects.create(
        document=document,
        page_number=1,
        display_order=1,
        rendered_file='exam-prep-v4/source/pages/PRIVATE_RENDER_KEY.png',
        thumbnail_file='exam-prep-v4/source/thumbnails/PRIVATE_THUMB_KEY.jpg',
        width=1000,
        height=1400,
        sha256='c' * 64,
        perceptual_hash='PRIVATE_PERCEPTUAL_HASH',
        native_text_sample='PRIVATE_NATIVE_TEXT_SAMPLE',
        native_text_length=999,
        predicted_role=ExamSourceRole.COVER,
        predicted_confidence=Decimal('0.9900'),
        classification_metadata={
            'reason': 'PRIVATE_CLASSIFIER_REASON',
            'printedNumbers': ['PRIVATE_PRINTED_NUMBER'],
        },
    )
    first_question_page = ExamSourcePage.objects.create(
        document=document,
        page_number=2,
        display_order=3,
        rendered_file='exam-prep-v4/source/pages/PRIVATE_RENDER_2.png',
        thumbnail_file='exam-prep-v4/source/thumbnails/PRIVATE_THUMB_2.jpg',
        width=1000,
        height=1400,
        sha256='d' * 64,
        native_text_sample='PRIVATE_NATIVE_TEXT_2',
        predicted_role=ExamSourceRole.ANSWER_SOLUTIONS,
        predicted_confidence=Decimal('0.7000'),
        teacher_role=ExamSourceRole.QUESTIONS,
        orientation=90,
    )
    ExamSourcePage.objects.create(
        document=document,
        page_number=3,
        display_order=2,
        rendered_file='exam-prep-v4/source/pages/PRIVATE_RENDER_3.png',
        thumbnail_file='exam-prep-v4/source/thumbnails/PRIVATE_THUMB_3.jpg',
        width=1000,
        height=1400,
        sha256='d' * 64,
        duplicate_of=first_question_page,
        predicted_role=ExamSourceRole.QUESTIONS,
        predicted_confidence=Decimal('0.8800'),
    )

    ExamSourceSegment.objects.create(
        document=document,
        revision=1,
        order=0,
        start_page=1,
        end_page=3,
        role=ExamSourceRole.IGNORED,
        predicted_role=ExamSourceRole.IGNORED,
        predicted_confidence=Decimal('0.1000'),
        fingerprint='PRIVATE_STALE_FINGERPRINT',
        metadata={'raw': 'PRIVATE_STALE_METADATA'},
    )
    current_cover = ExamSourceSegment.objects.create(
        document=document,
        revision=2,
        order=0,
        start_page=1,
        end_page=1,
        role=ExamSourceRole.COVER,
        predicted_role=ExamSourceRole.COVER,
        predicted_confidence=Decimal('0.9900'),
        section_key='PRIVATE_SECTION_KEY',
        fingerprint='PRIVATE_SEGMENT_FINGERPRINT',
        metadata={
            'raw': 'PRIVATE_SEGMENT_METADATA',
            'pageNumbers': [1],
            'displayOrderStart': 1,
            'displayOrderEnd': 1,
        },
        error_detail='PRIVATE_SEGMENT_ERROR_DETAIL',
    )
    current_questions = ExamSourceSegment.objects.create(
        document=document,
        revision=2,
        order=1,
        start_page=3,
        end_page=2,
        role=ExamSourceRole.QUESTIONS,
        predicted_role=ExamSourceRole.UNKNOWN,
        predicted_confidence=Decimal('0.7900'),
        teacher_confirmed=True,
        expected_number_start=1,
        expected_number_end=20,
        metadata={
            'pageNumbers': [3, 2],
            'displayOrderStart': 2,
            'displayOrderEnd': 3,
            'raw': 'PRIVATE_QUESTIONS_METADATA',
        },
    )
    return project, document, current_cover, current_questions


def _all_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for nested in value.values():
            keys.update(_all_keys(nested))
        return keys
    if isinstance(value, list):
        keys = set()
        for nested in value:
            keys.update(_all_keys(nested))
        return keys
    return set()


def test_list_requires_authentication(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    response = APIClient().get(LIST_URL)
    assert response.status_code == 401


def test_student_cannot_read_teacher_projects(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    response = _client(_user('STUDENT')).get(LIST_URL)
    assert response.status_code == 403


def test_list_and_detail_are_hidden_when_v4_is_disabled(settings):
    settings.EXAM_PREP_V4_ENABLED = False
    teacher = _user()
    project = _project(teacher)
    client = _client(teacher)
    assert client.get(LIST_URL).status_code == 404
    assert client.get(_detail_url(project.id)).status_code == 404


def test_list_returns_only_current_teachers_projects_in_updated_order(
    settings,
    django_assert_num_queries,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    other = _user()
    older = _project(teacher, title='قدیمی')
    newer = _project(teacher, title='جدید')
    _project(other, title='نباید دیده شود')
    ExamSourceDocument.objects.create(project=newer, original_name='private.pdf')
    ExamProject.objects.filter(id=older.id).update(updated_at='2026-08-01T00:00:00Z')
    ExamProject.objects.filter(id=newer.id).update(updated_at='2026-08-02T00:00:00Z')

    with django_assert_num_queries(2):
        response = _client(teacher).get(LIST_URL)

    assert response.status_code == 200
    assert response.data['count'] == 2
    assert [item['id'] for item in response.data['results']] == [newer.id, older.id]
    assert response.data['results'][0]['documentCount'] == 1
    assert all(item['title'] != 'نباید دیده شود' for item in response.data['results'])


def test_list_does_not_expose_scope_ids_or_private_project_fields(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    project, _document, _segment1, _segment2 = _build_sensitive_source_map(teacher)
    response = _client(teacher).get(LIST_URL)

    assert response.status_code == 200
    item = response.data['results'][0]
    assert item['id'] == project.id
    keys = _all_keys(response.data)
    assert 'organizationId' not in keys
    assert 'studyGroupId' not in keys
    assert 'clientRequestId' not in keys
    assert 'workflowState' not in keys
    assert 'errorDetail' not in keys
    rendered = json.dumps(response.data, ensure_ascii=False, default=str)
    assert 'PRIVATE_WORKFLOW_MESSAGE' not in rendered
    assert 'PRIVATE_PROJECT_ERROR_DETAIL' not in rendered
    assert 'PRIVATE_ORGANIZATION_NAME' not in rendered
    assert 'PRIVATE_STUDY_GROUP_NAME' not in rendered


def test_other_teacher_receives_404_for_project_detail(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    owner = _user()
    attacker = _user()
    project = _project(owner)
    response = _client(attacker).get(_detail_url(project.id))
    assert response.status_code == 404


def test_detail_returns_safe_source_map_in_virtual_order(
    settings,
    django_assert_num_queries,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    project, document, current_cover, current_questions = _build_sensitive_source_map(
        teacher
    )

    with django_assert_num_queries(4):
        response = _client(teacher).get(_detail_url(project.id))

    assert response.status_code == 200
    assert response.data['id'] == project.id
    assert response.data['revision'] == 3
    assert response.data['documentCount'] == 1
    assert response.data['progress'] == {
        'stage': 'awaiting_source_confirmation',
        'progressPercent': 20,
        'warningCount': 2,
    }

    source = response.data['documents'][0]
    assert source['id'] == document.id
    assert source['pageCount'] == 3
    assert source['classificationRevision'] == 2
    assert source['hasClassification'] is True
    assert source['issueCount'] == 2
    assert source['issues'] == [
        {'code': 'missing_page_prediction', 'pageNumber': 2},
        {'code': 'unknown', 'pageNumber': None},
    ]
    assert [page['pageNumber'] for page in source['pages']] == [1, 3, 2]
    assert [page['displayOrder'] for page in source['pages']] == [1, 2, 3]
    by_number = {page['pageNumber']: page for page in source['pages']}
    assert by_number[1]['effectiveRole'] == ExamSourceRole.COVER
    assert by_number[1]['hasThumbnail'] is True
    assert by_number[2]['predictedRole'] == ExamSourceRole.ANSWER_SOLUTIONS
    assert by_number[2]['teacherRole'] == ExamSourceRole.QUESTIONS
    assert by_number[2]['effectiveRole'] == ExamSourceRole.QUESTIONS
    assert by_number[2]['orientation'] == 90
    assert by_number[3]['isDuplicate'] is True

    assert [segment['id'] for segment in source['segments']] == [
        current_cover.id,
        current_questions.id,
    ]
    assert all(segment['revision'] == 2 for segment in source['segments'])
    assert source['segments'][1]['startPage'] == 3
    assert source['segments'][1]['endPage'] == 2
    assert source['segments'][1]['displayOrderStart'] == 2
    assert source['segments'][1]['displayOrderEnd'] == 3
    assert source['segments'][1]['pageNumbers'] == [3, 2]
    assert source['segments'][1]['expectedNumberStart'] == 1
    assert source['segments'][1]['expectedNumberEnd'] == 20
    assert source['segments'][1]['teacherConfirmed'] is True


def test_detail_response_contains_no_private_content_or_storage_identifiers(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    project, _document, _segment1, _segment2 = _build_sensitive_source_map(teacher)
    response = _client(teacher).get(_detail_url(project.id))

    assert response.status_code == 200
    keys = _all_keys(response.data)
    forbidden_keys = {
        'originalName',
        'mimeType',
        'sourceFile',
        'sourceSha256',
        'byteSize',
        'classificationFingerprint',
        'classificationMetadata',
        'nativeTextSample',
        'nativeTextLength',
        'sha256',
        'perceptualHash',
        'renderedFile',
        'thumbnailFile',
        'duplicateOf',
        'reason',
        'detail',
        'fingerprint',
        'metadata',
        'sectionKey',
        'errorDetail',
        'organizationId',
        'studyGroupId',
    }
    assert keys.isdisjoint(forbidden_keys)

    rendered = json.dumps(response.data, ensure_ascii=False, default=str)
    for secret in (
        'PRIVATE_SOURCE_FILENAME',
        'PRIVATE_STORAGE_KEY',
        'PRIVATE_RENDER_KEY',
        'PRIVATE_THUMB_KEY',
        'PRIVATE_NATIVE_TEXT',
        'PRIVATE_CLASSIFIER_REASON',
        'PRIVATE_PRINTED_NUMBER',
        'PRIVATE_ISSUE_DETAIL',
        'PRIVATE_DOCUMENT_RAW_PAYLOAD',
        'PRIVATE_MODEL_NAME',
        'PRIVATE_PROJECT_ERROR_DETAIL',
        'PRIVATE_DOCUMENT_ERROR_DETAIL',
        'PRIVATE_SECTION_KEY',
        'PRIVATE_SEGMENT_FINGERPRINT',
        'PRIVATE_SEGMENT_METADATA',
        'PRIVATE_QUESTIONS_METADATA',
        'PRIVATE_SEGMENT_ERROR_DETAIL',
        'PRIVATE_ORGANIZATION_NAME',
        'PRIVATE_STUDY_GROUP_NAME',
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    ):
        assert secret not in rendered


def test_detail_with_no_documents_returns_empty_source_map(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    project = _project(teacher)
    response = _client(teacher).get(_detail_url(project.id))
    assert response.status_code == 200
    assert response.data['documentCount'] == 0
    assert response.data['documents'] == []


def test_rendered_unknown_pages_are_not_exposed_as_source_map_before_classification(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    project = _project(teacher, status=ExamProject.Status.CLASSIFYING)
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='private.pdf',
        page_count=2,
        status=ExamSourceDocument.Status.CLASSIFYING,
        classification_fingerprint='',
    )
    for page_number in (1, 2):
        ExamSourcePage.objects.create(
            document=document,
            page_number=page_number,
            display_order=page_number,
            predicted_role=ExamSourceRole.UNKNOWN,
            predicted_confidence=Decimal('0.0000'),
        )

    response = _client(teacher).get(_detail_url(project.id))

    assert response.status_code == 200
    source = response.data['documents'][0]
    assert source['hasClassification'] is False
    assert source['hasSourceMap'] is False
    assert source['sourceMapFingerprint'] is None
    assert len(source['pages']) == 2


def test_nonexistent_project_returns_404(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    response = _client(_user()).get(_detail_url(999999))
    assert response.status_code == 404
