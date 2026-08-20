"""Regression tests for post-OCR inline-option recovery in the Mistral facade.

A recurring ``mistral-ocr-4-0`` shape emits the four numbered options *inside*
the question stem and leaves ``options[]`` empty (often with an empty trailing
option). That used to force otherwise-answerable questions into the teacher
review lane with ``missing_options``. The production facade recovers those
options deterministically (no provider call) before quality is rebuilt, while a
genuinely option-less stem stays review-blocking per the locked owner policy.
"""
from __future__ import annotations

from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services.exam_prep_page_output import (
    REVIEW_BLOCKING_ISSUE_CODES,
)
from apps.classes.services.exam_prep_page_records import PageAssemblyResult
from apps.classes.services.exam_prep_question_verifier import (
    canonical_question_issues,
    rebuild_assembly_quality,
)


# The exact real-world broken shape from session-198 review dump: a clean
# ۱)…۲)…۳)…۴) run appended to the stem, with an empty trailing 4th option.
BROKEN_STEM = (
    "اگر متمم مجموعه $(A - B) \\cup (B - A)$ برابر $A' \\cap B'$ باشد، "
    "حاصل $B' - A'$ با کدام مجموعه برابر است؟\n"
    "۱) $A \\cup B$\n۲) $B'$ ۳) $\\emptyset$ ۴)"
)


def _result(questions: list[dict]) -> PageAssemblyResult:
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "آزمون", "questions": questions}},
        issues=[],
        question_count=len(questions),
        questions_needing_review=0,
    )


def _question(**overrides) -> dict:
    base = {
        "question_id": "default-q-1",
        "scope_key": "default",
        "source_question_number": "1",
        "question_text_markdown": "",
        "options": [],
        "correct_option_label": None,
        "correct_option_text_markdown": "",
        "teacher_solution_markdown": "",
        "final_answer_markdown": "",
        "confidence": 0.0,
        "issues": [],
        "source_pages": [5],
    }
    base.update(overrides)
    return base


def test_split_recovers_inline_options_and_keeps_empty_trailing_option():
    recovered = production._split_inline_stem_options(BROKEN_STEM)
    assert recovered is not None
    stem, options = recovered
    assert stem.endswith("برابر است؟")
    assert "۱)" not in stem and "۴)" not in stem
    assert [item["label"] for item in options] == ["1", "2", "3", "4"]
    assert options[0]["text_markdown"] == "$A \\cup B$"
    assert options[1]["text_markdown"] == "$B'$"
    assert options[2]["text_markdown"] == "$\\emptyset$"
    # The empty trailing option keeps its label (image option / OCR truncation);
    # only advisory ``missing_option_text`` applies, never a review block.
    assert options[3]["text_markdown"] == ""


def test_recovery_clears_the_missing_options_review_gate():
    question = _question(
        question_text_markdown=BROKEN_STEM,
        options=[],
        issues=["mistral_question_option_parse_failed"],
    )
    recovered = production._recover_inline_stem_options(_result([question]))
    result_question = recovered.projection["exam_prep"]["questions"][0]

    assert len(result_question["options"]) == 4
    # The region-level parse-failure code is stale once options are recovered.
    assert "mistral_question_option_parse_failed" not in result_question["issues"]

    rebuilt = rebuild_assembly_quality(recovered)
    rebuilt_question = rebuilt.projection["exam_prep"]["questions"][0]
    assert "missing_options" not in rebuilt_question["issues"]
    assert not (set(rebuilt_question["issues"]) & REVIEW_BLOCKING_ISSUE_CODES)


def test_recovery_emits_labels_for_pure_image_options():
    # Four bare markers with no inline text: an all-image option row. Recovery
    # must still emit four labelled options so option-role visuals attach and
    # the row renders as options (never as a missing-options review block).
    stem = "کدام گزینه درباره مدار زیر درست است؟\n۱)\n۲)\n۳)\n۴)"
    recovered = production._split_inline_stem_options(stem)
    assert recovered is not None
    clean_stem, options = recovered
    assert clean_stem == "کدام گزینه درباره مدار زیر درست است؟"
    assert [item["label"] for item in options] == ["1", "2", "3", "4"]
    assert all(item["text_markdown"] == "" for item in options)


def test_marker_less_question_stays_review_blocking():
    question = _question(
        source_question_number="2",
        question_text_markdown="این پرسش هیچ گزینه‌ای ندارد؟",
        options=[],
    )
    recovered = production._recover_inline_stem_options(_result([question]))
    result_question = recovered.projection["exam_prep"]["questions"][0]
    # Nothing to split → left untouched → genuinely option-less → stays blocking.
    assert result_question["options"] == []
    assert "missing_options" in canonical_question_issues(result_question)


def test_stem_that_is_only_option_markers_is_not_recovered():
    # No real question text before the markers → not a recoverable question.
    recovered = production._split_inline_stem_options("۱) الف ۲) ب ۳) ج ۴) د")
    assert recovered is None


def test_recovery_leaves_questions_with_existing_options_untouched():
    stem = "کدام صحیح است؟ ۱) الف ۲) ب ۳) ج ۴) د"
    question = _question(
        question_text_markdown=stem,
        options=[
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
        ],
    )
    recovered = production._recover_inline_stem_options(_result([question]))
    result_question = recovered.projection["exam_prep"]["questions"][0]
    assert result_question["question_text_markdown"] == stem
    assert len(result_question["options"]) == 2


