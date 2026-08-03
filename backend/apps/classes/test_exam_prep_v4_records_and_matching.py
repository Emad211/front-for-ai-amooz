import json
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction
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
    ExamSourceBlockKind,
)
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamAnswerSolutionRecordEvidence,
    ExamExtractionLifecycle,
    ExamMatchDecision,
    ExamQuestionRecord,
    ExamQuestionRecordEvidence,
)
from apps.classes.services.exam_prep_v4_blocks import (
    BlockFragmentProposal,
    SourceBlockProposal,
    persist_source_blocks,
)
from apps.classes.services.exam_prep_v4_records import (
    AnswerSolutionRecordProposal,
    InvalidRecordInput,
    QuestionOptionProposal,
    QuestionRecordProposal,
    RecordSetNotReady,
    StaleBlockSet,
    build_deterministic_matches,
    parse_answer_solution_extraction_output,
    parse_question_extraction_output,
    persist_answer_solution_records,
    persist_question_records,
)


pytestmark = pytest.mark.django_db


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _summary_url(project_id: int) -> str:
    return f'/api/classes/exam-prep-v4/projects/{project_id}/records/summary/'


def _fragment(order: int, page_number: int, *, continuation: bool = False):
    return BlockFragmentProposal(
        order=order,
        page_number=page_number,
        x0=Decimal('0.050000'),
        y0=Decimal('0.050000'),
        x1=Decimal('0.950000'),
        y1=Decimal('0.950000'),
        column_index=0,
        is_continuation=continuation,
    )


