from copy import deepcopy
from decimal import Decimal

import pytest
from model_bakery import baker

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
from apps.classes.services.exam_prep_v4_source_map_mutation import (
    SourceMapFingerprintConflict,
    SourceMapMutationError,
    SourceMapNotConfirmable,
    StaleSourceMapRevision,
    confirm_teacher_source_map,
    mutate_teacher_source_map,
)


pytestmark = pytest.mark.django_db


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _build_map(*, unknown_page: bool = False):
    teacher = _teacher()
    project = ExamProject.objects.create(
        teacher=teacher,
        title='آزمون',
        revision=4,
        status=ExamProject.Status.AWAITING_SOURCE_CONFIRMATION,
        reviewed_revision=3,
        reviewed_projection_fingerprint='f' * 64,
    )
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='private.pdf',
        page_count=4,
        status=ExamSourceDocument.Status.AWAITING_CONFIRMATION,
        classification_revision=2,
        classification_fingerprint='a' * 64,
        classification_metadata={
            'issues': [{'code': 'missing_page_prediction', 'pageNumber': 2}],
            'issueCount': 1,
            'segmentCount': 3,
        },
    )
    roles = [
        ExamSourceRole.COVER,
        ExamSourceRole.UNKNOWN if unknown_page else ExamSourceRole.QUESTIONS,
        ExamSourceRole.QUESTIONS,
        ExamSourceRole.ANSWER_SOLUTIONS,
    ]
    for number, role in enumerate(roles, start=1):
        ExamSourcePage.objects.create(
            document=document,
            page_number=number,
            display_order=number,
            predicted_role=role,
            predicted_confidence=Decimal('0.8000'),
            classification_metadata={'printedNumbers': [str(number)]},
        )
    segments = [
        (1, 1, ExamSourceRole.COVER),
        (2, 3, ExamSourceRole.UNKNOWN if unknown_page else ExamSourceRole.QUESTIONS),
        (4, 4, ExamSourceRole.ANSWER_SOLUTIONS),
    ]
    for order, (start, end, role) in enumerate(segments):
        page_numbers = list(range(start, end + 1))
        ExamSourceSegment.objects.create(
            document=document,
            revision=2,
            order=order,
            start_page=start,
            end_page=end,
            role=role,
            predicted_role=role,
            predicted_confidence=Decimal('0.8000'),
            status=ExamSourceSegment.Status.PROPOSED,
            metadata={
                'pageNumbers': page_numbers,
                'displayOrderStart': start,
                'displayOrderEnd': end,
                'physicalContiguous': True,
            },
        )
    return teacher, project, document


def _current_payload(document):
    return [
        {
            'pageNumber': page.page_number,
            'displayOrder': page.display_order,
            'role': page.effective_role,
            'orientation': page.orientation,
        }
        for page in document.pages.order_by('display_order', 'page_number')
    ]


def _edited_payload(document):
    payload = _current_payload(document)
    by_page = {item['pageNumber']: item for item in payload}
    by_page[2]['role'] = ExamSourceRole.ANSWER_KEY
    by_page[3]['orientation'] = 90
    return payload


def _reordered_payload(document):
    payload = _current_payload(document)
    desired_order = [1, 3, 2, 4]
    by_page = {item['pageNumber']: item for item in payload}
    for display_order, page_number in enumerate(desired_order, start=1):
        by_page[page_number]['displayOrder'] = display_order
    return list(by_page.values())


def test_noop_map_is_idempotent_without_revision_increment():
    teacher, project, document = _build_map()

    result = mutate_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        pages=_current_payload(document),
    )

    document.refresh_from_db()
    project.refresh_from_db()
    assert result.reused is True
    assert result.revision == 2
    assert len(result.fingerprint) == 64
    assert document.classification_revision == 2
    assert project.revision == 4
    assert document.segments.count() == 3


