import pytest
from django.db import IntegrityError
from model_bakery import baker

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)
from apps.classes.services.exam_prep_v4_classification import (
    ClassificationFingerprintConflict,
    InvalidClassificationInput,
    PagePrediction,
    StaleClassificationRevision,
    build_segment_proposals,
    normalize_printed_number,
    parse_page_predictions,
    persist_classification_result,
)


pytestmark = pytest.mark.django_db


def _document(*, page_count=5):
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(teacher=teacher, title='آزمون')
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='exam.pdf',
        page_count=page_count,
    )
    return project, document


def _pages(pattern):
    return tuple(
        PagePrediction(
            page_number=page_number,
            display_order=page_number,
            role=role,
            confidence=confidence,
            predicted_role=role,
            predicted_confidence=confidence,
        )
        for page_number, role, confidence in pattern
    )


def test_printed_number_normalizes_persian_arabic_and_whitespace():
    assert normalize_printed_number(' ۱ ٢ 3 ') == '123'


def test_partial_invalid_output_keeps_valid_sibling_pages():
    result = parse_page_predictions(
        raw_output={
            'pages': [
                {
                    'page_number': 1,
                    'role': 'cover',
                    'confidence': 0.99,
                    'ignored_extra_key': 'allowed',
                },
                {'page_number': 2, 'role': 'not-a-real-role'},
                {
                    'page_number': 3,
                    'role': 'questions',
                    'confidence': 0.91,
                    'printed_numbers': ['۱', '2'],
                },
            ]
        },
        page_count=3,
    )

    assert [page.role for page in result.pages] == [
        ExamSourceRole.COVER,
        ExamSourceRole.UNKNOWN,
        ExamSourceRole.QUESTIONS,
    ]
    assert [page.display_order for page in result.pages] == [1, 2, 3]
    assert result.pages[2].printed_numbers == ('1', '2')
    assert {issue.code for issue in result.issues} == {
        'invalid_page_record',
        'missing_page_prediction',
    }


def test_missing_pages_are_explicit_unknown_records():
    result = parse_page_predictions(
        raw_output={'pages': [{'page_number': 2, 'role': 'questions'}]},
        page_count=4,
    )

    assert [page.page_number for page in result.pages] == [1, 2, 3, 4]
    assert [page.display_order for page in result.pages] == [1, 2, 3, 4]
    assert [page.role for page in result.pages] == [
        'unknown',
        'questions',
        'unknown',
        'unknown',
    ]
    assert sum(issue.code == 'missing_page_prediction' for issue in result.issues) == 3


def test_duplicate_page_prediction_keeps_higher_confidence_record():
    result = parse_page_predictions(
        raw_output={
            'pages': [
                {'page_number': 1, 'role': 'cover', 'confidence': 0.3},
                {'page_number': 1, 'role': 'questions', 'confidence': 0.9},
            ]
        },
        page_count=1,
    )

    assert result.pages[0].role == ExamSourceRole.QUESTIONS
    assert result.pages[0].confidence == 0.9
    assert [issue.code for issue in result.issues] == ['duplicate_page_prediction']


def test_out_of_range_record_is_reported_not_added():
    result = parse_page_predictions(
        raw_output={'pages': [{'page_number': 8, 'role': 'questions'}]},
        page_count=2,
    )

    assert len(result.pages) == 2
    assert {issue.code for issue in result.issues} == {
        'page_out_of_range',
        'missing_page_prediction',
    }


def test_teacher_role_is_authoritative_without_erasing_prediction():
    result = parse_page_predictions(
        raw_output={
            'pages': [
                {'page_number': 1, 'role': 'answer_solutions', 'confidence': 0.8}
            ]
        },
        page_count=1,
        teacher_roles={1: 'cover'},
    )

    page = result.pages[0]
    assert page.role == ExamSourceRole.COVER
    assert page.source == 'teacher'
    assert page.confidence == 1.0
    assert page.predicted_role == ExamSourceRole.ANSWER_SOLUTIONS
    assert page.predicted_confidence == 0.8


