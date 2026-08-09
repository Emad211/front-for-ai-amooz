"""Recompute Stage-3 visual blockers from immutable visual metadata.

Teacher review must not trust a stale or edited ``question.issues`` list. This
module derives critical visual state again from the stored Stage-3 asset contract
so review refresh and publication cannot accidentally forget a clipped,
review-only, missing-option, deleted, or whole-page fallback visual.

The optional ``source_contract`` argument is the server-side immutable contract
captured in ``workflow_state.extractionAudit`` at extraction time. When present,
it is authoritative over the editable copy carried inside ``exam_prep_json``.
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


def _selected_contract(
    question: Mapping[str, Any],
    source_contract: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if isinstance(source_contract, Mapping):
        return source_contract
    value = question.get("visualSourceContract")
    return value if isinstance(value, Mapping) else None


def _source_contract_mismatch(
    question: Mapping[str, Any],
    stage3: list[Mapping[str, Any]],
    source_contract: Mapping[str, Any] | None = None,
) -> bool:
    contract = _selected_contract(question, source_contract)
    if not isinstance(contract, Mapping):
        return bool(stage3)
    if int(contract.get("schemaVersion") or 0) != 1:
        return True

    current_ids = {
        str(asset.get("id") or "")
        for asset in stage3
        if str(asset.get("id") or "")
    }
    required_ids = {
        str(value)
        for value in (contract.get("requiredAssetIds") or [])
        if str(value)
    }
    if not required_ids or not required_ids.issubset(current_ids):
        return True

    role_counts = contract.get("roleCounts")
    if not isinstance(role_counts, Mapping):
        return True
    for role in _VALID_ROLES:
        try:
            required_count = int(role_counts.get(role) or 0)
        except (TypeError, ValueError):
            return True
        current_count = sum(
            str(asset.get("role") or "") == role for asset in stage3
        )
        if current_count < required_count:
            return True

    required_pages = {
        int(value)
        for value in (contract.get("sourcePages") or [])
        if str(value).isdigit() and int(value) > 0
    }
    current_pages = {
        int(asset.get("sourcePage") or 0)
        for asset in stage3
        if str(asset.get("sourcePage") or "").isdigit()
        and int(asset.get("sourcePage") or 0) > 0
    }
    if required_pages and not required_pages.issubset(current_pages):
        return True

    required_options = {
        str(value)
        for value in (contract.get("optionLabels") or [])
        if str(value) in {"1", "2", "3", "4"}
    }
    current_options = {
        str(asset.get("optionLabel") or "")
        for asset in stage3
        if str(asset.get("role") or "") == "option"
        and str(asset.get("optionLabel") or "") in {"1", "2", "3", "4"}
    }
    if required_options and not required_options.issubset(current_options):
        return True

    required_grouped = {
        str(value)
        for value in (contract.get("groupedOptionLabels") or [])
        if str(value) in {"1", "2", "3", "4"}
    }
    current_grouped = {
        str(value)
        for asset in stage3
        if str(asset.get("visualMode") or "") == "grouped_options"
        for value in (asset.get("groupedOptionLabels") or [])
        if str(value) in {"1", "2", "3", "4"}
    }
    return bool(
        required_grouped and not required_grouped.issubset(current_grouped)
    )


def _stage3_visuals(
    question: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    return [
        item
        for item in (question.get("visuals") or [])
        if isinstance(item, Mapping) and _stage3_asset(item)
    ]


def visual_options_complete(
    question: Mapping[str, Any],
    *,
    source_contract: Mapping[str, Any] | None = None,
) -> bool:
    """True only when source metadata supports a complete visual-only 1..4 set."""

    stage3 = _stage3_visuals(question)
    if not stage3 or _source_contract_mismatch(
        question,
        stage3,
        source_contract,
    ):
        return False

    grouped = [
        asset
        for asset in stage3
        if str(asset.get("visualMode") or "") == "grouped_options"
        and asset.get("reviewOnly") is not True
        and isinstance(asset.get("sanity"), Mapping)
        and str(asset["sanity"].get("status") or "") == "passed"
    ]
    if any(
        {
            str(value)
            for value in (asset.get("groupedOptionLabels") or [])
        }
        == {"1", "2", "3", "4"}
        for asset in grouped
    ):
        return True

    labels = {
        str(asset.get("optionLabel") or "")
        for asset in stage3
        if str(asset.get("role") or "") == "option"
        and asset.get("reviewOnly") is not True
        and isinstance(asset.get("sanity"), Mapping)
        and str(asset["sanity"].get("status") or "") == "passed"
    }
    return labels == {"1", "2", "3", "4"}


def visual_metadata_issue_codes(
    question: Mapping[str, Any],
    *,
    source_contract: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return deterministic Stage-3 visual blockers derived from asset metadata."""

    stage3 = _stage3_visuals(question)
    contract = _selected_contract(question, source_contract)
    if not stage3 and not isinstance(contract, Mapping):
        return []

    issues: list[str] = []
    if _source_contract_mismatch(question, stage3, source_contract):
        issues.append("visual_precise_crop_unresolved")

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
            if not any(
                code in VISUAL_CRITICAL_ISSUE_CODES
                for code in sanity_issues
            ):
                issues.append("visual_precise_crop_unresolved")
        elif sanity_status != "passed":
            issues.append("visual_precise_crop_unresolved")

        if role == "option":
            option_assets.append(asset)
            if str(asset.get("optionLabel") or "") not in {
                "1",
                "2",
                "3",
                "4",
            }:
                issues.append("visual_option_binding_unresolved")
        if (
            mode == "grouped_options"
            and asset.get("reviewOnly") is not True
        ):
            labels = {
                str(value)
                for value in (asset.get("groupedOptionLabels") or [])
            }
            if (
                labels == {"1", "2", "3", "4"}
                and sanity_status == "passed"
            ):
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
    "visual_options_complete",
]
