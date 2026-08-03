from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.classes.models_v4 import ExamSourceRole
from apps.classes.models_v4_blocks import (
    ExamSourceBlock,
    ExamSourceBlockKind,
)
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamQuestionRecord,
)
from apps.classes.services.exam_prep_v4_live_pipeline import (
    ExtractionImageError,
    PreparedBlockExtraction,
    PreparedVisionImage,
    bounded_extraction_batches,
    run_document_extraction_pipeline,
)
from apps.classes.test_exam_prep_v4_full_pipeline import _confirmed_document


pytestmark = pytest.mark.django_db


def _fragment(page_number: int, order: int) -> dict:
    top = 0.05 + (order * 0.30)
    return {
        'order': 0,
        'pageNumber': page_number,
        'x0': 0.05,
        'y0': top,
        'x1': 0.95,
        'y1': min(0.95, top + 0.24),
        'columnIndex': 0,
        'isContinuation': False,
    }


class BatchAwareProvider:
    def __init__(self, *, heal_questions: bool = False):
        self.provider_calls = 0
        self.heal_questions = heal_questions
        self.question_batches: list[tuple[int, ...]] = []
        self.answer_batches: list[tuple[int, ...]] = []

    def detect_segment_blocks(self, *, document, segment, pages, images):
        self.provider_calls += 1
        if segment.role == ExamSourceRole.QUESTIONS:
            return {
                'blocks': [
                    {
                        'order': index,
                        'kind': 'question',
                        'printedNumber': str(index + 1),
                        'confidence': 0.99,
                        'fragments': [_fragment(pages[0].page_number, index)],
                    }
                    for index in range(3)
                ]
            }
        if segment.role == ExamSourceRole.ANSWER_SOLUTIONS:
            return {
                'blocks': [
                    {
                        'order': index,
                        'kind': 'answer_solution',
                        'printedNumber': str(index + 1),
                        'confidence': 0.99,
                        'fragments': [
                            _fragment(
                                pages[min(index, len(pages) - 1)].page_number,
                                max(0, index - 1),
                            )
                        ],
                    }
                    for index in range(3)
                ]
            }
        return {'blocks': []}

    def extract_questions_batch(self, *, document, items, batch_index):
        self.provider_calls += 1
        ids = tuple(item.block.id for item in items)
        self.question_batches.append(ids)
        assert all(
            item.block.kind
            in {
                ExamSourceBlockKind.QUESTION,
                ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
            }
            for item in items
        )

        if self.heal_questions:
            return {
                'questions': [
                    {
                        'blockId': item.block.id,
                        'printedNumber': item.block.printed_number,
                        'sectionKey': item.block.segment.section_key,
                        'questionText': (
                            f'متن بازیابی‌شده سؤال {item.block.printed_number}'
                        ),
                        'options': [
                            {'label': '1', 'text': 'گزینه یک'},
                            {'label': '2', 'text': 'گزینه دو'},
                        ],
                        'confidence': 0.99,
                        'warnings': [],
                    }
                    for item in items
                ]
            }

        first, second, _third = items
        valid = {
            'blockId': first.block.id,
            'printedNumber': first.block.printed_number,
            'sectionKey': first.block.segment.section_key,
            'questionText': 'سؤال سالم باید با وجود همسایه خراب ذخیره شود.',
            'options': [
                {'label': '1', 'text': 'گزینه یک'},
                {'label': '2', 'text': 'گزینه دو'},
            ],
            'confidence': 0.99,
            'warnings': [],
        }
        duplicate = {
            **valid,
            'questionText': 'رکورد تکراری کم‌اعتماد',
            'confidence': 0.50,
        }
        malformed = {
            'blockId': second.block.id,
            'printedNumber': second.block.printed_number,
            'questionText': '',
            'confidence': 0.90,
        }
        return {'questions': [valid, duplicate, malformed]}

    def extract_answer_solutions_batch(
        self,
        *,
        document,
        items,
        batch_index,
    ):
        self.provider_calls += 1
        ids = tuple(item.block.id for item in items)
        self.answer_batches.append(ids)
        assert all(
            item.block.kind
            in {
                ExamSourceBlockKind.ANSWER_SOLUTION,
                ExamSourceBlockKind.ANSWER_KEY,
                ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
            }
            for item in items
        )
        return {
            'answers': [
                {
                    'blockId': item.block.id,
                    'printedNumber': item.block.printed_number,
                    'sectionKey': item.block.segment.section_key,
                    'correctOption': '1',
                    'finalAnswer': 'گزینه ۱',
                    'solutionText': (
                        f'راه‌حل کامل پاسخ {item.block.printed_number}'
                    ),
                    'confidence': 0.99,
                    'warnings': [],
                }
                for item in items
            ]
        }

    def extract_question(self, **kwargs):
        raise AssertionError(
            'Batch-aware provider must not use per-block question calls.'
        )

    def extract_answer_solution(self, **kwargs):
        raise AssertionError(
            'Batch-aware provider must not use per-block answer calls.'
        )


