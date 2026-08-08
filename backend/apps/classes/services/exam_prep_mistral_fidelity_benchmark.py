from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, Field


_DEFAULT_TARGET_TOKENS = (
    # Question-side: visual grouping, formulas, chemistry, tables, math and graphs.
    "question:18",
    "question:52",
    "question:57",
    "question:65",
    "question:74",
    "question:79",
    "question:81",
    "question:89",
    "question:94",
    "question:111",
    "question:113",
    "question:116",
    "question:120",
    "question:122",
    "question:129",
    "question:150",
    # Solution-side: known formula-heavy / OCR-fragile worked solutions.
    "solution:45",
    "solution:46",
    "solution:50",
    "solution:55",
    "solution:56",
    "solution:57",
    "solution:74",
    "solution:94",
    "solution:133",
    "solution:150",
)

_ALLOWED_ERROR_CATEGORIES = frozenset(
    {
        "persian_text",
        "number",
        "formula",
        "option_label",
        "omission",
        "hallucination",
        "visual_dependency",
        "table_or_diagram",
        "reading_order",
        "other",
    }
)


@dataclass(frozen=True, slots=True)
class FidelityTarget:
    kind: Literal["question", "solution"]
    question_number: int

    @property
    def item_id(self) -> str:
        prefix = "q" if self.kind == "question" else "s"
        return f"{prefix}-{self.question_number:03d}"


def default_fidelity_target_tokens() -> tuple[str, ...]:
    return _DEFAULT_TARGET_TOKENS


def parse_fidelity_targets(raw: str | None) -> tuple[FidelityTarget, ...]:
    tokens = (
        [part.strip() for part in str(raw or "").split(",") if part.strip()]
        if raw is not None
        else list(_DEFAULT_TARGET_TOKENS)
    )
    if not tokens:
        raise ValueError("At least one fidelity target is required.")

    output: list[FidelityTarget] = []
    seen: set[tuple[str, int]] = set()
    for token in tokens:
        match = re.fullmatch(r"(?P<kind>question|solution)\s*:\s*(?P<number>\d{1,3})", token)
        if not match:
            raise ValueError(
                "Fidelity targets must use question:N or solution:N tokens."
            )
        kind = match.group("kind")
        number = int(match.group("number"))
        if number < 1:
            raise ValueError("Fidelity question numbers must be positive.")
        key = (kind, number)
        if key in seen:
            continue
        seen.add(key)
        output.append(FidelityTarget(kind=kind, question_number=number))
    if len(output) > 40:
        raise ValueError("Fidelity benchmark is capped at 40 source regions per run.")
    return tuple(output)


def find_target_regions(
    analysis: Mapping[str, Any],
    targets: Sequence[FidelityTarget],
) -> list[dict[str, Any]]:
    indexed: dict[tuple[str, int], list[tuple[int, Mapping[str, Any]]]] = {}
    for page in analysis.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        physical_page = int(page.get("originalPageNumber") or 0)
        for region in page.get("regions") or []:
            if not isinstance(region, Mapping):
                continue
            kind = str(region.get("kind") or "")
            try:
                number = int(region.get("questionNumber"))
            except (TypeError, ValueError):
                continue
            indexed.setdefault((kind, number), []).append((physical_page, region))

    selected: list[dict[str, Any]] = []
    for target in targets:
        matches = indexed.get((target.kind, target.question_number), [])
        if len(matches) != 1:
            raise ValueError(
                f"Target {target.kind}:{target.question_number} resolved to "
                f"{len(matches)} regions; expected exactly one."
            )
        physical_page, region = matches[0]
        bbox = region.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            raise ValueError(f"Target {target.item_id} has no usable bbox.")
        try:
            normalized_bbox = [float(value) for value in bbox]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Target {target.item_id} bbox is invalid.") from exc
        if not (
            0.0 <= normalized_bbox[0] < normalized_bbox[2] <= 1.0
            and 0.0 <= normalized_bbox[1] < normalized_bbox[3] <= 1.0
        ):
            raise ValueError(f"Target {target.item_id} bbox is outside the page.")
        selected.append(
            {
                "itemId": target.item_id,
                "kind": target.kind,
                "questionNumber": target.question_number,
                "physicalPageNumber": physical_page,
                "bbox": normalized_bbox,
                "candidateText": str(region.get("text") or ""),
                "regionIssues": sorted(str(code) for code in (region.get("issues") or [])),
            }
        )
    return selected


def padded_pixel_box(
    normalized_bbox: Sequence[float],
    *,
    width: int,
    height: int,
    padding_ratio: float = 0.012,
) -> tuple[int, int, int, int]:
    if len(normalized_bbox) != 4 or width < 1 or height < 1:
        raise ValueError("Invalid crop inputs.")
    x0, y0, x1, y1 = (float(value) for value in normalized_bbox)
    px = max(2, round(width * max(0.0, padding_ratio)))
    py = max(2, round(height * max(0.0, padding_ratio)))
    left = max(0, int(x0 * width) - px)
    top = max(0, int(y0 * height) - py)
    right = min(width, int(x1 * width + 0.999999) + px)
    bottom = min(height, int(y1 * height + 0.999999) + py)
    if right <= left or bottom <= top:
        raise ValueError("Computed crop is empty.")
    return left, top, right, bottom


