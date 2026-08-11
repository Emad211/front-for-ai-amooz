"""Stable production-facing visual API for the Mistral OCR4 Exam Prep engine.

Geometry/crop primitives are frozen in ``exam_prep_mistral_visual_primitives``.
The actual production policy is loaded lazily from
``exam_prep_mistral_visual_runtime`` so option binding and fallback behavior stay
fail-closed without creating import cycles.

Production policies layered here are deliberately conservative:
- option markers are tiny standalone 1..4 labels adjacent to OCR visuals;
- axis/tick numbers inside a graph are never accepted as option labels;
- repeated body graphics are never discarded merely because they repeat;
- nearby caption/legend/axis/equation evidence must fit inside the crop set;
- every stored asset identity includes source page + semantic role;
- each question keeps a source-visual contract so an edit cannot silently drop
  required Stage-3 evidence.

This module intentionally contains no LLM dependency.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_visual_primitives as _p
from .exam_prep_mistral_artifacts import validate_storage_namespace


MISTRAL_VISUAL_STORAGE_PREFIX = _p.MISTRAL_VISUAL_STORAGE_PREFIX
MISTRAL_VISUAL_MAX_BYTES = _p.MISTRAL_VISUAL_MAX_BYTES
VISUAL_CRITICAL_ISSUE_CODES = _p.VISUAL_CRITICAL_ISSUE_CODES
VisualAssetStore = _p.VisualAssetStore
PrivateVisualAssetStore = _p.PrivateVisualAssetStore
VisualPipelineConfig = _p.VisualPipelineConfig
VisualPipelineStats = _p.VisualPipelineStats
VisualSeed = _p.VisualSeed
VisualPlan = _p.VisualPlan
BBox = _p.BBox

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
_asset_alt = _p._asset_alt

_OPTION_MARKER_ONLY_RE = re.compile(
    r"^\s*(?:گزین[ههۀ]\s*)?[\(\[]?\s*(?P<label>[1-4۱-۴١-٤])"
    r"\s*[\)\].:：\-–—،]?\s*$",
    re.IGNORECASE,
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
_VISUAL_ROLES = frozenset({"question", "option", "solution"})
def visual_storage_path_matches_source(
    storage_path: str,
    *,
    source_sha256: str,
) -> bool:
    """Accept legacy source-first paths and isolated namespace-first paths."""

    path = str(storage_path or "").strip()
    source = str(source_sha256 or "").strip().lower()
    root = f"{MISTRAL_VISUAL_STORAGE_PREFIX}/"
    if (
        _SHA256_RE.fullmatch(source) is None
        or not path.startswith(root)
        or path.startswith("/")
        or ".." in path.split("/")
        or "\\" in path
    ):
        return False
    parts = path[len(root):].split("/")
    if len(parts) >= 2 and parts[0] == source:
        return True
    if len(parts) < 3 or parts[1] != source:
        return False
    try:
        return bool(validate_storage_namespace(parts[0]))
    except ValueError:
        return False


def _immutable_visual_registry_entry(
    asset: Mapping[str, Any],
    *,
    question_id: str,
    source_sha256: str,
) -> dict[str, Any] | None:
    """Return the security-sensitive subset of one valid Stage-3 asset."""

    asset_id = str(asset.get("id") or "").strip()
    question_id = str(question_id or "").strip()
    source_sha256 = str(source_sha256 or "").strip().lower()
    payload_sha256 = str(asset.get("sha256") or "").strip().lower()
    role = str(asset.get("role") or "").strip().lower()
    storage_path = str(asset.get("storagePath") or "").strip()
    content_type = str(asset.get("contentType") or "").strip().lower()
    try:
        byte_size = int(asset.get("byteSize"))
    except (TypeError, ValueError):
        return None
    if (
        not asset_id
        or not question_id
        or _SHA256_RE.fullmatch(source_sha256) is None
        or _SHA256_RE.fullmatch(payload_sha256) is None
        or role not in _VISUAL_ROLES
        or content_type not in _SAFE_CONTENT_TYPES
        or byte_size <= 0
        or byte_size > MISTRAL_VISUAL_MAX_BYTES
        or not visual_storage_path_matches_source(
            storage_path,
            source_sha256=source_sha256,
        )
    ):
        return None
    option_label = asset.get("optionLabel")
    option_label = str(option_label).strip() if option_label not in (None, "") else None
    if option_label is not None and option_label not in {"1", "2", "3", "4"}:
        return None
    return {
        "id": asset_id,
        "questionId": question_id,
        "role": role,
        "optionLabel": option_label,
        "storagePath": storage_path,
        "contentType": content_type,
        "byteSize": byte_size,
        "sha256": payload_sha256,
        "sourceSha256": source_sha256,
    }


def build_visual_asset_registry(
    projection: Mapping[str, Any],
    *,
    source_sha256: str,
) -> dict[str, dict[str, Any]]:
    """Freeze stored Stage-3 asset identities outside the editable projection."""

    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    registry: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for question in questions or []:
        if not isinstance(question, Mapping):
            continue
        question_id = str(question.get("question_id") or "").strip()
        for asset in question.get("visuals") or []:
            if not isinstance(asset, Mapping):
                continue
            entry = _immutable_visual_registry_entry(
                asset,
                question_id=question_id,
                source_sha256=source_sha256,
            )
            if entry is None:
                continue
            asset_id = entry["id"]
            if asset_id in registry:
                duplicate_ids.add(asset_id)
                continue
            registry[asset_id] = entry
    for asset_id in duplicate_ids:
        registry.pop(asset_id, None)
    return registry


def validated_visual_asset_registry(
    extraction_audit: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Read a persisted registry fail-closed and discard malformed records."""

    raw = (
        extraction_audit.get("visualAssetRegistry")
        if isinstance(extraction_audit, Mapping)
        else None
    )
    if not isinstance(raw, Mapping):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(value, Mapping) or str(key) != str(value.get("id") or ""):
            continue
        entry = _immutable_visual_registry_entry(
            value,
            question_id=str(value.get("questionId") or ""),
            source_sha256=str(value.get("sourceSha256") or ""),
        )
        if entry is not None:
            output[str(key)] = entry
    return output


