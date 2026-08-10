"""Stable source-precise Stage-3 reconciliation facade.

This facade is the shared deterministic visual-policy bootstrap used by both the
production pipeline and production-shaped acceptance replay. It owns only
layout/recovery/visual policies; Stage-4 provider transport is deliberately
installed at the Stage-4 runtime seam to keep the import graph acyclic.
"""
from __future__ import annotations

from typing import Any, Mapping

from .exam_prep_mistral_full_width_layout_policy import install_full_width_layout_policy
from .exam_prep_mistral_full_width_visual_option_policy import (
    install_full_width_visual_option_policy,
)
from .exam_prep_mistral_targeted_recovery_policy import install_targeted_recovery_policy
from . import exam_prep_mistral_visual_reconcile_v3 as _impl


# Production and final acceptance import this facade before rebuilding OCR4
# layout evidence. These policies are deterministic and provider-free.
install_full_width_layout_policy()
install_full_width_visual_option_policy()
install_targeted_recovery_policy()

MISTRAL_VISUAL_STORAGE_PREFIX = _impl.MISTRAL_VISUAL_STORAGE_PREFIX
PrivateVisualAssetStore = _impl.PrivateVisualAssetStore
VISUAL_CRITICAL_ISSUE_CODES = _impl.VISUAL_CRITICAL_ISSUE_CODES
VisualAssetStore = _impl.VisualAssetStore
VisualPipelineConfig = _impl.VisualPipelineConfig
VisualPipelineStats = _impl.VisualPipelineStats


def _dedupe_exact_visual_assets(result, stats, audit):
    """Remove only byte-identical assets with the same semantic attachment role."""

    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    questions: list[dict[str, Any]] = []
    removed = 0
    removed_roles: dict[str, int] = {"question": 0, "option": 0, "solution": 0}

    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        question = dict(raw)
        visuals = [dict(item) for item in (question.get("visuals") or []) if isinstance(item, Mapping)]
        seen: set[tuple[str, str, str, str]] = set()
        kept: list[dict[str, Any]] = []
        kept_ids: set[str] = set()
        for asset in visuals:
            digest = str(asset.get("sha256") or "").strip().lower()
            role = str(asset.get("role") or "")
            option_label = str(asset.get("optionLabel") or "")
            variant = str(asset.get("selectedVariant") or "")
            key = (digest, role, option_label, variant)
            if digest and key in seen:
                removed += 1
                if role in removed_roles:
                    removed_roles[role] += 1
                continue
            if digest:
                seen.add(key)
            kept.append(asset)
            asset_id = str(asset.get("id") or "")
            if asset_id:
                kept_ids.add(asset_id)
        question["visuals"] = kept

        contract = question.get("visualSourceContract")
        if isinstance(contract, Mapping):
            updated_contract = dict(contract)
            required = [str(value) for value in (contract.get("requiredAssetIds") or []) if str(value)]
            updated_contract["requiredAssetIds"] = [value for value in required if value in kept_ids]
            question["visualSourceContract"] = updated_contract
        questions.append(question)

    if not removed:
        return result, stats, audit

    exam["questions"] = questions
    projection["exam_prep"] = exam
    updated_result = result.model_copy(update={"projection": projection})

    updated_stats = dict(stats)
    updated_stats["assetsAttached"] = max(0, int(updated_stats.get("assetsAttached") or 0) - removed)
    for role, count in removed_roles.items():
        field = {
            "question": "questionVisuals",
            "option": "optionVisuals",
            "solution": "solutionVisuals",
        }[role]
        updated_stats[field] = max(0, int(updated_stats.get(field) or 0) - count)
    updated_stats["exactDuplicateAssetsRemoved"] = removed

    updated_audit = dict(audit)
    updated_audit["stats"] = dict(updated_stats)
    policy = dict(updated_audit.get("policy") or {})
    policy["exactVisualHashDedup"] = True
    policy["fullWidthQuestionLayoutPolicy"] = True
    policy["fullWidthExactOptionBinding"] = True
    policy["missingHeadingIsNotRecoveredSolution"] = True
    updated_audit["policy"] = policy
    return updated_result, updated_stats, updated_audit


def reconcile_mistral_source_visuals(*args, **kwargs):
    result, stats, audit = _impl.reconcile_mistral_source_visuals(*args, **kwargs)
    result, stats, audit = _dedupe_exact_visual_assets(result, stats, audit)
    audit = dict(audit)
    policy = dict(audit.get("policy") or {})
    policy["fullWidthQuestionLayoutPolicy"] = True
    policy["fullWidthExactOptionBinding"] = True
    policy["missingHeadingIsNotRecoveredSolution"] = True
    audit["policy"] = policy
    return result, stats, audit


__all__ = [
    "MISTRAL_VISUAL_STORAGE_PREFIX",
    "PrivateVisualAssetStore",
    "VISUAL_CRITICAL_ISSUE_CODES",
    "VisualAssetStore",
    "VisualPipelineConfig",
    "VisualPipelineStats",
    "_dedupe_exact_visual_assets",
    "reconcile_mistral_source_visuals",
]
