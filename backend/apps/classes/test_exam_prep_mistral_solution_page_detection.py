from __future__ import annotations

from apps.classes.services.exam_prep_mistral_solution_headings import (
    is_solution_content_page,
    solution_heading_candidates,
)


def _block(content: str, y: float):
    return {
        "type": "text",
        "content": content,
        "x0": 0.55,
        "y0": y,
        "x1": 0.95,
        "y1": y + 0.03,
    }


def test_two_structural_answer_headings_make_solution_page_without_header_keyword():
    page = {
        "header": "فرهنگیان - دفترچه دوم",
        "blocks": [
            _block("251 - گزینه 2", 0.10),
            _block("252 - گزینه 4", 0.30),
        ],
    }
    assert is_solution_content_page(page) is True
    candidates = solution_heading_candidates(page, physical_page_number=55)
    assert [(item.raw_question_number, item.raw_option_label) for item in candidates] == [
        (251, 2),
        (252, 4),
    ]


def test_one_isolated_answer_like_heading_does_not_reclassify_page():
    page = {
        "header": "آزمون",
        "blocks": [
            _block("12 - گزینه 3", 0.20),
            _block("متن معمول سؤال", 0.40),
        ],
    }
    assert is_solution_content_page(page) is False
    assert solution_heading_candidates(page, physical_page_number=2) == []