def visual_registry_entry_matches(
    entry: Mapping[str, Any],
    editable_asset: Mapping[str, Any],
    *,
    question_id: str,
) -> bool:
    """Bind an editable visual reference to its immutable server record."""

    candidate = _immutable_visual_registry_entry(
        editable_asset,
        question_id=question_id,
        source_sha256=str(entry.get("sourceSha256") or ""),
    )
    return candidate == dict(entry)


def visual_registry_storage_names(
    extraction_audit: Mapping[str, Any] | None,
) -> list[str]:
    return sorted(
        {
            entry["storagePath"]
            for entry in validated_visual_asset_registry(extraction_audit).values()
        }
    )


def visual_registry_covers_projection(
    extraction_audit: Mapping[str, Any] | None,
    projection: Mapping[str, Any],
) -> bool:
    """Ensure every durable/required Stage-3 reference has a cleanup record."""

    audit = extraction_audit if isinstance(extraction_audit, Mapping) else {}
    registry = validated_visual_asset_registry(audit)
    referenced_ids: set[str] = set()
    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    for question in questions or []:
        if not isinstance(question, Mapping):
            continue
        for asset in question.get("visuals") or []:
            if not isinstance(asset, Mapping) or not str(asset.get("storagePath") or "").strip():
                continue
            asset_id = str(asset.get("id") or "").strip()
            if not asset_id:
                return False
            referenced_ids.add(asset_id)
    contracts = audit.get("visualSourceContracts")
    if isinstance(contracts, Mapping):
        for contract in contracts.values():
            if not isinstance(contract, Mapping):
                continue
            referenced_ids.update(
                str(value).strip()
                for value in (contract.get("requiredAssetIds") or [])
                if str(value).strip()
            )
    try:
        declared_count = int(audit.get("visualAssetsAttached") or 0)
    except (TypeError, ValueError):
        return False
    return (
        referenced_ids.issubset(registry)
        and declared_count <= len(registry)
    )


