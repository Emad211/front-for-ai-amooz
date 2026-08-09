from __future__ import annotations

from apps.classes.services.exam_prep_mistral_visual_review import (
    visual_options_complete,
)
from apps.classes.services.exam_prep_page_review import audit_page_first_projection


def _option_asset(label: str) -> dict:
    return {
        "id": f"inline-mistral-v1-source-p1-q1-option-o{label}-deadbeef",
        "role": "option",
        "optionLabel": label,
        "selectedVariant": "source",
        "sourcePage": 1,
        "sourceBBox": {"x0": 0.1, "y0": 0.2, "x1": 0.3, "y1": 0.4},
        "storagePath": f"exam-prep/source/visuals/v1/source/p001-q001-option-{label}.png",
        "visualMode": "separate_option",
        "reviewOnly": False,
        "sanity": {"status": "passed", "issues": []},
    }


def _question() -> dict:
    assets = [_option_asset(label) for label in ("1", "2", "3", "4")]
    return {
        "question_id": "default-q-1",
        "scope_key": "default",
        "source_question_number": "1",
        "source_pages": [1],
        "question_text_markdown": "کدام شکل درست است؟",
        "options": [
            {"label": label, "text_markdown": ""}
            for label in ("1", "2", "3", "4")
        ],
        "correct_option_label": "2",
        "teacher_solution_markdown": "این یک راه حل تشریحی معتبر و کافی برای تست است.",
        "final_answer_markdown": "گزینه 2",
        "visuals": assets,
        "visualSourceContract": {
            "schemaVersion": 1,
            "requiredAssetIds": [asset["id"] for asset in assets],
            "roleCounts": {"question": 0, "option": 4, "solution": 0},
            "optionLabels": ["1", "2", "3", "4"],
            "groupedOptionLabels": [],
            "sourcePages": [1],
            "fingerprint": "test",
        },
        "issues": [],
    }


def test_complete_stage3_option_assets_allow_empty_option_text_in_review():
    question = _question()
    assert visual_options_complete(question) is True
    audit = audit_page_first_projection(
        {"exam_prep": {"title": "تست", "questions": [question]}}
    )
    assert not any(
        issue["code"] == "missing_option_text"
        for issue in audit["issues"]
    )


def test_one_review_only_option_makes_visual_only_option_set_incomplete():
    question = _question()
    question["visuals"][3]["reviewOnly"] = True
    question["visuals"][3]["sanity"] = {
        "status": "needs_review",
        "issues": ["visual_crop_clipped"],
    }
    assert visual_options_complete(question) is False
    audit = audit_page_first_projection(
        {"exam_prep": {"title": "تست", "questions": [question]}}
    )
    assert any(
        issue["code"] in {"missing_option_text", "visual_crop_clipped"}
        and issue["severity"] == "critical"
        for issue in audit["issues"]
    )
