from __future__ import annotations

import io

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from model_bakery import baker
from PIL import Image, ImageDraw

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)
from apps.classes.models_v4_blocks import ExamSourceBlock, ExamSourceBlockKind
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamMatchDecision,
    ExamQuestionRecord,
)
from apps.classes.services.exam_prep_v4_live_pipeline import (
    PreparedVisionImage,
    prepare_block_crop_images,
    run_document_extraction_pipeline,
)


pytestmark = pytest.mark.django_db


def _png_bytes(label: str, *, width=900, height=1200) -> bytes:
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, width - 30, height - 30), outline='black', width=3)
    draw.text((70, 70), label, fill='black')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def _confirmed_document():
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(
        teacher=teacher,
        title='Full pipeline fixture',
        status=ExamProject.Status.SEGMENTING,
    )
    fingerprint = 'a' * 64
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='private.pdf',
        page_count=4,
        status=ExamSourceDocument.Status.CONFIRMED,
        classification_revision=1,
        source_map_fingerprint=fingerprint,
        teacher_confirmed_at=timezone.now(),
        teacher_confirmed_by=teacher,
        teacher_confirmed_revision=1,
        teacher_confirmed_fingerprint=fingerprint,
    )
    roles = [
        ExamSourceRole.COVER,
        ExamSourceRole.QUESTIONS,
        ExamSourceRole.ANSWER_SOLUTIONS,
        ExamSourceRole.ANSWER_SOLUTIONS,
    ]
    pages = []
    for page_number, role in enumerate(roles, start=1):
        page = ExamSourcePage(
            document=document,
            page_number=page_number,
            display_order=page_number,
            predicted_role=role,
            predicted_confidence='0.9500',
        )
        page.rendered_file.save(
            f'page-{page_number}.png',
            ContentFile(_png_bytes(f'PAGE {page_number}')),
            save=False,
        )
        page.save()
        pages.append(page)
    for order, (start, end, role, numbers, section) in enumerate(
        [
            (1, 1, ExamSourceRole.COVER, [1], ''),
            (2, 2, ExamSourceRole.QUESTIONS, [2], 'زیست'),
            (3, 4, ExamSourceRole.ANSWER_SOLUTIONS, [3, 4], 'زیست'),
        ]
    ):
        ExamSourceSegment.objects.create(
            document=document,
            revision=1,
            order=order,
            start_page=start,
            end_page=end,
            role=role,
            predicted_role=role,
            predicted_confidence='0.9500',
            teacher_confirmed=True,
            section_key=section,
            fingerprint=fingerprint,
            status=ExamSourceSegment.Status.CONFIRMED,
            metadata={
                'pageNumbers': numbers,
                'displayOrderStart': start,
                'displayOrderEnd': end,
            },
        )
    return teacher, project, document, tuple(pages)


class FakeFullPipelineProvider:
    def __init__(self):
        self.provider_calls = 0
        self.seen_images: list[PreparedVisionImage] = []

    def detect_segment_blocks(self, *, document, segment, pages, images):
        self.provider_calls += 1
        self.seen_images.extend(images)
        assert all(image.image.startswith(b'\xff\xd8') for image in images)
        if segment.role == ExamSourceRole.QUESTIONS:
            return {
                'blocks': [
                    {
                        'order': 0,
                        'kind': 'question',
                        'printedNumber': '۱',
                        'confidence': 0.98,
                        'fragments': [
                            {
                                'order': 0,
                                'pageNumber': pages[0].page_number,
                                'x0': 0.05,
                                'y0': 0.05,
                                'x1': 0.95,
                                'y1': 0.55,
                                'columnIndex': 0,
                                'isContinuation': False,
                            }
                        ],
                    },
                    {'order': 99, 'kind': 'bad-kind', 'fragments': []},
                ]
            }
        return {
            'blocks': [
                {
                    'order': 0,
                    'kind': 'answer_solution',
                    'printedNumber': '1',
                    'confidence': 0.97,
                    'fragments': [
                        {
                            'order': 0,
                            'pageNumber': pages[0].page_number,
                            'x0': 0.05,
                            'y0': 0.10,
                            'x1': 0.95,
                            'y1': 0.95,
                            'columnIndex': 0,
                            'isContinuation': False,
                        }
                    ],
                },
                {
                    'order': 1,
                    'kind': 'continuation',
                    'printedNumber': '',
                    'confidence': 0.90,
                    'continuationOfOrder': 0,
                    'fragments': [
                        {
                            'order': 0,
                            'pageNumber': pages[1].page_number,
                            'x0': 0.05,
                            'y0': 0.00,
                            'x1': 0.95,
                            'y1': 0.35,
                            'columnIndex': 0,
                            'isContinuation': True,
                        }
                    ],
                },
            ]
        }

    def extract_question(self, *, document, block, images):
        self.provider_calls += 1
        self.seen_images.extend(images)
        assert block.kind == ExamSourceBlockKind.QUESTION
        return {
            'questions': [
                {
                    'blockId': block.id,
                    'printedNumber': '۱',
                    'sectionKey': 'زیست',
                    'questionText': 'متن دقیق سؤال آزمایشی',
                    'options': [
                        {'label': '1', 'text': 'گزینه یک'},
                        {'label': '2', 'text': 'گزینه دو'},
                    ],
                    'confidence': 0.97,
                    'warnings': [],
                },
                {'blockId': block.id + 999, 'questionText': ''},
            ]
        }

    def extract_answer_solution(
        self,
        *,
        document,
        block,
        evidence_blocks,
        images,
    ):
        self.provider_calls += 1
        self.seen_images.extend(images)
        assert [item.kind for item in evidence_blocks] == [
            ExamSourceBlockKind.ANSWER_SOLUTION,
            ExamSourceBlockKind.CONTINUATION,
        ]
        assert len(images) == 2
        return {
            'answers': [
                {
                    'blockId': block.id,
                    'printedNumber': '1',
                    'sectionKey': 'زیست',
                    'correctOption': '2',
                    'finalAnswer': 'گزینهٔ ۲',
                    'solutionText': 'راه‌حل کامل که ادامهٔ صفحهٔ بعد را هم دارد.',
                    'confidence': 0.96,
                    'warnings': [],
                }
            ]
        }