def test_mutation_creates_revision_preserves_predictions_and_supersedes_history():
    teacher, project, document = _build_map()
    payload = _edited_payload(document)

    result = mutate_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        pages=payload,
    )

    document.refresh_from_db()
    project.refresh_from_db()
    pages = list(document.pages.order_by('page_number'))
    assert result.reused is False
    assert result.revision == 3
    assert result.fingerprint == document.source_map_fingerprint
    assert document.classification_fingerprint == ''
    assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
    assert document.teacher_confirmed_at is None
    assert document.teacher_confirmed_revision is None
    assert document.teacher_confirmed_fingerprint == ''

    assert pages[1].predicted_role == ExamSourceRole.QUESTIONS
    assert pages[1].teacher_role == ExamSourceRole.ANSWER_KEY
    assert pages[1].effective_role == ExamSourceRole.ANSWER_KEY
    assert pages[2].teacher_role == ''
    assert pages[2].orientation == 90
    assert [page.display_order for page in pages] == [1, 2, 3, 4]

    old_segments = list(document.segments.filter(revision=2).order_by('order'))
    assert len(old_segments) == 3
    assert all(segment.status == ExamSourceSegment.Status.SUPERSEDED for segment in old_segments)
    assert all(segment.metadata['supersededByRevision'] == 3 for segment in old_segments)

    new_segments = list(document.segments.filter(revision=3).order_by('order'))
    assert [
        (segment.start_page, segment.end_page, segment.role)
        for segment in new_segments
    ] == [
        (1, 1, ExamSourceRole.COVER),
        (2, 2, ExamSourceRole.ANSWER_KEY),
        (3, 3, ExamSourceRole.QUESTIONS),
        (4, 4, ExamSourceRole.ANSWER_SOLUTIONS),
    ]
    assert all(segment.fingerprint == result.fingerprint for segment in new_segments)

    history = document.classification_metadata['sourceMapHistory']
    assert history[-1]['revision'] == 2
    assert history[-1]['pages'][1] == {
        'pageNumber': 2,
        'displayOrder': 2,
        'role': ExamSourceRole.QUESTIONS,
        'orientation': 0,
    }
    assert project.revision == 5
    assert project.status == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    assert project.reviewed_revision is None
    assert project.reviewed_projection_fingerprint == ''


def test_virtual_reorder_preserves_physical_identity_and_builds_virtual_segments():
    teacher, project, document = _build_map()
    original_ids = dict(document.pages.values_list('page_number', 'id'))
    original_fingerprint = source_map_fingerprint(
        _current_payload(document),
        page_count=4,
    )

    result = mutate_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        pages=_reordered_payload(document),
    )

    document.refresh_from_db()
    virtual_pages = list(document.pages.order_by('display_order'))
    assert result.reused is False
    assert result.revision == 3
    assert result.fingerprint != original_fingerprint
    assert [page.page_number for page in virtual_pages] == [1, 3, 2, 4]
    assert [page.display_order for page in virtual_pages] == [1, 2, 3, 4]
    assert dict(document.pages.values_list('page_number', 'id')) == original_ids

    segments = list(document.segments.filter(revision=3).order_by('order'))
    assert [
        (segment.start_page, segment.end_page, segment.role)
        for segment in segments
    ] == [
        (1, 1, ExamSourceRole.COVER),
        (3, 2, ExamSourceRole.QUESTIONS),
        (4, 4, ExamSourceRole.ANSWER_SOLUTIONS),
    ]
    assert segments[1].metadata['pageNumbers'] == [3, 2]
    assert segments[1].metadata['displayOrderStart'] == 2
    assert segments[1].metadata['displayOrderEnd'] == 3
    assert segments[1].metadata['physicalContiguous'] is True

    history = document.classification_metadata['sourceMapHistory'][-1]
    assert [item['pageNumber'] for item in history['pages']] == [1, 2, 3, 4]
    assert [item['displayOrder'] for item in history['pages']] == [1, 2, 3, 4]


