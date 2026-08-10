from __future__ import annotations

from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision
from apps.classes.services.exam_prep_mistral_risk_engine_v2 import (
    _options_complete,
    _structural_signals,
)


def _decision(*, kind: str = "question") -> RegionRiskDecision:
    return RegionRiskDecision(
        question_number=125,
        kind=kind,
        page_number=20,
        bbox=(0.1, 0.1, 0.9, 0.8),
        score=0,
        suspicious=False,
        hard_math=False,
        signals=(),
        region_issues=(),
        candidate_text="",
    )


def _question():
    return {
        "source_question_number": "125",
        "question_text_markdown": "صورت سؤال",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "teacher_solution_markdown": "راه حل",
        "issues": [],
    }


def test_complete_four_option_contract_is_deterministic():
    question = _question()
    assert _options_complete(question) is True
    question["options"][3]["text_markdown"] = ""
    assert _options_complete(question) is False


def test_missing_stem_and_options_are_never_clean_question_evidence():
    question = _question()
    question["question_text_markdown"] = ""
    question["options"] = []
    question["issues"] = ["missing_question_text"]
    signals = _structural_signals(_decision(), question)
    assert "structural_missing_question_text" in signals
    assert "structural_options_incomplete" in signals


def test_unresolved_visual_source_is_structural_risk():
    question = _question()
    question["issues"] = ["visual_precise_crop_unresolved"]
    assert "structural_visual_source_unresolved" in _structural_signals(
        _decision(), question
    )


def test_missing_solution_body_is_never_clean_solution_evidence():
    question = _question()
    question["teacher_solution_markdown"] = ""
    signals = _structural_signals(_decision(kind="solution"), question)
    assert "structural_missing_solution_body" in signals