def test_parser_preserves_explicit_complete_virtual_order():
    result = parse_page_predictions(
        raw_output={
            'pages': [
                {'page_number': 1, 'role': 'cover'},
                {'page_number': 2, 'role': 'questions'},
                {'page_number': 3, 'role': 'questions'},
            ]
        },
        page_count=3,
        display_orders={1: 1, 2: 3, 3: 2},
    )

    assert [page.display_order for page in result.pages] == [1, 3, 2]
    segments = build_segment_proposals(result.pages)
    assert segments[1].metadata['pageNumbers'] == [3, 2]
    assert segments[1].start_page == 3
    assert segments[1].end_page == 2


@pytest.mark.parametrize(
    ('pattern', 'expected'),
    [
        (
            [
                (1, 'cover', 0.99),
                *[(page, 'questions', 0.9) for page in range(2, 9)],
                *[(page, 'answer_solutions', 0.92) for page in range(9, 17)],
            ],
            [(1, 1, 'cover'), (2, 8, 'questions'), (9, 16, 'answer_solutions')],
        ),
        (
            [
                *[(page, 'answer_solutions', 0.9) for page in range(1, 12)],
                (12, 'cover', 0.99),
                *[(page, 'questions', 0.94) for page in range(13, 28)],
            ],
            [(1, 11, 'answer_solutions'), (12, 12, 'cover'), (13, 27, 'questions')],
        ),
        (
            [
                (1, 'cover', 0.99),
                *[(page, 'questions', 0.9) for page in range(2, 9)],
                *[(page, 'answer_solutions', 0.91) for page in range(9, 16)],
            ],
            [(1, 1, 'cover'), (2, 8, 'questions'), (9, 15, 'answer_solutions')],
        ),
    ],
    ids=['questions-first-a', 'answers-first-cover-middle', 'questions-first-c'],
)
def test_segment_builder_preserves_arbitrary_internal_order(pattern, expected):
    segments = build_segment_proposals(_pages(pattern))

    assert [
        (segment.start_page, segment.end_page, segment.role)
        for segment in segments
    ] == expected
    assert [segment.order for segment in segments] == list(range(len(expected)))


def test_segment_builder_rejects_non_total_page_map():
    with pytest.raises(InvalidClassificationInput, match='complete 1-based map'):
        build_segment_proposals(
            _pages([(1, 'cover', 1.0), (3, 'questions', 1.0)])
        )


def test_segment_builder_rejects_non_total_virtual_order():
    with pytest.raises(InvalidClassificationInput, match='Virtual page order'):
        build_segment_proposals(
            (
                PagePrediction(
                    page_number=1,
                    display_order=1,
                    role='cover',
                    confidence=1.0,
                ),
                PagePrediction(
                    page_number=2,
                    display_order=1,
                    role='questions',
                    confidence=1.0,
                ),
            )
        )


def test_segment_number_bounds_are_advisory_and_normalized():
    parsed = parse_page_predictions(
        raw_output={
            'pages': [
                {'page_number': 1, 'role': 'questions', 'printed_numbers': ['51', '۵۲']},
                {'page_number': 2, 'role': 'questions', 'printed_numbers': ['53', 'x']},
            ]
        },
        page_count=2,
    )
    segment = build_segment_proposals(parsed.pages)[0]

    assert segment.expected_number_start == 51
    assert segment.expected_number_end == 53


def test_persist_classification_creates_total_page_map_and_segments():
    project, document = _document(page_count=4)

    result = persist_classification_result(
        document_id=document.id,
        expected_revision=1,
        fingerprint='a' * 64,
        raw_output={
            'pages': [
                {'page_number': 1, 'role': 'cover', 'confidence': 0.99},
                {'page_number': 2, 'role': 'questions', 'confidence': 0.91},
                {'page_number': 4, 'role': 'answer_solutions', 'confidence': 0.89},
            ]
        },
    )

    document.refresh_from_db()
    project.refresh_from_db()
    assert result.reused is False
    assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
    assert document.classification_fingerprint == 'a' * 64
    assert document.pages.count() == 4
    assert [page.predicted_role for page in document.pages.order_by('page_number')] == [
        'cover',
        'questions',
        'unknown',
        'answer_solutions',
    ]
    assert [page.display_order for page in document.pages.order_by('page_number')] == [
        1, 2, 3, 4,
    ]
    assert [
        (segment.start_page, segment.end_page, segment.role)
        for segment in document.segments.order_by('order')
    ] == [
        (1, 1, 'cover'),
        (2, 2, 'questions'),
        (3, 3, 'unknown'),
        (4, 4, 'answer_solutions'),
    ]
    assert project.status == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    assert {issue.code for issue in result.issues} == {'missing_page_prediction'}


