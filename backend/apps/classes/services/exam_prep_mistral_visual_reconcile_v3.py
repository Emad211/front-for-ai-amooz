"""Strong local-only solution visual recovery layered on Stage-3 v2.

The first replay proved that permissive local solution detection mostly captures
residual typography. Disabling it entirely, however, loses real vector diagrams
such as the known S133 source. This layer accepts only large structural connected
components after OCR text masking, and only when the question has no publish-safe
solution visual already.
"""
from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Callable, Mapping, Sequence

from . import exam_prep_mistral_visual_reconcile_v2 as base
from . import exam_prep_mistral_visuals as v
from .exam_prep_mistral_layout_analysis import detect_uncovered_graphics, normalize_page_blocks
from .exam_prep_page_records import PageAssemblyResult


VisualAssetStore = base.VisualAssetStore
PrivateVisualAssetStore = base.PrivateVisualAssetStore
VisualPipelineConfig = base.VisualPipelineConfig
VisualPipelineStats = base.VisualPipelineStats
VISUAL_CRITICAL_ISSUE_CODES = base.VISUAL_CRITICAL_ISSUE_CODES
MISTRAL_VISUAL_STORAGE_PREFIX = base.MISTRAL_VISUAL_STORAGE_PREFIX
_TARGETED_VISUAL_CUE_RE = re.compile(
    r"(?:مکعب|کره|بیضی|استوانه|مخروط)\s+(?:زیر|مقابل|نشان[‌ ]?داده)",
    re.IGNORECASE,
)


def _clamp(box, boundary):
    x0 = max(float(boundary[0]), float(box[0]))
    y0 = max(float(boundary[1]), float(box[1]))
    x1 = min(float(boundary[2]), float(box[2]))
    y1 = min(float(boundary[3]), float(box[3]))
    if x1 <= x0 or y1 <= y0:
        return tuple(float(value) for value in boundary)
    return (x0, y0, x1, y1)


if not hasattr(v, "_clamp"):
    v._clamp = _clamp


def _number(value: Any) -> int:
    parsed = v._number(value)
    return int(parsed or 0)


def _stage3_assets_by_question(result: PageAssemblyResult) -> dict[int, list[dict[str, Any]]]:
    output: dict[int, list[dict[str, Any]]] = {}
    questions = (result.projection.get("exam_prep") or {}).get("questions") or []
    for question in questions:
        if not isinstance(question, Mapping):
            continue
        number = _number(question.get("source_question_number"))
        if number < 1:
            continue
        assets = [
            dict(item)
            for item in (question.get("visuals") or [])
            if isinstance(item, Mapping)
            and str(item.get("id") or "").startswith("inline-mistral-v1-")
        ]
        if assets:
            output[number] = assets
    return output


def _publish_safe_solution_asset(asset: Mapping[str, Any]) -> bool:
    if str(asset.get("role") or "").lower() != "solution":
        return False
    if bool(asset.get("reviewOnly")):
        return False
    sanity = asset.get("sanity")
    if isinstance(sanity, Mapping) and str(sanity.get("status") or "").lower() == "failed":
        return False
    return True


def _strong_solution_clusters(
    *,
    region: Mapping[str, Any],
    components: Sequence[Mapping[str, Any]],
) -> list[list[Mapping[str, Any]]]:
    region_box = v._bbox(region.get("bbox"))
    if region_box is None:
        return []
    strong: list[Mapping[str, Any]] = []
    for component in components:
        box = base._component_bbox(component)
        if box is None or not base._center_inside(box, region_box):
            continue
        area = v._area(box)
        ink = int(component.get("inkPixels") or 0)
        width = box[2] - box[0]
        height = box[3] - box[1]
        aspect = max(width / max(height, 1e-9), height / max(width, 1e-9))
        if area < 0.0012 or ink < 80:
            continue
        if max(width, height) < 0.075 or min(width, height) < 0.018:
            continue
        if aspect > 14:
            continue
        strong.append(component)
    if not strong:
        return []

    clusters = base._cluster_components(strong, gap=0.032)
    scored: list[tuple[int, float, list[Mapping[str, Any]]]] = []
    for cluster in clusters:
        boxes = [
            box
            for item in cluster
            if (box := base._component_bbox(item)) is not None
        ]
        union = v._union(boxes)
        if union is None:
            continue
        ink = sum(int(item.get("inkPixels") or 0) for item in cluster)
        area = v._area(union)
        if area >= 0.0018:
            scored.append((ink, area, cluster))
    if not scored:
        return []
    maximum = max(item[0] for item in scored)
    return [
        cluster
        for ink, _area, cluster in scored
        if ink >= max(100, int(maximum * 0.22))
    ]


