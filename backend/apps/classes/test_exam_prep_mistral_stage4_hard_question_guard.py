from __future__ import annotations

from types import SimpleNamespace

from apps.classes.services import exam_prep_mistral_stage4_hard_question_guard as guard
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _question(stem: str):
    return {
        "question_id": "default-q-87",
        "scope_key": "default",
        "section_key": "default",
        "source_question_number": "87",
        "question_text_markdown": stem,
        "options": [
            {"label": "1", "text_markdown": "4"},
            {"label": "2", "text_markdown": "3"},
            {"label": "3", "text_markdown": "2"},
            {"label": "4", "text_markdown": "1"},
        ],
        "correct_option_label": "1",
        "teacher_solution_markdown": "راه حل",
        "final_answer_markdown": "گزینه 1",
        "issues": [],
        "visuals": [],
    }


def _result(stem: str):
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "test", "questions": [_question(stem)]}},
        issues=[],
        question_count=1,
        questions_needing_review=0,
        matched_answer_count=1,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=True,
    )


def _decision():
    return RegionRiskDecision(
        question_number=87,
        kind="question",
        page_number=18,
        bbox=(0.0, 0.1, 1.0, 0.6),
        score=100,
        suspicious=True,
        hard_math=True,
        signals=("missing_invalid_answer", "ocr_disagreement"),
        region_issues=(),
        candidate_text="source",
    )


def _audit():
    return {
        "stats": {
            "secondaryCalls": 0,
            "secondaryCostUsd": 0.0,
            "primaryCostUsd": 0.01,
            "totalLlmCostUsd": 0.01,
            "verified": 1,
            "repaired": 1,
            "unresolved": 0,
        },
        "policy": {},
        "regions": [
            {
                "targetId": "q-087-p018",
                "questionNumber": 87,
                "kind": "question",
                "status": "repaired_primary_fields",
                "neededFields": ["question_text_markdown"],
            }
        ],
    }


def _secondary(stem: str):
    result = SimpleNamespace(
        transcript={"transcriptionUncertain": False},
        safe_dict=lambda: {"model": "gpt-5.4-mini"},
    )
    payload = {
        "question_text_markdown": stem,
        "options": [
            {"label": "1", "text_markdown": "4"},
            {"label": "2", "text_markdown": "3"},
            {"label": "3", "text_markdown": "2"},
            {"label": "4", "text_markdown": "1"},
        ],
    }
    return result, payload, ()


def test_numeric_overwrite_requires_and_accepts_independent_consensus(monkeypatch):
    monkeypatch.setattr(guard, "score_region_risks", lambda **_kwargs: [_decision()])
    monkeypatch.setattr(guard.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        guard.impl,
        "_secondary_payload",
        lambda *_args, **_kwargs: _secondary("غلظت 33 ضربدر 10 به توان منفی 2 است"),
    )
    monkeypatch.setattr(guard.impl, "_secondary_cost", lambda _value: 0.001)

    updated, audit = guard.enforce_hard_question_numeric_consensus(
        _result("غلظت 1/33 ضربدر 10 به توان منفی 2 است"),
        _result("غلظت 33 ضربدر 10 به توان منفی 2 است"),
        _audit(),
        pdf_data=b"pdf",
        layout={},
        max_cost_usd=1.0,
    )
    assert "33" in updated.projection["exam_prep"]["questions"][0]["question_text_markdown"]
    assert audit["regions"][0]["status"] == "repaired_hard_question_numeric_consensus"
    assert audit["stats"]["secondaryCalls"] == 1


def test_q87_style_numeric_disagreement_rolls_back(monkeypatch):
    monkeypatch.setattr(guard, "score_region_risks", lambda **_kwargs: [_decision()])
    monkeypatch.setattr(guard.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        guard.impl,
        "_secondary_payload",
        lambda *_args, **_kwargs: _secondary("غلظت 1/33 ضربدر 10 به توان منفی 2 است"),
    )
    monkeypatch.setattr(guard.impl, "_secondary_cost", lambda _value: 0.001)

    updated, audit = guard.enforce_hard_question_numeric_consensus(
        _result("غلظت 1/33 ضربدر 10 به توان منفی 2 است"),
        _result("غلظت 33 ضربدر 10 به توان منفی 2 است"),
        _audit(),
        pdf_data=b"pdf",
        layout={},
        max_cost_usd=1.0,
    )
    question = updated.projection["exam_prep"]["questions"][0]
    assert "1/33" in question["question_text_markdown"]
    assert "stage4_verification_unresolved" in question["issues"]
    assert audit["regions"][0]["status"] == "hard_question_numeric_consensus_disagreement"
    assert audit["stats"]["repaired"] == 0
    assert audit["stats"]["unresolved"] == 1