# --- Live session-200 review-lane failure modes -----------------------------
# The clean ۱)…۴) run above is the easy case. On the 58-page booklet the OCR
# emitted three harder inline shapes the strict frozen ``_marker_sequence`` (all
# four markers, closing punctuation, strict order) could not split, so 21
# questions stayed in the review lane with ``missing_options``. Each mode below
# is one of those real shapes, reduced to its structure.


def test_split_recovers_half_open_paren_markers():
    # Mode A (Q81-like): markers are "(۱ ... (۲ ... (۳ ... (۴" — an opening
    # paren with NO closing paren, which the frozen ``_PAREN_OPTION_RE`` (needs a
    # closing bracket) and ``_OPTION_MARKER_RE`` (needs trailing punctuation)
    # both reject.
    stem = "کدام گزینه‌ها درست‌اند؟\n(۱ الف و ب (۲ ب و ج (۳ ج و د (۴ الف و د"
    recovered = production._split_inline_stem_options(stem)
    assert recovered is not None
    clean_stem, options = recovered
    assert clean_stem == "کدام گزینه‌ها درست‌اند؟"
    assert [item["label"] for item in options] == ["1", "2", "3", "4"]
    assert [item["text_markdown"] for item in options] == [
        "الف و ب",
        "ب و ج",
        "ج و د",
        "الف و د",
    ]


def test_split_recovers_run_with_one_ocr_dropped_marker():
    # Mode B (Q8-like): OCR dropped the "(۳)" marker, so only 1, 2, 4 survive.
    # The frozen sequencer needs all four in order and bails → options stay
    # inline. Recovery must emit four labelled options, filling the internal gap
    # with an empty labelled option (teacher confirms it), never blanking the
    # question.
    stem = "حاصل عبارت کدام است؟\n(۱) $-2$ (۲) $2/5$ (۴) $-2/5$"
    recovered = production._split_inline_stem_options(stem)
    assert recovered is not None
    clean_stem, options = recovered
    assert clean_stem == "حاصل عبارت کدام است؟"
    assert [item["label"] for item in options] == ["1", "2", "3", "4"]
    assert options[0]["text_markdown"] == "$-2$"
    assert options[1]["text_markdown"] == "$2/5$"
    assert options[2]["text_markdown"] == ""  # the OCR-dropped marker's slot
    assert options[3]["text_markdown"] == "$-2/5$"


def test_split_recovers_table_flattened_bare_digit_markers():
    # Mode C (Q30-like): a flattened numeric table where only the first marker
    # kept its parens and the rest became bare standalone digits interspersed
    # with numeric values. The recovery must treat 2/3/4 as markers WITHOUT
    # mistaking the multi-digit values (۱۰, ۲۰, ۱۲/۵) for markers.
    stem = "مقادیر جدول کدام است؟\n(۱) ۶/۵ ۲ ۱۰ ۳ ۱۲/۵ ۴ ۲۰"
    recovered = production._split_inline_stem_options(stem)
    assert recovered is not None
    clean_stem, options = recovered
    assert clean_stem == "مقادیر جدول کدام است؟"
    # Exactly four options — the two-digit values never spawn extra markers.
    assert [item["label"] for item in options] == ["1", "2", "3", "4"]
    assert options[0]["text_markdown"] == "۶/۵"
    assert options[1]["text_markdown"] == "۱۰"
    assert options[2]["text_markdown"] == "۱۲/۵"
    assert options[3]["text_markdown"] == "۲۰"


def test_split_does_not_fire_on_math_digits_without_an_option_run():
    # Precision guard: a stem full of math (digits 1-4 inside $...$, subscripts,
    # equalities) but NO real option-marker run must never be split. A bare "1"
    # anchor requires a bracket/punctuation, and math digits are glued to $, _,
    # =, / so they can't anchor a run.
    stem = "اگر $x_1 = 2$ و $x_2 = 4$ باشد، حاصل $x_3$ چیست؟"
    assert production._split_inline_stem_options(stem) is None


def test_split_requires_the_run_to_start_at_marker_one():
    # A stray "۴)" late in the prose (no 1→ run) is not an option run.
    stem = "طبق شکل ۴) که در بالا آمده است، کدام رابطه برقرار است؟"
    assert production._split_inline_stem_options(stem) is None


def test_recovery_clears_gate_for_all_live_failure_modes():
    modes = {
        "half_open": "کدام گزینه‌ها درست‌اند؟\n(۱ الف و ب (۲ ب و ج (۳ ج و د (۴ الف و د",
        "dropped_marker": "حاصل عبارت کدام است؟\n(۱) $-2$ (۲) $2/5$ (۴) $-2/5$",
        "table_flattened": "مقادیر جدول کدام است؟\n(۱) ۶/۵ ۲ ۱۰ ۳ ۱۲/۵ ۴ ۲۰",
    }
    questions = [
        _question(
            question_id=f"q-{key}",
            source_question_number=str(index + 1),
            question_text_markdown=stem,
            options=[],
            issues=["mistral_question_option_parse_failed"],
        )
        for index, (key, stem) in enumerate(modes.items())
    ]
    rebuilt = rebuild_assembly_quality(
        production._recover_inline_stem_options(_result(questions))
    )
    for question in rebuilt.projection["exam_prep"]["questions"]:
        assert len(question["options"]) == 4
        assert not (set(question["issues"]) & REVIEW_BLOCKING_ISSUE_CODES)
