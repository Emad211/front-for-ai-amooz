import re

from apps.classes.services.exam_prep_inventory import (
    build_exam_projection,
    build_extraction_audit,
    chunk_source_blocks,
    deduplicate_answer_records,
    deduplicate_question_records,
    match_answers_to_questions,
    normalize_source_number,
    parse_source_blocks,
)


def _questions(start: int, end: int, *, section: str = "دفترچه") -> list[dict]:
    return [
        {
            "source_question_number": str(number),
            "section_key": section,
            "source_pages": [1 + (number - start) // 5],
            "block_order": number - start,
            "question_text_markdown": f"صورت سؤال {number}",
            "options": [
                {"label": "الف", "text_markdown": "گزینه اول"},
                {"label": "ب", "text_markdown": "گزینه دوم"},
            ],
            "confidence": 0.99,
        }
        for number in range(start, end + 1)
    ]


def _answers(start: int, end: int, *, section: str = "دفترچه") -> list[dict]:
    return [
        {
            "source_question_number": str(number),
            "section_key": section,
            "source_pages": [20 + (number - start) // 5],
            "block_order": number - start,
            "correct_option_label": "الف",
            "final_answer_markdown": "الف",
            "teacher_solution_markdown": "",
            "confidence": 0.98,
        }
        for number in range(start, end + 1)
    ]


def test_parse_source_blocks_keeps_arbitrary_page_numbers():
    blocks = parse_source_blocks("## صفحه ۷۸\n\nالف\n\n## صفحه 79\n\nب")
    assert [block["page_number"] for block in blocks] == [78, 79]
    assert [block["content"] for block in blocks] == ["الف", "ب"]


def test_chunk_source_blocks_splits_oversized_media_without_losing_text():
    paragraphs = [f"بخش {index} " + ("متن " * 60) for index in range(12)]
    source = "\n\n".join(paragraphs)
    chunks = chunk_source_blocks(
        [{"page_number": 1, "block_order": 0, "content": source}],
        max_chars=700,
    )

    segments = [block for chunk in chunks for block in chunk]
    assert len(segments) > 1
    assert all(len(block["content"]) + 96 <= 700 for block in segments)
    assert [block["segment_index"] for block in segments] == list(range(len(segments)))
    normalized_source = re.sub(r"\s+", " ", source).strip()
    normalized_result = re.sub(
        r"\s+", " ", " ".join(block["content"] for block in segments)
    ).strip()
    assert normalized_result == normalized_source


def test_normalize_source_number_accepts_persian_and_arabic_digits():
    assert normalize_source_number("سؤال ۷۸") == "78"
    assert normalize_source_number("١١٦)") == "116"


def test_first_booklet_questions_then_answers_produces_exactly_fifty():
    questions, conflicts = deduplicate_question_records(_questions(1, 50))
    matched, unmatched, issues = match_answers_to_questions(questions, _answers(1, 50))
    audit = build_extraction_audit(
        questions=matched,
        unmatched_answers=unmatched,
        issues=[*conflicts, *issues],
    )

    assert len(matched) == 50
    assert unmatched == []
    assert audit["status"] == "passed"


def test_second_booklet_answers_before_questions_ignores_out_of_scope_answers():
    questions, conflicts = deduplicate_question_records(_questions(51, 115))
    answers = _answers(40, 115)
    matched, unmatched, issues = match_answers_to_questions(questions, answers)
    audit = build_extraction_audit(
        questions=matched,
        unmatched_answers=unmatched,
        issues=[*conflicts, *issues],
    )

    assert len(matched) == 65
    assert [item["source_question_number"] for item in unmatched] == [
        str(number) for number in range(40, 51)
    ]
    assert {item["match_status"] for item in unmatched} == {"out_of_scope"}
    assert audit["status"] == "passed"
    assert audit["outOfScopeAnswerCount"] == 11


def test_third_booklet_does_not_create_questions_from_previous_answers():
    questions, conflicts = deduplicate_question_records(_questions(116, 145))
    answers = _answers(112, 145)
    matched, unmatched, issues = match_answers_to_questions(questions, answers)

    assert len(matched) == 30
    assert [item["source_question_number"] for item in unmatched] == [
        "112",
        "113",
        "114",
        "115",
    ]
    assert all(item["match_status"] == "out_of_scope" for item in unmatched)
    assert not conflicts
    assert not issues


def test_same_number_in_different_sections_matches_by_composite_key():
    questions = _questions(1, 1, section="ریاضی") + _questions(1, 1, section="فیزیک")
    answers = _answers(1, 1, section="فیزیک") + _answers(1, 1, section="ریاضی")
    unique_questions, conflicts = deduplicate_question_records(questions)
    matched, unmatched, issues = match_answers_to_questions(unique_questions, answers)

    assert len(matched) == 2
    assert not conflicts
    assert not unmatched
    assert not issues
    assert {item["section_key"] for item in matched} == {"ریاضی", "فیزیک"}


def test_overlap_duplicate_is_removed_but_conflicting_same_number_is_critical():
    duplicate = _questions(78, 78)[0]
    equivalent = {**duplicate, "source_pages": [1, 2], "question_text_markdown": "صورت  سؤال  78"}
    conflict = {**duplicate, "source_pages": [3], "question_text_markdown": "یک سؤال متفاوت"}

    deduped, conflicts = deduplicate_question_records([duplicate, equivalent, conflict])

    assert len(deduped) == 1
    assert conflicts == [
        {
            "code": "duplicate_question_number",
            "severity": "critical",
            "questionKey": "دفترچه::78",
            "sourcePages": [1, 2, 3],
        }
    ]


def test_same_text_on_different_source_page_is_not_silently_deduplicated():
    first = _questions(78, 78)[0]
    second = {**first, "source_pages": [2]}

    deduped, conflicts = deduplicate_question_records([first, second])

    assert len(deduped) == 1
    assert conflicts[0]["code"] == "duplicate_question_number"


def test_answer_key_and_detailed_solution_merge_without_inventing_content():
    answer_key = _answers(78, 78)[0]
    detailed = {
        **answer_key,
        "source_pages": [22],
        "teacher_solution_markdown": "راه‌حل موجود در منبع",
    }

    answers, issues = deduplicate_answer_records([answer_key, detailed])

    assert issues == []
    assert len(answers) == 1
    assert answers[0]["source_pages"] == [20, 22]
    assert answers[0]["teacher_solution_markdown"] == "راه‌حل موجود در منبع"


def test_sparse_answer_never_invents_teacher_solution():
    questions, _ = deduplicate_question_records(_questions(78, 78))
    matched, unmatched, issues = match_answers_to_questions(
        questions,
        [
            {
                "source_question_number": "78",
                "section_key": "دفترچه",
                "source_pages": [9],
                "block_order": 1,
                "correct_option_label": "ب",
                "final_answer_markdown": "ب",
            }
        ],
    )
    projection = build_exam_projection(title="آزمون", questions=matched)
    question = projection["exam_prep"]["questions"][0]

    assert not unmatched
    assert not issues
    assert question["teacher_solution_markdown"] == ""
    assert question["correct_option_label"] == "ب"


def test_missing_answer_blocks_audit():
    questions, conflicts = deduplicate_question_records(_questions(1, 2))
    matched, unmatched, issues = match_answers_to_questions(questions, _answers(1, 1))
    audit = build_extraction_audit(
        questions=matched,
        unmatched_answers=unmatched,
        issues=[*conflicts, *issues],
    )

    assert audit["status"] == "needs_review"
    assert audit["criticalIssueCount"] == 1
    assert audit["issues"][0]["code"] == "missing_answer"
