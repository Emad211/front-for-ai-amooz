"""Stable Stage-3 reconciliation facade.

The v2 implementation deliberately consumes the existing visual geometry facade.
Keep the one clamp primitive local here so the implementation does not depend on
an accidentally-public private alias from the earlier Stage-3 module.
"""
from __future__ import annotations

from . import exam_prep_mistral_visual_reconcile_v2 as _impl


def _clamp(box, boundary):
    x0 = max(float(boundary[0]), float(box[0]))
    y0 = max(float(boundary[1]), float(box[1]))
    x1 = min(float(boundary[2]), float(box[2]))
    y1 = min(float(boundary[3]), float(box[3]))
    if x1 <= x0 or y1 <= y0:
        return tuple(float(value) for value in boundary)
    return (x0, y0, x1, y1)


# The implementation references the geometry facade so tests and production use
# exactly the same normalized coordinate rules. Inject only this missing private
# primitive; no runtime policy is monkeypatched.
if not hasattr(_impl.v, "_clamp"):
    _impl.v._clamp = _clamp

MISTRAL_VISUAL_STORAGE_PREFIX = _impl.MISTRAL_VISUAL_STORAGE_PREFIX
PrivateVisualAssetStore = _impl.PrivateVisualAssetStore
VISUAL_CRITICAL_ISSUE_CODES = _impl.VISUAL_CRITICAL_ISSUE_CODES
VisualAssetStore = _impl.VisualAssetStore
VisualPipelineConfig = _impl.VisualPipelineConfig
VisualPipelineStats = _impl.VisualPipelineStats
reconcile_mistral_source_visuals = _impl.reconcile_mistral_source_visuals

__all__ = [
    "MISTRAL_VISUAL_STORAGE_PREFIX",
    "PrivateVisualAssetStore",
    "VISUAL_CRITICAL_ISSUE_CODES",
    "VisualAssetStore",
    "VisualPipelineConfig",
    "VisualPipelineStats",
    "reconcile_mistral_source_visuals",
]