def _boxes_overlap(left, right) -> bool:
    return not (
        float(left[2]) <= float(right[0])
        or float(right[2]) <= float(left[0])
        or float(left[3]) <= float(right[1])
        or float(right[3]) <= float(left[1])
    )


def _targeted_recovery_components(
    image,
    blocks,
    region: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Recover structural ink hidden by a coarse base-OCR text mask.

    This fallback is deliberately narrow: it is available only for the precise
    synthetic solution regions created from accepted targeted-recovery headings,
    only when that region itself explicitly references a visual, and it keeps the
    existing strong structural-component gate. Text blocks intersecting the
    precise target region are omitted from the detector mask because a coarse OCR
    text bbox can enclose the real vector diagram that we need to preserve.
    """

    if not bool(region.get("targetedRecoveryRegion")):
        return []
    region_text = str(region.get("text") or "")
    if not (
        base._VISUAL_WORD_RE.search(region_text)
        or _TARGETED_VISUAL_CUE_RE.search(region_text)
    ):
        return []
    region_box = v._bbox(region.get("bbox"))
    if region_box is None:
        return []
    coverage = []
    for block in blocks:
        if block.block_type in {"image", "table"}:
            continue
        if _boxes_overlap(block.bbox, region_box):
            continue
        coverage.append(
            {
                "x0": block.bbox[0],
                "y0": block.bbox[1],
                "x1": block.bbox[2],
                "y1": block.bbox[3],
            }
        )
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


def _recover_solution_visuals(
    result: PageAssemblyResult,
    *,
    pdf_data: bytes,
    ocr_pages: Sequence[Mapping[str, Any]],
    layout: Mapping[str, Any],
    source_sha256: str,
    store: VisualAssetStore,
    config: VisualPipelineConfig,
    storage_namespace: str = "",
    should_cancel: Callable[[], bool] | None = None,
) -> tuple[PageAssemblyResult, int, list[dict[str, Any]]]:
    existing = _stage3_assets_by_question(result)
    questions_with_solution = {
        number
        for number, assets in existing.items()
        if any(_publish_safe_solution_asset(asset) for asset in assets)
    }
    analysis_pages = v._analysis_page_map(layout)
    ocr_by_page = v._page_map(ocr_pages)
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdfium2 is required for visual reconciliation") from exc

    recovered_assets: dict[int, list[dict[str, Any]]] = {}
    recovered_regions: list[dict[str, Any]] = []
    document = pdfium.PdfDocument(pdf_data)
    try:
        for page_number, page_analysis in analysis_pages.items():
            if should_cancel is not None and should_cancel():
                raise RuntimeError(
                    "Cancellation requested during Stage-3 visual reconciliation."
                )
            if page_number not in ocr_by_page:
                continue
            solution_regions = [
                region
                for region in (page_analysis.get("regions") or [])
                if isinstance(region, Mapping)
                and str(region.get("kind") or "") == "solution"
            ]
            if not solution_regions:
                continue
            needed = [
                region
                for region in solution_regions
                if _number(region.get("questionNumber")) not in questions_with_solution
            ]
            if not needed:
                continue
            image = v._render_page(document, page_number, config.detection_dpi)
            try:
                blocks = normalize_page_blocks(ocr_by_page[page_number])
                components = base._text_mask_components(image, blocks)
                for region in needed:
                    number = _number(region.get("questionNumber"))
                    if number < 1:
                        continue
                    clusters = _strong_solution_clusters(region=region, components=components)
                    recovery_mode = "strong_local"
                    union_blocks = blocks
                    if not clusters and bool(region.get("targetedRecoveryRegion")):
                        targeted_components = _targeted_recovery_components(image, blocks, region)
                        clusters = _strong_solution_clusters(
                            region=region,
                            components=targeted_components,
                        )
                        if clusters:
                            recovery_mode = "targeted_recovery_region"
                            union_blocks = []
                    if not clusters:
                        continue
                    region_box = v._bbox(region.get("bbox"))
                    if region_box is None:
                        continue
                    heading = region.get("headingProviderIndex")
                    heading_index = (
                        int(heading)
                        if isinstance(heading, int) and recovery_mode == "strong_local"
                        else None
                    )
                    plans: list[base.VisualPlan] = []
                    for cluster_index, cluster in enumerate(clusters, start=1):
                        boxes = [
                            box
                            for item in cluster
                            if (box := base._component_bbox(item)) is not None
                        ]
                        union = v._union(boxes)
                        if union is None:
                            continue
                        synthetic = [
                            base.VisualSeed(
                                seed_id=f"p{page_number}:solution:q{number}:strong-local:{cluster_index}:{index}",
                                page_number=page_number,
                                question_number=number,
                                region_kind="solution",
                                source_kind="local_graphic",
                                bbox=box,
                            )
                            for index, box in enumerate(boxes)
                        ]
                        crop_box, component_ids, source_kinds = v._smart_union_bbox(
                            synthetic,
                            blocks=union_blocks,
                            region_box=region_box,
                            heading_index=heading_index,
                            config=config,
                        )
                        sanity = v._plan_sanity(
                            box=crop_box,
                            region_box=region_box,
                            cluster=synthetic,
                            config=config,
                        )
                        if set(sanity) & VISUAL_CRITICAL_ISSUE_CODES:
                            continue
                        plans.append(
                            base.VisualPlan(
                                page_number=page_number,
                                question_number=number,
                                role="solution",
                                option_label=None,
                                mode=(
                                    "targeted_recovery_solution"
                                    if recovery_mode == "targeted_recovery_region"
                                    else "local_solution"
                                ),
                                bbox=crop_box,
                                source_kinds=source_kinds,
                                component_ids=component_ids,
                                sanity_issues=(),
                                review_only=False,
                            )
                        )
                    if not plans:
                        continue

                    crop_image = v._render_page(document, page_number, config.crop_dpi)
                    try:
                        for order, plan in enumerate(plans, start=1):
                            try:
                                payload = v._crop_bytes(crop_image, plan.bbox, config)
                                asset = v._asset_from_payload(
                                    plan=plan,
                                    order=order,
                                    payload=payload,
                                    source_sha256=source_sha256,
                                    store=store,
                                    storage_namespace=storage_namespace,
                                )
                            except Exception:
                                continue
                            recovered_assets.setdefault(number, []).append(asset)
                    finally:
                        crop_image.close()
                    if recovered_assets.get(number):
                        questions_with_solution.add(number)
                        recovered_regions.append(
                            {
                                "pageNumber": page_number,
                                "questionNumber": number,
                                "assetCount": len(recovered_assets[number]),
                                "mode": recovery_mode,
                            }
                        )
            finally:
                image.close()
    finally:
        document.close()

    if not recovered_assets:
        return result, 0, []
    combined: dict[int, list[dict[str, Any]]] = {
        number: list(assets) for number, assets in existing.items()
    }
    for number, values in recovered_assets.items():
        combined.setdefault(number, []).extend(values)
    rebuilt = v._rebuild_projection_quality(
        result,
        assets_by_question=combined,
        issues_by_question={},
    )
    return rebuilt, sum(len(values) for values in recovered_assets.values()), recovered_regions


def reconcile_mistral_source_visuals(
    result: PageAssemblyResult,
    *,
    pdf_data: bytes,
    ocr_pages: Sequence[Mapping[str, Any]],
    layout: Mapping[str, Any],
    source_sha256: str,
    store: VisualAssetStore | None = None,
    config: VisualPipelineConfig | None = None,
    storage_namespace: str = "",
    should_cancel: Callable[[], bool] | None = None,
):
    selected = config or VisualPipelineConfig.from_env()
    selected_store = store or PrivateVisualAssetStore()
    updated, stats, audit = base.reconcile_mistral_source_visuals(
        result,
        pdf_data=pdf_data,
        ocr_pages=ocr_pages,
        layout=layout,
        source_sha256=source_sha256,
        store=selected_store,
        config=selected,
        storage_namespace=storage_namespace,
        should_cancel=should_cancel,
    )
    updated, recovered_count, recovered_regions = _recover_solution_visuals(
        updated,
        pdf_data=pdf_data,
        ocr_pages=ocr_pages,
        layout=layout,
        source_sha256=source_sha256,
        store=selected_store,
        config=selected,
        storage_namespace=storage_namespace,
        should_cancel=should_cancel,
    )
    if recovered_count:
        stats = dict(stats)
        stats["assetsAttached"] = int(stats.get("assetsAttached", 0)) + recovered_count
        stats["solutionVisuals"] = int(stats.get("solutionVisuals", 0)) + recovered_count
        audit = dict(audit)
        audit["stats"] = dict(stats)
        audit["strongLocalSolutionRecovery"] = recovered_regions
        policy = dict(audit.get("policy") or {})
        policy["strongLocalSolutionRecovery"] = True
        audit["policy"] = policy
    return updated, stats, audit


__all__ = [
    "MISTRAL_VISUAL_STORAGE_PREFIX",
    "PrivateVisualAssetStore",
    "VISUAL_CRITICAL_ISSUE_CODES",
    "VisualAssetStore",
    "VisualPipelineConfig",
    "VisualPipelineStats",
    "reconcile_mistral_source_visuals",
]