def _decorative_candidate(seed: VisualSeed, repeated: int) -> bool:
    """Suppress only repeated margin/template graphics, never repeated body data."""

    x0, y0, x1, y1 = seed.bbox
    margin = y1 <= 0.17 or y0 >= 0.86 or x1 <= 0.07 or x0 >= 0.93
    reasonably_small = _area(seed.bbox) <= 0.045
    return repeated >= 3 and margin and reasonably_small


def _safe_option_markers(
    blocks: Sequence[_p.LayoutBlock],
    region_box: BBox,
) -> list[tuple[str, BBox]]:
    """Return only explicit standalone option labels adjacent to OCR visuals."""

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


_option_markers = _safe_option_markers


def _auxiliary_completeness_issues(
    *,
    region: Mapping[str, Any],
    seeds: Sequence[VisualSeed],
    blocks: Sequence[_p.LayoutBlock],
    plans: Sequence[VisualPlan],
    config: VisualPipelineConfig,
) -> list[str]:
    """Reject a crop set that leaves nearby visual annotations behind."""

    if not plans or not seeds:
        return []
    region_box = _bbox(region.get("bbox"))
    seed_box = _union(seed.bbox for seed in seeds)
    if region_box is None or seed_box is None:
        return []
    heading = region.get("headingProviderIndex")
    heading_index = int(heading) if isinstance(heading, int) else None
    audit_gap = min(
        0.065,
        max(config.auxiliary_gap, config.auxiliary_gap * 1.7),
    )
    for block in blocks:
        if heading_index is not None and block.provider_index == heading_index:
            continue
        if not _is_auxiliary(
            block,
            seed_box,
            region_box,
            heading_index,
            audit_gap,
        ):
            continue
        if any(
            _coverage(block.bbox, plan.bbox) >= 0.90
            for plan in plans
        ):
            continue
        return ["visual_residual_graphics"]
    return []


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
        plans, issues = _p._plans_for_region(
            page_number=page_number,
            region=region,
            seeds=seeds,
            blocks=blocks,
            config=config,
        )
        issues.extend(
            _auxiliary_completeness_issues(
                region=region,
                seeds=seeds,
                blocks=blocks,
                plans=plans,
                config=config,
            )
        )
        return plans, list(dict.fromkeys(issues))

    region_box = _bbox(region.get("bbox"))
    question_number = _number(region.get("questionNumber")) or 0
    if region_box is None or question_number < 1:
        return [], ["visual_option_binding_unresolved"]
    clusters = _cluster_seeds(seeds, gap=config.cluster_gap)
    markers = _safe_option_markers(blocks, region_box)
    if (
        len(clusters) != 4
        or {label for label, _box in markers}
        != {"1", "2", "3", "4"}
    ):
        return [], ["visual_option_binding_unresolved"]

    pairs: list[tuple[float, str, int]] = []
    for label, marker_box in markers:
        mx, my = _center(marker_box)
        for index, cluster in enumerate(clusters):
            cluster_box = _union(
                seed.bbox for seed in cluster
            ) or cluster[0].bbox
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
    if (
        set(assignments.values()) != {"1", "2", "3", "4"}
        or len(assignments) != 4
    ):
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
                review_only=bool(
                    set(sanity).intersection(
                        VISUAL_CRITICAL_ISSUE_CODES
                    )
                ),
            )
        )
    issues.extend(
        _auxiliary_completeness_issues(
            region=region,
            seeds=seeds,
            blocks=blocks,
            plans=plans,
            config=config,
        )
    )
    return plans, list(dict.fromkeys(issues))


def _asset_name(
    *,
    source_sha256: str,
    plan: VisualPlan,
    order: int,
    payload_sha256: str,
    storage_namespace: str = "",
) -> str:
    namespace = validate_storage_namespace(storage_namespace)
    storage_root = (
        f"{MISTRAL_VISUAL_STORAGE_PREFIX}/{namespace}/{source_sha256}"
        if namespace
        else f"{MISTRAL_VISUAL_STORAGE_PREFIX}/{source_sha256}"
    )
    option = f"-option-{plan.option_label}" if plan.option_label else ""
    return (
        f"{storage_root}/"
        f"p{plan.page_number:03d}-q{plan.question_number:03d}-{plan.role}"
        f"{option}-{order:02d}-{payload_sha256[:16]}.png"
    )