def test_reordered_map_can_be_confirmed_against_virtual_segments():
    teacher, project, document = _build_map()
    mutation = mutate_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        pages=_reordered_payload(document),
    )

    confirmation = confirm_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=mutation.revision,
        expected_fingerprint=mutation.fingerprint,
    )

    document.refresh_from_db()
    assert confirmation.confirmed is True
    assert document.status == ExamSourceDocument.Status.CONFIRMED
    assert document.teacher_confirmed_revision == 3
    assert all(
        segment.teacher_confirmed
        for segment in document.segments.filter(revision=3)
    )


def test_immediate_network_retry_with_previous_revision_reuses_new_map():
    teacher, project, document = _build_map()
    payload = _reordered_payload(document)
    first = mutate_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        pages=payload,
    )

    retry = mutate_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        pages=payload,
    )

    document.refresh_from_db()
    assert first.revision == retry.revision == 3
    assert retry.reused is True
    assert document.segments.filter(revision=3).count() == 3
    assert document.segments.filter(revision=4).count() == 0


def test_stale_revision_with_different_map_fails_without_writes():
    teacher, project, document = _build_map()
    before = deepcopy(_current_payload(document))

    with pytest.raises(StaleSourceMapRevision):
        mutate_teacher_source_map(
            teacher=teacher,
            project_id=project.id,
            document_id=document.id,
            expected_revision=1,
            pages=_reordered_payload(document),
        )

    document.refresh_from_db()
    assert document.classification_revision == 2
    assert _current_payload(document) == before
    assert document.segments.filter(revision=2).count() == 3
    assert document.segments.filter(revision=3).count() == 0


@pytest.mark.parametrize(
    'payload_transform',
    [
        lambda payload: payload[:-1],
        lambda payload: [*payload, deepcopy(payload[0])],
        lambda payload: [
            {**item, 'displayOrder': 1 if item['pageNumber'] == 2 else item['displayOrder']}
            for item in payload
        ],
        lambda payload: [
            {**item, 'displayOrder': 9 if item['pageNumber'] == 2 else item['displayOrder']}
            for item in payload
        ],
    ],
)
def test_incomplete_duplicate_or_invalid_virtual_map_is_rejected(payload_transform):
    teacher, project, document = _build_map()
    payload = payload_transform(_current_payload(document))

    with pytest.raises(SourceMapMutationError):
        mutate_teacher_source_map(
            teacher=teacher,
            project_id=project.id,
            document_id=document.id,
            expected_revision=2,
            pages=payload,
        )

    document.refresh_from_db()
    assert document.classification_revision == 2
    assert [
        page.display_order for page in document.pages.order_by('page_number')
    ] == [1, 2, 3, 4]


def test_other_teacher_cannot_mutate_document():
    owner, project, document = _build_map()
    attacker = _teacher()

    with pytest.raises(ExamProject.DoesNotExist):
        mutate_teacher_source_map(
            teacher=attacker,
            project_id=project.id,
            document_id=document.id,
            expected_revision=2,
            pages=_reordered_payload(document),
        )


def test_mutation_rolls_back_reorder_and_superseded_segments_on_failure(monkeypatch):
    teacher, project, document = _build_map()
    original_bulk_create = ExamSourceSegment.objects.bulk_create

    def fail_bulk_create(*args, **kwargs):
        raise RuntimeError('simulated segment persistence failure')

    monkeypatch.setattr(ExamSourceSegment.objects, 'bulk_create', fail_bulk_create)
    with pytest.raises(RuntimeError, match='simulated segment persistence failure'):
        mutate_teacher_source_map(
            teacher=teacher,
            project_id=project.id,
            document_id=document.id,
            expected_revision=2,
            pages=_reordered_payload(document),
        )
    monkeypatch.setattr(ExamSourceSegment.objects, 'bulk_create', original_bulk_create)

    document.refresh_from_db()
    pages = list(document.pages.order_by('page_number'))
    segments = list(document.segments.filter(revision=2).order_by('order'))
    assert document.classification_revision == 2
    assert [page.display_order for page in pages] == [1, 2, 3, 4]
    assert pages[1].teacher_role == ''
    assert pages[2].orientation == 0
    assert all(segment.status == ExamSourceSegment.Status.PROPOSED for segment in segments)
    assert document.segments.filter(revision=3).count() == 0


