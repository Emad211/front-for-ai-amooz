import json
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models.deletion import RestrictedError
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)
from apps.classes.models_v4_blocks import (
    ExamSourceBlock,
    ExamSourceBlockFragment,
    ExamSourceBlockKind,
)
from apps.classes.services.exam_prep_v4_blocks import (
    BlockFragmentProposal,
    InvalidBlockInput,
    SourceBlockProposal,
    SourceMapNotConfirmed,
    StaleBlockSourceMap,
    parse_block_detector_output,
    persist_source_blocks,
)


pytestmark = pytest.mark.django_db


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _blocks_url(project_id: int, document_id: int) -> str:
    return (
        f'/api/classes/exam-prep-v4/projects/{project_id}/documents/'
        f'{document_id}/blocks/'
    )


def _confirmed_map():
    teacher = _teacher()
    project = ExamProject.objects.create(
        teacher=teacher,
        title='Block fixture',
        status=ExamProject.Status.SEGMENTING,
    )
    fingerprint = 'a' * 64
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='private.pdf',
        page_count=4,
        status=ExamSourceDocument.Status.CONFIRMED,
        classification_revision=2,
        source_map_fingerprint=fingerprint,
        teacher_confirmed_at=timezone.now(),
        teacher_confirmed_by=teacher,
        teacher_confirmed_revision=2,
        teacher_confirmed_fingerprint=fingerprint,
    )
    roles = [
        ExamSourceRole.COVER,
        ExamSourceRole.QUESTIONS,
        ExamSourceRole.ANSWER_SOLUTIONS,
        ExamSourceRole.ANSWER_SOLUTIONS,
    ]
    for page_number, role in enumerate(roles, start=1):
        ExamSourcePage.objects.create(
            document=document,
            page_number=page_number,
            display_order=page_number,
            predicted_role=role,
            predicted_confidence=Decimal('0.9500'),
        )
    segments = []
    for order, (start, end, role, page_numbers) in enumerate(
        [
            (1, 1, ExamSourceRole.COVER, [1]),
            (2, 2, ExamSourceRole.QUESTIONS, [2]),
            (3, 4, ExamSourceRole.ANSWER_SOLUTIONS, [3, 4]),
        ]
    ):
        segments.append(
            ExamSourceSegment.objects.create(
                document=document,
                revision=2,
                order=order,
                start_page=start,
                end_page=end,
                role=role,
                predicted_role=role,
                predicted_confidence=Decimal('0.9500'),
                teacher_confirmed=True,
                fingerprint=fingerprint,
                status=ExamSourceSegment.Status.CONFIRMED,
                metadata={
                    'pageNumbers': page_numbers,
                    'displayOrderStart': start,
                    'displayOrderEnd': end,
                    'PRIVATE_SEGMENT_VALUE': 'must-not-leak',
                },
            )
        )
    return teacher, project, document, segments


def _fragment(
    order: int,
    page_number: int,
    *,
    y0: str = '0.100000',
    y1: str = '0.900000',
    continuation: bool = False,
):
    return BlockFragmentProposal(
        order=order,
        page_number=page_number,
        x0=Decimal('0.050000'),
        y0=Decimal(y0),
        x1=Decimal('0.950000'),
        y1=Decimal(y1),
        column_index=0,
        is_continuation=continuation,
        metadata={'PRIVATE_FRAGMENT_VALUE': 'must-not-leak'},
    )


def _proposals(*, changed: bool = False):
    return (
        SourceBlockProposal(
            order=0,
            segment_order=1,
            kind=ExamSourceBlockKind.QUESTION,
            printed_number='۱',
            confidence=0.97,
            fragments=(
                _fragment(
                    0,
                    2,
                    y0='0.120000' if changed else '0.100000',
                ),
            ),
            metadata={'PRIVATE_BLOCK_VALUE': 'must-not-leak'},
        ),
        SourceBlockProposal(
            order=1,
            segment_order=2,
            kind=ExamSourceBlockKind.ANSWER_SOLUTION,
            printed_number='1',
            confidence=0.96,
            fragments=(
                _fragment(0, 3, y0='0.200000', y1='0.980000'),
                _fragment(
                    1,
                    4,
                    y0='0.000000',
                    y1='0.350000',
                    continuation=True,
                ),
            ),
        ),
    )


def _persist(document, proposals=None):
    return persist_source_blocks(
        document_id=document.id,
        expected_source_map_revision=document.classification_revision,
        expected_source_map_fingerprint=document.source_map_fingerprint,
        proposals=proposals or _proposals(),
    )


def test_block_models_are_registered_under_classes_app():
    assert apps.get_model('classes', 'ExamSourceBlock') is ExamSourceBlock
    assert (
        apps.get_model('classes', 'ExamSourceBlockFragment')
        is ExamSourceBlockFragment
    )


