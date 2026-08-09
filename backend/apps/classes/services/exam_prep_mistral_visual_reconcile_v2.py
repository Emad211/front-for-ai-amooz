"""Second-generation deterministic visual reconciliation for Mistral OCR4.

This policy is driven by the real 55-page replay, not by review volume. It fixes
three observed Stage-3 failure modes:

1. residual Persian solution text was being treated as local graphics;
2. raster edge-ink made otherwise complete diagrams look clipped;
3. an OCR ``image`` bbox can contain the diagram plus unrelated prose/options.

The rendered PDF remains authoritative. OCR blocks provide semantic geometry,
while a text-masked rendered page refines image cores. No general LLM call is
made here. Ambiguity is left for the later machine risk/verifier stage rather
than being delegated to a teacher.
"""
from __future__ import annotations

from dataclasses import replace
import copy
import math
import re
from typing import Any, Mapping, Sequence

from PIL import Image

from . import exam_prep_mistral_visuals as v
from . import exam_prep_mistral_visual_runtime as legacy
from .exam_prep_mistral_layout_analysis import (
    LayoutBlock,
    detect_uncovered_graphics,
    normalize_page_blocks,
)
from .exam_prep_page_records import PageAssemblyResult


VisualAssetStore = v.VisualAssetStore
PrivateVisualAssetStore = v.PrivateVisualAssetStore
VisualPipelineConfig = v.VisualPipelineConfig
VisualPipelineStats = v.VisualPipelineStats
VisualPlan = v.VisualPlan
VisualSeed = v.VisualSeed
VISUAL_CRITICAL_ISSUE_CODES = v.VISUAL_CRITICAL_ISSUE_CODES
MISTRAL_VISUAL_STORAGE_PREFIX = v.MISTRAL_VISUAL_STORAGE_PREFIX

_VISUAL_WORD_RE = re.compile(
    r"(?:شکل|نمودار|مدار|جدول|ساختار|تصویر|طیف|نقشه|نمودارهای)",
    re.IGNORECASE,
)


def _component_bbox(value: Mapping[str, Any]) -> v.BBox | None:
    return v._bbox(value.get("bbox"))


def _center_inside(box: v.BBox, boundary: v.BBox) -> bool:
    cx, cy = v._center(box)
    return boundary[0] <= cx <= boundary[2] and boundary[1] <= cy <= boundary[3]


def _text_mask_components(
    image: Image.Image,
    blocks: Sequence[LayoutBlock],
) -> list[dict[str, Any]]:
    """Find rendered graphic cores after masking every OCR textual block.

    Text labels needed by a diagram are deliberately masked here: Smart Union
    adds short labels/captions back later from OCR geometry. The purpose of this
    pass is to discover the *graphic core* without dragging surrounding prose
    into an OCR image bbox.
    """

    coverage = [
        {
            "x0": block.bbox[0],
            "y0": block.bbox[1],
            "x1": block.bbox[2],
            "y1": block.bbox[3],
        }
        for block in blocks
        if block.block_type not in {"image", "table"}
    ]
    detector_page = {
        "dimensions": {"width": image.width, "height": image.height},
        "blocks": coverage,
    }
    return detect_uncovered_graphics(
        image_bytes=v._encode_png(image),
        page=detector_page,
        padding_px=max(4, round(max(image.size) / 240)),
        min_width_px=max(7, round(image.width * 0.007)),
        min_height_px=max(6, round(image.height * 0.005)),
        min_ink_pixels=max(14, round(image.width * image.height * 0.000012)),
    )


def _cluster_components(
    values: Sequence[Mapping[str, Any]],
    *,
    gap: float = 0.035,
) -> list[list[Mapping[str, Any]]]:
    clusters: list[list[Mapping[str, Any]]] = []
    for value in values:
        box = _component_bbox(value)
        if box is None:
            continue
        matches: list[list[Mapping[str, Any]]] = []
        for cluster in clusters:
            cluster_box = v._union(
                candidate
                for item in cluster
                if (candidate := _component_bbox(item)) is not None
            )
            if cluster_box is not None and v._gap(cluster_box, box) <= gap:
                matches.append(cluster)
        if not matches:
            clusters.append([value])
            continue
        target = matches[0]
        target.append(value)
        for extra in matches[1:]:
            target.extend(extra)
            clusters.remove(extra)
    return clusters


