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
from apps.classes.services.exam_prep_v4_source_map_contract import (
    source_map_fingerprint,
)


pytestmark = pytest.mark.django_db


def _user(role='TEACHER'):
    return baker.make('accounts.User', role=role)


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _mutation_url(project_id, document_id):
    return (
        f'/api/classes/exam-prep-v4/projects/{project_id}/documents/'
        f'{document_id}/source-map/'
    )


def _confirm_url(project_id, document_id):
    return _mutation_url(project_id, document_id) + 'confirm/'


def _build_map(*, unknown=False):
    teacher = _user()
    project = ExamProject.objects.create(
        teacher=teacher,
        title='آزمون',
        status=ExamProject.Status.AWAITING_SOURCE_CONFIRMATION,
    )
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='PRIVATE_SOURCE_NAME.pdf',
        source_sha256='a' * 64,
        page_count=3,
        status=ExamSourceDocument.Status.AWAITING_CONFIRMATION,
        classification_revision=1,
        classification_fingerprint='b' * 64,
        error_detail='PRIVATE_ERROR_DETAIL',
    )
    roles = [
        ExamSourceRole.COVER,
        ExamSourceRole.UNKNOWN if unknown else ExamSourceRole.QUESTIONS,
        ExamSourceRole.ANSWER_SOLUTIONS,
    ]
    for number, role in enumerate(roles, start=1):
        ExamSourcePage.objects.create(
            document=document,
            page_number=number,
            predicted_role=role,
            predicted_confidence=Decimal('0.9000'),
            native_text_sample='PRIVATE_NATIVE_TEXT',
            sha256=str(number) * 64,
        )
        ExamSourceSegment.objects.create(
            document=document,
            revision=1,
            order=number - 1,
            start_page=number,
            end_page=number,
            role=role,
            predicted_role=role,
            predicted_confidence=Decimal('0.9000'),
            metadata={'private': 'PRIVATE_SEGMENT_METADATA'},
        )
    return teacher, project, document


def _payload(document):
    return {
        'expectedRevision': document.classification_revision,
        'pages': [
            {
                'pageNumber': page.page_number,
                'role': page.effective_role,
                'orientation': page.orientation,
            }
            for page in document.pages.order_by('page_number')
        ],
    }


def test_mutation_and_confirmation_are_hidden_when_v4_disabled(settings):
    settings.EXAM_PREP_V4_ENABLED = False
    teacher, project, document = _build_map()
    client = _client(teacher)

    assert client.put(
        _mutation_url(project.id, document.id),
        _payload(document),
        format='json',
    ).status_code == 404
    assert client.post(
        _confirm_url(project.id, document.id),
        {
            'expectedRevision': 1,
            'sourceMapFingerprint': '0' * 64,
        },
        format='json',
    ).status_code == 404


def test_student_cannot_mutate_or_confirm(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    _teacher, project, document = _build_map()
    client = _client(_user('STUDENT'))

    assert client.put(
        _mutation_url(project.id, document.id),
        _payload(document),
        format='json',
    ).status_code == 403
    assert client.post(
        _confirm_url(project.id, document.id),
        {'expectedRevision': 1, 'sourceMapFingerprint': '0' * 64},
        format='json',
    ).status_code == 403


def test_other_teacher_receives_404_for_mutation_and_confirmation(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    _owner, project, document = _build_map()
    client = _client(_user())

    assert client.put(
        _mutation_url(project.id, document.id),
        _payload(document),
        format='json',
    ).status_code == 404
    assert client.post(
        _confirm_url(project.id, document.id),
        {'expectedRevision': 1, 'sourceMapFingerprint': '0' * 64},
        format='json',
    ).status_code == 404


def test_owner_can_replace_complete_map_and_receives_safe_binding(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document = _build_map()
    payload = _payload(document)
    payload['pages'][1]['role'] = ExamSourceRole.ANSWER_KEY
    payload['pages'][2]['orientation'] = 180

    response = _client(teacher).put(
        _mutation_url(project.id, document.id),
        payload,
        format='json',
    )

    assert response.status_code == 200
    assert response.data['documentId'] == document.id
    assert response.data['classificationRevision'] == 2
    assert len(response.data['sourceMapFingerprint']) == 64
    assert response.data['status'] == ExamSourceDocument.Status.AWAITING_CONFIRMATION
    assert response.data['reused'] is False
    assert response.data['isTeacherConfirmed'] is False

    rendered = json.dumps(response.data, ensure_ascii=False)
    for secret in (
        'PRIVATE_SOURCE_NAME',
        'PRIVATE_NATIVE_TEXT',
        'PRIVATE_ERROR_DETAIL',
        'PRIVATE_SEGMENT_METADATA',
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    ):
        assert secret not in rendered


def test_mutation_requires_complete_unique_page_map(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document = _build_map()
    payload = _payload(document)
    payload['pages'] = payload['pages'][:-1]

    response = _client(teacher).put(
        _mutation_url(project.id, document.id),
        payload,
        format='json',
    )

    assert response.status_code == 400
    assert response.data['code'] == 'invalid_source_map'
    document.refresh_from_db()
    assert document.classification_revision == 1


def test_stale_mutation_returns_stable_409_code(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document = _build_map()
    payload = _payload(document)
    payload['expectedRevision'] = 999
    payload['pages'][1]['role'] = ExamSourceRole.ANSWER_KEY

    response = _client(teacher).put(
        _mutation_url(project.id, document.id),
        payload,
        format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'stale_source_map_revision'


def test_owner_can_confirm_exact_revision_and_confirmation_is_idempotent(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document = _build_map()
    page_map = _payload(document)['pages']
    fingerprint = source_map_fingerprint(page_map, page_count=3)
    payload = {
        'expectedRevision': 1,
        'sourceMapFingerprint': fingerprint,
    }

    first = _client(teacher).post(
        _confirm_url(project.id, document.id),
        payload,
        format='json',
    )
    second = _client(teacher).post(
        _confirm_url(project.id, document.id),
        payload,
        format='json',
    )

    assert first.status_code == second.status_code == 200
    assert first.data['isTeacherConfirmed'] is True
    assert first.data['reused'] is False
    assert second.data['reused'] is True
    assert second.data['sourceMapFingerprint'] == fingerprint


def test_confirmation_rejects_wrong_fingerprint_with_409(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document = _build_map()

    response = _client(teacher).post(
        _confirm_url(project.id, document.id),
        {
            'expectedRevision': 1,
            'sourceMapFingerprint': '0' * 64,
        },
        format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'source_map_fingerprint_conflict'


def test_confirmation_rejects_unknown_page_with_stable_code(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document = _build_map(unknown=True)
    fingerprint = source_map_fingerprint(_payload(document)['pages'], page_count=3)

    response = _client(teacher).post(
        _confirm_url(project.id, document.id),
        {
            'expectedRevision': 1,
            'sourceMapFingerprint': fingerprint,
        },
        format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'source_map_not_confirmable'
