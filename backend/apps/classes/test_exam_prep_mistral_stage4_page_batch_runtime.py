from __future__ import annotations

from apps.classes.services import exam_prep_mistral_stage4_page_batch_runtime as runtime
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision


def test_solution_candidate_comparison_excludes_final_answer_metadata(monkeypatch):
    decision = RegionRiskDecision(
        question_number=52,
        kind="solution",
        page_number=40,
        bbox=(0.1, 0.1, 0.8, 0.5),
        score=55,
        suspicious=True,
        hard_math=True,
        signals=("visual_anomaly",),
        region_issues=(),
        candidate_text="راه حل 300 375 0.75\nگزینه 3",
    )
    monkeypatch.setattr(runtime, "_score", lambda **_kwargs: [decision])
    projection = {
        "exam_prep": {
            "questions": [
                {
                    "source_question_number": "52",
                    "question_text_markdown": "صورت سؤال",
                    "options": [
                        {"label": "1", "text_markdown": "الف"},
                        {"label": "2", "text_markdown": "ب"},
                        {"label": "3", "text_markdown": "ج"},
                        {"label": "4", "text_markdown": "د"},
                    ],
                    "teacher_solution_markdown": "راه حل 300 375 0.75",
                    "final_answer_markdown": "گزینه 3",
                }
            ]
        }
    }
    [normalized] = runtime._normalized_score_region_risks(
        projection=projection,
        layout={},
    )
    assert normalized.candidate_text == "راه حل 300 375 0.75"
    assert "گزینه 3" not in normalized.candidate_text
