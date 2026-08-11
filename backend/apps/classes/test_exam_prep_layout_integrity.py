import io
import json

import pytest
from PIL import Image, ImageDraw

from apps.classes.services.exam_prep_page_extractor import RenderedExamPage
from apps.classes.services.exam_prep_page_layout import (
    PageLayoutDecision,
    classify_exam_page,
)
from apps.classes.services.exam_prep_page_records import PageAssemblyResult
from apps.classes.services.exam_prep_page_routed_extractor import (
    LooseSourcePageExtraction,
    consume_page_runtime_stats,
    extract_exam_prep_page,
)
from apps.classes.services.exam_prep_projection_integrity import (
    apply_projection_integrity,
)
from apps.classes.services.exam_prep_question_targeted_verifier_v2 import (
    TargetedVerificationCancelled,
    verify_suspicious_questions,
)


def _png(draw=None):
    image = Image.new("RGB", (800, 1100), "white")
    if draw is not None:
        draw(ImageDraw.Draw(image))
    output = io.BytesIO()
    image.save(output, format="PNG")
    image.close()
    return output.getvalue()


def _result(questions):
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "آزمون", "questions": questions}},
        issues=[],
        question_count=len(questions),
        questions_needing_review=0,
        matched_answer_count=0,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=True,
    )


def test_cover_page_is_skipped_without_provider_evidence():
    decision = classify_exam_page(
        image=_png(lambda draw: draw.text((250, 200), "EXAM", fill="black")),
        native_text=(
            "دفترچه سوالات قلمچی\n"
            "آزمون زیست شناسی\n"
            "نام و نام خانوادگی"
        ),
    )
    assert decision.content_class == "non_content"
    assert decision.layout == "none"


def test_strong_vertical_gutter_routes_to_two_columns():
    image = _png(
        lambda draw: (
            draw.rectangle((450, 80, 760, 1030), fill="black"),
            draw.rectangle((40, 80, 350, 1030), fill="black"),
        )
    )
    decision = classify_exam_page(
        image=image,
        native_text="سؤال 1. متن\n" * 30,
        right_native_text="پاسخ 1\n" * 30,
        left_native_text="پاسخ 20\n" * 30,
    )
    assert decision.layout == "double"


def test_non_content_routed_extractor_makes_zero_calls(monkeypatch):
    from apps.classes.services import exam_prep_page_routed_extractor as routed

    monkeypatch.setattr(
        routed,
        "classify_exam_page",
        lambda **_kwargs: PageLayoutDecision(
            "non_content",
            "none",
            0.99,
            ("cover",),
        ),
    )
    monkeypatch.setattr(
        routed,
        "generate_structured",
        lambda **_kwargs: pytest.fail("provider must not be called"),
    )
    result = extract_exam_prep_page(
        RenderedExamPage(page_number=1, image=_png()),
        model="vision-model",
    )
    stats = consume_page_runtime_stats(1)
    assert result.records == []
    assert stats[-1]["providerCallCount"] == 0
    assert stats[-1]["skippedNonContent"] is True


def test_uncertain_layout_uses_one_multi_image_call(monkeypatch):
    from apps.classes.services import exam_prep_page_routed_extractor as routed

    monkeypatch.setattr(
        routed,
        "classify_exam_page",
        lambda **_kwargs: PageLayoutDecision(
            "content",
            "uncertain",
            0.6,
            ("mixed",),
        ),
    )
    calls = []

    def fake_generate(**kwargs):
        calls.append(kwargs)
        return LooseSourcePageExtraction(page_number=1, records=[])

    monkeypatch.setattr(routed, "generate_structured", fake_generate)
    extract_exam_prep_page(
        RenderedExamPage(page_number=1, image=_png()),
        model="vision-model",
    )
    content = calls[0]["messages"][1]["content"]
    image_parts = [item for item in content if item.get("type") != "text"]
    assert len(calls) == 1
    assert len(image_parts) == 3


