from __future__ import annotations

from types import SimpleNamespace

from apps.classes.services import exam_prep_mistral_stage4_pathological_guard as guard
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _question(solution: str):
    return {
        "question_id": "default-q-88",
        "scope_key": "default",
        "section_key": "default",
        "source_question_number": "88",
        "question_text_markdown": "صورت سؤال",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "2",
        "teacher_solution_markdown": solution,
        "final_answer_markdown": "گزینه 2",
        "issues": [],
        "visuals": [],
    }


def _result(solution: str):
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "test", "questions": [_question(solution)]}},
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
        question_number=88,
        kind="solution",
        page_number=40,
        bbox=(0.1, 0.1, 0.8, 0.5),
        score=100,
        suspicious=True,
        hard_math=True,
        signals=("pathological_repetition",),
        region_issues=(),
        candidate_text="متن خراب 1 2",
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
            "partialRepairs": 0,
            "unresolved": 0,
        },
        "policy": {},
        "regions": [
            {
                "targetId": "s-088-p040",
                "questionNumber": 88,
                "kind": "solution",
                "status": "repaired_primary_fields",
                "neededFields": ["teacher_solution_markdown"],
            }
        ],
    }


def _secondary(payload_text: str):
    result = SimpleNamespace(
        transcript={"transcriptionUncertain": False},
        safe_dict=lambda: {"model": "gpt-5.4-mini"},
    )
    payload = {
        "correct_option_label": "2",
        "teacher_solution_markdown": payload_text,
    }
    return result, payload, ()


def test_pathological_repair_is_kept_only_with_independent_consensus(monkeypatch):
    monkeypatch.setattr(guard, "score_region_risks", lambda **_kwargs: [_decision()])
    monkeypatch.setattr(guard.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        guard.impl,
        "_secondary_payload",
        lambda *_args, **_kwargs: _secondary("x=2 و y=3"),
    )
    monkeypatch.setattr(guard.impl, "_secondary_cost", lambda _value: 0.001)

    updated, audit = guard.enforce_pathological_repair_consensus(
        _result("متن خراب 1 2"),
        _result("x=2 و y=3"),
        _audit(),
        pdf_data=b"pdf",
        layout={},
        max_cost_usd=1.0,
    )
    question = updated.projection["exam_prep"]["questions"][0]
    assert question["teacher_solution_markdown"] == "x=2 و y=3"
    assert audit["regions"][0]["status"] == "repaired_pathological_two_model_consensus"
    assert audit["stats"]["unresolved"] == 0
    assert audit["stats"]["secondaryCalls"] == 1


def test_pathological_disagreement_rolls_back_entire_question(monkeypatch):
    monkeypatch.setattr(guard, "score_region_risks", lambda **_kwargs: [_decision()])
    monkeypatch.setattr(guard.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        guard.impl,
        "_secondary_payload",
        lambda *_args, **_kwargs: _secondary("x=9 و y=8"),
    )
    monkeypatch.setattr(guard.impl, "_secondary_cost", lambda _value: 0.001)

    updated, audit = guard.enforce_pathological_repair_consensus(
        _result("متن خراب 1 2"),
        _result("x=2 و y=3"),
        _audit(),
        pdf_data=b"pdf",
        layout={},
        max_cost_usd=1.0,
    )
    question = updated.projection["exam_prep"]["questions"][0]
    assert question["teacher_solution_markdown"] == "متن خراب 1 2"
    assert "stage4_verification_unresolved" in question["issues"]
    assert audit["regions"][0]["status"] == "pathological_consensus_disagreement"
    assert audit["stats"]["repaired"] == 0
    assert audit["stats"]["unresolved"] == 1
