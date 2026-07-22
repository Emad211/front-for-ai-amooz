"""Regression coverage for video-derived exam-prep structure and math text."""

from __future__ import annotations

import pytest

from apps.classes.services import exam_prep_structure as structure
from apps.classes.services.exam_prep_utils import normalize_exam_prep_questions
from apps.classes.services.schemas import ExamPrepOutput
from apps.commons.llm_prompts import PROMPTS


pytestmark = pytest.mark.unit


def test_prompt_requires_video_duplicate_reconciliation_and_field_separation():
    prompt = PROMPTS["exam_prep_structure"]["default"]

    assert "audio/video" in prompt
    assert "STRICT FIELD SEPARATION" in prompt
    assert "only inside `options`" in prompt


def test_latex_repair_preserves_real_line_breaks():
    raw = "صورت سؤال\nالف) پاسخ" + "\f" + "rac{1}{2}" + " و p" + "\n" + "eq q"

    cleaned = structure._clean(raw)

    assert "صورت سؤال\nالف) پاسخ" in cleaned
    assert r"\frac{1}{2}" in cleaned
    assert r"p\neq q" in cleaned
    assert r"\nالف" not in cleaned


def test_latex_repair_handles_double_escapes_without_breaking_array_newlines():
    raw = r"$\\frac{1}{2} \\neq 0$ and \\(x+1\\)" + "\n" + r"$a \\ b$"

    cleaned = structure._clean(raw)

    assert r"$\frac{1}{2} \neq 0$" in cleaned
    assert r"\(x+1\)" in cleaned
    assert r"$a \\ b$" in cleaned


@pytest.mark.parametrize(
    "question_text, options, expected",
    [
        (
            "حاصل دنباله کدام است؟\nالف) ۱\nب) ۲\nج) ۳\nد) ۴",
            [
                {"label": "الف", "text_markdown": "۱"},
                {"label": "ب", "text_markdown": "۲"},
                {"label": "ج", "text_markdown": "۳"},
                {"label": "د", "text_markdown": "۴"},
            ],
            "حاصل دنباله کدام است؟",
        ),
        (
            r"بازه تابع کدام است؟\n1) 22\n2) 22.25\n3) 22.5\n4) 22.75",
            [
                {"label": "الف", "text_markdown": "22"},
                {"label": "ب", "text_markdown": "22.25"},
                {"label": "ج", "text_markdown": "22.5"},
                {"label": "د", "text_markdown": "22.75"},
            ],
            "بازه تابع کدام است؟",
        ),
    ],
)
def test_normalizer_removes_only_a_complete_trailing_option_block(question_text, options, expected):
    payload = {
        "exam_prep": {
            "questions": [
                {
                    "question_id": "q-1",
                    "question_text_markdown": question_text,
                    "options": options,
                }
            ]
        }
    }

    normalized, changed = normalize_exam_prep_questions(payload)

    assert changed is True
    assert normalized["exam_prep"]["questions"][0]["question_text_markdown"] == expected


def test_normalizer_does_not_delete_partial_or_unlabelled_question_text():
    original = "اگر گزینه الف برابر ۲ باشد، مقدار گزینه ب را پیدا کنید."
    payload = {
        "exam_prep": {
            "questions": [
                {
                    "question_id": "q-1",
                    "question_text_markdown": original,
                    "options": [
                        {"label": "الف", "text_markdown": "۲"},
                        {"label": "ب", "text_markdown": "۴"},
                    ],
                }
            ]
        }
    }

    normalized, _ = normalize_exam_prep_questions(payload)

    assert normalized["exam_prep"]["questions"][0]["question_text_markdown"] == original


def test_video_transcript_output_is_structured_and_cleaned(monkeypatch):
    monkeypatch.setenv("STRUCTURE_MODEL", "test-model")
    dirty_question = {
        "question_text_markdown": "کدام درست است؟\nالف) اول\nب) دوم",
        "options": [
            {"label": "الف", "text_markdown": "اول"},
            {"label": "ب", "text_markdown": "دوم"},
        ],
    }

    monkeypatch.setattr(
        structure,
        "generate_structured",
        lambda **_: ExamPrepOutput.model_validate(
            {"exam_prep": {"title": "آزمون", "questions": [dirty_question]}}
        ),
    )

    result, _, _ = structure.extract_exam_prep_structure(
        transcript_markdown="گفتار مدرس و متن گزینه‌های دیده‌شده در فریم ویدیو"
    )

    question = result["exam_prep"]["questions"][0]
    assert question["question_text_markdown"] == "کدام درست است؟"
    assert [item["text_markdown"] for item in question["options"]] == ["اول", "دوم"]


def test_windowing_advances_when_configured_overlap_is_too_large(monkeypatch):
    monkeypatch.setenv("STRUCTURE_MODEL", "test-model")
    monkeypatch.setenv("EXAM_PREP_WINDOW_CHARS", "4000")
    monkeypatch.setenv("EXAM_PREP_WINDOW_OVERLAP", "8000")
    calls = []

    def fake_generate(**kwargs):
        calls.append(kwargs["messages"][1]["content"])
        return ExamPrepOutput.model_validate(
            {
                "exam_prep": {
                    "questions": [
                        {"question_text_markdown": f"سؤال یکتا {len(calls)}", "options": []}
                    ]
                }
            }
        )

    monkeypatch.setattr(structure, "generate_structured", fake_generate)
    structure.extract_exam_prep_structure(transcript_markdown="متن " * 2500)

    assert 2 <= len(calls) <= 5