def test_persist_classification_respects_existing_teacher_page_override():
    _, document = _document(page_count=2)
    ExamSourcePage.objects.create(
        document=document,
        page_number=1,
        display_order=1,
        teacher_role=ExamSourceRole.COVER,
    )

    persist_classification_result(
        document_id=document.id,
        expected_revision=1,
        fingerprint='b' * 64,
        raw_output={
            'pages': [
                {'page_number': 1, 'role': 'answer_solutions', 'confidence': 0.95},
                {'page_number': 2, 'role': 'questions', 'confidence': 0.95},
            ]
        },
    )

    page = document.pages.get(page_number=1)
    assert page.teacher_role == ExamSourceRole.COVER
    assert page.predicted_role == ExamSourceRole.ANSWER_SOLUTIONS
    assert document.segments.get(order=0).role == ExamSourceRole.COVER


def test_persist_classification_preserves_existing_virtual_order():
    _, document = _document(page_count=3)
    for page_number, display_order in ((1, 1), (2, 3), (3, 2)):
        ExamSourcePage.objects.create(
            document=document,
            page_number=page_number,
            display_order=display_order,
        )

    result = persist_classification_result(
        document_id=document.id,
        expected_revision=1,
        fingerprint='9' * 64,
        raw_output={
            'pages': [
                {'page_number': 1, 'role': 'cover'},
                {'page_number': 2, 'role': 'questions'},
                {'page_number': 3, 'role': 'questions'},
            ]
        },
    )

    assert [page.page_number for page in result.pages] == [1, 3, 2]
    assert [page.display_order for page in result.pages] == [1, 2, 3]
    question_segment = document.segments.get(order=1)
    assert question_segment.start_page == 3
    assert question_segment.end_page == 2
    assert question_segment.metadata['pageNumbers'] == [3, 2]


def test_same_fingerprint_reuses_persisted_result_without_duplicate_segments():
    _, document = _document(page_count=2)
    payload = {
        'pages': [
            {'page_number': 1, 'role': 'cover'},
            {'page_number': 2, 'role': 'questions'},
        ]
    }
    first = persist_classification_result(
        document_id=document.id,
        expected_revision=1,
        fingerprint='c' * 64,
        raw_output=payload,
    )
    second = persist_classification_result(
        document_id=document.id,
        expected_revision=1,
        fingerprint='c' * 64,
        raw_output={'pages': []},
    )

    assert first.reused is False
    assert second.reused is True
    assert document.segments.filter(revision=1).count() == 2


def test_different_fingerprint_cannot_overwrite_accepted_revision():
    _, document = _document(page_count=1)
    persist_classification_result(
        document_id=document.id,
        expected_revision=1,
        fingerprint='d' * 64,
        raw_output={'pages': [{'page_number': 1, 'role': 'cover'}]},
    )

    with pytest.raises(ClassificationFingerprintConflict):
        persist_classification_result(
            document_id=document.id,
            expected_revision=1,
            fingerprint='e' * 64,
            raw_output={'pages': [{'page_number': 1, 'role': 'questions'}]},
        )


def test_stale_revision_is_rejected_before_writes():
    _, document = _document(page_count=1)
    document.classification_revision = 2
    document.save(update_fields=['classification_revision', 'updated_at'])

    with pytest.raises(StaleClassificationRevision):
        persist_classification_result(
            document_id=document.id,
            expected_revision=1,
            fingerprint='f' * 64,
            raw_output={'pages': [{'page_number': 1, 'role': 'cover'}]},
        )

    assert document.pages.count() == 0
    assert document.segments.count() == 0


def test_unknown_page_count_blocks_persistence():
    _, document = _document(page_count=0)

    with pytest.raises(InvalidClassificationInput, match='page count'):
        persist_classification_result(
            document_id=document.id,
            expected_revision=1,
            fingerprint='1' * 64,
            raw_output={'pages': []},
        )
