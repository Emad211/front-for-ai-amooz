"""Regression tests: teacher edits must re-derive stored per-question issues.

The teacher review lane badge reads each question's stored ``issues[]`` (mirrored
on the frontend by ``buildExamReviewSummary``). Before this fix the teacher-edit
write path (``normalize_exam_prep_json``) copied ``issues`` verbatim, so a
question whose stem/options the teacher had just fixed kept its stale
``missing_options`` / ``missing_question_text`` code and never left the review
lane — the edit "saved" but visibly "did not apply". Re-deriving the issues from
the edited content (the same ``canonical_question_issues`` the session audit
uses) keeps the per-question badge consistent with the recomputed audit, while a
genuinely-broken question stays review-blocking and non-repairable advisory
codes are preserved.
"""
from __future__ import annotations

import json

from apps.classes.services.exam_prep_page_output import (
    REVIEW_BLOCKING_ISSUE_CODES,
)
from apps.classes.services.exam_prep_question_verifier import (
    rebuild_projection_question_issues,
)
from apps.classes.services.exam_prep_utils import normalize_exam_prep_json


def _projection(questions: list[dict]) -> dict:
    return {"exam_prep": {"title": "آزمون", "questions": questions}}


def _fixed_question() -> dict:
    # A question that was extracted with empty options (so it carried the
    # review-blocking ``missing_options`` code) but the teacher has now filled in
    # four real options. The stale code must not survive.
    return {
        "question_id": "q-1",
        "scope_key": "default",
        "source_question_number": "1",
        "question_text_markdown": "کدام گزینه درست است؟",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "2",
        "teacher_solution_markdown": "",
        "final_answer_markdown": "",
        "issues": ["missing_options"],
        "source_pages": [3],
    }


def test_rebuild_clears_repairable_code_after_teacher_fixes_options():
    projection = _projection([_fixed_question()])
    changed = rebuild_projection_question_issues(projection)
    question = projection["exam_prep"]["questions"][0]
    assert changed is True
    assert "missing_options" not in question["issues"]
    assert not (set(question["issues"]) & REVIEW_BLOCKING_ISSUE_CODES)


def test_rebuild_keeps_genuinely_broken_question_blocking():
    broken = _fixed_question()
    broken["options"] = []  # teacher did not actually add options
    projection = _projection([broken])
    rebuild_projection_question_issues(projection)
    question = projection["exam_prep"]["questions"][0]
    assert "missing_options" in question["issues"]
    assert set(question["issues"]) & REVIEW_BLOCKING_ISSUE_CODES


def test_rebuild_preserves_non_repairable_advisory_codes():
    question = _fixed_question()
    # A blocked-finalization advisory is not a repairable code — it must survive
    # the teacher edit as an advisory warning (never a review block).
    question["issues"] = ["missing_options", "stage5_finalization_blocked"]
    projection = _projection([question])
    rebuild_projection_question_issues(projection)
    result = projection["exam_prep"]["questions"][0]
    assert "missing_options" not in result["issues"]
    assert "stage5_finalization_blocked" in result["issues"]
    assert not (set(result["issues"]) & REVIEW_BLOCKING_ISSUE_CODES)


def test_rebuild_reports_no_change_when_issues_already_consistent():
    question = _fixed_question()
    question["issues"] = []  # already consistent with the four real options
    projection = _projection([question])
    assert rebuild_projection_question_issues(projection) is False
    assert projection["exam_prep"]["questions"][0]["issues"] == []


def test_normalize_exam_prep_json_rederives_issues_on_teacher_edit():
    # The integration point the PATCH handler actually calls: edited JSON in,
    # normalized JSON out with per-question issues re-derived from content.
    raw = json.dumps(_projection([_fixed_question()]), ensure_ascii=False)
    normalized_json, _changed = normalize_exam_prep_json(raw)
    payload = json.loads(normalized_json)
    question = payload["exam_prep"]["questions"][0]
    assert "missing_options" not in question["issues"]
    assert not (set(question["issues"]) & REVIEW_BLOCKING_ISSUE_CODES)


def test_normalize_exam_prep_json_keeps_broken_question_in_review_lane():
    broken = _fixed_question()
    broken["options"] = []
    raw = json.dumps(_projection([broken]), ensure_ascii=False)
    normalized_json, _changed = normalize_exam_prep_json(raw)
    payload = json.loads(normalized_json)
    question = payload["exam_prep"]["questions"][0]
    assert "missing_options" in question["issues"]