def _asset_id(
    *,
    source_sha256: str,
    plan: VisualPlan,
    order: int,
    payload_sha256: str,
) -> str:
    option = f"-o{plan.option_label}" if plan.option_label else ""
    return (
        f"inline-mistral-v1-{source_sha256[:10]}-p{plan.page_number}"
        f"-q{plan.question_number}-{plan.role}{option}-{order}-{payload_sha256[:8]}"
    )


def _asset_from_payload(
    *,
    plan: VisualPlan,
    order: int,
    payload: bytes,
    source_sha256: str,
    store: VisualAssetStore,
    storage_namespace: str = "",
) -> dict[str, Any]:
    digest = hashlib.sha256(payload).hexdigest()
    stored_name = store.save(
        _asset_name(
            source_sha256=source_sha256,
            plan=plan,
            order=order,
            payload_sha256=digest,
            storage_namespace=storage_namespace,
        ),
        payload,
    )
    return {
        "id": _asset_id(
            source_sha256=source_sha256,
            plan=plan,
            order=order,
            payload_sha256=digest,
        ),
        "role": plan.role,
        "optionLabel": plan.option_label,
        "altText": _asset_alt(plan),
        "selectedVariant": "source",
        "sourcePage": plan.page_number,
        "sourceBBox": {
            "x0": plan.bbox[0],
            "y0": plan.bbox[1],
            "x1": plan.bbox[2],
            "y1": plan.bbox[3],
        },
        "storagePath": stored_name,
        "contentType": "image/png",
        "byteSize": len(payload),
        "sha256": digest,
        "visualMode": plan.mode,
        "groupedOptionLabels": list(plan.grouped_option_labels),
        "sourceKinds": list(plan.source_kinds),
        "componentIds": list(plan.component_ids),
        "reviewOnly": plan.review_only,
        "sanity": {
            "status": "needs_review" if plan.sanity_issues else "passed",
            "issues": list(plan.sanity_issues),
        },
    }


def _source_contract(assets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ids = sorted(
        {
            str(asset.get("id") or "")
            for asset in assets
            if str(asset.get("id") or "")
        }
    )
    role_counts = {
        role: sum(str(asset.get("role") or "") == role for asset in assets)
        for role in ("question", "option", "solution")
    }
    option_labels = sorted(
        {
            str(asset.get("optionLabel") or "")
            for asset in assets
            if str(asset.get("role") or "") == "option"
            and str(asset.get("optionLabel") or "") in {"1", "2", "3", "4"}
        }
    )
    grouped_labels = sorted(
        {
            str(label)
            for asset in assets
            if str(asset.get("visualMode") or "") == "grouped_options"
            for label in (asset.get("groupedOptionLabels") or [])
            if str(label) in {"1", "2", "3", "4"}
        }
    )
    source_pages = sorted(
        {
            int(asset.get("sourcePage") or 0)
            for asset in assets
            if int(asset.get("sourcePage") or 0) > 0
        }
    )
    payload = {
        "schemaVersion": 1,
        "requiredAssetIds": ids,
        "roleCounts": role_counts,
        "optionLabels": option_labels,
        "groupedOptionLabels": grouped_labels,
        "sourcePages": source_pages,
    }
    canonical = repr(
        (
            tuple(ids),
            tuple(sorted(role_counts.items())),
            tuple(option_labels),
            tuple(grouped_labels),
            tuple(source_pages),
        )
    ).encode("utf-8")
    payload["fingerprint"] = hashlib.sha256(canonical).hexdigest()
    return payload


def _rebuild_projection_quality(
    result: Any,
    *,
    assets_by_question: Mapping[int, Sequence[dict[str, Any]]],
    issues_by_question: Mapping[int, Sequence[str]],
):
    """Rebuild canonical quality and persist the immutable source-visual contract."""

    updated = _p._rebuild_projection_quality(
        result,
        assets_by_question=assets_by_question,
        issues_by_question=issues_by_question,
    )
    projection = dict(updated.projection)
    exam = dict(projection.get("exam_prep") or {})
    questions: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, dict):
            continue
        question = dict(raw)
        number = _number(question.get("source_question_number")) or 0
        assets = [
            asset
            for asset in assets_by_question.get(number, ())
            if isinstance(asset, Mapping)
        ]
        if assets:
            question["visualSourceContract"] = _source_contract(assets)
        questions.append(question)
    exam["questions"] = questions
    projection["exam_prep"] = exam
    return updated.model_copy(update={"projection": projection})


