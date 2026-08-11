from __future__ import annotations

import pytest

from apps.classes.services.exam_prep_mistral_risk_engine import score_region_risks
from apps.classes.services.exam_prep_mistral_solution_headings import parse_solution_heading
from apps.classes.services.exam_prep_mistral_targeted_recovery import (
    overlay_recovered_solution_regions,
    recovered_solution_layout_regions,
)


def _projection():
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
                    "source_regions": [],
                }
            ]
        }
    }


def _targeted_root():
    return {
        "pages": [
            {
                "index": 0,
                "blocks": [
                    {
                        "type": "text",
                        "content": "127- گزینه 3",
                        "bbox": {"x0": 0.05, "y0": 0.10, "x1": 0.95, "y1": 0.15},
                    },
                    {
                        "type": "text",
                        "content": "متن پاسخ سؤال 127",
                        "bbox": {"x0": 0.05, "y0": 0.16, "x1": 0.95, "y1": 0.23},
                    },
                    {
                        "type": "image",
                        "content": "",
                        "bbox": {"x0": 0.20, "y0": 0.24, "x1": 0.80, "y1": 0.34},
                    },
                    {
                        "type": "text",
                        "content": "128- گزینه 2",
                        "bbox": {"x0": 0.05, "y0": 0.40, "x1": 0.95, "y1": 0.45},
                    },
                    {
                        "type": "image",
                        "content": "",
                        "bbox": {"x0": 0.20, "y0": 0.50, "x1": 0.80, "y1": 0.60},
                    },
                ],
            }
        ]
    }


def test_markdown_wrapped_solution_heading_is_still_target_evidence():
    parsed = parse_solution_heading("**۱۳۶- گزینهٔ «۲»**")

    assert parsed is not None
    assert parsed["rawQuestionNumber"] == 136
    assert parsed["rawOptionLabel"] == 2


def test_precise_recovered_solution_region_becomes_stage5_decision_and_keeps_visual():
    regions = recovered_solution_layout_regions(
        _targeted_root(),
        crop_specs=[{"physicalPageNumber": 11, "column": "left"}],
        recovered_targets={127: ("3", 11, "left")},
    )

    assert len(regions) == 1
    region = regions[0]
    assert region["questionNumber"] == 127
    assert region["originalPageNumber"] == 11
    assert region["targetedRecoveryRegion"] is True
    assert region["bbox"] == pytest.approx([0.02, 0.164, 0.51, 0.431])
    assert region["targetedRecoveryVisualCandidateCount"] == 1
    assert len(region["visuals"]) == 1
    visual = region["visuals"][0]
    assert visual["type"] == "image"
    assert visual["role"] == "solution"
    assert visual["targetedRecoveryVisual"] is True
    assert visual["bbox"] == pytest.approx([0.118, 0.2886, 0.412, 0.3776])

    layout = overlay_recovered_solution_regions(
        {"pages": [{"originalPageNumber": 11, "regions": []}]},
        regions,
    )
    decisions = score_region_risks(
        projection=_projection(),
        layout=layout,
        recovered_solution_targets={127},
    )

    assert len(decisions) == 1
    decision = decisions[0]
    assert (decision.question_number, decision.kind, decision.page_number) == (127, "solution", 11)
    assert decision.bbox == pytest.approx((0.02, 0.164, 0.51, 0.431))
    assert "heading_conflict" in decision.signals


def test_multi_heading_provider_block_stays_fail_closed():
    root = {
        "pages": [
            {
                "index": 0,
                "blocks": [
                    {
                        "type": "text",
                        "content": "127- گزینه 3\n128- گزینه 2",
                        "bbox": {"x0": 0.05, "y0": 0.10, "x1": 0.95, "y1": 0.50},
                    }
                ],
            }
        ]
    }

    regions = recovered_solution_layout_regions(
        root,
        crop_specs=[{"physicalPageNumber": 11, "column": "left"}],
        recovered_targets={127: ("3", 11, "left")},
    )

    assert regions == []
    decisions = score_region_risks(
        projection=_projection(),
        layout={"pages": [{"originalPageNumber": 11, "regions": []}]},
        recovered_solution_targets={127},
    )
    assert decisions == []
