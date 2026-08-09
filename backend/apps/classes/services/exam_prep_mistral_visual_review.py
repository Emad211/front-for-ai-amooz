"""Recompute Stage-3 visual blockers from immutable visual metadata.

Teacher review must not trust a stale or edited ``question.issues`` list.  This
module derives the critical visual state again from the stored Stage-3 asset
contract so review refresh and publication cannot accidentally forget a clipped,
review-only, missing-option, or whole-page fallback visual.
"""
from __future__ import annotations

from typing import Any, Mapping

from .exam_prep_mistral_visual_primitives import (
    MISTRAL_VISUAL_STORAGE_PREFIX,
    VISUAL_CRITICAL_ISSUE_CODES,
)


_STAGE3_ID_PREFIX = "inline-mistral-v1-"
_VALID_ROLES = frozenset({"question", "option", "solution"})


def _bbox_valid(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        x0 = float(value.get("x0"))
        y0 = float(value.get("y0"))
        x1 = float(value.get("x1"))
        y1 = float(value.get("y1"))
    except (TypeError, ValueError):
        return False
    return 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1


def _stage3_asset(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    asset_id = str(value.get("id") or "")
    storage = str(value.get("storagePath") or "")
    return asset_id.startswith(_STAGE3_ID_PREFIX) or storage.startswith(
        MISTRAL_VISUAL_STORAGE_PREFIX + "/"
    )


def visual_metadata_issue_codes(question: Mapping[str, Any]) -> list[str]:
    """Return deterministic Stage-3 visual blockers derived from asset metadata."""

    assets = [
        item
        for item in (question.get("visuals") or [])
        if isinstance(item, Mapping)
    ]
    stage3 = [item for item in assets if _stage3_asset(item)]
    if not stage3:
        return []

    issues: list[str] = []
    option_assets: list[Mapping[str, Any]] = []
    grouped_option_safe = False

    for asset in stage3:
        role = str(asset.get("role") or "")
        mode = str(asset.get("visualMode") or "")
        if role not in _VALID_ROLES:
            issues.append("visual_precise_crop_unresolved")
        if mode == "whole_page_review_fallback":
            issues.append("visual_precise_crop_unresolved")
        if not _bbox_valid(asset.get("sourceBBox")):
            issues.append("visual_precise_crop_unresolved")
        try:
            source_page = int(asset.get("sourcePage") or 0)
        except (TypeError, ValueError):
            source_page = 0
        storage = str(asset.get("storagePath") or "")
        if source_page < 1 or not storage.startswith(
            MISTRAL_VISUAL_STORAGE_PREFIX + "/"
        ):
            issues.append("visual_precise_crop_unresolved")

        sanity = asset.get("sanity")
        sanity_issues = (
            [str(code) for code in (sanity.get("issues") or [])]
            if isinstance(sanity, Mapping)
            else []
        )
        for code in sanity_issues:
            if code in VISUAL_CRITICAL_ISSUE_CODES:
                issues.append(code)
        sanity_status = (
            str(sanity.get("status") or "")
            if isinstance(sanity, Mapping)
            else ""
        )
        if asset.get("reviewOnly") is True:
            if not any(code in VISUAL_CRITICAL_ISSUE_CODES for code in sanity_issues):
                issues.append("visual_precise_crop_unresolved")
        elif sanity_status != "passed":
            # A publishable Stage-3 visual must positively carry the local sanity
            # result; silently missing metadata is not accepted.
            issues.append("visual_precise_crop_unresolved")

        if role == "option":
            option_assets.append(asset)
            if str(asset.get("optionLabel") or "") not in {"1", "2", "3", "4"}:
                issues.append("visual_option_binding_unresolved")
        if mode == "grouped_options" and asset.get("reviewOnly") is not True:
            labels = {
                str(value)
                for value in (asset.get("groupedOptionLabels") or [])
            }
            if labels == {"1", "2", "3", "4"} and sanity_status == "passed":
                grouped_option_safe = True
            else:
                issues.append("visual_missing_option_asset")

    if option_assets and not grouped_option_safe:
        usable_labels = {
            str(asset.get("optionLabel") or "")
            for asset in option_assets
            if asset.get("reviewOnly") is not True
            and isinstance(asset.get("sanity"), Mapping)
            and str(asset["sanity"].get("status") or "") == "passed"
        }
        if usable_labels != {"1", "2", "3", "4"}:
            issues.append("visual_missing_option_asset")

    return list(dict.fromkeys(issues))


__all__ = [
    "VISUAL_CRITICAL_ISSUE_CODES",
    "visual_metadata_issue_codes",
]
