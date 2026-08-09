"""Fail-closed runtime orchestration for OCR4 visual reconciliation.

The lower-level geometry/crop primitives live in ``exam_prep_mistral_visuals``.
This module applies production safety policy around them:

* a question-heading block can never masquerade as an option label;
* option-to-image bindings inferred only from geometry are not publish-safe;
* region-level visual ambiguity makes every affected crop review-only;
* significant ink touching a supposedly padded crop edge is treated as clipping;
* a precise-crop encoding failure falls back to a whole-page review asset rather
  than silently dropping the source evidence;
* rendered-page graphic discovery uses a bounded local mask while keeping all
  candidate bboxes normalized to the authoritative physical page.

No LLM call is made here.
"""
from __future__ import annotations

from dataclasses import replace
import copy
import os
from typing import Any, Mapping, Sequence

from PIL import Image

from . import exam_prep_mistral_visuals as v
from .exam_prep_mistral_layout_analysis import (
    LayoutBlock,
    associate_uncovered_graphics,
    detect_uncovered_graphics,
    normalize_page_blocks,
)
from .exam_prep_page_records import PageAssemblyResult


VISUAL_CRITICAL_ISSUE_CODES = v.VISUAL_CRITICAL_ISSUE_CODES
MISTRAL_VISUAL_STORAGE_PREFIX = v.MISTRAL_VISUAL_STORAGE_PREFIX
VisualAssetStore = v.VisualAssetStore
PrivateVisualAssetStore = v.PrivateVisualAssetStore
VisualPipelineConfig = v.VisualPipelineConfig
VisualPipelineStats = v.VisualPipelineStats
VisualPlan = v.VisualPlan
VisualSeed = v.VisualSeed


def _detector_max_dimension() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_VISUAL_DETECTOR_MAX_DIMENSION", "1000"))
    except (TypeError, ValueError):
        value = 1000
    return max(600, min(1400, value))