def _refined_image_bbox(
    seed_box: v.BBox,
    components: Sequence[Mapping[str, Any]],
    *,
    region_box: v.BBox,
) -> v.BBox:
    """Shrink a provider image bbox to the rendered graphic core when safe."""

    inside: list[Mapping[str, Any]] = []
    for component in components:
        box = _component_bbox(component)
        if box is None or not _center_inside(box, seed_box):
            continue
        if v._coverage(box, seed_box) < 0.72:
            continue
        inside.append(component)
    if not inside:
        return seed_box

    clusters = _cluster_components(inside)
    scored: list[tuple[int, float, list[Mapping[str, Any]]]] = []
    for cluster in clusters:
        boxes = [
            box
            for item in cluster
            if (box := _component_bbox(item)) is not None
        ]
        union_box = v._union(boxes)
        if union_box is None:
            continue
        ink = sum(int(item.get("inkPixels") or 0) for item in cluster)
        scored.append((ink, v._area(union_box), cluster))
    if not scored:
        return seed_box

    max_ink = max(item[0] for item in scored)
    kept = [
        cluster
        for ink, area, cluster in scored
        if ink >= max(18, int(max_ink * 0.08))
        and area >= 0.00008
    ]
    if not kept:
        return seed_box
    union_box = v._union(
        box
        for cluster in kept
        for item in cluster
        if (box := _component_bbox(item)) is not None
    )
    if union_box is None:
        return seed_box

    original_area = max(v._area(seed_box), 1e-9)
    ratio = v._area(union_box) / original_area
    # A tiny surviving glyph cluster is not a diagram; an almost-identical union
    # gives us no useful refinement. Both cases keep the provider seed.
    if ratio < 0.045 or ratio > 0.94:
        return seed_box
    padded = v._expand(union_box, 0.007)
    return v._clamp(padded, v._expand(region_box, 0.004))


def _prepare_layout(
    *,
    pdf_data: bytes,
    ocr_pages: Sequence[Mapping[str, Any]],
    layout: Mapping[str, Any],
    config: VisualPipelineConfig,
) -> tuple[dict[str, Any], int]:
    """Refine OCR image boxes and add conservative question-side local graphics."""

    working = copy.deepcopy(dict(layout))
    analysis_pages = v._analysis_page_map(working)
    ocr_by_page = v._page_map(ocr_pages)
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdfium2 is required for visual reconciliation") from exc

    local_added = 0
    document = pdfium.PdfDocument(pdf_data)
    try:
        for page_number, page_analysis in analysis_pages.items():
            if page_number not in ocr_by_page:
                continue
            if str(page_analysis.get("pageRole") or "") not in {
                "question",
                "solution",
                "mixed",
            }:
                continue
            image = v._render_page(document, page_number, config.detection_dpi)
            try:
                blocks = normalize_page_blocks(ocr_by_page[page_number])
                components = _text_mask_components(image, blocks)
                for region in page_analysis.get("regions") or []:
                    if not isinstance(region, dict):
                        continue
                    region_box = v._bbox(region.get("bbox"))
                    if region_box is None:
                        continue
                    visuals = [
                        item
                        for item in (region.get("visuals") or [])
                        if isinstance(item, dict)
                    ]
                    original_ocr_boxes: list[v.BBox] = []
                    for visual in visuals:
                        box = v._bbox(visual.get("bbox"))
                        if box is None:
                            continue
                        original_ocr_boxes.append(box)
                        if str(visual.get("type") or "") != "image":
                            continue
                        visual["bbox"] = list(
                            _refined_image_bbox(
                                box,
                                components,
                                region_box=region_box,
                            )
                        )

                    # The replay showed that local-only solution discovery is
                    # overwhelmingly residual typography. Keep solution visuals
                    # provider-anchored; local graphics may supplement only the
                    # question side, where they recovered known misses such as Q94.
                    if str(region.get("kind") or "") != "question":
                        region.pop("uncoveredGraphics", None)
                        region["issues"] = [
                            code
                            for code in (region.get("issues") or [])
                            if code != "uncovered_graphics_in_region"
                        ]
                        continue

                    text = str(region.get("text") or "")
                    explicit_visual_language = bool(_VISUAL_WORD_RE.search(text))
                    accepted_local: list[dict[str, Any]] = []
                    for component in components:
                        box = _component_bbox(component)
                        if box is None or not _center_inside(box, region_box):
                            continue
                        if any(v._coverage(box, ocr_box) >= 0.72 for ocr_box in original_ocr_boxes):
                            continue
                        area = v._area(box)
                        ink = int(component.get("inkPixels") or 0)
                        near_ocr = any(v._gap(box, ocr_box) <= 0.045 for ocr_box in original_ocr_boxes)
                        if not near_ocr and not explicit_visual_language:
                            continue
                        if area < 0.00045 or ink < 35:
                            continue
                        accepted_local.append(dict(component))
                    if accepted_local:
                        region["uncoveredGraphics"] = accepted_local
                        local_added += len(accepted_local)
                    else:
                        region.pop("uncoveredGraphics", None)
                    region["issues"] = [
                        code
                        for code in (region.get("issues") or [])
                        if code != "uncovered_graphics_in_region"
                    ]
                    if accepted_local:
                        region.setdefault("issues", []).append("uncovered_graphics_in_region")
                        region["issues"] = sorted(set(region["issues"]))
            finally:
                image.close()
    finally:
        document.close()
    return working, local_added