def test_full_fake_provider_pipeline_uses_real_crops_and_exact_match():
    _teacher, project, document, _pages = _confirmed_document()
    provider = FakeFullPipelineProvider()

    result = run_document_extraction_pipeline(
        document_id=document.id,
        provider=provider,
    )

    project.refresh_from_db()
    assert result.provider_calls == 4
    assert provider.provider_calls == 4
    assert [(issue.stage, issue.code) for issue in result.issues] == [
        ('block_detection', 'invalid_block_record'),
        ('question_extraction', 'invalid_question_record'),
    ]
    assert result.block_set.block_count == 3
    assert result.block_set.fragment_count == 3
    assert result.question_set.record_count == 1
    assert result.answer_set.record_count == 1
    assert result.answer_set.evidence_link_count == 2
    assert result.matches.matched_count == 1
    assert result.matches.out_of_scope_count == 0
    assert project.status == ExamProject.Status.AWAITING_REVIEW
    assert ExamQuestionRecord.objects.get(project=project).printed_number == '1'
    answer = ExamAnswerSolutionRecord.objects.get(project=project)
    assert answer.correct_option == '2'
    assert answer.evidence_links.count() == 2
    decision = ExamMatchDecision.objects.get(project=project)
    assert decision.decision == ExamMatchDecision.Decision.MATCHED
    assert decision.question_record.printed_number == '1'
    assert all(image.image.startswith(b'\xff\xd8') for image in provider.seen_images)


def test_unchanged_warm_full_pipeline_makes_zero_provider_calls():
    _teacher, _project, document, _pages = _confirmed_document()
    cold_provider = FakeFullPipelineProvider()
    cold = run_document_extraction_pipeline(
        document_id=document.id,
        provider=cold_provider,
    )
    warm_provider = FakeFullPipelineProvider()

    warm = run_document_extraction_pipeline(
        document_id=document.id,
        provider=warm_provider,
    )

    assert cold.provider_calls == 4
    assert warm.provider_calls == 0
    assert warm_provider.provider_calls == 0
    assert warm.block_set.reused is True
    assert warm.question_set.reused is True
    assert warm.answer_set.reused is True
    assert warm.matches.reused is True
    assert warm.block_set.revision == cold.block_set.revision
    assert warm.question_set.revision == cold.question_set.revision
    assert warm.answer_set.revision == cold.answer_set.revision
    assert warm.matches.revision == cold.matches.revision


def test_crop_builder_applies_orientation_without_changing_source_page_identity():
    _teacher, _project, document, pages = _confirmed_document()
    page = pages[1]
    page.orientation = 90
    page.save(update_fields=['orientation', 'updated_at'])
    provider = FakeFullPipelineProvider()
    result = run_document_extraction_pipeline(
        document_id=document.id,
        provider=provider,
    )
    question_block = ExamSourceBlock.objects.get(
        document=document,
        kind=ExamSourceBlockKind.QUESTION,
    )

    crops = prepare_block_crop_images(question_block)

    assert result.matches.matched_count == 1
    assert crops[0].page_number == 2
    assert question_block.fragments.get().page.page_number == 2