def _pipeline_fixture(*, question_numbers=('1', '2')):
    teacher = _teacher()
    project = ExamProject.objects.create(
        teacher=teacher,
        title='Typed vertical fixture',
        status=ExamProject.Status.SEGMENTING,
    )
    source_map_fingerprint = 'a' * 64
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='private.pdf',
        page_count=6,
        status=ExamSourceDocument.Status.CONFIRMED,
        classification_revision=1,
        source_map_fingerprint=source_map_fingerprint,
        teacher_confirmed_at=timezone.now(),
        teacher_confirmed_by=teacher,
        teacher_confirmed_revision=1,
        teacher_confirmed_fingerprint=source_map_fingerprint,
    )
    roles = [
        ExamSourceRole.COVER,
        ExamSourceRole.QUESTIONS,
        ExamSourceRole.QUESTIONS,
        ExamSourceRole.ANSWER_SOLUTIONS,
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
    for order, (start, end, role, page_numbers, section_key) in enumerate(
        [
            (1, 1, ExamSourceRole.COVER, [1], ''),
            (2, 3, ExamSourceRole.QUESTIONS, [2, 3], 'زیست'),
            (4, 6, ExamSourceRole.ANSWER_SOLUTIONS, [4, 5, 6], 'زیست'),
        ]
    ):
        segments.append(
            ExamSourceSegment.objects.create(
                document=document,
                revision=1,
                order=order,
                start_page=start,
                end_page=end,
                role=role,
                predicted_role=role,
                predicted_confidence=Decimal('0.9500'),
                teacher_confirmed=True,
                section_key=section_key,
                fingerprint=source_map_fingerprint,
                status=ExamSourceSegment.Status.CONFIRMED,
                metadata={
                    'pageNumbers': page_numbers,
                    'displayOrderStart': start,
                    'displayOrderEnd': end,
                },
            )
        )
    block_result = persist_source_blocks(
        document_id=document.id,
        expected_source_map_revision=1,
        expected_source_map_fingerprint=source_map_fingerprint,
        proposals=(
            SourceBlockProposal(
                order=0,
                segment_order=1,
                kind=ExamSourceBlockKind.QUESTION,
                printed_number=question_numbers[0],
                confidence=0.98,
                fragments=(_fragment(0, 2),),
            ),
            SourceBlockProposal(
                order=1,
                segment_order=1,
                kind=ExamSourceBlockKind.QUESTION,
                printed_number=question_numbers[1],
                confidence=0.97,
                fragments=(_fragment(0, 3),),
            ),
            SourceBlockProposal(
                order=2,
                segment_order=2,
                kind=ExamSourceBlockKind.ANSWER_SOLUTION,
                printed_number='1',
                confidence=0.96,
                fragments=(_fragment(0, 4),),
            ),
            SourceBlockProposal(
                order=3,
                segment_order=2,
                kind=ExamSourceBlockKind.ANSWER_SOLUTION,
                printed_number='99',
                confidence=0.95,
                fragments=(_fragment(0, 5),),
            ),
            SourceBlockProposal(
                order=4,
                segment_order=2,
                kind=ExamSourceBlockKind.CONTINUATION,
                confidence=0.90,
                continuation_of_order=2,
                fragments=(_fragment(0, 6, continuation=True),),
            ),
        ),
    )
    blocks = {
        block.order: block
        for block in ExamSourceBlock.objects.filter(document=document).order_by('order')
    }
    return teacher, project, document, blocks, block_result.set_fingerprint


def _question_proposals(blocks, *, changed=False, sections=('زیست', 'زیست')):
    return (
        QuestionRecordProposal(
            block_id=blocks[0].id,
            printed_number=blocks[0].printed_number,
            section_key=sections[0],
            question_text='متن دقیق سؤال یک' + (' ویرایش‌شده' if changed else ''),
            options=(
                QuestionOptionProposal(label='1', text='گزینهٔ اول'),
                QuestionOptionProposal(label='2', text='گزینهٔ دوم'),
                QuestionOptionProposal(label='3', text='گزینهٔ سوم'),
                QuestionOptionProposal(label='4', text='گزینهٔ چهارم'),
            ),
            confidence=0.97,
            warnings=('PRIVATE_QUESTION_WARNING',),
            raw_payload={'PRIVATE_QUESTION_RAW': 'must-not-leak'},
        ),
        QuestionRecordProposal(
            block_id=blocks[1].id,
            printed_number=blocks[1].printed_number,
            section_key=sections[1],
            question_text='متن دقیق سؤال دو',
            options=(
                QuestionOptionProposal(label='1', text='الف'),
                QuestionOptionProposal(label='2', text='ب'),
            ),
            confidence=0.96,
        ),
    )


def _answer_proposals(blocks, *, option='2', first_section='زیست'):
    return (
        AnswerSolutionRecordProposal(
            block_id=blocks[2].id,
            printed_number='1',
            section_key=first_section,
            correct_option=option,
            final_answer='گزینهٔ ۲',
            solution_text='راه‌حل کامل سؤال یک که از دو صفحه پشتیبانی می‌شود.',
            confidence=0.96,
            warnings=('PRIVATE_ANSWER_WARNING',),
            raw_payload={'PRIVATE_ANSWER_RAW': 'must-not-leak'},
        ),
        AnswerSolutionRecordProposal(
            block_id=blocks[3].id,
            printed_number='99',
            section_key='زیست',
            correct_option='1',
            final_answer='گزینهٔ ۱',
            solution_text='راه‌حل پاسخ خارج از موجودی سؤال‌ها.',
            confidence=0.95,
        ),
    )


def _persist_questions(document, block_set_fingerprint, proposals):
    return persist_question_records(
        document_id=document.id,
        expected_block_set_fingerprint=block_set_fingerprint,
        proposals=proposals,
    )


def _persist_answers(document, block_set_fingerprint, proposals):
    return persist_answer_solution_records(
        document_id=document.id,
        expected_block_set_fingerprint=block_set_fingerprint,
        proposals=proposals,
    )


def test_typed_models_are_registered_under_classes_app():
    assert apps.get_model('classes', 'ExamQuestionRecord') is ExamQuestionRecord
    assert (
        apps.get_model('classes', 'ExamAnswerSolutionRecord')
        is ExamAnswerSolutionRecord
    )
    assert apps.get_model('classes', 'ExamMatchDecision') is ExamMatchDecision


def test_question_parser_keeps_valid_sibling_and_normalizes_numbers():
    result = parse_question_extraction_output(
        {
            'questions': [
                {
                    'blockId': 10,
                    'printedNumber': ' ۱ ',
                    'sectionKey': '  زیست  ',
                    'questionText': 'متن سؤال',
                    'options': [{'label': '۱', 'text': 'پاسخ'}],
                    'confidence': 0.9,
                    'PRIVATE_EXTRA': 'ignored',
                },
                {
                    'blockId': 11,
                    'printedNumber': '2',
                    'questionText': '',
                },
            ]
        }
    )

    assert len(result.records) == 1
    assert result.records[0].printed_number == '1'
    assert result.records[0].section_key == 'زیست'
    assert result.records[0].options[0].label == '1'
    assert [issue.code for issue in result.issues] == ['invalid_question_record']
    assert 'PRIVATE_EXTRA' not in result.records[0].raw_payload


def test_answer_parser_keeps_answer_and_solution_in_one_record():
    result = parse_answer_solution_extraction_output(
        {
            'answers': [
                {
                    'blockId': 20,
                    'printedNumber': '١',
                    'correctOption': '۲',
                    'finalAnswer': 'گزینه دو',
                    'solutionText': 'حل کامل',
                    'confidence': 0.9,
                },
                {'blockId': 21},
            ]
        }
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record.printed_number == '1'
    assert record.correct_option == '2'
    assert record.final_answer == 'گزینه دو'
    assert record.solution_text == 'حل کامل'
    assert [issue.code for issue in result.issues] == [
        'invalid_answer_solution_record'
    ]


def test_question_persistence_is_private_evidence_bound_and_idempotent():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture()
    proposals = _question_proposals(blocks)

    first = _persist_questions(document, block_set, proposals)
    second = _persist_questions(document, block_set, proposals)

    project.refresh_from_db()
    records = list(
        ExamQuestionRecord.objects.filter(
            document=document,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).order_by('order')
    )
    assert first.revision == second.revision == 1
    assert second.reused is True
    assert first.record_count == 2
    assert first.evidence_link_count == 2
    assert [record.printed_number for record in records] == ['1', '2']
    assert records[0].question_text == 'متن دقیق سؤال یک'
    assert records[0].options[1] == {'label': '2', 'text': 'گزینهٔ دوم'}
    assert records[0].raw_payload['PRIVATE_QUESTION_RAW'] == 'must-not-leak'
    assert ExamQuestionRecordEvidence.objects.filter(record__in=records).count() == 2
    assert project.status == ExamProject.Status.EXTRACTING_ANSWERS


def test_changed_question_set_supersedes_history_without_erasing_old_content():
    _teacher_user, _project, document, blocks, block_set = _pipeline_fixture()
    first = _persist_questions(document, block_set, _question_proposals(blocks))
    second = _persist_questions(
        document,
        block_set,
        _question_proposals(blocks, changed=True),
    )

    assert first.revision == 1
    assert second.revision == 2
    old = ExamQuestionRecord.objects.get(document=document, revision=1, order=0)
    current = ExamQuestionRecord.objects.get(document=document, revision=2, order=0)
    assert old.lifecycle_status == ExamExtractionLifecycle.SUPERSEDED
    assert old.question_text == 'متن دقیق سؤال یک'
    assert current.question_text.endswith('ویرایش‌شده')


def test_answer_persistence_includes_continuation_evidence_chain():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture()
    _persist_questions(document, block_set, _question_proposals(blocks))

    result = _persist_answers(document, block_set, _answer_proposals(blocks))

    project.refresh_from_db()
    first = ExamAnswerSolutionRecord.objects.get(document=document, order=0)
    links = list(first.evidence_links.select_related('block').order_by('order'))
    assert result.record_count == 2
    assert result.evidence_link_count == 3
    assert first.correct_option == '2'
    assert first.final_answer == 'گزینهٔ ۲'
    assert first.solution_text.startswith('راه‌حل کامل')
    assert [link.block.order for link in links] == [2, 4]
    assert links[1].block.kind == ExamSourceBlockKind.CONTINUATION
    assert project.status == ExamProject.Status.MATCHING


def test_answer_solution_block_requires_both_answer_and_full_solution():
    _teacher_user, _project, document, blocks, block_set = _pipeline_fixture()

    with pytest.raises(InvalidRecordInput, match='complete source solution'):
        _persist_answers(
            document,
            block_set,
            (
                AnswerSolutionRecordProposal(
                    block_id=blocks[2].id,
                    printed_number='1',
                    correct_option='2',
                    solution_text='',
                    confidence=0.9,
                ),
            ),
        )
    with pytest.raises(InvalidRecordInput, match='correct option or final answer'):
        _persist_answers(
            document,
            block_set,
            (
                AnswerSolutionRecordProposal(
                    block_id=blocks[2].id,
                    printed_number='1',
                    solution_text='حل بدون پاسخ نهایی',
                    confidence=0.9,
                ),
            ),
        )
    assert not ExamAnswerSolutionRecord.objects.filter(document=document).exists()


def test_stale_block_set_or_number_conflict_is_rejected_before_writes():
    _teacher_user, _project, document, blocks, block_set = _pipeline_fixture()

    with pytest.raises(StaleBlockSet):
        _persist_questions(document, '0' * 64, _question_proposals(blocks))
    conflict = list(_question_proposals(blocks))
    conflict[0] = QuestionRecordProposal(
        block_id=blocks[0].id,
        printed_number='77',
        question_text='نباید ذخیره شود',
        confidence=0.9,
    )
    with pytest.raises(InvalidRecordInput, match='conflicts with source block'):
        _persist_questions(document, block_set, tuple(conflict))
    assert not ExamQuestionRecord.objects.filter(document=document).exists()


def test_exact_match_and_out_of_scope_answer_do_not_invent_questions():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture()
    _persist_questions(document, block_set, _question_proposals(blocks))
    _persist_answers(document, block_set, _answer_proposals(blocks))

    result = build_deterministic_matches(project_id=project.id)

    project.refresh_from_db()
    decisions = list(
        ExamMatchDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).order_by('order')
    )
    assert result.matched_count == 1
    assert result.out_of_scope_count == 1
    assert result.unresolved_count == 0
    assert decisions[0].decision == ExamMatchDecision.Decision.MATCHED
    assert decisions[0].method == ExamMatchDecision.Method.EXACT_SCOPE_NUMBER
    assert decisions[0].question_record.printed_number == '1'
    assert decisions[1].decision == ExamMatchDecision.Decision.OUT_OF_SCOPE
    assert decisions[1].question_record_id is None
    assert ExamQuestionRecord.objects.filter(project=project).count() == 2
    assert project.status == ExamProject.Status.AWAITING_REVIEW
    assert project.workflow_state['matchedCount'] == 1
    assert project.workflow_state['outOfScopeCount'] == 1


def test_unique_project_number_can_match_across_missing_section_scope():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture()
    _persist_questions(
        document,
        block_set,
        _question_proposals(blocks, sections=('بخش الف', 'بخش ب')),
    )
    _persist_answers(
        document,
        block_set,
        _answer_proposals(blocks, first_section='بخش ناشناخته'),
    )

    build_deterministic_matches(project_id=project.id)

    decision = ExamMatchDecision.objects.get(project=project, order=0)
    assert decision.decision == ExamMatchDecision.Decision.MATCHED
    assert decision.method == ExamMatchDecision.Method.UNIQUE_NUMBER


def test_duplicate_question_number_refuses_automatic_match():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture(
        question_numbers=('1', '1')
    )
    _persist_questions(
        document,
        block_set,
        _question_proposals(blocks, sections=('زیست', 'زیست')),
    )
    _persist_answers(document, block_set, _answer_proposals(blocks))

    result = build_deterministic_matches(project_id=project.id)

    first = ExamMatchDecision.objects.get(project=project, order=0)
    assert result.ambiguous_count == 1
    assert first.decision == ExamMatchDecision.Decision.AMBIGUOUS
    assert first.question_record_id is None
    assert first.reason_code == 'duplicate_scope_number'


def test_correct_option_outside_question_options_becomes_conflict():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture()
    _persist_questions(document, block_set, _question_proposals(blocks))
    _persist_answers(
        document,
        block_set,
        _answer_proposals(blocks, option='9'),
    )

    result = build_deterministic_matches(project_id=project.id)

    first = ExamMatchDecision.objects.get(project=project, order=0)
    assert result.conflict_count == 1
    assert first.decision == ExamMatchDecision.Decision.CONFLICT
    assert first.question_record_id is None
    assert first.reason_code == 'correct_option_not_in_question_options'


def test_match_rebuild_is_idempotent_for_unchanged_record_sets():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture()
    _persist_questions(document, block_set, _question_proposals(blocks))
    _persist_answers(document, block_set, _answer_proposals(blocks))

    first = build_deterministic_matches(project_id=project.id)
    second = build_deterministic_matches(project_id=project.id)

    assert first.revision == second.revision == 1
    assert second.reused is True
    assert ExamMatchDecision.objects.filter(project=project).count() == 2


def test_matcher_never_uses_question_from_another_project():
    _teacher_a, project_a, document_a, blocks_a, block_set_a = _pipeline_fixture()
    _persist_questions(document_a, block_set_a, _question_proposals(blocks_a))

    _teacher_b, project_b, document_b, blocks_b, block_set_b = _pipeline_fixture()
    _persist_questions(
        document_b,
        block_set_b,
        _question_proposals(blocks_b, sections=('شیمی', 'شیمی')),
    )
    answers = list(_answer_proposals(blocks_b, first_section='شیمی'))
    answers[0] = AnswerSolutionRecordProposal(
        block_id=blocks_b[2].id,
        printed_number='1',
        section_key='زیست',
        correct_option='2',
        final_answer='گزینه ۲',
        solution_text='نباید به سؤال پروژهٔ دیگر متصل شود.',
        confidence=0.9,
    )
    _persist_answers(document_b, block_set_b, tuple(answers))

    result = build_deterministic_matches(project_id=project_b.id)

    decision = ExamMatchDecision.objects.get(project=project_b, order=0)
    assert result.matched_count == 1
    assert decision.question_record.project_id == project_b.id
    assert decision.question_record.project_id != project_a.id


def test_matcher_requires_current_question_and_answer_sets():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture()

    with pytest.raises(RecordSetNotReady, match='question inventory'):
        build_deterministic_matches(project_id=project.id)
    _persist_questions(document, block_set, _question_proposals(blocks))
    with pytest.raises(RecordSetNotReady, match='answer-solution'):
        build_deterministic_matches(project_id=project.id)


def test_database_rejects_empty_question_text_and_empty_answer_content():
    _teacher_user, project, document, blocks, block_set = _pipeline_fixture()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExamQuestionRecord.objects.create(
                project=project,
                document=document,
                source_block=blocks[0],
                revision=1,
                order=0,
                question_text='',
                block_set_fingerprint=block_set,
                set_fingerprint='b' * 64,
                fingerprint='c' * 64,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExamAnswerSolutionRecord.objects.create(
                project=project,
                document=document,
                source_block=blocks[2],
                revision=1,
                order=0,
                block_set_fingerprint=block_set,
                set_fingerprint='d' * 64,
                fingerprint='e' * 64,
            )


def test_safe_summary_is_owner_scoped_and_never_exposes_private_content(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document, blocks, block_set = _pipeline_fixture()
    _persist_questions(document, block_set, _question_proposals(blocks))
    _persist_answers(document, block_set, _answer_proposals(blocks))
    build_deterministic_matches(project_id=project.id)

    response = _client(teacher).get(_summary_url(project.id))

    assert response.status_code == 200
    assert response.data['questionCount'] == 2
    assert response.data['answerSolutionCount'] == 2
    assert response.data['matchedCount'] == 1
    assert response.data['outOfScopeCount'] == 1
    rendered = json.dumps(response.data, ensure_ascii=False, default=str)
    for forbidden in (
        'متن دقیق سؤال',
        'راه‌حل کامل',
        'PRIVATE_QUESTION_RAW',
        'PRIVATE_ANSWER_RAW',
        'PRIVATE_QUESTION_WARNING',
        'PRIVATE_ANSWER_WARNING',
        'questionText',
        'solutionText',
        'finalAnswer',
        'options',
        'rawPayload',
        'fingerprint',
        'metadata',
    ):
        assert forbidden not in rendered

    outsider = _teacher()
    assert _client(outsider).get(_summary_url(project.id)).status_code == 404
