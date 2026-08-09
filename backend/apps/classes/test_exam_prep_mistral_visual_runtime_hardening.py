from __future__ import annotations

import inspect

from apps.classes.services import exam_prep_mistral_visual_runtime as runtime
from apps.classes.services import exam_prep_mistral_visuals as visuals
from apps.classes.services.exam_prep_mistral_layout_analysis import LayoutBlock


def _block(index: int, kind: str, text: str, bbox):
    return LayoutBlock(
        provider_index=index,
        block_type=kind,
        content=text,
        bbox=bbox,
        column="right" if bbox[0] >= 0.5 else "left",
        raw={},
    )


def _seed(seed_id: str, bbox):
    return visuals.VisualSeed(
        seed_id=seed_id,
        page_number=1,
        question_number=2,
        region_kind="question",
        source_kind="ocr_image",
        bbox=bbox,
    )


def test_runtime_contains_no_general_llm_dependency():
    source = inspect.getsource(runtime)
    assert "generate_structured(" not in source
    assert "llm_client" not in source
    assert "exam_prep_v4" not in source


def test_question_heading_two_is_never_accepted_as_option_two_marker():
    region_box = (0.50, 0.10, 1.0, 0.85)
    blocks = [
        _block(7, "text", "2- متن سؤال", (0.55, 0.11, 0.88, 0.16)),
        _block(10, "image", "", (0.58, 0.30, 0.74, 0.44)),
    ]
    region = {
        "bbox": list(region_box),
        "headingProviderIndex": 7,
    }
    safe = runtime._without_heading(blocks, region)
    assert {label for label, _box in visuals._option_markers(safe, region_box)} == set()


def test_axis_ticks_inside_visual_boxes_are_not_option_markers():
    region_box = (0.05, 0.10, 0.95, 0.90)
    image_boxes = [
        (0.55, 0.22, 0.72, 0.38),
        (0.30, 0.22, 0.47, 0.38),
        (0.55, 0.48, 0.72, 0.64),
        (0.30, 0.48, 0.47, 0.64),
    ]
    blocks = [
        *[
            _block(index, "image", "", box)
            for index, box in enumerate(image_boxes, start=10)
        ],
        _block(20, "text", "1", (0.58, 0.30, 0.60, 0.32)),
        _block(21, "text", "2", (0.33, 0.30, 0.35, 0.32)),
        _block(22, "text", "3", (0.58, 0.56, 0.60, 0.58)),
        _block(23, "text", "4", (0.33, 0.56, 0.35, 0.58)),
    ]
    assert visuals._option_markers(blocks, region_box) == []


def test_separate_option_assets_require_four_explicit_external_labels():
    region = {
        "kind": "question",
        "questionNumber": 2,
        "bbox": [0.05, 0.10, 0.95, 0.90],
        "visualOptionMode": "separate_candidates",
        "headingProviderIndex": 1,
        "captions": [],
    }
    image_boxes = [
        (0.55, 0.22, 0.72, 0.38),
        (0.30, 0.22, 0.47, 0.38),
        (0.55, 0.48, 0.72, 0.64),
        (0.30, 0.48, 0.47, 0.64),
    ]
    seeds = [_seed(str(index), box) for index, box in enumerate(image_boxes, start=1)]
    blocks = [
        _block(1, "text", "2- سؤال", (0.55, 0.11, 0.85, 0.15)),
        *[
            _block(index, "image", "", box)
            for index, box in enumerate(image_boxes, start=10)
        ],
    ]
    plans, issues = visuals._plans_for_region(
        page_number=1,
        region=region,
        seeds=seeds,
        blocks=runtime._without_heading(blocks, region),
        config=visuals.VisualPipelineConfig(),
    )
    assert plans == []
    assert issues == ["visual_option_binding_unresolved"]


def test_geometry_only_binding_becomes_grouped_review_only_in_runtime():
    region = {
        "kind": "question",
        "questionNumber": 2,
        "bbox": [0.05, 0.10, 0.95, 0.90],
        "visualOptionMode": "separate_candidates",
        "headingProviderIndex": 1,
        "captions": [],
    }
    image_boxes = [
        (0.55, 0.22, 0.72, 0.38),
        (0.30, 0.22, 0.47, 0.38),
        (0.55, 0.48, 0.72, 0.64),
        (0.30, 0.48, 0.47, 0.64),
    ]
    seeds = [_seed(str(index), box) for index, box in enumerate(image_boxes, start=1)]
    blocks = [
        _block(1, "text", "2- سؤال", (0.55, 0.11, 0.85, 0.15)),
        *[
            _block(index, "image", "", box)
            for index, box in enumerate(image_boxes, start=10)
        ],
    ]
    plans, issues = runtime._harden_region_plans(
        page_number=1,
        region=region,
        seeds=seeds,
        blocks=blocks,
        config=visuals.VisualPipelineConfig(),
    )
    assert len(plans) == 1
    assert plans[0].mode == "grouped_options"
    assert plans[0].review_only is True
    assert "visual_option_binding_unresolved" in issues
    assert "visual_option_binding_unresolved" in plans[0].sanity_issues
