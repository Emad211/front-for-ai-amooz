from __future__ import annotations

from apps.classes.services.exam_prep_mistral_stage4_source_invariant_guard import (
    _anchor_conflicts,
    _leading_solution_evidence,
    _solution_invariant_conflicts,
    enforce_source_invariants,
)
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _question(number: int = 87):
    return {
        "source_question_number": str(number),
        "question_text_markdown": "قانون هنری را بررسی کنید",
        "options": [
            {"label": "1", "text_markdown": "4"},
            {"label": "2", "text_markdown": "3"},
            {"label": "3", "text_markdown": "2"},
            {"label": "4", "text_markdown": "1"},
        ],
        "correct_option_label": "4",
        "final_answer_markdown": "گزینه 4",
        "teacher_solution_markdown": "راه حل قدیمی",
        "issues": ["native_pdf_answer_label_authority"],
        "visuals": [],
    }


def _result(question):
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "x", "questions": [question]}},
        issues=[],
        question_count=1,
        questions_needing_review=0,
        matched_answer_count=1,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=True,
    )


def test_non_needed_stem_is_source_anchor_for_option_only_repair():
    row = {
        "kind": "question",
        "status": "repaired_primary_fields",
        "neededFields": ["option_1", "option_2", "option_3", "option_4"],
        "candidateFieldAgreement": {
            "question_text_markdown": {
                "criticalConflict": True,
                "textSimilarity": 0.03,
            }
        },
    }
    assert _anchor_conflicts(row) == ["question_text_markdown"]


def test_low_prose_overlap_is_anchor_conflict_even_without_math_conflict():
    row = {
        "kind": "question",
        "status": "repaired_primary_fields",
        "neededFields": ["option_1"],
        "candidateFieldAgreement": {
            "question_text_markdown": {
                "criticalConflict": False,
                "textSimilarity": 0.08,
            }
        },
    }
    assert _anchor_conflicts(row) == ["question_text_markdown"]


def test_solution_leading_evidence_is_strict_and_structural():
    assert _leading_solution_evidence("87. گزینه 2\nراه حل") == (87, "2")
    assert _leading_solution_evidence("در ادامه گزینه 2 را رد می‌کنیم") == (0, "")


def test_native_answer_label_and_question_number_veto_solution_body():
    original = _question(87)
    current = {**original, "teacher_solution_markdown": "58. گزینه 2\nراه حل جعلی"}
    row = {
        "kind": "solution",
        "status": "repaired_primary_fields",
        "questionNumber": 87,
        "neededFields": ["teacher_solution_markdown"],
    }
    assert _solution_invariant_conflicts(
        row,
        original_question=original,
        current_question=current,
    ) == ["leading_question_number", "native_answer_label"]


def test_guard_rolls_back_only_question_field_family_and_updates_stats():
    original_q = _question(87)
    current_q = {
        **original_q,
        "options": [
            {"label": "1", "text_markdown": "4.55"},
            {"label": "2", "text_markdown": "5.67"},
            {"label": "3", "text_markdown": "6.12"},
            {"label": "4", "text_markdown": "8.1"},
        ],
        "teacher_solution_markdown": "راه حل سالم دیگر",
    }
    audit = {
        "stats": {"repaired": 1, "verified": 1, "unresolved": 0, "partialRepairs": 0},
        "regions": [
            {
                "targetId": "q-087-p018",
                "kind": "question",
                "questionNumber": 87,
                "status": "repaired_primary_fields",
                "neededFields": ["option_1", "option_2", "option_3", "option_4"],
                "candidateFieldAgreement": {
                    "question_text_markdown": {
                        "criticalConflict": True,
                        "textSimilarity": 0.02,
                    }
                },
            }
        ],
    }
    guarded, guarded_audit = enforce_source_invariants(
        _result(original_q), _result(current_q), audit
    )
    q = guarded.projection["exam_prep"]["questions"][0]
    assert q["options"] == original_q["options"]
    assert q["teacher_solution_markdown"] == "راه حل سالم دیگر"
    assert "stage4_verification_unresolved" in q["issues"]
    assert guarded_audit["regions"][0]["status"] == "source_anchor_conflict_rolled_back"
    assert guarded_audit["stats"]["repaired"] == 0
    assert guarded_audit["stats"]["unresolved"] == 1