def _table_plans(
    *,
    page_number: int,
    region: Mapping[str, Any],
    seeds: Sequence[VisualSeed],
    config: VisualPipelineConfig,
) -> tuple[list[VisualPlan], list[str]] | None:
    table_seeds = [seed for seed in seeds if seed.is_table]
    if not table_seeds:
        return None
    region_box = v._bbox(region.get("bbox"))
    number = v._number(region.get("questionNumber")) or 0
    if region_box is None or number < 1:
        return [], ["visual_precise_crop_unresolved"]
    table_box = v._union(seed.bbox for seed in table_seeds)
    if table_box is None:
        return [], ["visual_precise_crop_unresolved"]
    crop_box = v._clamp(
        v._expand(table_box, max(0.006, config.padding)),
        v._expand(region_box, config.region_guard),
    )
    sanity = v._plan_sanity(
        box=crop_box,
        region_box=region_box,
        cluster=table_seeds,
        config=config,
    )
    plan = VisualPlan(
        page_number=page_number,
        question_number=number,
        role=("solution" if str(region.get("kind") or "") == "solution" else "question"),
        option_label=None,
        mode="table",
        bbox=crop_box,
        source_kinds=tuple(sorted({seed.source_kind for seed in table_seeds})),
        component_ids=tuple(seed.seed_id for seed in table_seeds),
        table=True,
        sanity_issues=tuple(sanity),
        review_only=bool(set(sanity) & VISUAL_CRITICAL_ISSUE_CODES),
    )
    return [plan], list(sanity)


def _plans_for_region(
    *,
    page_number: int,
    region: Mapping[str, Any],
    seeds: Sequence[VisualSeed],
    blocks: Sequence[LayoutBlock],
    config: VisualPipelineConfig,
) -> tuple[list[VisualPlan], list[str]]:
    table = _table_plans(
        page_number=page_number,
        region=region,
        seeds=seeds,
        config=config,
    )
    if table is not None:
        return table

    plans, issues = legacy._harden_region_plans(
        page_number=page_number,
        region=region,
        seeds=seeds,
        blocks=blocks,
        config=config,
    )
    # A grouped source image containing all four visual options does not require
    # per-option image binding. The student can select labels 1..4 while viewing
    # the source-faithful grouped panel. Do not manufacture four crops and do not
    # send this to a teacher merely because individual binding is unavailable.
    if len(plans) == 1 and plans[0].mode == "grouped_options":
        benign = {
            "visual_option_binding_unresolved",
            "visual_missing_option_asset",
            "visual_option_binding_inferred",
        }
        remaining = [code for code in issues if code not in benign]
        if not any(code in VISUAL_CRITICAL_ISSUE_CODES for code in remaining):
            plan = plans[0]
            plans = [
                replace(
                    plan,
                    review_only=False,
                    sanity_issues=tuple(
                        code for code in plan.sanity_issues if code not in benign
                    ),
                    grouped_option_labels=("1", "2", "3", "4"),
                )
            ]
            issues = remaining
    return plans, list(dict.fromkeys(issues))


