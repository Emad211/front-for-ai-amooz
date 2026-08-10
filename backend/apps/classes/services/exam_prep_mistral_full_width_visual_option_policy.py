"""Turn geometry-bound full-width option images into exact Stage-3 option assets.

The layout policy marks an option image only after proving a bottom RTL row of
exactly four images. This adapter consumes those explicit labels. It never tries
to infer labels from arbitrary graphs, ticks, captions, or image similarity.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_visual_reconcile_v2 as reconcile
from . import exam_prep_mistral_visuals as v


_ORIGINAL_PLANS_FOR_REGION = reconcile._plans_for_region


def _labeled_visuals(region: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for raw in region.get("visuals") or []:
        if not isinstance(raw, Mapping) or str(raw.get("role") or "") != "option":
            continue
        label = str(raw.get("optionLabel") or "").translate(v._p._DIGIT_TRANS).strip()
        if label not in {"1", "2", "3", "4"} or label in output:
            return {}
        if v._bbox(raw.get("bbox")) is None:
            return {}
        output[label] = raw
    return output if set(output) == {"1", "2", "3", "4"} else {}


def _seed_for_visual(
    *,
    page_number: int,
    question_number: int,
    raw: Mapping[str, Any],
    seeds: Sequence[v.VisualSeed],
) -> v.VisualSeed:
    provider = raw.get("providerIndex")
    provider_index = int(provider) if isinstance(provider, int) else None
    if provider_index is not None:
        for seed in seeds:
            if seed.provider_index == provider_index:
                return seed
    box = v._bbox(raw.get("bbox"))
    assert box is not None
    return v.VisualSeed(
        seed_id=f"p{page_number}:question:q{question_number}:bound-option:{provider_index}",
        page_number=page_number,
        question_number=question_number,
        region_kind="question",
        source_kind="ocr_image",
        bbox=box,
        content=str(raw.get("content") or ""),
        provider_index=provider_index,
    )


def production_plans_for_region(
    *,
    page_number: int,
    region: Mapping[str, Any],
    seeds: Sequence[v.VisualSeed],
    blocks,
    config,
):
    labeled = _labeled_visuals(region)
    if not labeled:
        return _ORIGINAL_PLANS_FOR_REGION(
            page_number=page_number,
            region=region,
            seeds=seeds,
            blocks=blocks,
            config=config,
        )

    region_box = v._bbox(region.get("bbox"))
    question_number = v._number(region.get("questionNumber")) or 0
    if region_box is None or question_number < 1:
        return [], ["visual_option_binding_unresolved"]

    plans: list[v.VisualPlan] = []
    issues: list[str] = []
    for label in ("1", "2", "3", "4"):
        raw = labeled[label]
        seed = _seed_for_visual(
            page_number=page_number,
            question_number=question_number,
            raw=raw,
            seeds=seeds,
        )
        crop = v._clamp(
            v._expand(seed.bbox, max(0.006, float(config.padding))),
            v._expand(region_box, float(config.region_guard)),
        )
        sanity = v._plan_sanity(
            box=crop,
            region_box=region_box,
            cluster=[seed],
            config=config,
        )
        issues.extend(sanity)
        plans.append(
            v.VisualPlan(
                page_number=page_number,
                question_number=question_number,
                role="option",
                option_label=label,
                mode="full_width_exact_option",
                bbox=crop,
                source_kinds=(seed.source_kind,),
                component_ids=(seed.seed_id,),
                sanity_issues=tuple(sanity),
                review_only=bool(set(sanity) & v.VISUAL_CRITICAL_ISSUE_CODES),
            )
        )

    question_visuals = [
        raw for raw in (region.get("visuals") or [])
        if isinstance(raw, Mapping)
        and str(raw.get("role") or "") == "question"
        and str(raw.get("type") or "") == "image"
        and v._bbox(raw.get("bbox")) is not None
    ]
    if question_visuals:
        boxes = [v._bbox(raw.get("bbox")) for raw in question_visuals]
        union = v._union(box for box in boxes if box is not None)
        if union is not None:
            crop = v._clamp(
                v._expand(union, max(0.006, float(config.padding))),
                v._expand(region_box, float(config.region_guard)),
            )
            question_seeds = [
                _seed_for_visual(
                    page_number=page_number,
                    question_number=question_number,
                    raw=raw,
                    seeds=seeds,
                )
                for raw in question_visuals
            ]
            sanity = v._plan_sanity(
                box=crop,
                region_box=region_box,
                cluster=question_seeds,
                config=config,
            )
            issues.extend(sanity)
            plans.insert(
                0,
                v.VisualPlan(
                    page_number=page_number,
                    question_number=question_number,
                    role="question",
                    option_label=None,
                    mode="full_width_question_group",
                    bbox=crop,
                    source_kinds=tuple(sorted({seed.source_kind for seed in question_seeds})),
                    component_ids=tuple(seed.seed_id for seed in question_seeds),
                    sanity_issues=tuple(sanity),
                    review_only=bool(set(sanity) & v.VISUAL_CRITICAL_ISSUE_CODES),
                ),
            )

    return plans, list(dict.fromkeys(issues))


def install_full_width_visual_option_policy() -> None:
    if reconcile._plans_for_region is not production_plans_for_region:
        reconcile._plans_for_region = production_plans_for_region


__all__ = [
    "install_full_width_visual_option_policy",
    "production_plans_for_region",
]