def test_tolerant_detector_parser_keeps_valid_siblings_and_normalizes_digits():
    result = parse_block_detector_output(
        {
            'blocks': [
                {
                    'order': 0,
                    'segmentOrder': 1,
                    'kind': 'question',
                    'printedNumber': ' ۱ ',
                    'confidence': 0.9,
                    'fragments': [
                        {
                            'order': 0,
                            'pageNumber': 2,
                            'x0': 0.1,
                            'y0': 0.1,
                            'x1': 0.9,
                            'y1': 0.9,
                        }
                    ],
                },
                {
                    'order': 99,
                    'segmentOrder': 1,
                    'kind': 'question',
                    'fragments': [
                        {
                            'order': 0,
                            'pageNumber': 2,
                            'x0': 0.8,
                            'y0': 0.1,
                            'x1': 0.2,
                            'y1': 0.9,
                        }
                    ],
                },
                {
                    'order': 1,
                    'segmentOrder': 2,
                    'kind': 'answer_solution',
                    'printedNumber': '١',
                    'confidence': 0.8,
                    'fragments': [
                        {
                            'order': 0,
                            'pageNumber': 3,
                            'x0': 0,
                            'y0': 0,
                            'x1': 1,
                            'y1': 1,
                        }
                    ],
                },
            ]
        }
    )

    assert [block.order for block in result.blocks] == [0, 1]
    assert [block.printed_number for block in result.blocks] == ['1', '1']
    assert [issue.code for issue in result.issues] == ['invalid_block_record']


def test_persist_blocks_binds_fragments_to_confirmed_source_evidence():
    _teacher_user, project, document, _segments = _confirmed_map()

    result = _persist(document)

    project.refresh_from_db()
    blocks = list(
        ExamSourceBlock.objects.filter(document=document).order_by('order')
    )
    assert result.reused is False
    assert result.revision == 1
    assert result.block_count == 2
    assert result.fragment_count == 3
    assert len(result.set_fingerprint) == 64
    assert [block.kind for block in blocks] == [
        ExamSourceBlockKind.QUESTION,
        ExamSourceBlockKind.ANSWER_SOLUTION,
    ]
    assert blocks[0].printed_number == '1'
    assert [
        fragment.page.page_number
        for fragment in blocks[1].fragments.select_related('page').order_by('order')
    ] == [3, 4]
    assert blocks[1].fragments.get(order=1).is_continuation is True
    assert all(len(block.fingerprint) == 64 for block in blocks)
    assert project.status == ExamProject.Status.EXTRACTING_QUESTIONS
    assert project.workflow_state['stage'] == 'blocks_ready'


def test_continuation_candidate_links_only_to_earlier_block_in_same_revision():
    _teacher_user, _project, document, _segments = _confirmed_map()
    proposals = (
        _proposals()[0],
        SourceBlockProposal(
            order=1,
            segment_order=2,
            kind=ExamSourceBlockKind.ANSWER_SOLUTION,
            printed_number='1',
            confidence=0.9,
            fragments=(_fragment(0, 3),),
        ),
        SourceBlockProposal(
            order=2,
            segment_order=2,
            kind=ExamSourceBlockKind.CONTINUATION,
            confidence=0.8,
            continuation_of_order=1,
            fragments=(_fragment(0, 4, continuation=True),),
        ),
    )

    _persist(document, proposals)

    continuation = ExamSourceBlock.objects.get(document=document, order=2)
    assert continuation.continuation_of.order == 1
    assert continuation.continuation_of.revision == continuation.revision


def test_exact_block_set_retry_is_idempotent():
    _teacher_user, _project, document, _segments = _confirmed_map()
    first = _persist(document)
    second = _persist(document)

    assert first.revision == second.revision == 1
    assert second.reused is True
    assert ExamSourceBlock.objects.filter(document=document).count() == 2
    assert ExamSourceBlockFragment.objects.filter(block__document=document).count() == 3


def test_changed_block_set_supersedes_previous_revision_without_deleting_history():
    _teacher_user, _project, document, _segments = _confirmed_map()
    first = _persist(document)
    second = _persist(document, _proposals(changed=True))

    assert first.revision == 1
    assert second.revision == 2
    assert ExamSourceBlock.objects.filter(
        document=document,
        revision=1,
        status=ExamSourceBlock.Status.SUPERSEDED,
    ).count() == 2
    assert ExamSourceBlock.objects.filter(
        document=document,
        revision=2,
        status=ExamSourceBlock.Status.ACCEPTED,
    ).count() == 2


