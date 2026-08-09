from __future__ import annotations

import io

from PIL import Image, ImageDraw
from pypdf import PdfWriter

from apps.classes.services import exam_prep_mistral_visual_runtime as runtime
from apps.classes.services import exam_prep_mistral_visuals as visuals
from apps.classes.services.exam_prep_mistral_layout_analysis import LayoutBlock
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


class MemoryStore:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def save(self, name: str, payload: bytes) -> str:
        self.files.setdefault(name, payload)
        return name


def _pdf(page_count: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _result(question: dict | None = None) -> PageAssemblyResult:
    payload = question or {
        "question_id": "default-q-1",
        "scope_key": "default",
        "source_question_number": "1",
        "question_text_markdown": "مطابق شکل، پاسخ دهید.",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "1",
        "teacher_solution_markdown": "راه حل",
        "final_answer_markdown": "گزینه 1",
        "confidence": 0.0,
        "issues": ["visual_reference_without_ocr_visual"],
        "source_pages": [1],
    }
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "تست", "questions": [payload]}},
        issues=[],
        question_count=1,
        questions_needing_review=1,
        matched_answer_count=1,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=False,
    )


def _block(index: int, kind: str, content: str, bbox) -> LayoutBlock:
    return LayoutBlock(
        provider_index=index,
        block_type=kind,
        content=content,
        bbox=bbox,
        column="right" if bbox[0] >= 0.5 else "left",
        raw={},
    )


def _seed(seed_id: str, bbox, *, page: int = 1, role: str = "question", table: bool = False):
    return visuals.VisualSeed(
        seed_id=seed_id,
        page_number=page,
        question_number=1,
        region_kind=role,
        source_kind="ocr_table" if table else "ocr_image",
        bbox=bbox,
        is_table=table,
    )


def test_smart_union_includes_caption_axis_equation_but_not_distant_stem():
    seed = _seed("graph", (0.55, 0.35, 0.82, 0.62))
    blocks = [
        _block(1, "text", "صورت سؤال بلند و نامرتبط", (0.52, 0.15, 0.93, 0.25)),
        _block(2, "caption", "v (m/s)", (0.53, 0.32, 0.62, 0.35)),
        _block(3, "equation", "t=2s", (0.80, 0.61, 0.88, 0.65)),
    ]
    box, components, _sources = visuals._smart_union_bbox(
        [seed],
        blocks=blocks,
        region_box=(0.50, 0.10, 1.0, 0.80),
        heading_index=None,
        config=visuals.VisualPipelineConfig(padding=0.005, auxiliary_gap=0.03),
    )
    assert box[1] < seed.bbox[1]
    assert box[2] > seed.bbox[2]
    assert "block:2" in components
    assert "block:3" in components
    assert "block:1" not in components


def test_repetition_suppresses_margin_template_but_never_repeated_body_diagram():
    margin = _seed("logo", (0.02, 0.02, 0.12, 0.07))
    body = _seed("axis-template", (0.25, 0.30, 0.75, 0.70))
    assert visuals._decorative_candidate(margin, 3) is True
    assert visuals._decorative_candidate(body, 20) is False


def test_grouped_single_block_remains_one_grouped_option_visual():
    region = {
        "kind": "question",
        "questionNumber": 65,
        "bbox": [0.50, 0.10, 1.0, 0.80],
        "visualOptionMode": "grouped_single_block",
        "headingProviderIndex": 0,
        "captions": [],
    }
    seed = visuals.VisualSeed(
        seed_id="circuits",
        page_number=13,
        question_number=65,
        region_kind="question",
        source_kind="ocr_image",
        bbox=(0.55, 0.30, 0.94, 0.65),
    )
    plans, issues = visuals._plans_for_region(
        page_number=13,
        region=region,
        seeds=[seed],
        blocks=[],
        config=visuals.VisualPipelineConfig(),
    )
    assert issues == []
    assert len(plans) == 1
    assert plans[0].mode == "grouped_options"
    assert plans[0].grouped_option_labels == ("1", "2", "3", "4")