def test_batch_keeps_valid_sibling_and_surfaces_duplicate_and_missing_ids(
    monkeypatch,
):
    monkeypatch.setenv('EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BLOCKS', '4')
    _teacher, project, document, _pages = _confirmed_document()
    provider = BatchAwareProvider()

    result = run_document_extraction_pipeline(
        document_id=document.id,
        provider=provider,
    )

    question_blocks = tuple(
        ExamSourceBlock.objects.filter(
            document=document,
            kind=ExamSourceBlockKind.QUESTION,
        ).order_by('order')
    )
    assert provider.provider_calls == 4
    assert provider.question_batches == [
        tuple(block.id for block in question_blocks)
    ]
    assert [len(batch) for batch in provider.answer_batches] == [3]
    assert result.question_set.record_count == 1
    assert result.answer_set.record_count == 3
    assert result.matches.matched_count == 1
    assert result.matches.out_of_scope_count == 2
    assert ExamQuestionRecord.objects.filter(project=project).count() == 1
    assert ExamAnswerSolutionRecord.objects.filter(project=project).count() == 3

    issue_codes = [issue.code for issue in result.issues]
    assert 'duplicate_question_block' in issue_codes
    assert 'invalid_question_record' in issue_codes
    missing = {
        issue.block_id
        for issue in result.issues
        if issue.code == 'missing_question_block_id'
    }
    assert missing == {question_blocks[1].id, question_blocks[2].id}
    assert all(
        issue.retryable
        for issue in result.issues
        if issue.code == 'missing_question_block_id'
    )


def test_partial_rerun_calls_provider_only_for_missing_blocks(monkeypatch):
    monkeypatch.setenv('EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BLOCKS', '4')
    _teacher, _project, document, _pages = _confirmed_document()
    cold_provider = BatchAwareProvider()
    cold = run_document_extraction_pipeline(
        document_id=document.id,
        provider=cold_provider,
    )
    accepted_before = ExamQuestionRecord.objects.get(
        document=document,
        lifecycle_status='accepted',
    )
    accepted_block_id = accepted_before.source_block_id

    healing_provider = BatchAwareProvider(heal_questions=True)
    healed = run_document_extraction_pipeline(
        document_id=document.id,
        provider=healing_provider,
    )

    assert cold.question_set.record_count == 1
    assert healing_provider.provider_calls == 1
    assert len(healing_provider.question_batches) == 1
    assert accepted_block_id not in healing_provider.question_batches[0]
    assert len(healing_provider.question_batches[0]) == 2
    assert healing_provider.answer_batches == []
    assert healed.question_set.record_count == 3
    assert healed.answer_set.reused is True
    assert healed.matches.matched_count == 3

    warm_provider = BatchAwareProvider(heal_questions=True)
    warm = run_document_extraction_pipeline(
        document_id=document.id,
        provider=warm_provider,
    )
    assert warm.provider_calls == 0
    assert warm_provider.provider_calls == 0
    assert warm.question_set.reused is True
    assert warm.answer_set.reused is True
    assert warm.matches.reused is True


def _prepared_item(block_id: int, sizes: tuple[int, ...]):
    block = SimpleNamespace(id=block_id)
    images = tuple(
        PreparedVisionImage(
            image=b'x' * size,
            mime_type='image/jpeg',
            page_number=1,
            label=f'IMAGE {index}',
        )
        for index, size in enumerate(sizes)
    )
    return PreparedBlockExtraction(block=block, images=images)


def test_bounded_batches_limit_blocks_images_and_total_bytes(monkeypatch):
    monkeypatch.setenv('EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BLOCKS', '2')
    monkeypatch.setenv('EXAM_PREP_V4_EXTRACTION_BATCH_MAX_IMAGES', '3')
    monkeypatch.setenv('EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BYTES', '9')

    batches = bounded_extraction_batches(
        (
            _prepared_item(1, (2, 2)),
            _prepared_item(2, (4,)),
            _prepared_item(3, (4,)),
        )
    )

    assert [
        [item.block.id for item in batch]
        for batch in batches
    ] == [[1, 2], [3]]
    assert all(len(batch) <= 2 for batch in batches)
    assert all(
        sum(len(item.images) for item in batch) <= 3
        for batch in batches
    )
    assert all(
        sum(item.byte_size for item in batch) <= 9
        for batch in batches
    )

    with pytest.raises(ExtractionImageError, match='exceeds'):
        bounded_extraction_batches((_prepared_item(9, (10,)),))