def test_unconfirmed_or_stale_source_map_cannot_create_blocks():
    _teacher_user, _project, document, _segments = _confirmed_map()
    document.teacher_confirmed_at = None
    document.save(update_fields=['teacher_confirmed_at', 'updated_at'])

    with pytest.raises(SourceMapNotConfirmed):
        _persist(document)

    document.teacher_confirmed_at = timezone.now()
    document.save(update_fields=['teacher_confirmed_at', 'updated_at'])
    with pytest.raises(StaleBlockSourceMap):
        persist_source_blocks(
            document_id=document.id,
            expected_source_map_revision=1,
            expected_source_map_fingerprint=document.source_map_fingerprint,
            proposals=_proposals(),
        )
    assert not ExamSourceBlock.objects.filter(document=document).exists()


def test_cross_segment_page_and_incompatible_kind_are_rejected_before_writes():
    _teacher_user, _project, document, _segments = _confirmed_map()
    cross_page = (
        SourceBlockProposal(
            order=0,
            segment_order=1,
            kind=ExamSourceBlockKind.QUESTION,
            fragments=(_fragment(0, 3),),
        ),
    )
    with pytest.raises(InvalidBlockInput, match='current segment'):
        _persist(document, cross_page)

    wrong_kind = (
        SourceBlockProposal(
            order=0,
            segment_order=1,
            kind=ExamSourceBlockKind.ANSWER_SOLUTION,
            fragments=(_fragment(0, 2),),
        ),
    )
    with pytest.raises(InvalidBlockInput, match='incompatible'):
        _persist(document, wrong_kind)
    assert not ExamSourceBlock.objects.filter(document=document).exists()


def test_replacement_failure_rolls_back_supersession_and_new_rows(monkeypatch):
    _teacher_user, project, document, _segments = _confirmed_map()
    _persist(document)
    original_status = project.status

    def fail_bulk_create(*args, **kwargs):
        raise RuntimeError('simulated fragment persistence failure')

    monkeypatch.setattr(
        ExamSourceBlockFragment.objects,
        'bulk_create',
        fail_bulk_create,
    )
    with pytest.raises(RuntimeError, match='simulated fragment persistence failure'):
        _persist(document, _proposals(changed=True))

    project.refresh_from_db()
    assert project.status == original_status
    assert ExamSourceBlock.objects.filter(
        document=document,
        revision=1,
        status=ExamSourceBlock.Status.ACCEPTED,
    ).count() == 2
    assert not ExamSourceBlock.objects.filter(document=document, revision=2).exists()


def test_database_rejects_invalid_fragment_bbox():
    _teacher_user, _project, document, segments = _confirmed_map()
    block = ExamSourceBlock.objects.create(
        document=document,
        segment=segments[1],
        revision=1,
        order=0,
        kind=ExamSourceBlockKind.QUESTION,
        source_map_fingerprint=document.source_map_fingerprint,
        set_fingerprint='b' * 64,
        fingerprint='c' * 64,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExamSourceBlockFragment.objects.create(
                block=block,
                page=document.pages.get(page_number=2),
                order=0,
                x0=Decimal('0.800000'),
                y0=Decimal('0.100000'),
                x1=Decimal('0.200000'),
                y1=Decimal('0.900000'),
            )


def test_evidence_page_is_restricted_individually_but_project_delete_cascades():
    _teacher_user, project, document, _segments = _confirmed_map()
    _persist(document)
    page = document.pages.get(page_number=2)

    with pytest.raises(RestrictedError):
        page.delete()

    project.delete()
    assert not ExamSourceBlock.objects.exists()
    assert not ExamSourceBlockFragment.objects.exists()


def test_safe_block_endpoint_is_owner_scoped_and_excludes_private_metadata(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document, _segments = _confirmed_map()
    _persist(document)

    response = _client(teacher).get(_blocks_url(project.id, document.id))

    assert response.status_code == 200
    assert response.data['blockRevision'] == 1
    assert response.data['blockCount'] == 2
    assert response.data['blocks'][0]['printedNumber'] == '1'
    assert response.data['blocks'][1]['fragments'][1]['pageNumber'] == 4
    assert response.data['blocks'][1]['fragments'][1]['isContinuation'] is True
    rendered = json.dumps(response.data, ensure_ascii=False, default=str)
    for forbidden in (
        'PRIVATE_BLOCK_VALUE',
        'PRIVATE_FRAGMENT_VALUE',
        'PRIVATE_SEGMENT_VALUE',
        'sourceMapFingerprint',
        'setFingerprint',
        'fingerprint',
        'metadata',
        'errorDetail',
    ):
        assert forbidden not in rendered

    outsider = _teacher()
    assert (
        _client(outsider).get(_blocks_url(project.id, document.id)).status_code
        == 404
    )


def test_safe_block_endpoint_returns_empty_current_set(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document, _segments = _confirmed_map()

    response = _client(teacher).get(_blocks_url(project.id, document.id))

    assert response.status_code == 200
    assert response.data == {
        'documentId': document.id,
        'sourceMapRevision': 2,
        'blockRevision': None,
        'blockCount': 0,
        'blocks': [],
    }