def _augment_unresolved_audit(
    updated: Any,
    stats: dict[str, int],
    audit: dict[str, Any],
) -> tuple[dict[str, int], dict[str, Any]]:
    """Make unresolved-region metrics include every review-only visual asset."""

    unresolved = [
        dict(item)
        for item in (audit.get("unresolvedRegions") or [])
        if isinstance(item, Mapping)
    ]
    seen = {
        (
            int(item.get("pageNumber") or 0),
            int(item.get("questionNumber") or 0),
            str(item.get("role") or ""),
        )
        for item in unresolved
    }
    projection = getattr(updated, "projection", {})
    questions = (
        (projection.get("exam_prep") or {}).get("questions")
        if isinstance(projection, Mapping)
        else []
    )
    for question in questions or []:
        if not isinstance(question, Mapping):
            continue
        number = _number(question.get("source_question_number")) or 0
        critical = [
            str(code)
            for code in (question.get("issues") or [])
            if str(code) in VISUAL_CRITICAL_ISSUE_CODES
        ]
        for asset in question.get("visuals") or []:
            if not isinstance(asset, Mapping) or not asset.get("reviewOnly"):
                continue
            page = int(asset.get("sourcePage") or 0)
            role = str(asset.get("role") or "unknown")
            key = (page, number, role)
            if key in seen:
                continue
            sanity = asset.get("sanity")
            sanity_issues = (
                list(sanity.get("issues") or [])
                if isinstance(sanity, Mapping)
                else []
            )
            unresolved.append(
                {
                    "pageNumber": page,
                    "questionNumber": number,
                    "role": role,
                    "reason": str(
                        next(
                            (
                                code
                                for code in sanity_issues
                                if code in VISUAL_CRITICAL_ISSUE_CODES
                            ),
                            critical[0] if critical else "visual_precise_crop_unresolved",
                        )
                    ),
                }
            )
            seen.add(key)
        if critical and not any(key[1] == number for key in seen):
            pages = [
                int(value)
                for value in (question.get("source_pages") or [])
                if str(value).isdigit()
            ]
            page = pages[0] if pages else 0
            key = (page, number, "unknown")
            unresolved.append(
                {
                    "pageNumber": page,
                    "questionNumber": number,
                    "role": "unknown",
                    "reason": critical[0],
                }
            )
            seen.add(key)

    new_stats = dict(stats)
    new_stats["unresolvedRegions"] = len(unresolved)
    new_audit = dict(audit)
    new_audit["unresolvedRegions"] = unresolved
    nested_stats = dict(new_audit.get("stats") or {})
    nested_stats["unresolvedRegions"] = len(unresolved)
    new_audit["stats"] = nested_stats
    return new_stats, new_audit


def reconcile_mistral_source_visuals(*args: Any, **kwargs: Any):
    """Run the hardened visual runtime through the stable public seam."""

    from .exam_prep_mistral_visual_runtime import (
        reconcile_mistral_source_visuals as _runtime_reconcile,
    )

    updated, stats, audit = _runtime_reconcile(*args, **kwargs)
    stats, audit = _augment_unresolved_audit(
        updated,
        stats,
        audit,
    )
    return updated, stats, audit


__all__ = [
    "BBox",
    "MISTRAL_VISUAL_MAX_BYTES",
    "MISTRAL_VISUAL_STORAGE_PREFIX",
    "PrivateVisualAssetStore",
    "VISUAL_CRITICAL_ISSUE_CODES",
    "VisualAssetStore",
    "VisualPipelineConfig",
    "VisualPipelineStats",
    "VisualPlan",
    "VisualSeed",
    "build_visual_asset_registry",
    "reconcile_mistral_source_visuals",
    "validated_visual_asset_registry",
    "visual_registry_entry_matches",
    "visual_registry_covers_projection",
    "visual_registry_storage_names",
    "visual_storage_path_matches_source",
]
