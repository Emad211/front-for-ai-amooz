"""Stable production-facing visual API for the Mistral OCR4 Exam Prep engine.

Geometry/crop primitives are frozen in ``exam_prep_mistral_visual_primitives``.
The actual production policy is loaded lazily from
``exam_prep_mistral_visual_runtime`` so option binding and fallback behavior stay
fail-closed without creating import cycles.

This module intentionally contains no LLM dependency.
"""
from __future__ import annotations

from typing import Any

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

# Focused deterministic seams retained for unit tests and the fail-closed runtime.
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
_option_markers = _p._option_markers
_rtl_reading_order = _p._rtl_reading_order
_bind_option_clusters = _p._bind_option_clusters
_is_auxiliary = _p._is_auxiliary
_smart_union_bbox = _p._smart_union_bbox
_plan_sanity = _p._plan_sanity
_should_group = _p._should_group
_plans_for_region = _p._plans_for_region
_visual_required = _p._visual_required
_fallback_plan = _p._fallback_plan
_asset_name = _p._asset_name
_asset_id = _p._asset_id
_asset_alt = _p._asset_alt
_asset_from_payload = _p._asset_from_payload
_rebuild_projection_quality = _p._rebuild_projection_quality


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