def test_nearby_unincluded_axis_label_blocks_region_as_residual_graphics():
    region = {
        "kind": "question",
        "questionNumber": 1,
        "bbox": [0.50, 0.10, 1.0, 0.80],
        "headingProviderIndex": 0,
        "captions": [],
    }
    seed = _seed("graph", (0.58, 0.30, 0.78, 0.55))
    blocks = [
        _block(0, "text", "1- سؤال", (0.55, 0.12, 0.90, 0.16)),
        # Farther than normal Smart Union gap (0.028), but close enough for the
        # widened completeness audit. Losing this axis label must block.
        _block(2, "text", "v (m/s)", (0.58, 0.588, 0.68, 0.615)),
    ]
    plans, issues = visuals._plans_for_region(
        page_number=1,
        region=region,
        seeds=[seed],
        blocks=blocks,
        config=visuals.VisualPipelineConfig(),
    )
    assert len(plans) == 1
    assert "visual_residual_graphics" in issues


def test_table_seed_touching_region_boundary_is_review_only_border_risk():
    region = {
        "kind": "question",
        "questionNumber": 1,
        "bbox": [0.10, 0.10, 0.90, 0.70],
        "headingProviderIndex": 0,
        "captions": [],
    }
    seed = _seed("table", (0.10, 0.25, 0.75, 0.60), table=True)
    plans, issues = runtime._harden_region_plans(
        page_number=1,
        region=region,
        seeds=[seed],
        blocks=[],
        config=visuals.VisualPipelineConfig(padding=0.002, region_guard=0.0),
    )
    assert len(plans) == 1
    assert "visual_table_border_risk" in issues
    assert plans[0].review_only is True