def test_double_layout_uses_exactly_two_calls(monkeypatch):
    from apps.classes.services import exam_prep_page_routed_extractor as routed

    monkeypatch.setattr(
        routed,
        "classify_exam_page",
        lambda **_kwargs: PageLayoutDecision(
            "content",
            "double",
            0.95,
            ("gutter",),
        ),
    )
    calls = []

    def fake_generate(**_kwargs):
        calls.append(1)
        return LooseSourcePageExtraction(page_number=1, records=[])

    monkeypatch.setattr(routed, "generate_structured", fake_generate)
    extract_exam_prep_page(
        RenderedExamPage(page_number=1, image=_png()),
        model="vision-model",
    )
    stats = consume_page_runtime_stats(1)
    assert len(calls) == 2
    assert stats[-1]["columnCalls"] == 2


def test_integrity_fixes_serialized_option_and_combining_hamza_label():
    result, stats = apply_projection_integrity(
        _result(
            [
                {
                    "question_id": "default-q-21",
                    "scope_key": "default",
                    "source_question_number": "21",
                    "question_text_markdown": "کدام گزینه درست است؟",
                    "options": [
                        {
                            "label": "1",
                            "text_markdown": json.dumps(
                                {"label": "۱", "text_markdown": "الف"},
                                ensure_ascii=False,
                            ),
                        },
                        {"label": "2", "text_markdown": "ب"},
                        {"label": "3", "text_markdown": "ج"},
                        {"label": "4", "text_markdown": "د"},
                    ],
                    "correct_option_label": None,
                    "teacher_solution_markdown": "گزینهٔ «۴» پاسخ صحیح است.",
                    "issues": [],
                    "source_pages": [4, 12],
                }
            ]
        )
    )
    question = result.projection["exam_prep"]["questions"][0]
    assert question["options"][0] == {
        "label": "1",
        "text_markdown": "الف",
    }
    assert question["correct_option_label"] == "4"
    assert "missing_correct_option_label" not in question["issues"]
    assert stats["serializedOptionsFixed"] == 1
    assert stats["inferredCorrectOptionCount"] == 1


def test_duplicate_solution_across_different_questions_is_flagged():
    solution = "این یک راه حل بسیار طولانی و تکراری است. " * 20
    result, stats = apply_projection_integrity(
        _result(
            [
                {
                    "question_id": "default-q-7",
                    "scope_key": "default",
                    "source_question_number": "7",
                    "question_text_markdown": "سؤال درباره تولید پروتئین",
                    "options": [
                        {"label": "1", "text_markdown": "الف"},
                        {"label": "2", "text_markdown": "ب"},
                    ],
                    "correct_option_label": "1",
                    "teacher_solution_markdown": solution,
                    "issues": [],
                    "source_pages": [2, 9],
                },
                {
                    "question_id": "default-q-8",
                    "scope_key": "default",
                    "source_question_number": "8",
                    "question_text_markdown": (
                        "سؤال کاملاً متفاوت درباره تاریخ زیست فناوری"
                    ),
                    "options": [
                        {"label": "1", "text_markdown": "الف"},
                        {"label": "2", "text_markdown": "ب"},
                    ],
                    "correct_option_label": "2",
                    "teacher_solution_markdown": solution,
                    "issues": [],
                    "source_pages": [2, 9],
                },
            ]
        )
    )
    question = result.projection["exam_prep"]["questions"][1]
    assert "duplicate_solution_across_questions" in question["issues"]
    assert stats["duplicateSolutionCount"] == 1


def test_targeted_verifier_honors_cancel_before_any_question_call():
    with pytest.raises(TargetedVerificationCancelled):
        verify_suspicious_questions(
            _result(
                [
                    {
                        "question_id": "default-q-1",
                        "scope_key": "default",
                        "source_question_number": "1",
                        "question_text_markdown": "",
                        "options": [],
                        "correct_option_label": None,
                        "teacher_solution_markdown": "",
                        "issues": ["missing_question_text"],
                        "source_pages": [1],
                    }
                ]
            ),
            source_pages_by_number={},
            model="vision-model",
            should_cancel=lambda: True,
        )
