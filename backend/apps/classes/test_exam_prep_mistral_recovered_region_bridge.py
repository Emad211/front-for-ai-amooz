from __future__ import annotations

from apps.classes.services.exam_prep_mistral_risk_engine import score_region_risks


def _projection(source_regions):
    return {
        "exam_prep": {
            "questions": [
                {
                    "source_question_number": 127,
                    "question_text_markdown": "صورت سؤال",
                    "options": [
                        {"label": "1", "text_markdown": "الف"},
                        {"label": "2", "text_markdown": "ب"},
                        {"label": "3", "text_markdown": "پ"},
                        {"label": "4", "text_markdown": "ت"},
                    ],
                    "correct_option_label": "3",
                    "teacher_solution_markdown": "",
                    "issues": [],
                    "visuals": [],
                    "source_regions": source_regions,
                }
            ]
        }
    }


def test_recovered_answer_region_becomes_stage5_solution_decision():
    decisions = score_region_risks(
        projection=_projection(
            [
                {
                    "page_number": 11,
                    "role": "answer",
                    "record_type": "answer",
                    "bbox": {"x0": 0.02, "y0": 0.075, "x1": 0.51, "y1": 0.965},
                }
            ]
        ),
        layout={"pages": []},
        recovered_solution_targets={127},
    )

    assert len(decisions) == 1
    decision = decisions[0]
    assert (decision.question_number, decision.kind, decision.page_number) == (127, "solution", 11)
    assert decision.bbox == (0.02, 0.075, 0.51, 0.965)
    assert "targeted_recovery_region" in decision.signals


def test_ambiguous_recovered_answer_regions_stay_fail_closed():
    decisions = score_region_risks(
        projection=_projection(
            [
                {
                    "page_number": 11,
                    "role": "answer",
                    "bbox": {"x0": 0.02, "y0": 0.075, "x1": 0.51, "y1": 0.965},
                },
                {
                    "page_number": 13,
                    "role": "answer",
                    "bbox": {"x0": 0.49, "y0": 0.075, "x1": 0.98, "y1": 0.965},
                },
            ]
        ),
        layout={"pages": []},
        recovered_solution_targets={127},
    )

    assert decisions == []
