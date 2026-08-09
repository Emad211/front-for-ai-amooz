"""Stable production-facing visual API for the Mistral OCR4 Exam Prep engine.

Geometry/crop primitives are frozen in ``exam_prep_mistral_visual_primitives``.
The actual production policy is loaded lazily from
``exam_prep_mistral_visual_runtime`` so option binding and fallback behavior stay
fail-closed without creating import cycles.

This facade also narrows option-marker detection for production: a marker must be
a tiny standalone 1..4 label immediately outside an OCR visual block. Numbers
inside graphs/axes are therefore not accepted as option labels.

This module intentionally contains no LLM dependency.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_visual_primitives as _p


# Public contracts.
MISTRAL_VISUAL_STORAGE_PREFIX = _p.MISTRAL_VISUAL_STORAGE_PREFIX
VISUAL_CRITICAL_ISSUE_CODES = _p.VISUAL_CRITICAL_ISSUE_CODES
VisualAssetStore = _p.VisualAssetStore
PrivateVisualAssetStore = _p.PrivateVisualAssetStore
VisualPipelineConfig = _p.VisualPipelineConfig
VisualPipelineStats = _p.VisualPipelineStats
VisualSeed = _p.VisualSeed
VisualPlan = _p.VisualPlan
BBox = _p.BBox

# Focused deterministic seams retained for tests/runtime.
_bbox = _p._bbox
_number = _p._number
_area = _p._area
_center = _p._center
_union = _p._union
_expand = _p._expand
_intersection_area = _p._intersection_area
_coverage = _p._coverage
_gap = _p._gap
_within = _p._within
_render_page = _p._render_page
_encode_png = _p._encode_png
_crop_bytes = _p._crop_bytes
_fingerprint = _p._fingerprint
_page_map = _p._page_map
_analysis_page_map = _p._analysis_page_map
_region_seeds = _p._region_seeds
_decorative_candidate = _p._decorative_candidate
_cluster_seeds = _p._cluster_seeds
_option_label = _p._option_label
_rtl_reading_order = _p._rtl_reading_order
_bind_option_clusters = _p._bind_option_clusters
_is_auxiliary = _p._is_auxiliary
_smart_union_bbox = _p._smart_union_bbox
_plan_sanity = _p._plan_sanity
_should_group = _p._should_group
_visual_required = _p._visual_required
_fallback_plan = _p._fallback_plan
_asset_name = _p._asset_name
_asset_id = _p._asset_id
_asset_alt = _p._asset_alt
_asset_from_payload = _p._asset_from_payload
_rebuild_projection_quality = _p._rebuild_projection_quality

_OPTION_MARKER_ONLY_RE = re.compile(
    r"^\s*(?:گزین[ههۀ]\s*)?[\(\[]?\s*(?P<label>[1-4۱-۴١-٤])"
    r"\s*[\)\].:：\-–—،]?\s*$",
    re.IGNORECASE,
)


def _safe_option_markers(
    blocks: Sequence[_p.LayoutBlock],
    region_box: BBox,
) -> list[tuple[str, BBox]]:
    """Return only explicit standalone option labels adjacent to OCR visuals.

    Axis/tick numbers commonly look like 1..4. A valid option marker must be a
    tiny standalone label, lie outside the visual's own bbox, and sit within a
    narrow geometric gap of an OCR image/table block.
    """

    visual_boxes = [
        block.bbox
        for block in blocks
        if block.block_type in {"image", "table"}
        and _within(block.bbox, region_box, slack=0.015)
    ]
    if not visual_boxes:
        return []
    markers: list[tuple[str, BBox]] = []
    seen: set[str] = set()
    for block in blocks:
        if block.block_type in {"image", "table", "header", "footer", "signature"}:
            continue
        if not _within(block.bbox, region_box, slack=0.01):
            continue
        text = str(block.content or "").translate(_p._DIGIT_TRANS).strip()
        match = _OPTION_MARKER_ONLY_RE.fullmatch(text)
        if match is None or _area(block.bbox) > 0.012:
            continue
        label = str(match.group("label") or "").translate(_p._DIGIT_TRANS)
        if label not in {"1", "2", "3", "4"} or label in seen:
            continue
        cx, cy = _center(block.bbox)
        if any(
            box[0] - 0.004 <= cx <= box[2] + 0.004
            and box[1] - 0.004 <= cy <= box[3] + 0.004
            for box in visual_boxes
        ):
            continue
        if min(_gap(block.bbox, box) for box in visual_boxes) > 0.026:
            continue
        seen.add(label)
        markers.append((label, block.bbox))
    return markers


# Production runtime calls this narrowed seam. The frozen primitive version is
# still available internally as ``_p._option_markers`` for research comparison.
_option_markers = _safe_option_markers


def _plans_for_region(
    *,
    page_number: int,
    region: Mapping[str, Any],
    seeds: Sequence[VisualSeed],
    blocks: Sequence[_p.LayoutBlock],
    config: VisualPipelineConfig,
) -> tuple[list[VisualPlan], list[str]]:
    """Use explicit source labels for separate option assets; never axis ticks."""

    if str(region.get("visualOptionMode") or "") != "separate_candidates":
        return _p._plans_for_region(
            page_number=page_number,
            region=region,
            seeds=seeds,
            blocks=blocks,
            config=config,
        )

    region_box = _bbox(region.get("bbox"))
    question_number = _number(region.get("questionNumber")) or 0
    if region_box is None or question_number < 1:
        return [], ["visual_option_binding_unresolved"]
    clusters = _cluster_seeds(seeds, gap=config.cluster_gap)
    markers = _safe_option_markers(blocks, region_box)
    if len(clusters) != 4 or {label for label, _box in markers} != {"1", "2", "3", "4"}:
        return [], ["visual_option_binding_unresolved"]

    pairs: list[tuple[float, str, int]] = []
    for label, marker_box in markers:
        mx, my = _center(marker_box)
        for index, cluster in enumerate(clusters):
            cluster_box = _union(seed.bbox for seed in cluster) or cluster[0].bbox
            cx, cy = _center(cluster_box)
            distance = ((cx - mx) ** 2 + (cy - my) ** 2) ** 0.5
            if distance <= 0.18:
                pairs.append((distance, label, index))
    assigned_labels: set[str] = set()
    assigned_clusters: set[int] = set()
    assignments: dict[int, str] = {}
    for _distance, label, index in sorted(pairs):
        if label in assigned_labels or index in assigned_clusters:
            continue
        assignments[index] = label
        assigned_labels.add(label)
        assigned_clusters.add(index)
    if set(assignments.values()) != {"1", "2", "3", "4"} or len(assignments) != 4:
        return [], ["visual_option_binding_unresolved"]

    heading = region.get("headingProviderIndex")
    heading_index = int(heading) if isinstance(heading, int) else None
    plans: list[VisualPlan] = []
    issues: list[str] = []
    for index, cluster in enumerate(clusters):
        crop_box, component_ids, source_kinds = _smart_union_bbox(
            cluster,
            blocks=blocks,
            region_box=region_box,
            heading_index=heading_index,
            config=config,
        )
        sanity = _plan_sanity(
            box=crop_box,
            region_box=region_box,
            cluster=cluster,
            config=config,
        )
        issues.extend(sanity)
        plans.append(
            VisualPlan(
                page_number=page_number,
                question_number=question_number,
                role="option",
                option_label=assignments[index],
                mode="separate_option",
                bbox=crop_box,
                source_kinds=source_kinds,
                component_ids=component_ids,
                table=any(seed.is_table for seed in cluster),
                sanity_issues=tuple(sanity),
                review_only=bool(set(sanity).intersection(VISUAL_CRITICAL_ISSUE_CODES)),
            )
        )
    return plans, list(dict.fromkeys(issues))


def reconcile_mistral_source_visuals(*args: Any, **kwargs: Any):
    """Run the hardened visual runtime through the stable public seam."""

    from .exam_prep_mistral_visual_runtime import (
        reconcile_mistral_source_visuals as _runtime_reconcile,
    )

    return _runtime_reconcile(*args, **kwargs)


__all__ = [
    "BBox",
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