def test_confirmation_binds_current_revision_and_fingerprint():
    teacher, project, document = _build_map()
    payload = _current_payload(document)
    fingerprint = source_map_fingerprint(payload, page_count=4)

    result = confirm_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        expected_fingerprint=fingerprint,
    )

    document.refresh_from_db()
    project.refresh_from_db()
    assert result.confirmed is True
    assert result.reused is False
    assert document.status == ExamSourceDocument.Status.CONFIRMED
    assert document.teacher_confirmed_by_id == teacher.id
    assert document.teacher_confirmed_revision == 2
    assert document.teacher_confirmed_fingerprint == fingerprint
    assert document.source_map_fingerprint == fingerprint
    assert all(
        segment.status == ExamSourceSegment.Status.CONFIRMED
        and segment.teacher_confirmed
        for segment in document.segments.filter(revision=2)
    )
    assert project.status == ExamProject.Status.SEGMENTING
    assert project.workflow_state['stage'] == 'source_map_confirmed'


def test_confirmation_is_idempotent_for_same_revision_and_fingerprint():
    teacher, project, document = _build_map()
    fingerprint = source_map_fingerprint(_current_payload(document), page_count=4)
    first = confirm_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        expected_fingerprint=fingerprint,
    )
    confirmed_at = ExamSourceDocument.objects.get(id=document.id).teacher_confirmed_at

    second = confirm_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        expected_fingerprint=fingerprint,
    )

    document.refresh_from_db()
    assert first.reused is False
    assert second.reused is True
    assert document.teacher_confirmed_at == confirmed_at


def test_confirmation_rejects_unknown_page_role():
    teacher, project, document = _build_map(unknown_page=True)
    fingerprint = source_map_fingerprint(_current_payload(document), page_count=4)

    with pytest.raises(SourceMapNotConfirmable):
        confirm_teacher_source_map(
            teacher=teacher,
            project_id=project.id,
            document_id=document.id,
            expected_revision=2,
            expected_fingerprint=fingerprint,
        )

    document.refresh_from_db()
    assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
    assert document.teacher_confirmed_at is None


def test_confirmation_rejects_stale_revision_or_fingerprint_without_writes():
    teacher, project, document = _build_map()
    fingerprint = source_map_fingerprint(_current_payload(document), page_count=4)

    with pytest.raises(StaleSourceMapRevision):
        confirm_teacher_source_map(
            teacher=teacher,
            project_id=project.id,
            document_id=document.id,
            expected_revision=1,
            expected_fingerprint=fingerprint,
        )
    with pytest.raises(SourceMapFingerprintConflict):
        confirm_teacher_source_map(
            teacher=teacher,
            project_id=project.id,
            document_id=document.id,
            expected_revision=2,
            expected_fingerprint='0' * 64,
        )

    document.refresh_from_db()
    assert document.teacher_confirmed_at is None
    assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION


def test_edit_after_confirmation_invalidates_confirmation():
    teacher, project, document = _build_map()
    fingerprint = source_map_fingerprint(_current_payload(document), page_count=4)
    confirm_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        expected_fingerprint=fingerprint,
    )

    result = mutate_teacher_source_map(
        teacher=teacher,
        project_id=project.id,
        document_id=document.id,
        expected_revision=2,
        pages=_reordered_payload(document),
    )

    document.refresh_from_db()
    assert result.revision == 3
    assert result.confirmed is False
    assert document.teacher_confirmed_at is None
    assert document.teacher_confirmed_by_id is None
    assert document.teacher_confirmed_revision is None
    assert document.teacher_confirmed_fingerprint == ''
    assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
