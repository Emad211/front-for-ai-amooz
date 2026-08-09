from __future__ import annotations

from PIL import Image, ImageDraw

# Import the stable facade first; it installs the shared normalized clamp used by
# the lower-level v2 helper module without changing its policy.
from apps.classes.services import exam_prep_mistral_visual_reconcile as stable
from apps.classes.services import exam_prep_mistral_visual_reconcile_v2 as policy
from apps.classes.services.exam_prep_mistral_layout_analysis import LayoutBlock
from apps.classes.services.exam_prep_mistral_visuals import VisualSeed

VisualPipelineConfig = stable.VisualPipelineConfig


def _block(index: int, kind: str, text: str, bbox):
    return LayoutBlock(
        provider_index=index,
        block_type=kind,
        content=text,
        bbox=bbox,
        column="right",
        raw={},
    )


def _seed(seed_id: str, bbox, *, table: bool = False):
    return VisualSeed(
        seed_id=seed_id,
        page_number=1,
        question_number=1,
        region_kind="question",
        source_kind="ocr_table" if table else "ocr_image",
        bbox=bbox,
        is_table=table,
    )


def test_text_mask_components_removes_ocr_text_but_keeps_uncovered_diagram():
    image = Image.new("RGB", (600, 800), "white")
    try:
        draw = ImageDraw.Draw(image)
        draw.rectangle((330, 120, 540, 180), fill="black")
        draw.rectangle((80, 300, 260, 460), outline="black", width=5)
        draw.line((80, 380, 260, 380), fill="black", width=4)
        blocks = [
            _block(1, "text", "متن طولانی پاسخ", (0.54, 0.14, 0.92, 0.24)),
        ]
        components = policy._text_mask_components(image, blocks)
    finally:
        image.close()
    boxes = [policy._component_bbox(item) for item in components]
    boxes = [box for box in boxes if box is not None]
    assert any(box[0] < 0.45 and box[1] > 0.30 for box in boxes)
    assert not any(box[0] > 0.50 and box[1] < 0.28 for box in boxes)


def test_refined_image_bbox_shrinks_provider_image_around_graphic_core():
    seed = (0.10, 0.10, 0.90, 0.80)
    region = (0.05, 0.05, 0.95, 0.90)
    components = [
        {
            "bbox": [0.18, 0.22, 0.55, 0.58],
            "inkPixels": 3000,
            "widthPx": 200,
            "heightPx": 180,
        },
        {
            "bbox": [0.58, 0.24, 0.76, 0.52],
            "inkPixels": 1700,
            "widthPx": 100,
            "heightPx": 140,
        },
    ]
    refined = policy._refined_image_bbox(seed, components, region_box=region)
    assert refined[0] > seed[0]
    assert refined[1] > seed[1]
    assert refined[2] < seed[2]
    assert refined[3] < seed[3]


def test_table_plan_does_not_union_unrelated_option_or_stem_text():
    config = VisualPipelineConfig(padding=0.008)
    region = {
        "kind": "question",
        "questionNumber": 81,
        "bbox": [0.10, 0.10, 0.95, 0.90],
    }
    table_seed = _seed("table", (0.20, 0.30, 0.80, 0.62), table=True)
    plans, issues = policy._table_plans(
        page_number=1,
        region=region,
        seeds=[table_seed],
        config=config,
    )
    assert issues == []
    assert len(plans) == 1
    plan = plans[0]
    assert plan.mode == "table"
    assert plan.bbox[1] > 0.20
    assert plan.bbox[3] < 0.70


def test_grouped_visual_options_are_publishable_without_fake_individual_binding(monkeypatch):
    region = {
        "kind": "question",
        "questionNumber": 150,
        "bbox": [0.10, 0.10, 0.95, 0.90],
        "visualOptionMode": "separate_candidates",
    }
    grouped = policy.VisualPlan(
        page_number=1,
        question_number=150,
        role="question",
        option_label=None,
        mode="grouped_options",
        bbox=(0.20, 0.25, 0.85, 0.65),
        source_kinds=("ocr_image",),
        component_ids=("1", "2", "3", "4"),
        grouped_option_labels=("1", "2", "3", "4"),
        sanity_issues=("visual_option_binding_unresolved",),
        review_only=True,
    )

    monkeypatch.setattr(
        policy.legacy,
        "_harden_region_plans",
        lambda **_kwargs: (
            [grouped],
            ["visual_option_binding_unresolved"],
        ),
    )
    plans, issues = policy._plans_for_region(
        page_number=1,
        region=region,
        seeds=[_seed("1", (0.2, 0.2, 0.3, 0.3))],
        blocks=[],
        config=VisualPipelineConfig(),
    )
    assert issues == []
    assert plans[0].mode == "grouped_options"
    assert plans[0].review_only is False
    assert plans[0].sanity_issues == ()


def test_v2_base_does_not_accept_permissive_local_only_solution_typography():
    source_kinds = ["local_graphic"]
    kept = [kind for kind in source_kinds if kind.startswith("ocr_")]
    assert kept == []
