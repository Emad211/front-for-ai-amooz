from __future__ import annotations

from types import SimpleNamespace

from apps.classes.services import exam_prep_mistral_stage4_page_batch_runtime as runtime


def test_native_pdf_answer_label_is_never_an_llm_repair_field():
    decision = SimpleNamespace(
        kind="solution",
        signals=("missing_invalid_answer", "ocr_disagreement", "source_corruption"),
        region_issues=("missing_answer",),
    )
    question = {
        "correct_option_label": "2",
        "teacher_solution_markdown": "متن خراب",
        "issues": [
            "native_pdf_answer_label_authority",
            "missing_answer",
            "broken_persian_text",
        ],
    }
    payload = {
        "correct_option_label": "4",
        "teacher_solution_markdown": "راه حل خوانا",
    }
    needed = runtime._needed_fields(decision, question, payload)
    assert "teacher_solution_markdown" in needed
    assert "correct_option_label" not in needed