def test_raster_edge_ink_turns_precise_plan_into_review_only_clipping():
    image = Image.new("RGB", (500, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.line((100, 100, 400, 100), fill="black", width=8)
    plan = visuals.VisualPlan(
        page_number=1,
        question_number=1,
        role="question",
        option_label=None,
        mode="single_question",
        bbox=(0.20, 0.20, 0.80, 0.80),
        source_kinds=("ocr_image",),
        component_ids=("x",),
    )
    try:
        hardened = runtime._raster_harden_plan(image, plan)
    finally:
        image.close()
    assert hardened.review_only is True
    assert "visual_crop_clipped" in hardened.sanity_issues


def test_asset_identity_keeps_page_and_role_even_for_identical_payload():
    q1 = visuals.VisualPlan(
        page_number=10,
        question_number=57,
        role="question",
        option_label=None,
        mode="single_question",
        bbox=(0.2, 0.2, 0.5, 0.5),
        source_kinds=("ocr_image",),
        component_ids=("a",),
    )
    q2 = visuals.VisualPlan(
        page_number=11,
        question_number=57,
        role="question",
        option_label=None,
        mode="single_question",
        bbox=(0.2, 0.2, 0.5, 0.5),
        source_kinds=("ocr_image",),
        component_ids=("a",),
    )
    solution = visuals.VisualPlan(
        page_number=40,
        question_number=57,
        role="solution",
        option_label=None,
        mode="solution",
        bbox=(0.2, 0.2, 0.5, 0.5),
        source_kinds=("ocr_image",),
        component_ids=("a",),
    )
    kwargs = {"source_sha256": "a" * 64, "order": 1, "payload_sha256": "b" * 64}
    assert len({
        visuals._asset_name(plan=q1, **kwargs),
        visuals._asset_name(plan=q2, **kwargs),
        visuals._asset_name(plan=solution, **kwargs),
    }) == 3


def test_complete_option_visuals_allow_four_empty_text_slots_without_missing_options():
    question = {
        "question_id": "default-q-1",
        "scope_key": "default",
        "source_question_number": "1",
        "question_text_markdown": "کدام گزینه درست است؟",
        "options": [],
        "correct_option_label": "2",
        "teacher_solution_markdown": "راه حل",
        "final_answer_markdown": "گزینه 2",
        "confidence": 0.0,
        "issues": ["mistral_question_option_parse_failed", "missing_options", "visual_evidence_required"],
        "source_pages": [1],
    }
    assets = [
        {"id": f"inline-mistral-v1-x-o{n}", "role": "option", "optionLabel": str(n), "reviewOnly": False}
        for n in range(1, 5)
    ]
    updated = visuals._rebuild_projection_quality(
        _result(question),
        assets_by_question={1: assets},
        issues_by_question={},
    )
    value = updated.projection["exam_prep"]["questions"][0]
    assert [item["label"] for item in value["options"]] == ["1", "2", "3", "4"]
    assert all(item["text_markdown"] == "" for item in value["options"])
    assert "missing_options" not in value["issues"]
    assert "mistral_question_option_parse_failed" not in value["issues"]
    assert "visual_evidence_required" not in value["issues"]


def test_precise_reconciliation_persists_private_crop_and_removes_resolved_visual_issue():
    data = _pdf()
    ocr_pages = [{
        "index": 0,
        "sourcePhysicalPage": 1,
        "dimensions": {"width": 612, "height": 792},
        "blocks": [{
            "type": "image",
            "content": "",
            "bbox": {"x0": 0.58, "y0": 0.30, "x1": 0.82, "y1": 0.55},
        }],
    }]
    layout = {"pages": [{
        "originalPageNumber": 1,
        "pageRole": "question",
        "regions": [{
            "kind": "question",
            "questionNumber": 1,
            "bbox": [0.50, 0.10, 1.0, 0.80],
            "headingProviderIndex": 9,
            "visuals": [{
                "type": "image",
                "bbox": [0.58, 0.30, 0.82, 0.55],
                "providerIndex": 0,
                "content": "",
            }],
            "captions": [],
            "issues": [],
        }],
    }]}
    store = MemoryStore()
    updated, stats, audit = visuals.reconcile_mistral_source_visuals(
        _result(),
        pdf_data=data,
        ocr_pages=ocr_pages,
        layout=layout,
        source_sha256="c" * 64,
        store=store,
        config=visuals.VisualPipelineConfig(detection_dpi=96, crop_dpi=150),
    )
    question = updated.projection["exam_prep"]["questions"][0]
    assert stats["assetsAttached"] == 1
    assert stats["wholePageFallbacks"] == 0
    assert audit["unresolvedRegions"] == []
    assert len(store.files) == 1
    asset = question["visuals"][0]
    assert asset["role"] == "question"
    assert asset["reviewOnly"] is False
    assert asset["storagePath"].startswith(visuals.MISTRAL_VISUAL_STORAGE_PREFIX + "/")
    assert "dataUrl" not in asset
    assert "visual_reference_without_ocr_visual" not in question["issues"]


def test_missing_precise_seed_creates_review_only_whole_page_fallback_and_unresolved_audit():
    data = _pdf()
    ocr_pages = [{
        "index": 0,
        "sourcePhysicalPage": 1,
        "dimensions": {"width": 612, "height": 792},
        "blocks": [],
    }]
    layout = {"pages": [{
        "originalPageNumber": 1,
        "pageRole": "question",
        "regions": [{
            "kind": "question",
            "questionNumber": 1,
            "bbox": [0.0, 0.10, 1.0, 0.80],
            "visuals": [],
            "captions": [],
            "issues": ["visual_reference_without_ocr_visual"],
        }],
    }]}
    store = MemoryStore()
    updated, stats, audit = visuals.reconcile_mistral_source_visuals(
        _result(),
        pdf_data=data,
        ocr_pages=ocr_pages,
        layout=layout,
        source_sha256="d" * 64,
        store=store,
        config=visuals.VisualPipelineConfig(detection_dpi=96, crop_dpi=150),
    )
    question = updated.projection["exam_prep"]["questions"][0]
    asset = question["visuals"][0]
    assert asset["visualMode"] == "whole_page_review_fallback"
    assert asset["reviewOnly"] is True
    assert "visual_precise_crop_unresolved" in question["issues"]
    assert stats["wholePageFallbacks"] == 1
    assert stats["reviewOnlyAssets"] == 1
    assert stats["unresolvedRegions"] >= 1
    assert audit["unresolvedRegions"]