def _bounded_detector_page(
    image: Image.Image,
    raw_page: Mapping[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    """Build a bounded rendered mask with normalized OCR coverage boxes.

    ``detect_uncovered_graphics`` is intentionally a pure-Python connected
    component detector. Running it at the provider's full OCR pixel dimensions
    across a large document is unnecessarily expensive. We downsample only the
    discovery mask, normalize every OCR block first, and keep the returned
    candidate coordinates in 0..1 page space. Final crops are still rendered
    separately at the configured high crop DPI.
    """

    max_dimension = _detector_max_dimension()
    width, height = image.size
    ratio = min(1.0, max_dimension / max(1, max(width, height)))
    target = (
        max(1, round(width * ratio)),
        max(1, round(height * ratio)),
    )
    if target == image.size:
        rendered = image.copy()
    else:
        rendered = image.resize(target, Image.Resampling.BILINEAR)
    try:
        payload = v._encode_png(rendered)
    finally:
        rendered.close()

    blocks = normalize_page_blocks(raw_page)
    detector_page = {
        "dimensions": {"width": target[0], "height": target[1]},
        "blocks": [
            {
                "x0": block.bbox[0],
                "y0": block.bbox[1],
                "x1": block.bbox[2],
                "y1": block.bbox[3],
            }
            for block in blocks
        ],
    }
    return payload, detector_page


def _detect_uncovered_graphics_bounded(
    image: Image.Image,
    raw_page: Mapping[str, Any],
) -> list[dict[str, Any]]:
    payload, detector_page = _bounded_detector_page(image, raw_page)
    return detect_uncovered_graphics(
        image_bytes=payload,
        page=detector_page,
        padding_px=2,
        min_width_px=9,
        min_height_px=7,
        min_ink_pixels=12,
    )


def _without_heading(
    blocks: Sequence[LayoutBlock],
    region: Mapping[str, Any],
) -> list[LayoutBlock]:
    raw = region.get("headingProviderIndex")
    heading_index = int(raw) if isinstance(raw, int) else None
    if heading_index is None:
        return list(blocks)
    return [block for block in blocks if block.provider_index != heading_index]


def _region_box(region: Mapping[str, Any]) -> v.BBox | None:
    return v._bbox(region.get("bbox"))


def _explicit_option_labels(
    blocks: Sequence[LayoutBlock],
    region: Mapping[str, Any],
) -> set[str]:
    box = _region_box(region)
    if box is None:
        return set()
    return {
        label
        for label, _marker_box in v._option_markers(
            _without_heading(blocks, region),
            box,
        )
    }


def _grouped_option_plan(
    *,
    page_number: int,
    region: Mapping[str, Any],
    seeds: Sequence[VisualSeed],
    blocks: Sequence[LayoutBlock],
    config: VisualPipelineConfig,
    review_only: bool,
    issues: Sequence[str],
) -> VisualPlan | None:
    box = _region_box(region)
    question_number = v._number(region.get("questionNumber")) or 0
    if box is None or question_number < 1 or not seeds:
        return None
    heading = region.get("headingProviderIndex")
    heading_index = int(heading) if isinstance(heading, int) else None
    crop_box, component_ids, source_kinds = v._smart_union_bbox(
        list(seeds),
        blocks=_without_heading(blocks, region),
        region_box=box,
        heading_index=heading_index,
        config=config,
    )
    sanity = list(
        dict.fromkeys(
            [
                *v._plan_sanity(
                    box=crop_box,
                    region_box=box,
                    cluster=list(seeds),
                    config=config,
                ),
                *[
                    str(code)
                    for code in issues
                    if str(code) in VISUAL_CRITICAL_ISSUE_CODES
                ],
            ]
        )
    )
    return VisualPlan(
        page_number=page_number,
        question_number=question_number,
        role="question",
        option_label=None,
        mode="grouped_options",
        bbox=crop_box,
        source_kinds=source_kinds,
        component_ids=component_ids,
        grouped_option_labels=("1", "2", "3", "4"),
        table=any(seed.is_table for seed in seeds),
        sanity_issues=tuple(sanity),
        review_only=bool(review_only or sanity),
    )


def _harden_region_plans(
    *,
    page_number: int,
    region: Mapping[str, Any],
    seeds: Sequence[VisualSeed],
    blocks: Sequence[LayoutBlock],
    config: VisualPipelineConfig,
) -> tuple[list[VisualPlan], list[str]]:
    """Build plans without trusting geometry-only option-label inference."""

    safe_blocks = _without_heading(blocks, region)
    plans, issues = v._plans_for_region(
        page_number=page_number,
        region=region,
        seeds=seeds,
        blocks=safe_blocks,
        config=config,
    )
    mode = str(region.get("visualOptionMode") or "")

    if mode == "separate_candidates":
        labels = _explicit_option_labels(safe_blocks, region)
        option_plans = [plan for plan in plans if plan.role == "option"]
        explicit_complete = (
            labels == {"1", "2", "3", "4"}
            and len(option_plans) == 4
            and {plan.option_label for plan in option_plans}
            == {"1", "2", "3", "4"}
        )
        geometry_inferred = "visual_option_binding_inferred" in issues
        binding_problem = bool(
            set(issues)
            & {
                "visual_missing_option_asset",
                "visual_option_binding_unresolved",
            }
        )
        if not explicit_complete or geometry_inferred or binding_problem:
            grouped_issues = [
                code
                for code in issues
                if code != "visual_option_binding_inferred"
            ]
            if labels != {"1", "2", "3", "4"}:
                grouped_issues = list(
                    dict.fromkeys(
                        [
                            *grouped_issues,
                            "visual_option_binding_unresolved",
                        ]
                    )
                )
            else:
                grouped_issues = [
                    code
                    for code in grouped_issues
                    if code
                    not in {
                        "visual_missing_option_asset",
                        "visual_option_binding_unresolved",
                    }
                ]
            grouped = _grouped_option_plan(
                page_number=page_number,
                region=region,
                seeds=seeds,
                blocks=safe_blocks,
                config=config,
                review_only=(labels != {"1", "2", "3", "4"}),
                issues=grouped_issues,
            )
            plans = [grouped] if grouped is not None else []
            issues = grouped_issues

    critical = [
        code
        for code in issues
        if code in VISUAL_CRITICAL_ISSUE_CODES
    ]
    if critical:
        hardened: list[VisualPlan] = []
        for plan in plans:
            merged = tuple(
                dict.fromkeys([*plan.sanity_issues, *critical])
            )
            hardened.append(
                replace(
                    plan,
                    sanity_issues=merged,
                    review_only=True,
                )
            )
        plans = hardened
    return plans, list(dict.fromkeys(issues))


def _edge_ink_ratio(
    image: Image.Image,
    box: v.BBox,
    *,
    band_px: int = 3,
    dark_threshold: int = 170,
) -> float:
    """Measure dark source ink touching the exact final crop boundary."""

    width, height = image.size
    left = max(0, min(width - 1, int(box[0] * width)))
    top = max(0, min(height - 1, int(box[1] * height)))
    right = max(
        left + 1,
        min(width, int(box[2] * width + 0.9999)),
    )
    bottom = max(
        top + 1,
        min(height, int(box[3] * height + 0.9999)),
    )
    crop = image.crop((left, top, right, bottom)).convert("L")
    try:
        if crop.width < 12 or crop.height < 12:
            return 1.0
        band = max(
            1,
            min(band_px, crop.width // 4, crop.height // 4),
        )
        pixels = crop.load()
        dark = total = 0
        for y in range(crop.height):
            for x in range(crop.width):
                if (
                    x < band
                    or x >= crop.width - band
                    or y < band
                    or y >= crop.height - band
                ):
                    total += 1
                    dark += int(pixels[x, y] < dark_threshold)
        return dark / max(1, total)
    finally:
        crop.close()


def _raster_harden_plan(
    image: Image.Image,
    plan: VisualPlan,
) -> VisualPlan:
    if plan.mode == "whole_page_review_fallback":
        return plan
    if _edge_ink_ratio(image, plan.bbox) < 0.018:
        return plan
    issues = tuple(
        dict.fromkeys(
            [*plan.sanity_issues, "visual_crop_clipped"]
        )
    )
    return replace(
        plan,
        sanity_issues=issues,
        review_only=True,
    )


def _fallback_after_precise_failure(
    plan: VisualPlan,
) -> VisualPlan:
    fallback = v._fallback_plan(
        page_number=plan.page_number,
        question_number=plan.question_number,
        kind=(
            "solution"
            if plan.role == "solution"
            else "question"
        ),
    )
    return replace(
        fallback,
        sanity_issues=tuple(
            dict.fromkeys(
                [
                    *fallback.sanity_issues,
                    "visual_crop_oversized",
                ]
            )
        ),
        review_only=True,
    )


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
    """Reconcile precise visuals with fail-closed option binding and crops."""

    if not pdf_data or not pdf_data.lstrip().startswith(b"%PDF"):
        raise ValueError(
            "visual reconciliation requires authoritative PDF bytes"
        )
    selected = config or VisualPipelineConfig.from_env()
    selected_store = store or PrivateVisualAssetStore()
    working_layout = copy.deepcopy(dict(layout))
    analysis_pages = v._analysis_page_map(working_layout)
    ocr_by_page = v._page_map(ocr_pages)
    relevant_pages = sorted(
        page_number
        for page_number, page in analysis_pages.items()
        if str(page.get("pageRole") or "")
        in {"question", "solution", "mixed"}
        and page_number in ocr_by_page
    )

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pypdfium2 is required for visual reconciliation"
        ) from exc

    fingerprints: dict[tuple[Any, ...], list[str]] = {}
    seed_cache: dict[
        tuple[int, int, str],
        list[VisualSeed],
    ] = {}
    local_count = 0
    ocr_count = 0
    document = pdfium.PdfDocument(pdf_data)
    try:
        for page_number in relevant_pages:
            image = v._render_page(
                document,
                page_number,
                selected.detection_dpi,
            )
            try:
                raw_page = ocr_by_page[page_number]
                uncovered = _detect_uncovered_graphics_bounded(
                    image,
                    raw_page,
                )
                local_count += len(uncovered)
                analysis_page = analysis_pages[page_number]
                associate_uncovered_graphics(
                    analysis_page,
                    uncovered,
                )
                for region in analysis_page.get("regions") or []:
                    if not isinstance(region, Mapping):
                        continue
                    number = (
                        v._number(region.get("questionNumber"))
                        or 0
                    )
                    kind = str(
                        region.get("kind") or "question"
                    )
                    seeds = v._region_seeds(
                        page_number,
                        region,
                    )
                    ocr_count += sum(
                        seed.source_kind.startswith("ocr_")
                        for seed in seeds
                    )
                    seed_cache[
                        (page_number, number, kind)
                    ] = seeds
                    for seed in seeds:
                        x0, y0, x1, y1 = seed.bbox
                        signature = (
                            round((x0 + x1) / 2.0, 2),
                            round((y0 + y1) / 2.0, 2),
                            round(x1 - x0, 2),
                            round(y1 - y0, 2),
                            v._fingerprint(
                                image,
                                seed.bbox,
                            ),
                        )
                        fingerprints.setdefault(
                            signature,
                            [],
                        ).append(seed.seed_id)
            finally:
                image.close()
    finally:
        document.close()

    seed_by_id = {
        seed.seed_id: seed
        for seeds in seed_cache.values()
        for seed in seeds
    }
    decorative_ids: set[str] = set()
    for seed_ids in fingerprints.values():
        repeated = len(
            {
                seed_by_id[item].page_number
                for item in seed_ids
                if item in seed_by_id
            }
        )
        for seed_id in seed_ids:
            seed = seed_by_id.get(seed_id)
            if (
                seed is not None
                and v._decorative_candidate(
                    seed,
                    repeated,
                )
            ):
                decorative_ids.add(seed_id)

    plans_by_page: dict[int, list[VisualPlan]] = {}
    issues_by_question: dict[int, list[str]] = {}
    unresolved_regions: list[dict[str, Any]] = []
    for page_number in relevant_pages:
        blocks = normalize_page_blocks(
            ocr_by_page[page_number]
        )
        analysis_page = analysis_pages[page_number]
        for region in analysis_page.get("regions") or []:
            if not isinstance(region, Mapping):
                continue
            number = (
                v._number(region.get("questionNumber"))
                or 0
            )
            kind = str(region.get("kind") or "question")
            if number < 1:
                continue
            seeds = [
                seed
                for seed in seed_cache.get(
                    (page_number, number, kind),
                    [],
                )
                if seed.seed_id not in decorative_ids
            ]
            if not seeds and not v._visual_required(region):
                continue
            if seeds:
                plans, region_issues = _harden_region_plans(
                    page_number=page_number,
                    region=region,
                    seeds=seeds,
                    blocks=blocks,
                    config=selected,
                )
            else:
                plans = []
                region_issues = [
                    "visual_precise_crop_unresolved"
                ]
            if not plans:
                plans = [
                    v._fallback_plan(
                        page_number=page_number,
                        question_number=number,
                        kind=kind,
                    )
                ]
                unresolved_regions.append(
                    {
                        "pageNumber": page_number,
                        "questionNumber": number,
                        "role": kind,
                        "reason": (
                            "visual_precise_crop_unresolved"
                        ),
                    }
                )
            plans_by_page.setdefault(
                page_number,
                [],
            ).extend(plans)
            issues_by_question.setdefault(
                number,
                [],
            ).extend(region_issues)

    assets_by_question: dict[
        int,
        list[dict[str, Any]],
    ] = {}
    storage_failures = 0
    fallback_keys: set[tuple[int, int, str]] = set()
    document = pdfium.PdfDocument(pdf_data)
    try:
        for page_number, raw_plans in sorted(
            plans_by_page.items()
        ):
            image = v._render_page(
                document,
                page_number,
                selected.crop_dpi,
            )
            try:
                plans = [
                    _raster_harden_plan(image, plan)
                    for plan in raw_plans
                ]
                counters: dict[
                    tuple[int, str, str | None],
                    int,
                ] = {}
                for original_plan in plans:
                    plan = original_plan
                    key = (
                        plan.question_number,
                        plan.role,
                        plan.option_label,
                    )
                    counters[key] = counters.get(key, 0) + 1
                    order = counters[key]
                    try:
                        payload = v._crop_bytes(
                            image,
                            plan.bbox,
                            selected,
                        )
                    except ValueError:
                        issues_by_question.setdefault(
                            plan.question_number,
                            [],
                        ).extend(
                            [
                                "visual_crop_oversized",
                                "visual_precise_crop_unresolved",
                            ]
                        )
                        fallback_key = (
                            plan.page_number,
                            plan.question_number,
                            plan.role,
                        )
                        if fallback_key in fallback_keys:
                            continue
                        fallback_keys.add(fallback_key)
                        plan = _fallback_after_precise_failure(
                            plan
                        )
                        try:
                            payload = v._crop_bytes(
                                image,
                                plan.bbox,
                                selected,
                            )
                        except ValueError:
                            continue
                        order = 1
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
                        issues_by_question.setdefault(
                            plan.question_number,
                            [],
                        ).append("visual_storage_failed")
                        continue
                    if plan.sanity_issues:
                        asset["reviewOnly"] = True
                        asset["sanity"] = {
                            "status": "needs_review",
                            "issues": list(
                                plan.sanity_issues
                            ),
                        }
                        issues_by_question.setdefault(
                            plan.question_number,
                            [],
                        ).extend(plan.sanity_issues)
                    assets_by_question.setdefault(
                        plan.question_number,
                        [],
                    ).append(asset)
            finally:
                image.close()
    finally:
        document.close()

    for plans in plans_by_page.values():
        for plan in plans:
            if any(
                asset.get("sourcePage")
                == plan.page_number
                and asset.get("role") == plan.role
                and (
                    plan.option_label is None
                    or asset.get("optionLabel")
                    == plan.option_label
                )
                for asset in assets_by_question.get(
                    plan.question_number,
                    (),
                )
            ):
                continue
            issues_by_question.setdefault(
                plan.question_number,
                [],
            ).append("visual_precise_crop_unresolved")

    normalized_issues = {
        number: list(dict.fromkeys(codes))
        for number, codes in issues_by_question.items()
    }
    updated = v._rebuild_projection_quality(
        result,
        assets_by_question=assets_by_question,
        issues_by_question=normalized_issues,
    )
    all_assets = [
        asset
        for values in assets_by_question.values()
        for asset in values
    ]
    all_codes = [
        code
        for values in normalized_issues.values()
        for code in values
    ]
    stats = VisualPipelineStats(
        pages_scanned=len(relevant_pages),
        local_graphic_candidates=local_count,
        ocr_visual_candidates=ocr_count,
        decorative_suppressed=len(decorative_ids),
        assets_attached=len(all_assets),
        question_visuals=sum(
            asset.get("role") == "question"
            for asset in all_assets
        ),
        option_visuals=sum(
            asset.get("role") == "option"
            for asset in all_assets
        ),
        solution_visuals=sum(
            asset.get("role") == "solution"
            for asset in all_assets
        ),
        grouped_visuals=sum(
            str(
                asset.get("visualMode") or ""
            ).startswith("grouped_")
            for asset in all_assets
        ),
        table_visuals=sum(
            "ocr_table"
            in (asset.get("sourceKinds") or [])
            for asset in all_assets
        ),
        whole_page_fallbacks=sum(
            asset.get("visualMode")
            == "whole_page_review_fallback"
            for asset in all_assets
        ),
        review_only_assets=sum(
            bool(asset.get("reviewOnly"))
            for asset in all_assets
        ),
        sanity_failures=sum(
            code in VISUAL_CRITICAL_ISSUE_CODES
            for code in all_codes
        ),
        unresolved_regions=len(unresolved_regions),
        storage_failures=storage_failures,
    )
    audit = {
        "schemaVersion": 2,
        "sourceSha256": source_sha256,
        "stats": stats.as_dict(),
        "unresolvedRegions": unresolved_regions,
        "criticalIssueCodes": sorted(
            {
                code
                for code in all_codes
                if code in VISUAL_CRITICAL_ISSUE_CODES
            }
        ),
        "policy": {
            "geometryOnlyOptionBindingAccepted": False,
            "wholePageFallbackPublishSafe": False,
            "sourceAndSolutionDeduplicated": False,
            "localDetectorMaxDimension": (
                _detector_max_dimension()
            ),
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
    "VisualPlan",
    "VisualSeed",
    "reconcile_mistral_source_visuals",
]