def reconcile_mistral_source_visuals(
    result: PageAssemblyResult,
    *,
    pdf_data: bytes,
    ocr_pages: Sequence[Mapping[str, Any]],
    layout: Mapping[str, Any],
    source_sha256: str,
    store: VisualAssetStore | None = None,
    config: VisualPipelineConfig | None = None,
) -> tuple[PageAssemblyResult, dict[str, int], dict[str, Any]]:
    """Produce precise source visuals without defaulting work to teachers."""

    if not pdf_data or not pdf_data.lstrip().startswith(b"%PDF"):
        raise ValueError("visual reconciliation requires authoritative PDF bytes")
    selected = config or VisualPipelineConfig.from_env()
    selected_store = store or PrivateVisualAssetStore()
    working, local_count = _prepare_layout(
        pdf_data=pdf_data,
        ocr_pages=ocr_pages,
        layout=layout,
        config=selected,
    )
    analysis_pages = v._analysis_page_map(working)
    ocr_by_page = v._page_map(ocr_pages)
    relevant_pages = sorted(
        number
        for number, page in analysis_pages.items()
        if number in ocr_by_page
        and str(page.get("pageRole") or "") in {"question", "solution", "mixed"}
    )

    plans_by_page: dict[int, list[VisualPlan]] = {}
    issues_by_question: dict[int, list[str]] = {}
    unresolved_regions: list[dict[str, Any]] = []
    ocr_count = 0
    for page_number in relevant_pages:
        blocks = normalize_page_blocks(ocr_by_page[page_number])
        for region in analysis_pages[page_number].get("regions") or []:
            if not isinstance(region, Mapping):
                continue
            number = v._number(region.get("questionNumber")) or 0
            if number < 1:
                continue
            seeds = v._region_seeds(page_number, region)
            # Never turn unanchored solution typography into a visual. Provider
            # image/table evidence remains allowed and is refined above.
            if str(region.get("kind") or "") == "solution":
                seeds = [seed for seed in seeds if seed.source_kind.startswith("ocr_")]
            ocr_count += sum(seed.source_kind.startswith("ocr_") for seed in seeds)
            if not seeds:
                if str(region.get("kind") or "") == "question" and v._visual_required(region):
                    issues_by_question.setdefault(number, []).append(
                        "visual_precise_crop_unresolved"
                    )
                    unresolved_regions.append(
                        {
                            "pageNumber": page_number,
                            "questionNumber": number,
                            "role": str(region.get("kind") or "question"),
                            "reason": "visual_precise_crop_unresolved",
                        }
                    )
                continue
            plans, issues = _plans_for_region(
                page_number=page_number,
                region=region,
                seeds=seeds,
                blocks=blocks,
                config=selected,
            )
            if not plans:
                issues = list(dict.fromkeys([*issues, "visual_precise_crop_unresolved"]))
                unresolved_regions.append(
                    {
                        "pageNumber": page_number,
                        "questionNumber": number,
                        "role": str(region.get("kind") or "question"),
                        "reason": "visual_precise_crop_unresolved",
                    }
                )
                issues_by_question.setdefault(number, []).extend(issues)
                continue
            critical = [code for code in issues if code in VISUAL_CRITICAL_ISSUE_CODES]
            if critical:
                plans = [
                    replace(
                        plan,
                        review_only=True,
                        sanity_issues=tuple(dict.fromkeys([*plan.sanity_issues, *critical])),
                    )
                    for plan in plans
                ]
                unresolved_regions.append(
                    {
                        "pageNumber": page_number,
                        "questionNumber": number,
                        "role": str(region.get("kind") or "question"),
                        "reason": critical[0],
                    }
                )
            plans_by_page.setdefault(page_number, []).extend(plans)
            issues_by_question.setdefault(number, []).extend(issues)

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdfium2 is required for visual reconciliation") from exc

    assets_by_question: dict[int, list[dict[str, Any]]] = {}
    storage_failures = 0
    document = pdfium.PdfDocument(pdf_data)
    try:
        for page_number, plans in sorted(plans_by_page.items()):
            image = v._render_page(document, page_number, selected.crop_dpi)
            try:
                counters: dict[tuple[int, str, str | None], int] = {}
                for plan in plans:
                    key = (plan.question_number, plan.role, plan.option_label)
                    counters[key] = counters.get(key, 0) + 1
                    order = counters[key]
                    try:
                        payload = v._crop_bytes(image, plan.bbox, selected)
                    except ValueError:
                        issues_by_question.setdefault(plan.question_number, []).append(
                            "visual_crop_oversized"
                        )
                        unresolved_regions.append(
                            {
                                "pageNumber": page_number,
                                "questionNumber": plan.question_number,
                                "role": plan.role,
                                "reason": "visual_crop_oversized",
                            }
                        )
                        continue
                    try:
                        asset = v._asset_from_payload(
                            plan=plan,
                            order=order,
                            payload=payload,
                            source_sha256=source_sha256,
                            store=selected_store,
                        )
                    except Exception:
                        storage_failures += 1
                        issues_by_question.setdefault(plan.question_number, []).append(
                            "visual_storage_failed"
                        )
                        continue
                    assets_by_question.setdefault(plan.question_number, []).append(asset)
            finally:
                image.close()
    finally:
        document.close()

    normalized_issues = {
        number: list(dict.fromkeys(codes))
        for number, codes in issues_by_question.items()
    }
    updated = v._rebuild_projection_quality(
        result,
        assets_by_question=assets_by_question,
        issues_by_question=normalized_issues,
    )
    all_assets = [asset for values in assets_by_question.values() for asset in values]
    all_codes = [code for values in normalized_issues.values() for code in values]
    unresolved_unique = {
        (
            int(item.get("pageNumber") or 0),
            int(item.get("questionNumber") or 0),
            str(item.get("role") or ""),
            str(item.get("reason") or ""),
        )
        for item in unresolved_regions
    }
    unresolved_regions = [
        {
            "pageNumber": page,
            "questionNumber": question,
            "role": role,
            "reason": reason,
        }
        for page, question, role, reason in sorted(unresolved_unique)
    ]
    stats = VisualPipelineStats(
        pages_scanned=len(relevant_pages),
        local_graphic_candidates=local_count,
        ocr_visual_candidates=ocr_count,
        decorative_suppressed=0,
        assets_attached=len(all_assets),
        question_visuals=sum(asset.get("role") == "question" for asset in all_assets),
        option_visuals=sum(asset.get("role") == "option" for asset in all_assets),
        solution_visuals=sum(asset.get("role") == "solution" for asset in all_assets),
        grouped_visuals=sum(
            str(asset.get("visualMode") or "").startswith("grouped_") for asset in all_assets
        ),
        table_visuals=sum("ocr_table" in (asset.get("sourceKinds") or []) for asset in all_assets),
        whole_page_fallbacks=0,
        review_only_assets=sum(bool(asset.get("reviewOnly")) for asset in all_assets),
        sanity_failures=sum(code in VISUAL_CRITICAL_ISSUE_CODES for code in all_codes),
        unresolved_regions=len(unresolved_regions),
        storage_failures=storage_failures,
    )
    audit = {
        "schemaVersion": 3,
        "sourceSha256": source_sha256,
        "stats": stats.as_dict(),
        "unresolvedRegions": unresolved_regions,
        "criticalIssueCodes": sorted(
            {code for code in all_codes if code in VISUAL_CRITICAL_ISSUE_CODES}
        ),
        "policy": {
            "teacherReviewIsDefault": False,
            "textMaskedRenderedCore": True,
            "localOnlySolutionGraphicsAccepted": False,
            "rasterEdgeInkIsPublicationBlocker": False,
            "groupedVisualOptionsRequirePerOptionBinding": False,
            "wholePageFallbackPublishSafe": False,
        },
    }
    return updated, stats.as_dict(), audit


__all__ = [
    "MISTRAL_VISUAL_STORAGE_PREFIX",
    "PrivateVisualAssetStore",
    "VISUAL_CRITICAL_ISSUE_CODES",
    "VisualAssetStore",
    "VisualPipelineConfig",
    "VisualPipelineStats",
    "reconcile_mistral_source_visuals",
]
