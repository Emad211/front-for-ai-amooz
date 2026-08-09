from __future__ import annotations

import io

from pypdf import PdfWriter

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


def _block(
    index: int,
    kind: str,
    content: str,
    bbox: tuple[float, float, float, float],
) -> LayoutBlock:
    return LayoutBlock(
        provider_index=index,
        block_type=kind,
        content=content,
        bbox=bbox,
        column="right" if bbox[0] >= 0.5 else "left",
        raw={},
    )


def _seed(
    seed_id: str,
    bbox: tuple[float, float, float, float],
    *,
    table: bool = False,
) -> visuals.VisualSeed:
    return visuals.VisualSeed(
        seed_id=seed_id,
        page_number=1,
        question_number=1,
        region_kind="question",
        source_kind="ocr_table" if table else "ocr_image",
        bbox=bbox,
        is_table=table,
    )


def test_smart_union_adds_nearby_axis_caption_but_not_question_stem():
    config = visuals.VisualPipelineConfig(padding=0.005, auxiliary_gap=0.03)
    seed = _seed("s1", (0.55, 0.35, 0.82, 0.62))
    blocks = [
        _block(
            1,
            "text",
            "صورت سؤال بلند و نامرتبط که نباید وارد crop شود",
            (0.52, 0.15, 0.93, 0.25),
        ),
        _block(2, "caption", "v (m/s)", (0.53, 0.32, 0.62, 0.35)),
        _block(3, "equation", "t=2s", (0.80, 0.61, 0.88, 0.65)),
    ]
    box, component_ids, _sources = visuals._smart_union_bbox(
        [seed],
        blocks=blocks,
        region_box=(0.5, 0.10, 1.0, 0.80),
        heading_index=None,
        config=config,
    )
    assert box[1] < seed.bbox[1]
    assert box[2] > seed.bbox[2]
    assert "block:2" in component_ids
    assert "block:3" in component_ids
    assert "block:1" not in component_ids


def test_decorative_repetition_requires_repeat_plus_margin_or_tiny_geometry():
    margin = _seed("logo", (0.02, 0.02, 0.12, 0.07))
    body = _seed("body", (0.25, 0.30, 0.75, 0.70))
    assert visuals._decorative_candidate(margin, 3) is True
    assert visuals._decorative_candidate(body, 3) is False
    assert visuals._decorative_candidate(body, 5) is True


def test_rtl_option_binding_falls_back_to_reading_order_for_four_visuals():
    clusters = [
        [_seed("1", (0.55, 0.20, 0.70, 0.34))],
        [_seed("2", (0.30, 0.20, 0.45, 0.34))],
        [_seed("3", (0.55, 0.42, 0.70, 0.56))],
        [_seed("4", (0.30, 0.42, 0.45, 0.56))],
    ]
    bound, issues = visuals._bind_option_clusters(
        clusters,
        blocks=[],
        region_box=(0.20, 0.10, 0.80, 0.65),
    )
    by_seed = {cluster[0].seed_id: label for label, cluster in bound}
    assert by_seed == {"1": "1", "2": "2", "3": "3", "4": "4"}
    assert "visual_option_binding_inferred" in issues
    assert "visual_missing_option_asset" not in issues


def test_grouped_option_region_stays_one_asset_and_keeps_option_contract():
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


def test_question_and_solution_asset_names_are_not_semantically_deduplicated():
    question_plan = visuals.VisualPlan(
        page_number=10,
        question_number=57,
        role="question",
        option_label=None,
        mode="single_question",
        bbox=(0.2, 0.2, 0.5, 0.5),
        source_kinds=("ocr_image",),
        component_ids=("a",),
    )
    solution_plan = visuals.VisualPlan(
        page_number=40,
        question_number=57,
        role="solution",
        option_label=None,
        mode="solution",
        bbox=(0.2, 0.2, 0.5, 0.5),
        source_kinds=("ocr_image",),
        component_ids=("a",),
    )
    kwargs = {
        "source_sha256": "a" * 64,
        "order": 1,
        "payload_sha256": "b" * 64,
    }
    assert visuals._asset_name(plan=question_plan, **kwargs) != visuals._asset_name(
        plan=solution_plan,
        **kwargs,
    )


def test_complete_option_visuals_make_four_empty_option_slots_safe():
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
        "issues": [
            "mistral_question_option_parse_failed",
            "missing_options",
            "visual_evidence_required",
        ],
        "source_pages": [1],
    }
    assets = [
        {
            "id": f"inline-mistral-v1-x-q1-option-o{number}",
            "role": "option",
            "optionLabel": str(number),
            "reviewOnly": False,
        }
        for number in range(1, 5)
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


def test_reconciliation_persists_precise_crop_without_inline_db_blob():
    data = _pdf()
    ocr_pages = [
        {
            "index": 0,
            "sourcePhysicalPage": 1,
            "dimensions": {"width": 612, "height": 792},
            "blocks": [
                {
                    "type": "image",
                    "content": "",
                    "bbox": {
                        "x0": 0.58,
                        "y0": 0.30,
                        "x1": 0.82,
                        "y1": 0.55,
                    },
                }
            ],
        }
    ]
    layout = {
        "pages": [
            {
                "originalPageNumber": 1,
                "pageRole": "question",
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "bbox": [0.50, 0.10, 1.0, 0.80],
                        "headingProviderIndex": 9,
                        "visuals": [
                            {
                                "type": "image",
                                "bbox": [0.58, 0.30, 0.82, 0.55],
                                "providerIndex": 0,
                                "content": "",
                            }
                        ],
                        "captions": [],
                        "issues": [],
                    }
                ],
            }
        ]
    }
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


def test_missing_seed_gets_review_only_whole_page_fallback_and_blocker():
    data = _pdf()
    ocr_pages = [
        {
            "index": 0,
            "sourcePhysicalPage": 1,
            "dimensions": {"width": 612, "height": 792},
            "blocks": [],
        }
    ]
    layout = {
        "pages": [
            {
                "originalPageNumber": 1,
                "pageRole": "question",
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "bbox": [0.0, 0.10, 1.0, 0.80],
                        "visuals": [],
                        "captions": [],
                        "issues": ["visual_reference_without_ocr_visual"],
                    }
                ],
            }
        ]
    }
    store = MemoryStore()
    updated, stats, _audit = visuals.reconcile_mistral_source_visuals(
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
