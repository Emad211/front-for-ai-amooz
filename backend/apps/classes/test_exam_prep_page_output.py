"""Contract for the narrow review-blocking set (owner policy: `همیشه مجاز`).

Two disjoint metrics live on every exam-prep audit:

* ``criticalIssueCount`` — the broad **advisory** metric (all ``CRITICAL_ISSUE_CODES``).
  Still surfaced to the teacher so they can see every flagged issue.
* the **review-blocking** set — the ONLY thing that gates publish/status/review.
  Per the owner's locked decision a question is "واقعاً خراب" (forced into the
  review lane) *only* when it has no stem text or no options; everything else
  (Stage-5 rate-limit blocks, image-based options, answer-label authority,
  LaTeX doubts, …) is an advisory warning that must never block publishing.

These tests are deterministic and provider-free (no live LLM).
"""
from __future__ import annotations

import pytest

from apps.classes.services.exam_prep_page_output import (
    CRITICAL_ISSUE_CODES,
    REVIEW_BLOCKING_ISSUE_CODES,
    build_strict_exam_audit,
    is_critical_page_issue,
    is_review_blocking_issue,
)
from apps.classes.services.exam_prep_page_quality import reconcile_page_extraction
from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
    assemble_page_extractions,
)


pytestmark = pytest.mark.unit


_DEFAULT_OPTIONS = object()


def _question(number, *, text="کدام گزینه درست است؟", options=_DEFAULT_OPTIONS, issues=None):
    if options is _DEFAULT_OPTIONS:
        options = [
            PageOption(label="1", text_markdown="متن واقعی اول"),
            PageOption(label="2", text_markdown="متن واقعی دوم"),
        ]
    return PageRecord(
        question_number=number,
        record_type="question",
        question_text_markdown=text,
        options=options,
        confidence=0.9,
        issues=issues or [],
    )


def _assemble(*records):
    page = reconcile_page_extraction(
        PageExtraction(page_number=2, records=list(records))
    )
    return assemble_page_extractions([page], title="آزمون")


# --- the set itself -------------------------------------------------------


def test_review_blocking_set_is_exactly_the_three_broken_shapes():
    assert REVIEW_BLOCKING_ISSUE_CODES == frozenset(
        {"no_questions", "missing_question_text", "missing_options"}
    )


@pytest.mark.parametrize(
    "code", ["no_questions", "missing_question_text", "missing_options"]
)
def test_blocking_codes_block(code):
    assert is_review_blocking_issue(code) is True


@pytest.mark.parametrize(
    "code",
    [
        # advisory codes that must NOT block publish/review anymore
        "stage5_finalization_blocked",
        "missing_option_text",
        "placeholder_option_text",
        "visual_evidence_required",
        "correct_option_not_in_options",
        "missing_question_number",
        "source_verification_failed",
        "native_pdf_answer_label_authority",
        "conflicting_option:1",
        "",
    ],
)
def test_non_blocking_codes_do_not_block(code):
    assert is_review_blocking_issue(code) is False


def test_blocking_set_is_a_strict_subset_of_the_advisory_set():
    # Every blocking code is still advisory-critical (so it shows up in the
    # broad count too), but the advisory set is much larger.
    assert REVIEW_BLOCKING_ISSUE_CODES <= CRITICAL_ISSUE_CODES
    assert len(REVIEW_BLOCKING_ISSUE_CODES) < len(CRITICAL_ISSUE_CODES)
    for code in REVIEW_BLOCKING_ISSUE_CODES:
        assert is_critical_page_issue(code) is True


# --- how the strict audit consumes the two metrics ------------------------


def test_advisory_only_question_is_publishable():
    """A placeholder-option question keeps its advisory critical flag but the
    audit still passes — it has a stem and four option labels."""

    result = _assemble(
        _question(
            1,
            options=[
                PageOption(label="1", text_markdown="1"),
                PageOption(label="2", text_markdown="2"),
                PageOption(label="3", text_markdown="3"),
                PageOption(label="4", text_markdown="4"),
            ],
        )
    )

    audit = build_strict_exam_audit(result)

    assert audit["status"] == "passed"
    assert audit["questionsNeedingReview"] == 0
    assert audit["usableQuestionCount"] == 1
    # advisory metric still reports the placeholder issue
    assert audit["criticalIssueCount"] >= 1


def test_question_without_options_is_forced_into_review():
    result = _assemble(_question(1, options=[]))

    audit = build_strict_exam_audit(result)

    assert audit["status"] == "needs_review"
    assert audit["questionsNeedingReview"] == 1
    assert audit["usableQuestionCount"] == 0
    codes = {issue["code"] for issue in audit["issues"]}
    assert "missing_options" in codes


def test_empty_exam_is_forced_into_review():
    result = _assemble()

    audit = build_strict_exam_audit(result)

    assert audit["status"] == "needs_review"
    assert audit["questionCount"] == 0
