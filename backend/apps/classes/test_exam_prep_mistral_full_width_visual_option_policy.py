from __future__ import annotations

from apps.classes.services.exam_prep_mistral_full_width_visual_option_policy import (
    production_plans_for_region,
)
from apps.classes.services import exam_prep_mistral_visuals as v


def _visual(provider: int, label: str | None, box):
    value = {
        "type": "image",
        "bbox": list(box),
        "providerIndex": provider,
        "role": "option" if label else "question",
    }
    if label:
        value["optionLabel"] = label
    return value


def test_prebound_full_width_options_become_four_option_plans():
    region = {
        "kind": "question",
        "questionNumber": 286,
        "bbox": [0.0, 0.05, 1.0, 0.90],
        "visuals": [
            _visual(10, None, (0.10, 0.12, 0.30, 0.30)),
            _visual(11, "4", (0.10, 0.55, 0.22, 0.70)),
            _visual(12, "3", (0.30, 0.55, 0.42, 0.70)),
            _visual(13, "2", (0.52, 0.55, 0.64, 0.70)),
            _visual(14, "1", (0.76, 0.55, 0.88, 0.70)),
        ],
    }
    seeds = [
        v.VisualSeed(
            seed_id=f"seed-{raw['providerIndex']}",
            page_number=29,
            question_number=286,
            region_kind="question",
            source_kind="ocr_image",
            bbox=tuple(raw["bbox"]),
            provider_index=raw["providerIndex"],
        )
        for raw in region["visuals"]
    ]
    plans, _issues = production_plans_for_region(
        page_number=29,
        region=region,
        seeds=seeds,
        blocks=[],
        config=v.VisualPipelineConfig(),
    )
    option_plans = [plan for plan in plans if plan.role == "option"]
    assert {plan.option_label for plan in option_plans} == {"1", "2", "3", "4"}
    assert all(plan.mode == "full_width_exact_option" for plan in option_plans)
    assert any(plan.role == "question" for plan in plans)
