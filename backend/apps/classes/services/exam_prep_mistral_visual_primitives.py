"""Deterministic visual reconciliation for the Mistral OCR4 Exam Prep engine.

The rendered PDF is authoritative. OCR image/table blocks are only candidates;
local rendered-page graphics are reconciled with them before a precise crop is
built. Repeated decoration is suppressed. Question, option, grouped-option and
solution visuals remain distinct semantic assets. Whole-page images are emitted
only as review-only fallbacks and can never make publication ready.

This module makes no general LLM call.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import io
import math
import os
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence

from PIL import Image

from .exam_prep_mistral_layout_analysis import (
    LayoutBlock,
    associate_uncovered_graphics,
    detect_uncovered_graphics,
    normalize_page_blocks,
)
from .exam_prep_page_output import is_critical_page_issue
from .exam_prep_page_records import AssemblyIssue, PageAssemblyResult
from .exam_prep_utils import clean_exam_markdown


MISTRAL_VISUAL_STORAGE_PREFIX = "exam-prep/source/visuals/v1"
_VISUAL_SIGNAL_CODES = frozenset(
    {
        "visual_reference_without_ocr_visual",
        "caption_visual_count_mismatch",
        "visual_options_grouped_in_single_block",
        "table_contains_visual_or_empty_cells",
        "uncovered_graphics_in_region",
        "multi_visual_solution_union_required",
    }
)
VISUAL_CRITICAL_ISSUE_CODES = frozenset(
    {
        "visual_precise_crop_unresolved",
        "visual_crop_clipped",
        "visual_bbox_too_small",
        "visual_bbox_too_large",
        "visual_caption_mismatch",
        "visual_missing_option_asset",
        "visual_option_binding_unresolved",
        "visual_table_border_risk",
        "visual_residual_graphics",
        "visual_crop_oversized",
        "visual_storage_failed",
    }
)
_OPTION_START_RE = re.compile(
    r"^\s*[\(\[]?\s*(?P<label>[1-4۱-۴١-٤])\s*[\)\].:：\-–—،]?",
    re.IGNORECASE,
)
_PURE_OPTION_RE = re.compile(
    r"^\s*(?:گزین[ههۀ]\s*)?[\(\[]?\s*[1-4۱-۴١-٤]\s*[\)\].:：\-–—،]?\s*$",
    re.IGNORECASE,
)
_SHORT_LABEL_RE = re.compile(
    r"^(?:[A-Da-d]|[1-9۱-۹١-٩]|[xyzXYZ]|[A-Za-z]{1,4}|"
    r"\d+(?:\.\d+)?\s*(?:cm|mm|m|s|N|V|A|Ω|Hz|kg|g|°)?)$"
)
_DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

BBox = tuple[float, float, float, float]


class VisualAssetStore(Protocol):
    def save(self, name: str, payload: bytes) -> str: ...


class PrivateVisualAssetStore:
    """Persist immutable crops through the existing private storage alias."""

    def save(self, name: str, payload: bytes) -> str:
        from django.core.files.base import ContentFile
        from django.core.files.storage import storages

        storage = storages["answer_sources"]
        if storage.exists(name):
            return name
        return str(storage.save(name, ContentFile(payload)))


@dataclass(frozen=True, slots=True)
class VisualPipelineConfig:
    detection_dpi: int = 150
    crop_dpi: int = 260
    padding: float = 0.009
    region_guard: float = 0.006
    cluster_gap: float = 0.018
    auxiliary_gap: float = 0.028
    min_final_area: float = 0.0006
    max_final_area: float = 0.48
    max_crop_dimension: int = 3200
    max_crop_bytes: int = 5 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "VisualPipelineConfig":
        def integer(name: str, default: int, low: int, high: int) -> int:
            try:
                value = int(os.getenv(name, str(default)))
            except (TypeError, ValueError):
                value = default
            return max(low, min(high, value))

        def number(name: str, default: float, low: float, high: float) -> float:
            try:
                value = float(os.getenv(name, str(default)))
            except (TypeError, ValueError):
                value = default
            return max(low, min(high, value))

        return cls(
            detection_dpi=integer("EXAM_PREP_VISUAL_DETECTION_DPI", 150, 96, 240),
            crop_dpi=integer("EXAM_PREP_VISUAL_CROP_DPI", 260, 150, 450),
            padding=number("EXAM_PREP_VISUAL_CROP_PADDING", 0.009, 0.002, 0.03),
            region_guard=number("EXAM_PREP_VISUAL_REGION_GUARD", 0.006, 0.0, 0.02),
            cluster_gap=number("EXAM_PREP_VISUAL_CLUSTER_GAP", 0.018, 0.003, 0.06),
            auxiliary_gap=number("EXAM_PREP_VISUAL_AUXILIARY_GAP", 0.028, 0.005, 0.08),
            min_final_area=number("EXAM_PREP_VISUAL_MIN_PAGE_AREA", 0.0006, 0.0001, 0.01),
            max_final_area=number("EXAM_PREP_VISUAL_MAX_PAGE_AREA", 0.48, 0.15, 0.75),
            max_crop_dimension=integer("EXAM_PREP_VISUAL_MAX_DIMENSION", 3200, 1200, 5000),
            max_crop_bytes=integer(
                "EXAM_PREP_VISUAL_MAX_BYTES",
                5 * 1024 * 1024,
                512 * 1024,
                12 * 1024 * 1024,
            ),
        )


@dataclass(frozen=True, slots=True)
class VisualSeed:
    seed_id: str
    page_number: int
    question_number: int
    region_kind: str
    source_kind: str
    bbox: BBox
    content: str = ""
    provider_index: int | None = None
    is_table: bool = False


@dataclass(frozen=True, slots=True)
class VisualPlan:
    page_number: int
    question_number: int
    role: str
    option_label: str | None
    mode: str
    bbox: BBox
    source_kinds: tuple[str, ...]
    component_ids: tuple[str, ...]
    grouped_option_labels: tuple[str, ...] = ()
    table: bool = False
    sanity_issues: tuple[str, ...] = ()
    review_only: bool = False


@dataclass(frozen=True, slots=True)
class VisualPipelineStats:
    pages_scanned: int = 0
    local_graphic_candidates: int = 0
    ocr_visual_candidates: int = 0
    decorative_suppressed: int = 0
    assets_attached: int = 0
    question_visuals: int = 0
    option_visuals: int = 0
    solution_visuals: int = 0
    grouped_visuals: int = 0
    table_visuals: int = 0
    whole_page_fallbacks: int = 0
    review_only_assets: int = 0
    sanity_failures: int = 0
    unresolved_regions: int = 0
    storage_failures: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "pagesScanned": self.pages_scanned,
            "localGraphicCandidates": self.local_graphic_candidates,
            "ocrVisualCandidates": self.ocr_visual_candidates,
            "decorativeSuppressed": self.decorative_suppressed,
            "assetsAttached": self.assets_attached,
            "questionVisuals": self.question_visuals,
            "optionVisuals": self.option_visuals,
            "solutionVisuals": self.solution_visuals,
            "groupedVisuals": self.grouped_visuals,
            "tableVisuals": self.table_visuals,
            "wholePageFallbacks": self.whole_page_fallbacks,
            "reviewOnlyAssets": self.review_only_assets,
            "sanityFailures": self.sanity_failures,
            "unresolvedRegions": self.unresolved_regions,
            "storageFailures": self.storage_failures,
        }


def _number(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or "").translate(_DIGIT_TRANS))
    if not match:
        return None
    try:
        parsed = int(match.group(0))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _bbox(value: Any) -> BBox | None:
    if isinstance(value, Mapping):
        values = [value.get("x0"), value.get("y0"), value.get("x1"), value.get("y1")]
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        values = list(value)
    else:
        return None
    try:
        x0, y0, x1, y1 = (float(item) for item in values)
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return x0, y0, x1, y1


def _area(box: BBox) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _center(box: BBox) -> tuple[float, float]:
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def _union(boxes: Iterable[BBox]) -> BBox | None:
    values = list(boxes)
    if not values:
        return None
    return (
        min(box[0] for box in values),
        min(box[1] for box in values),
        max(box[2] for box in values),
        max(box[3] for box in values),
    )


def _expand(box: BBox, amount: float) -> BBox:
    return (
        max(0.0, box[0] - amount),
        max(0.0, box[1] - amount),
        min(1.0, box[2] + amount),
        min(1.0, box[3] + amount),
    )


def _clamp(box: BBox, boundary: BBox) -> BBox:
    x0 = max(boundary[0], box[0])
    y0 = max(boundary[1], box[1])
    x1 = min(boundary[2], box[2])
    y1 = min(boundary[3], box[3])
    return boundary if x1 <= x0 or y1 <= y0 else (x0, y0, x1, y1)


def _intersection_area(left: BBox, right: BBox) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def _coverage(inner: BBox, outer: BBox) -> float:
    return _intersection_area(inner, outer) / max(_area(inner), 1e-9)


def _gap(left: BBox, right: BBox) -> float:
    dx = max(0.0, max(left[0], right[0]) - min(left[2], right[2]))
    dy = max(0.0, max(left[1], right[1]) - min(left[3], right[3]))
    return math.hypot(dx, dy)


def _within(box: BBox, boundary: BBox, *, slack: float = 0.002) -> bool:
    return (
        box[0] >= boundary[0] - slack
        and box[1] >= boundary[1] - slack
        and box[2] <= boundary[2] + slack
        and box[3] <= boundary[3] + slack
    )


def _render_page(document: Any, page_number: int, dpi: int) -> Image.Image:
    page = document[page_number - 1]
    try:
        bitmap = page.render(scale=float(dpi) / 72.0)
        try:
            return bitmap.to_pil().convert("RGB")
        finally:
            bitmap.close()
    finally:
        page.close()


def _encode_png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _crop_bytes(image: Image.Image, box: BBox, config: VisualPipelineConfig) -> bytes:
    width, height = image.size
    left = max(0, min(width - 1, int(math.floor(box[0] * width))))
    top = max(0, min(height - 1, int(math.floor(box[1] * height))))
    right = max(left + 1, min(width, int(math.ceil(box[2] * width))))
    bottom = max(top + 1, min(height, int(math.ceil(box[3] * height))))
    crop = image.crop((left, top, right, bottom)).convert("RGB")
    try:
        if max(crop.size) > config.max_crop_dimension:
            ratio = config.max_crop_dimension / max(crop.size)
            resized = crop.resize(
                (max(1, round(crop.width * ratio)), max(1, round(crop.height * ratio))),
                Image.Resampling.LANCZOS,
            )
            crop.close()
            crop = resized
        payload = _encode_png(crop)
        while len(payload) > config.max_crop_bytes and min(crop.size) > 500:
            resized = crop.resize(
                (max(500, round(crop.width * 0.86)), max(500, round(crop.height * 0.86))),
                Image.Resampling.LANCZOS,
            )
            crop.close()
            crop = resized
            payload = _encode_png(crop)
        if len(payload) > config.max_crop_bytes:
            raise ValueError("visual crop exceeds bounded byte limit")
        return payload
    finally:
        crop.close()


def _fingerprint(image: Image.Image, box: BBox) -> str:
    width, height = image.size
    left = max(0, min(width - 1, int(box[0] * width)))
    top = max(0, min(height - 1, int(box[1] * height)))
    right = max(left + 1, min(width, int(math.ceil(box[2] * width))))
    bottom = max(top + 1, min(height, int(math.ceil(box[3] * height))))
    crop = image.crop((left, top, right, bottom)).convert("L")
    try:
        thumb = crop.resize((16, 16), Image.Resampling.BILINEAR)
        try:
            quantized = bytes((int(value) // 32) * 32 for value in thumb.getdata())
        finally:
            thumb.close()
    finally:
        crop.close()
    return hashlib.sha256(quantized).hexdigest()[:20]


def _page_map(pages: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    output: dict[int, Mapping[str, Any]] = {}
    for page in pages:
        physical = _number(page.get("sourcePhysicalPage"))
        if physical is None:
            try:
                physical = int(page.get("index") or 0) + 1
            except (TypeError, ValueError):
                physical = None
        if physical:
            output[physical] = page
    return output


def _analysis_page_map(layout: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for page in layout.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        number = _number(page.get("originalPageNumber"))
        if number:
            output[number] = dict(page)
    return output


def _region_seeds(page_number: int, region: Mapping[str, Any]) -> list[VisualSeed]:
    question_number = _number(region.get("questionNumber")) or 0
    kind = str(region.get("kind") or "question")
    seeds: list[VisualSeed] = []
    for index, raw in enumerate(region.get("visuals") or []):
        if not isinstance(raw, Mapping):
            continue
        box = _bbox(raw.get("bbox"))
        visual_type = str(raw.get("type") or "")
        if box is None or visual_type not in {"image", "table"}:
            continue
        provider = raw.get("providerIndex")
        provider_index = int(provider) if isinstance(provider, int) else None
        seeds.append(
            VisualSeed(
                seed_id=f"p{page_number}:{kind}:q{question_number}:ocr:{provider_index if provider_index is not None else index}",
                page_number=page_number,
                question_number=question_number,
                region_kind=kind,
                source_kind=f"ocr_{visual_type}",
                bbox=box,
                content=str(raw.get("content") or ""),
                provider_index=provider_index,
                is_table=visual_type == "table",
            )
        )
    for index, raw in enumerate(region.get("uncoveredGraphics") or []):
        if not isinstance(raw, Mapping):
            continue
        box = _bbox(raw.get("bbox"))
        if box is None:
            continue
        seeds.append(
            VisualSeed(
                seed_id=f"p{page_number}:{kind}:q{question_number}:local:{index}",
                page_number=page_number,
                question_number=question_number,
                region_kind=kind,
                source_kind="local_graphic",
                bbox=box,
            )
        )
    return seeds


def _decorative_candidate(seed: VisualSeed, repeated: int) -> bool:
    x0, y0, x1, y1 = seed.bbox
    margin = y1 <= 0.16 or y0 >= 0.84 or x1 <= 0.08 or x0 >= 0.92
    tiny = _area(seed.bbox) <= 0.008
    return repeated >= 3 and (margin or tiny or repeated >= 5)


def _cluster_seeds(seeds: Sequence[VisualSeed], *, gap: float) -> list[list[VisualSeed]]:
    clusters: list[list[VisualSeed]] = []
    for seed in sorted(seeds, key=lambda item: (item.bbox[1], -item.bbox[0])):
        matches = []
        for cluster in clusters:
            cluster_box = _union(item.bbox for item in cluster)
            if cluster_box is not None and _gap(cluster_box, seed.bbox) <= gap:
                matches.append(cluster)
        if not matches:
            clusters.append([seed])
            continue
        target = matches[0]
        target.append(seed)
        for extra in matches[1:]:
            target.extend(extra)
            clusters.remove(extra)
    return clusters


def _option_label(value: str) -> str | None:
    match = _OPTION_START_RE.match(str(value or "").translate(_DIGIT_TRANS))
    if not match:
        return None
    label = str(match.group("label") or "").translate(_DIGIT_TRANS)
    return label if label in {"1", "2", "3", "4"} else None


def _option_markers(blocks: Sequence[LayoutBlock], region_box: BBox) -> list[tuple[str, BBox]]:
    markers: list[tuple[str, BBox]] = []
    for block in blocks:
        if not _within(block.bbox, region_box, slack=0.01):
            continue
        label = _option_label(block.content)
        if label:
            markers.append((label, block.bbox))
    return markers


def _rtl_reading_order(clusters: Sequence[list[VisualSeed]]) -> list[list[VisualSeed]]:
    pending = list(clusters)
    pending.sort(key=lambda cluster: _center(_union(seed.bbox for seed in cluster) or cluster[0].bbox)[1])
    rows: list[list[list[VisualSeed]]] = []
    centers: list[float] = []
    for cluster in pending:
        box = _union(seed.bbox for seed in cluster) or cluster[0].bbox
        cy = _center(box)[1]
        tolerance = max(0.035, min(0.09, (box[3] - box[1]) * 0.7))
        row_index = next((index for index, center in enumerate(centers) if abs(cy - center) <= tolerance), None)
        if row_index is None:
            rows.append([cluster])
            centers.append(cy)
        else:
            rows[row_index].append(cluster)
            centers[row_index] = sum(
                _center(_union(seed.bbox for seed in item) or item[0].bbox)[1]
                for item in rows[row_index]
            ) / len(rows[row_index])
    ordered: list[list[VisualSeed]] = []
    for _cy, row in sorted(zip(centers, rows), key=lambda item: item[0]):
        row.sort(
            key=lambda cluster: _center(_union(seed.bbox for seed in cluster) or cluster[0].bbox)[0],
            reverse=True,
        )
        ordered.extend(row)
    return ordered


def _bind_option_clusters(
    clusters: Sequence[list[VisualSeed]],
    *,
    blocks: Sequence[LayoutBlock],
    region_box: BBox,
) -> tuple[list[tuple[str | None, list[VisualSeed]]], list[str]]:
    markers = _option_markers(blocks, region_box)
    assignments: dict[int, str] = {}
    used: set[str] = set()
    for index, cluster in enumerate(clusters):
        box = _union(seed.bbox for seed in cluster) or cluster[0].bbox
        cx, cy = _center(box)
        candidates = []
        for label, marker_box in markers:
            if label in used:
                continue
            mx, my = _center(marker_box)
            distance = math.hypot(cx - mx, cy - my)
            if distance <= 0.17:
                candidates.append((distance, label))
        if candidates:
            label = min(candidates)[1]
            assignments[index] = label
            used.add(label)

    issues: list[str] = []
    if len(clusters) == 4:
        ordered = _rtl_reading_order(clusters)
        index_by_id = {id(cluster): index for index, cluster in enumerate(clusters)}
        remaining_labels = [label for label in ("1", "2", "3", "4") if label not in used]
        remaining_clusters = [cluster for cluster in ordered if index_by_id[id(cluster)] not in assignments]
        for label, cluster in zip(remaining_labels, remaining_clusters):
            assignments[index_by_id[id(cluster)]] = label
        if remaining_clusters:
            issues.append("visual_option_binding_inferred")
    if len(clusters) != 4 or len(assignments) != len(clusters):
        issues.append("visual_missing_option_asset")
    if any(index not in assignments for index in range(len(clusters))):
        issues.append("visual_option_binding_unresolved")
    return [
        (assignments.get(index), cluster)
        for index, cluster in enumerate(clusters)
    ], list(dict.fromkeys(issues))


def _is_auxiliary(
    block: LayoutBlock,
    seed_box: BBox,
    region_box: BBox,
    heading_index: int | None,
    gap: float,
) -> bool:
    if heading_index is not None and block.provider_index == heading_index:
        return False
    if not _within(block.bbox, _expand(region_box, 0.01), slack=0.002):
        return False
    if block.block_type in {"image", "table", "header", "footer", "signature"}:
        return False
    if _gap(seed_box, block.bbox) > gap and _intersection_area(seed_box, block.bbox) <= 0:
        return False
    text = clean_exam_markdown(block.content).strip()
    if not text:
        return False
    if block.block_type == "caption":
        return True
    if _PURE_OPTION_RE.fullmatch(text) or _SHORT_LABEL_RE.fullmatch(text):
        return True
    if block.block_type == "equation" and len(text) <= 140 and _area(block.bbox) <= 0.045:
        return True
    if len(text) <= 72 and len(text.splitlines()) <= 3 and _area(block.bbox) <= 0.035:
        if re.search(r"[0-9A-Za-z°%Ω±=<>:/]", text):
            return True
    if len(text) <= 120 and _intersection_area(_expand(seed_box, gap / 2), block.bbox) > 0:
        return True
    return False


def _smart_union_bbox(
    cluster: Sequence[VisualSeed],
    *,
    blocks: Sequence[LayoutBlock],
    region_box: BBox,
    heading_index: int | None,
    config: VisualPipelineConfig,
) -> tuple[BBox, tuple[str, ...], tuple[str, ...]]:
    boxes = [seed.bbox for seed in cluster]
    ids = [seed.seed_id for seed in cluster]
    seed_box = _union(boxes) or region_box
    for _ in range(2):
        changed = False
        current = _union(boxes) or seed_box
        for block in blocks:
            component_id = f"block:{block.provider_index}"
            if component_id in ids:
                continue
            if _is_auxiliary(block, current, region_box, heading_index, config.auxiliary_gap):
                boxes.append(block.bbox)
                ids.append(component_id)
                changed = True
        if not changed:
            break
    union_box = _union(boxes) or seed_box
    boundary = _expand(region_box, config.region_guard)
    padded = _clamp(_expand(union_box, config.padding), boundary)
    return padded, tuple(ids), tuple(sorted({seed.source_kind for seed in cluster}))


def _plan_sanity(
    *,
    box: BBox,
    region_box: BBox,
    cluster: Sequence[VisualSeed],
    config: VisualPipelineConfig,
) -> list[str]:
    issues: list[str] = []
    if _area(box) < config.min_final_area:
        issues.append("visual_bbox_too_small")
    if _area(box) > config.max_final_area:
        issues.append("visual_bbox_too_large")
    seed_union = _union(seed.bbox for seed in cluster)
    if seed_union is not None:
        close_to_region = any(abs(seed_union[i] - region_box[i]) <= 0.003 for i in range(4))
        close_to_crop = any(abs(seed_union[i] - box[i]) <= 0.002 for i in range(4))
        if close_to_region and close_to_crop:
            issues.append("visual_crop_clipped")
        if any(seed.is_table for seed in cluster) and close_to_crop:
            issues.append("visual_table_border_risk")
    return issues


def _should_group(clusters: Sequence[list[VisualSeed]], region_box: BBox, *, max_ratio: float) -> bool:
    union_box = _union(seed.bbox for cluster in clusters for seed in cluster)
    if union_box is None:
        return False
    return (
        _area(union_box) / max(_area(region_box), 1e-9) <= max_ratio
        and _area(union_box) <= 0.42
    )


def _plans_for_region(
    *,
    page_number: int,
    region: Mapping[str, Any],
    seeds: Sequence[VisualSeed],
    blocks: Sequence[LayoutBlock],
    config: VisualPipelineConfig,
) -> tuple[list[VisualPlan], list[str]]:
    region_box = _bbox(region.get("bbox"))
    question_number = _number(region.get("questionNumber")) or 0
    kind = str(region.get("kind") or "question")
    if region_box is None or question_number < 1:
        return [], ["visual_precise_crop_unresolved"] if seeds else []
    clusters = _cluster_seeds(seeds, gap=config.cluster_gap)
    if not clusters:
        return [], ["visual_precise_crop_unresolved"]
    mode = str(region.get("visualOptionMode") or "")
    heading_index = region.get("headingProviderIndex")
    heading_index = int(heading_index) if isinstance(heading_index, int) else None
    issues: list[str] = []
    specs: list[tuple[str, str | None, str, list[VisualSeed], tuple[str, ...]]] = []

    if kind == "question" and mode == "separate_candidates":
        bound, binding_issues = _bind_option_clusters(clusters, blocks=blocks, region_box=region_box)
        issues.extend(binding_issues)
        for label, cluster in bound:
            specs.append(("option", label, "separate_option", cluster, ()))
    elif kind == "question" and mode == "grouped_single_block":
        merged = [seed for cluster in clusters for seed in cluster]
        specs.append(("question", None, "grouped_options", merged, ("1", "2", "3", "4")))
    elif kind == "question":
        if len(clusters) > 1 and _should_group(clusters, region_box, max_ratio=0.52):
            merged = [seed for cluster in clusters for seed in cluster]
            specs.append(("question", None, "grouped_question", merged, ()))
        else:
            for cluster in clusters:
                specs.append(("question", None, "single_question", cluster, ()))
    else:
        if len(clusters) > 1 and _should_group(clusters, region_box, max_ratio=0.36):
            merged = [seed for cluster in clusters for seed in cluster]
            specs.append(("solution", None, "grouped_solution", merged, ()))
        else:
            for cluster in clusters:
                specs.append(("solution", None, "solution", cluster, ()))

    plans: list[VisualPlan] = []
    for role, option_label, plan_mode, cluster, grouped_labels in specs:
        box, component_ids, source_kinds = _smart_union_bbox(
            cluster,
            blocks=blocks,
            region_box=region_box,
            heading_index=heading_index,
            config=config,
        )
        sanity = _plan_sanity(box=box, region_box=region_box, cluster=cluster, config=config)
        plans.append(
            VisualPlan(
                page_number=page_number,
                question_number=question_number,
                role=role,
                option_label=option_label,
                mode=plan_mode,
                bbox=box,
                source_kinds=source_kinds,
                component_ids=component_ids,
                grouped_option_labels=grouped_labels,
                table=any(seed.is_table for seed in cluster),
                sanity_issues=tuple(sanity),
                review_only=bool(set(sanity).intersection(VISUAL_CRITICAL_ISSUE_CODES)),
            )
        )
        issues.extend(sanity)

    for seed in seeds:
        if not any(_coverage(seed.bbox, plan.bbox) >= 0.94 for plan in plans):
            issues.append("visual_residual_graphics")
            break
    for caption in region.get("captions") or []:
        if not isinstance(caption, Mapping):
            continue
        caption_box = _bbox(caption.get("bbox"))
        if caption_box is None:
            continue
        if any(_gap(caption_box, seed.bbox) <= 0.06 for seed in seeds) and not any(
            _coverage(caption_box, plan.bbox) >= 0.90 for plan in plans
        ):
            issues.append("visual_caption_mismatch")
            break
    return plans, list(dict.fromkeys(issues))


def _visual_required(region: Mapping[str, Any]) -> bool:
    return bool(
        region.get("visuals")
        or region.get("uncoveredGraphics")
        or set(str(code) for code in (region.get("issues") or [])).intersection(_VISUAL_SIGNAL_CODES)
    )


def _fallback_plan(*, page_number: int, question_number: int, kind: str) -> VisualPlan:
    return VisualPlan(
        page_number=page_number,
        question_number=question_number,
        role="solution" if kind == "solution" else "question",
        option_label=None,
        mode="whole_page_review_fallback",
        bbox=(0.0, 0.0, 1.0, 1.0),
        source_kinds=("page_review_fallback",),
        component_ids=(),
        sanity_issues=("visual_precise_crop_unresolved",),
        review_only=True,
    )


def _asset_name(
    *,
    source_sha256: str,
    plan: VisualPlan,
    order: int,
    payload_sha256: str,
) -> str:
    option = f"-option-{plan.option_label}" if plan.option_label else ""
    return (
        f"{MISTRAL_VISUAL_STORAGE_PREFIX}/{source_sha256}/"
        f"q{plan.question_number:03d}-{plan.role}{option}-{order:02d}-{payload_sha256[:16]}.png"
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
        f"inline-mistral-v1-{source_sha256[:10]}-q{plan.question_number}-{plan.role}"
        f"{option}-{order}-{payload_sha256[:8]}"
    )


def _asset_alt(plan: VisualPlan) -> str:
    if plan.role == "solution":
        return "شکل یا نمودار اصلی راه‌حل از صفحهٔ منبع"
    if plan.role == "option" and plan.option_label:
        return f"تصویر اصلی گزینه {plan.option_label} از صفحهٔ منبع"
    if plan.mode == "grouped_options":
        return "مجموعه تصاویر اصلی گزینه‌ها از صفحهٔ منبع"
    return "شکل، نمودار یا جدول اصلی سؤال از صفحهٔ منبع"


def _asset_from_payload(
    *,
    plan: VisualPlan,
    order: int,
    payload: bytes,
    source_sha256: str,
    store: VisualAssetStore,
) -> dict[str, Any]:
    digest = hashlib.sha256(payload).hexdigest()
    stored_name = store.save(
        _asset_name(
            source_sha256=source_sha256,
            plan=plan,
            order=order,
            payload_sha256=digest,
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


def _rebuild_projection_quality(
    result: PageAssemblyResult,
    *,
    assets_by_question: Mapping[int, Sequence[dict[str, Any]]],
    issues_by_question: Mapping[int, Sequence[str]],
) -> PageAssemblyResult:
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    output: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, dict):
            continue
        question = dict(raw)
        number = _number(question.get("source_question_number")) or 0
        existing = [
            dict(item)
            for item in (question.get("visuals") or [])
            if isinstance(item, Mapping)
            and not str(item.get("id") or "").startswith("inline-mistral-v1-")
        ]
        assets = [dict(item) for item in assets_by_question.get(number, ())]
        if assets or existing:
            question["visuals"] = [*existing, *assets]

        usable_question_visual = any(
            item.get("role") in {"question", "option"} and not item.get("reviewOnly")
            for item in assets
        )
        usable_solution_visual = any(
            item.get("role") == "solution" and not item.get("reviewOnly")
            for item in assets
        )
        grouped_options = any(
            item.get("visualMode") == "grouped_options" and not item.get("reviewOnly")
            for item in assets
        )
        option_labels = {
            str(item.get("optionLabel") or "")
            for item in assets
            if item.get("role") == "option" and not item.get("reviewOnly")
        }
        complete_option_visuals = grouped_options or option_labels == {"1", "2", "3", "4"}
        if complete_option_visuals:
            current = {
                str(item.get("label") or ""): dict(item)
                for item in (question.get("options") or [])
                if isinstance(item, Mapping) and str(item.get("label") or "") in {"1", "2", "3", "4"}
            }
            question["options"] = [
                {
                    "label": label,
                    "text_markdown": str(current.get(label, {}).get("text_markdown") or ""),
                }
                for label in ("1", "2", "3", "4")
            ]

        issues = [str(code) for code in (question.get("issues") or []) if str(code).strip()]
        new_issues = [str(code) for code in issues_by_question.get(number, ()) if str(code).strip()]
        if usable_question_visual:
            issues = [
                code
                for code in issues
                if code not in {
                    "visual_reference_without_ocr_visual",
                    "visual_evidence_required",
                    "uncovered_graphics_in_region",
                    "visual_options_grouped_in_single_block",
                    "visual_attachment_missing",
                }
            ]
        if complete_option_visuals:
            issues = [
                code
                for code in issues
                if code not in {
                    "mistral_question_option_parse_failed",
                    "missing_options",
                    "missing_option_text",
                    "missing_options_text",
                    "unexpected_option_count",
                    "placeholder_option_text",
                }
            ]
        if usable_solution_visual:
            issues = [code for code in issues if code != "multi_visual_solution_union_required"]
        if usable_question_visual and "visual_caption_mismatch" not in new_issues:
            issues = [code for code in issues if code != "caption_visual_count_mismatch"]
        if "visual_table_border_risk" not in new_issues and any(
            "ocr_table" in (item.get("sourceKinds") or []) and not item.get("reviewOnly")
            for item in assets
        ):
            issues = [code for code in issues if code != "table_contains_visual_or_empty_cells"]
        question["issues"] = list(dict.fromkeys([*issues, *new_issues]))
        output.append(question)

    exam["questions"] = output
    projection["exam_prep"] = exam
    assembly_issues: list[AssemblyIssue] = []
    matched_answers = 0
    for question in output:
        number = _number(question.get("source_question_number")) or 0
        scope = str(question.get("scope_key") or "default")
        pages = [int(value) for value in (question.get("source_pages") or []) if str(value).isdigit()]
        for code in question.get("issues") or []:
            assembly_issues.append(
                AssemblyIssue(
                    code=str(code),
                    scope_key=scope,
                    question_number=number,
                    source_pages=pages,
                )
            )
        if any(
            clean_exam_markdown(question.get(field) or "")
            for field in (
                "correct_option_label",
                "correct_option_text_markdown",
                "teacher_solution_markdown",
                "final_answer_markdown",
            )
        ):
            matched_answers += 1
    for scope, numbers in result.question_number_gaps.items():
        for number in numbers:
            assembly_issues.append(
                AssemblyIssue(
                    code="missing_question_number",
                    scope_key=scope,
                    question_number=number,
                    source_pages=[],
                )
            )
    publication_ready = bool(output) and not any(
        is_critical_page_issue(issue.code) or issue.code in VISUAL_CRITICAL_ISSUE_CODES
        for issue in assembly_issues
    )
    return result.model_copy(
        update={
            "projection": projection,
            "issues": assembly_issues,
            "question_count": len(output),
            "questions_needing_review": sum(bool(item.get("issues")) for item in output),
            "matched_answer_count": matched_answers,
            "publication_ready": publication_ready,
        }
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
    """Attach precise private source crops and local visual audit evidence."""

    if not pdf_data or not pdf_data.lstrip().startswith(b"%PDF"):
        raise ValueError("visual reconciliation requires authoritative PDF bytes")
    selected = config or VisualPipelineConfig.from_env()
    selected_store = store or PrivateVisualAssetStore()
    working_layout = copy.deepcopy(dict(layout))
    analysis_pages = _analysis_page_map(working_layout)
    ocr_by_page = _page_map(ocr_pages)
    relevant_pages = sorted(
        page_number
        for page_number, page in analysis_pages.items()
        if str(page.get("pageRole") or "") in {"question", "solution", "mixed"}
        and page_number in ocr_by_page
    )

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdfium2 is required for visual reconciliation") from exc

    fingerprints: dict[tuple[Any, ...], list[str]] = {}
    seed_cache: dict[tuple[int, int, str], list[VisualSeed]] = {}
    local_count = 0
    ocr_count = 0
    document = pdfium.PdfDocument(pdf_data)
    try:
        for page_number in relevant_pages:
            image = _render_page(document, page_number, selected.detection_dpi)
            try:
                raw_page = ocr_by_page[page_number]
                uncovered = detect_uncovered_graphics(
                    image_bytes=_encode_png(image),
                    page=raw_page,
                )
                local_count += len(uncovered)
                analysis_page = analysis_pages[page_number]
                associate_uncovered_graphics(analysis_page, uncovered)
                for region in analysis_page.get("regions") or []:
                    if not isinstance(region, Mapping):
                        continue
                    question_number = _number(region.get("questionNumber")) or 0
                    kind = str(region.get("kind") or "question")
                    seeds = _region_seeds(page_number, region)
                    ocr_count += sum(seed.source_kind.startswith("ocr_") for seed in seeds)
                    seed_cache[(page_number, question_number, kind)] = seeds
                    for seed in seeds:
                        x0, y0, x1, y1 = seed.bbox
                        signature = (
                            round((x0 + x1) / 2.0, 2),
                            round((y0 + y1) / 2.0, 2),
                            round(x1 - x0, 2),
                            round(y1 - y0, 2),
                            _fingerprint(image, seed.bbox),
                        )
                        fingerprints.setdefault(signature, []).append(seed.seed_id)
            finally:
                image.close()
    finally:
        document.close()

    seed_by_id = {seed.seed_id: seed for seeds in seed_cache.values() for seed in seeds}
    decorative_ids: set[str] = set()
    for seed_ids in fingerprints.values():
        repeated = len({seed_by_id[item].page_number for item in seed_ids if item in seed_by_id})
        for seed_id in seed_ids:
            seed = seed_by_id.get(seed_id)
            if seed is not None and _decorative_candidate(seed, repeated):
                decorative_ids.add(seed_id)

    plans_by_page: dict[int, list[VisualPlan]] = {}
    issues_by_question: dict[int, list[str]] = {}
    unresolved_regions: list[dict[str, Any]] = []
    for page_number in relevant_pages:
        blocks = normalize_page_blocks(ocr_by_page[page_number])
        analysis_page = analysis_pages[page_number]
        for region in analysis_page.get("regions") or []:
            if not isinstance(region, Mapping):
                continue
            question_number = _number(region.get("questionNumber")) or 0
            kind = str(region.get("kind") or "question")
            if question_number < 1:
                continue
            seeds = [
                seed
                for seed in seed_cache.get((page_number, question_number, kind), [])
                if seed.seed_id not in decorative_ids
            ]
            if not seeds and not _visual_required(region):
                continue
            if seeds:
                plans, region_issues = _plans_for_region(
                    page_number=page_number,
                    region=region,
                    seeds=seeds,
                    blocks=blocks,
                    config=selected,
                )
            else:
                plans, region_issues = [], ["visual_precise_crop_unresolved"]
            if not plans:
                plans = [
                    _fallback_plan(
                        page_number=page_number,
                        question_number=question_number,
                        kind=kind,
                    )
                ]
                unresolved_regions.append(
                    {
                        "pageNumber": page_number,
                        "questionNumber": question_number,
                        "role": kind,
                        "reason": "visual_precise_crop_unresolved",
                    }
                )
            plans_by_page.setdefault(page_number, []).extend(plans)
            issues_by_question.setdefault(question_number, []).extend(region_issues)

    assets_by_question: dict[int, list[dict[str, Any]]] = {}
    storage_failures = 0
    document = pdfium.PdfDocument(pdf_data)
    try:
        for page_number, plans in sorted(plans_by_page.items()):
            image = _render_page(document, page_number, selected.crop_dpi)
            try:
                counters: dict[tuple[int, str, str | None], int] = {}
                for plan in plans:
                    key = (plan.question_number, plan.role, plan.option_label)
                    counters[key] = counters.get(key, 0) + 1
                    order = counters[key]
                    try:
                        payload = _crop_bytes(image, plan.bbox, selected)
                    except ValueError:
                        issues_by_question.setdefault(plan.question_number, []).append("visual_crop_oversized")
                        continue
                    try:
                        asset = _asset_from_payload(
                            plan=plan,
                            order=order,
                            payload=payload,
                            source_sha256=source_sha256,
                            store=selected_store,
                        )
                    except Exception:
                        storage_failures += 1
                        issues_by_question.setdefault(plan.question_number, []).append("visual_storage_failed")
                        continue
                    assets_by_question.setdefault(plan.question_number, []).append(asset)
            finally:
                image.close()
    finally:
        document.close()

    for plans in plans_by_page.values():
        for plan in plans:
            if not any(
                asset.get("sourcePage") == plan.page_number
                and asset.get("role") == plan.role
                and asset.get("optionLabel") == plan.option_label
                and asset.get("visualMode") == plan.mode
                for asset in assets_by_question.get(plan.question_number, ())
            ):
                issues_by_question.setdefault(plan.question_number, []).append("visual_precise_crop_unresolved")

    normalized_issues = {
        number: list(dict.fromkeys(codes))
        for number, codes in issues_by_question.items()
    }
    updated = _rebuild_projection_quality(
        result,
        assets_by_question=assets_by_question,
        issues_by_question=normalized_issues,
    )
    all_assets = [asset for values in assets_by_question.values() for asset in values]
    all_codes = [code for values in normalized_issues.values() for code in values]
    stats = VisualPipelineStats(
        pages_scanned=len(relevant_pages),
        local_graphic_candidates=local_count,
        ocr_visual_candidates=ocr_count,
        decorative_suppressed=len(decorative_ids),
        assets_attached=len(all_assets),
        question_visuals=sum(asset.get("role") == "question" for asset in all_assets),
        option_visuals=sum(asset.get("role") == "option" for asset in all_assets),
        solution_visuals=sum(asset.get("role") == "solution" for asset in all_assets),
        grouped_visuals=sum(str(asset.get("visualMode") or "").startswith("grouped_") for asset in all_assets),
        table_visuals=sum("ocr_table" in (asset.get("sourceKinds") or []) for asset in all_assets),
        whole_page_fallbacks=sum(asset.get("visualMode") == "whole_page_review_fallback" for asset in all_assets),
        review_only_assets=sum(bool(asset.get("reviewOnly")) for asset in all_assets),
        sanity_failures=sum(code in VISUAL_CRITICAL_ISSUE_CODES for code in all_codes),
        unresolved_regions=len(unresolved_regions),
        storage_failures=storage_failures,
    )
    audit = {
        "schemaVersion": 1,
        "sourceSha256": source_sha256,
        "stats": stats.as_dict(),
        "unresolvedRegions": unresolved_regions,
        "criticalIssueCodes": sorted(
            {code for code in all_codes if code in VISUAL_CRITICAL_ISSUE_CODES}
        ),
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