class FidelityError(BaseModel):
    category: Literal[
        "persian_text",
        "number",
        "formula",
        "option_label",
        "omission",
        "hallucination",
        "visual_dependency",
        "table_or_diagram",
        "reading_order",
        "other",
    ]
    severity: Literal["minor", "major", "critical"]
    candidate_fragment: str = Field(default="", max_length=240)
    source_reading: str = Field(default="", max_length=600)
    note: str = Field(default="", max_length=600)


class FidelityItemReview(BaseModel):
    item_id: str = Field(min_length=1, max_length=32)
    verdict: Literal["exact", "minor_error", "major_error", "unreadable"]
    candidate_usable_without_repair: bool
    source_visual_required: bool
    errors: list[FidelityError] = Field(default_factory=list, max_length=24)


class FidelityBatchReview(BaseModel):
    items: list[FidelityItemReview] = Field(default_factory=list, max_length=12)


def normalize_review_batch(
    batch: FidelityBatchReview,
    *,
    expected_item_ids: Sequence[str],
) -> list[dict[str, Any]]:
    expected = list(expected_item_ids)
    by_id: dict[str, FidelityItemReview] = {}
    for item in batch.items:
        if item.item_id in by_id:
            raise ValueError(f"Verifier duplicated item {item.item_id}.")
        by_id[item.item_id] = item
    if set(by_id) != set(expected):
        missing = sorted(set(expected) - set(by_id))
        extra = sorted(set(by_id) - set(expected))
        raise ValueError(f"Verifier item mismatch; missing={missing}, extra={extra}.")

    output: list[dict[str, Any]] = []
    for item_id in expected:
        item = by_id[item_id]
        errors = []
        for error in item.errors:
            category = str(error.category)
            if category not in _ALLOWED_ERROR_CATEGORIES:
                category = "other"
            errors.append(
                {
                    "category": category,
                    "severity": str(error.severity),
                    "candidateFragment": error.candidate_fragment,
                    "sourceReading": error.source_reading,
                    "note": error.note,
                }
            )
        output.append(
            {
                "itemId": item_id,
                "verdict": str(item.verdict),
                "candidateUsableWithoutRepair": bool(item.candidate_usable_without_repair),
                "sourceVisualRequired": bool(item.source_visual_required),
                "errors": errors,
            }
        )
    return output


def _severity_rank(value: str) -> int:
    return {"minor": 1, "major": 2, "critical": 3}.get(str(value), 0)


def summarize_verifier_consensus(
    *,
    targets: Sequence[Mapping[str, Any]],
    reviews_by_model: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    models = list(reviews_by_model)
    if len(models) < 2:
        raise ValueError("Consensus benchmark requires at least two verifier models.")
    per_model = {
        model: {str(item.get("itemId")): item for item in rows}
        for model, rows in reviews_by_model.items()
    }

    items: list[dict[str, Any]] = []
    for target in targets:
        item_id = str(target.get("itemId"))
        model_rows = [per_model[model].get(item_id) for model in models]
        if any(row is None for row in model_rows):
            raise ValueError(f"Missing verifier review for {item_id}.")

        category_sets: list[set[str]] = []
        critical_flags: list[bool] = []
        unusable_flags: list[bool] = []
        verdicts: list[str] = []
        source_visual_flags: list[bool] = []
        max_severities: list[int] = []
        for row in model_rows:
            assert row is not None
            errors = list(row.get("errors") or [])
            category_sets.append({str(error.get("category")) for error in errors})
            critical_flags.append(
                any(str(error.get("severity")) == "critical" for error in errors)
            )
            unusable_flags.append(not bool(row.get("candidateUsableWithoutRepair")))
            verdicts.append(str(row.get("verdict") or ""))
            source_visual_flags.append(bool(row.get("sourceVisualRequired")))
            max_severities.append(
                max((_severity_rank(str(error.get("severity"))) for error in errors), default=0)
            )

        consensus_categories = sorted(set.intersection(*category_sets)) if category_sets else []
        any_categories = sorted(set.union(*category_sets)) if category_sets else []
        consensus_critical = all(critical_flags)
        consensus_unusable = all(unusable_flags)
        verifier_disagreement = (
            len(set(verdicts)) > 1
            or len(set(critical_flags)) > 1
            or len(set(unusable_flags)) > 1
            or len(set(max_severities)) > 1
        )
        items.append(
            {
                "itemId": item_id,
                "kind": target.get("kind"),
                "questionNumber": target.get("questionNumber"),
                "physicalPageNumber": target.get("physicalPageNumber"),
                "consensusCritical": consensus_critical,
                "consensusUnusable": consensus_unusable,
                "consensusIssueCategories": consensus_categories,
                "anyIssueCategories": any_categories,
                "sourceVisualRequiredByAll": all(source_visual_flags),
                "verifierDisagreement": verifier_disagreement,
                "verdictsByModel": {
                    model: verdict for model, verdict in zip(models, verdicts)
                },
            }
        )

    return {
        "schemaVersion": 1,
        "contentFree": True,
        "modelCount": len(models),
        "models": models,
        "itemCount": len(items),
        "consensusCriticalCount": sum(bool(item["consensusCritical"]) for item in items),
        "consensusUnusableCount": sum(bool(item["consensusUnusable"]) for item in items),
        "verifierDisagreementCount": sum(bool(item["verifierDisagreement"]) for item in items),
        "sourceVisualRequiredByAllCount": sum(
            bool(item["sourceVisualRequiredByAll"]) for item in items
        ),
        "items": items,
    }


def chunks(values: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    if size < 1:
        raise ValueError("Chunk size must be positive.")
    for start in range(0, len(values), size):
        yield values[start : start + size]
