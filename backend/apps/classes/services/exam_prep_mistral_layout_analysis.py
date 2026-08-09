from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw

_DIGIT_TRANS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_VISUAL_TYPES = frozenset({"image", "table"})
_DECORATIVE_TYPES = frozenset({"header", "footer", "signature"})
_TEXTUAL_TYPES = frozenset(
    {"text", "title", "list", "caption", "equation", "code", "references", "aside_text"}
)
_SOLUTION_HINT_RE = re.compile(r"پاسخ\s*(?:تشریحی|نامه)|گزین(?:ه|ۀ|هٔ)", re.IGNORECASE)
_BOOKLET_HINT_RE = re.compile(r"(?:دفترچه|تعداد\s*س[ؤو]ال|زمان\s*پاسخگویی)", re.IGNORECASE)
_RANGE_RE = re.compile(
    r"(?:س[ؤو]ال(?:ات)?\s*)?(?P<start>[0-9۰-۹٠-٩]{1,3})\s*(?:تا|الی|[-–—])\s*"
    r"(?:س[ؤو]ال(?:ات)?\s*)?(?P<end>[0-9۰-۹٠-٩]{1,3})",
    re.IGNORECASE,
)
_SOLUTION_HEADING_RE = re.compile(
    r"^\s*[#«»\"'()]*\s*(?P<number>[0-9۰-۹٠-٩]{1,3})\s*"
    r"(?:[-–—]\s*)?گزین(?:ه|ۀ|هٔ)\s*[«»\"'()]*\s*(?P<option>[0-9۰-۹٠-٩]{1,2})",
    re.IGNORECASE,
)
_QUESTION_HEADING_RE = re.compile(
    r"^\s*#?\s*(?P<number>[0-9۰-۹٠-٩]{1,3})\s*[-–—]\s*(?!گزین(?:ه|ۀ|هٔ))",
    re.IGNORECASE,
)
_VISUAL_REFERENCE_RE = re.compile(
    r"(?:با\s+توجه\s+به\s+(?:شکل|نمودار|جدول)|مطابق\s+(?:شکل|نمودار|جدول)|"
    r"در\s+(?:شکل|نمودار)\s+(?:زیر|مقابل)|(?:شکل|نمودار|تصویر|جدول)\s+(?:زیر|مقابل)|"
    r"مدار\s+شکل|ساختار(?:های)?\s+(?:زیر|داده\s*شده)|طیف\s+(?:زیر|مقابل))",
    re.IGNORECASE,
)
_VISUAL_OPTION_RE = re.compile(
    r"(?:گزینه(?:‌|\s)*های\s+(?:زیر|داده\s*شده)|کدام\s+یک\s+از\s+گزینه(?:‌|\s)*های\s+زیر)",
    re.IGNORECASE,
)
_LATIN_CAPTION_RE = re.compile(r"^\s*\(?\s*([A-D])\s*\)?\s*$", re.IGNORECASE)
_OPTION_LINE_RE = re.compile(r"^\s*[\(\[]?[1-6۱-۶١-٦][\)\].:：\-–—]?")


def _digits(value: str) -> str:
    return str(value or "").translate(_DIGIT_TRANS)


def _int(value: Any) -> int | None:
    match = re.search(r"\d+", _digits(str(value or "")))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bbox(record: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    nested = record.get("bbox")
    source = nested if isinstance(nested, Mapping) else record
    if all(key in source for key in ("x", "y", "width", "height")):
        x = _number(source.get("x"))
        y = _number(source.get("y"))
        width = _number(source.get("width"))
        height = _number(source.get("height"))
        if None not in {x, y, width, height} and width > 0 and height > 0:
            return (x, y, x + width, y + height)
    aliases = (
        ("top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"),
        ("x0", "y0", "x1", "y1"),
    )
    for x0_key, y0_key, x1_key, y1_key in aliases:
        if all(key in source for key in (x0_key, y0_key, x1_key, y1_key)):
            values = [_number(source.get(key)) for key in (x0_key, y0_key, x1_key, y1_key)]
            if None not in values:
                x0, y0, x1, y1 = (float(value) for value in values)
                if x1 > x0 and y1 > y0:
                    return (x0, y0, x1, y1)
    return None


def _dimensions(page: Mapping[str, Any]) -> tuple[float | None, float | None]:
    value = page.get("dimensions")
    if not isinstance(value, Mapping):
        return None, None
    return _number(value.get("width")), _number(value.get("height"))


def _normalized_bbox(
    raw: tuple[float, float, float, float] | None,
    *,
    width: float | None,
    height: float | None,
) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    x0, y0, x1, y1 = raw
    if x1 <= 1.0 and y1 <= 1.0:
        values = (x0, y0, x1, y1)
    elif width and height:
        values = (x0 / width, y0 / height, x1 / width, y1 / height)
    else:
        return None
    x0, y0, x1, y1 = values
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(1.0, x1), min(1.0, y1)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return (x0, y0, x1, y1)


def _block_type(record: Mapping[str, Any]) -> str:
    return str(
        record.get("type") or record.get("block_type") or record.get("label") or "unknown"
    ).strip().lower()


def _content(record: Mapping[str, Any]) -> str:
    return str(
        record.get("content") or record.get("text") or record.get("markdown") or ""
    ).strip()


@dataclass(frozen=True, slots=True)
class LayoutBlock:
    provider_index: int
    block_type: str
    content: str
    bbox: tuple[float, float, float, float]
    column: str
    raw: Mapping[str, Any]


def _column_for_bbox(box: tuple[float, float, float, float]) -> str:
    x0, _y0, x1, _y1 = box
    if x1 <= 0.49:
        return "left"
    if x0 >= 0.51:
        return "right"
    center = (x0 + x1) / 2
    width = x1 - x0
    if width <= 0.42:
        return "right" if center >= 0.5 else "left"
    return "span"


def normalize_page_blocks(page: Mapping[str, Any]) -> list[LayoutBlock]:
    width, height = _dimensions(page)
    output: list[LayoutBlock] = []
    for index, raw in enumerate(page.get("blocks") or []):
        if not isinstance(raw, Mapping):
            continue
        box = _normalized_bbox(_bbox(raw), width=width, height=height)
        if box is None:
            continue
        output.append(
            LayoutBlock(
                provider_index=index,
                block_type=_block_type(raw),
                content=_content(raw),
                bbox=box,
                column=_column_for_bbox(box),
                raw=raw,
            )
        )
    return output


def is_rtl_double_column(blocks: Sequence[LayoutBlock]) -> bool:
    content = [block for block in blocks if block.block_type not in _DECORATIVE_TYPES]
    left = [block for block in content if block.column == "left"]
    right = [block for block in content if block.column == "right"]
    spanning = [block for block in content if block.column == "span"]
    if len(left) < 4 or len(right) < 4:
        return False
    side_ratio = (len(left) + len(right)) / max(1, len(content))
    return side_ratio >= 0.78 and len(spanning) <= max(3, int(len(content) * 0.12))


def reorder_blocks(
    blocks: Sequence[LayoutBlock],
    *,
    rtl_double_column: bool,
) -> list[LayoutBlock]:
    content = [block for block in blocks if block.block_type not in _DECORATIVE_TYPES]
    if not rtl_double_column:
        return content
    right = sorted(
        (block for block in content if block.column == "right"),
        key=lambda block: (block.bbox[1], block.bbox[0]),
    )
    left = sorted(
        (block for block in content if block.column == "left"),
        key=lambda block: (block.bbox[1], block.bbox[0]),
    )
    span = sorted(
        (block for block in content if block.column == "span"),
        key=lambda block: (block.bbox[1], block.bbox[0]),
    )
    return span + right + left


def _parse_heading(block: LayoutBlock) -> dict[str, Any] | None:
    text = block.content.strip()
    solution = _SOLUTION_HEADING_RE.match(text)
    if solution:
        return {
            "kind": "solution",
            "rawNumber": _int(solution.group("number")),
            "optionLabel": _int(solution.group("option")),
            "rawText": text,
        }
    question = _QUESTION_HEADING_RE.match(text)
    if question:
        return {
            "kind": "question",
            "rawNumber": _int(question.group("number")),
            "optionLabel": None,
            "rawText": text,
        }
    return None


def _recover_sequence_number(raw_number: int | None, expected: int | None) -> tuple[int | None, bool]:
    if raw_number is None:
        return None, False
    if expected is None or raw_number == expected:
        return raw_number, False
    if 0 <= raw_number <= 9 and expected >= 10 and str(expected).endswith(str(raw_number)):
        return expected, True
    return raw_number, False


def _union_boxes(blocks: Iterable[LayoutBlock]) -> tuple[float, float, float, float] | None:
    values = list(blocks)
    if not values:
        return None
    return (
        min(block.bbox[0] for block in values),
        min(block.bbox[1] for block in values),
        max(block.bbox[2] for block in values),
        max(block.bbox[3] for block in values),
    )


def _declared_ranges(text: str) -> list[dict[str, int]]:
    ranges: list[dict[str, int]] = []
    seen: set[tuple[int, int]] = set()
    for match in _RANGE_RE.finditer(text):
        start = _int(match.group("start"))
        end = _int(match.group("end"))
        if start is None or end is None or start < 1 or end < start:
            continue
        pair = (start, end)
        if pair in seen:
            continue
        seen.add(pair)
        ranges.append({"start": start, "end": end})
    return ranges


def _page_role(
    page: Mapping[str, Any],
    blocks: Sequence[LayoutBlock],
    headings: Sequence[dict[str, Any]],
) -> str:
    header = str(page.get("header") or "")
    combined = "\n".join([header, *(block.content for block in blocks if block.content)])
    kinds = {heading["kind"] for heading in headings}
    if "solution" in kinds or _SOLUTION_HINT_RE.search(header):
        return "solution" if "question" not in kinds else "mixed"
    if "question" in kinds:
        return "question"
    if _declared_ranges(combined) or _BOOKLET_HINT_RE.search(combined):
        return "booklet_cover"
    return "other"


def _region_issue_codes(region: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    text = str(region.get("text") or "")
    visuals = list(region.get("visuals") or [])
    images = [visual for visual in visuals if visual.get("type") == "image"]
    tables = [visual for visual in visuals if visual.get("type") == "table"]
    captions = list(region.get("captions") or [])
    if (
        region.get("kind") == "question"
        and _VISUAL_REFERENCE_RE.search(text)
        and not visuals
    ):
        issues.append("visual_reference_without_ocr_visual")
    latin_captions = [
        caption
        for caption in captions
        if _LATIN_CAPTION_RE.match(str(caption.get("content") or ""))
    ]
    if latin_captions and len(latin_captions) > len(images):
        issues.append("caption_visual_count_mismatch")
    if region.get("kind") == "question":
        option_lines = [line for line in text.splitlines() if _OPTION_LINE_RE.match(line.strip())]
        if _VISUAL_OPTION_RE.search(text):
            if len(images) == 1:
                issues.append("visual_options_grouped_in_single_block")
                region["visualOptionMode"] = "grouped_single_block"
            elif len(images) >= 2 and len(option_lines) < 2:
                region["visualOptionMode"] = "separate_candidates"
                for visual in images:
                    visual["role"] = "option"
        elif len(images) >= 2:
            region["visualOptionMode"] = "question_visual_group"
    if region.get("kind") == "solution" and len(images) >= 2:
        issues.append("multi_visual_solution_union_required")
    for table in tables:
        table_content = str(table.get("content") or "")
        if "<td></td>" in table_content or "<td />" in table_content:
            issues.append("table_contains_visual_or_empty_cells")
            break
    return issues


def _table_content_by_id(page: Mapping[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in page.get("tables") or []:
        if not isinstance(item, Mapping):
            continue
        table_id = str(item.get("id") or "")
        if table_id:
            output[table_id] = str(item.get("content") or "")
    return output


def build_regions(
    page: Mapping[str, Any],
    ordered: Sequence[LayoutBlock],
    *,
    previous_numbers: Mapping[str, int | None],
    rtl_double_column: bool,
) -> tuple[list[dict[str, Any]], dict[str, int | None]]:
    table_content = _table_content_by_id(page)
    parsed: list[tuple[int, LayoutBlock, dict[str, Any]]] = []
    for order_index, block in enumerate(ordered):
        heading = _parse_heading(block)
        if heading:
            parsed.append((order_index, block, heading))

    last = dict(previous_numbers)
    regions: list[dict[str, Any]] = []
    for heading_index, (start, heading_block, heading) in enumerate(parsed):
        end = parsed[heading_index + 1][0] if heading_index + 1 < len(parsed) else len(ordered)
        body = list(ordered[start:end])
        kind = str(heading["kind"])
        expected = (last.get(kind) + 1) if isinstance(last.get(kind), int) else None
        number, recovered = _recover_sequence_number(heading.get("rawNumber"), expected)
        if number is not None:
            last[kind] = number

        content_box = _union_boxes(body)
        if rtl_double_column:
            column_x0, column_x1 = (
                (0.50, 1.0) if heading_block.column == "right" else (0.0, 0.50)
            )
            next_y = next(
                (
                    candidate_block.bbox[1]
                    for _candidate_start, candidate_block, _candidate_heading in parsed[heading_index + 1 :]
                    if candidate_block.column == heading_block.column
                ),
                0.98,
            )
        else:
            column_x0, column_x1 = (0.0, 1.0)
            next_y = (
                parsed[heading_index + 1][1].bbox[1]
                if heading_index + 1 < len(parsed)
                else 0.98
            )
        region_box = (
            column_x0,
            heading_block.bbox[1],
            column_x1,
            max(heading_block.bbox[3], next_y),
        )

        visuals: list[dict[str, Any]] = []
        captions: list[dict[str, Any]] = []
        for block in body:
            if block.block_type == "caption":
                captions.append(
                    {
                        "content": block.content,
                        "bbox": list(block.bbox),
                        "providerIndex": block.provider_index,
                    }
                )
            if block.block_type not in _VISUAL_TYPES:
                continue
            content = block.content
            if block.block_type == "table":
                table_id = str(block.raw.get("table_id") or "")
                content = table_content.get(table_id, content)
            visuals.append(
                {
                    "type": block.block_type,
                    "content": content,
                    "bbox": list(block.bbox),
                    "providerIndex": block.provider_index,
                    "column": block.column,
                    "role": "solution" if kind == "solution" else "question",
                }
            )
        text = "\n".join(
            block.content
            for block in body
            if block.block_type in _TEXTUAL_TYPES and block.content
        )
        region: dict[str, Any] = {
            "kind": kind,
            "questionNumber": number,
            "rawQuestionNumber": heading.get("rawNumber"),
            "numberRecoveredFromSequence": recovered,
            "correctOptionLabel": heading.get("optionLabel"),
            "column": heading_block.column,
            "bbox": list(region_box),
            "contentBBox": list(content_box) if content_box else None,
            "headingProviderIndex": heading_block.provider_index,
            "text": text,
            "visuals": visuals,
            "captions": captions,
        }
        issues = _region_issue_codes(region)
        if expected is not None and number != expected and not recovered:
            issues.append("heading_sequence_gap")
        region["issues"] = sorted(set(issues))
        regions.append(region)
    return regions, last


def _confidence_summary(page: Mapping[str, Any]) -> dict[str, Any]:
    raw = page.get("confidence_scores")
    raw = raw if isinstance(raw, Mapping) else {}
    words = raw.get("word_confidence_scores")
    words = words if isinstance(words, list) else []
    low_words: list[dict[str, Any]] = []
    for item in words:
        if not isinstance(item, Mapping):
            continue
        score = _number(
            item.get("confidence") or item.get("score") or item.get("confidence_score")
        )
        if score is not None and score < 0.75:
            low_words.append(
                {
                    "text": str(item.get("text") or item.get("word") or "")[:80],
                    "confidence": score,
                }
            )
    return {
        "average": _number(raw.get("average_page_confidence_score")),
        "minimum": _number(raw.get("minimum_page_confidence_score")),
        "wordScoresPresent": bool(words),
        "lowWordCount": len(low_words),
        "lowWords": low_words[:30],
    }


def associate_uncovered_graphics(
    page_analysis: dict[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> None:
    for candidate in candidates:
        raw_box = candidate.get("bbox")
        if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
            continue
        try:
            cx = (float(raw_box[0]) + float(raw_box[2])) / 2
            cy = (float(raw_box[1]) + float(raw_box[3])) / 2
        except (TypeError, ValueError):
            continue
        matches: list[tuple[float, dict[str, Any]]] = []
        for region in page_analysis.get("regions") or []:
            box = region.get("bbox")
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                continue
            x0, y0, x1, y1 = (float(value) for value in box)
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                matches.append(((x1 - x0) * (y1 - y0), region))
        if not matches:
            page_analysis.setdefault("unassignedUncoveredGraphics", []).append(dict(candidate))
            continue
        _area, region = min(matches, key=lambda item: item[0])
        region.setdefault("uncoveredGraphics", []).append(dict(candidate))
        region.setdefault("issues", []).append("uncovered_graphics_in_region")
        region["issues"] = sorted(set(region["issues"]))
        page_analysis.setdefault("issues", []).append("uncovered_graphics_in_region")
        page_analysis["issues"] = sorted(set(page_analysis["issues"]))


def analyze_ocr_document(
    root: Mapping[str, Any],
    *,
    original_page_numbers: Sequence[int] | None = None,
) -> dict[str, Any]:
    raw_pages = [page for page in (root.get("pages") or []) if isinstance(page, Mapping)]
    pages = sorted(raw_pages, key=lambda page: int(page.get("index") or 0))
    mapping = list(original_page_numbers or [])
    last: dict[str, int | None] = {"question": None, "solution": None}
    output_pages: list[dict[str, Any]] = []
    all_ranges: list[dict[str, int]] = []
    previous_original: int | None = None
    for position, page in enumerate(pages):
        provider_index = int(page.get("index") or 0)
        original = mapping[position] if position < len(mapping) else provider_index + 1
        if previous_original is not None and original != previous_original + 1:
            last = {"question": None, "solution": None}
        previous_original = original
        blocks = normalize_page_blocks(page)
        double = is_rtl_double_column(blocks)
        ordered = reorder_blocks(blocks, rtl_double_column=double)
        heading_previews = [
            heading
            for block in ordered
            if (heading := _parse_heading(block)) is not None
        ]
        role = _page_role(page, blocks, heading_previews)
        regions, last = build_regions(
            page,
            ordered,
            previous_numbers=last,
            rtl_double_column=double,
        )
        combined = "\n".join(
            [str(page.get("header") or ""), str(page.get("markdown") or "")]
        )
        ranges = _declared_ranges(combined)
        all_ranges.extend(ranges)
        page_issues: list[str] = []
        if role == "solution" and double:
            provider_solution_numbers = [
                heading.get("rawNumber")
                for block in blocks
                if (heading := _parse_heading(block)) is not None
                and heading.get("kind") == "solution"
            ]
            ordered_solution_numbers = [
                region.get("questionNumber")
                for region in regions
                if region.get("kind") == "solution"
            ]
            if (
                provider_solution_numbers
                and ordered_solution_numbers
                and provider_solution_numbers != ordered_solution_numbers
            ):
                page_issues.append("provider_reading_order_corrected_for_rtl_columns")
        confidence = _confidence_summary(page)
        if confidence.get("minimum") is not None and float(confidence["minimum"]) < 0.12:
            page_issues.append("very_low_minimum_ocr_confidence")
        page_issues.extend(code for region in regions for code in (region.get("issues") or []))
        output_pages.append(
            {
                "providerPageIndex": provider_index,
                "originalPageNumber": original,
                "pageRole": role,
                "rtlDoubleColumn": double,
                "providerBlockCount": len(blocks),
                "orderedBlockProviderIndexes": [block.provider_index for block in ordered],
                "declaredRanges": ranges,
                "confidence": confidence,
                "regions": regions,
                "issues": sorted(set(page_issues)),
            }
        )

    unique_ranges: list[dict[str, int]] = []
    seen_ranges: set[tuple[int, int]] = set()
    for item in all_ranges:
        pair = (item["start"], item["end"])
        if pair not in seen_ranges:
            unique_ranges.append(item)
            seen_ranges.add(pair)
    return {
        "schemaVersion": 1,
        "model": str(root.get("model") or ""),
        "pageCount": len(output_pages),
        "declaredQuestionRanges": unique_ranges,
        "pages": output_pages,
        "totals": {
            "questionRegions": sum(
                region.get("kind") == "question"
                for page in output_pages
                for region in page["regions"]
            ),
            "solutionRegions": sum(
                region.get("kind") == "solution"
                for page in output_pages
                for region in page["regions"]
            ),
            "rtlDoubleColumnPages": sum(bool(page["rtlDoubleColumn"]) for page in output_pages),
            "regionsNeedingLocalAttention": sum(
                bool(region.get("issues"))
                for page in output_pages
                for region in page["regions"]
            ),
        },
    }


def detect_uncovered_graphics(
    *,
    image_bytes: bytes,
    page: Mapping[str, Any],
    padding_px: int = 3,
    min_width_px: int = 18,
    min_height_px: int = 12,
    min_ink_pixels: int = 20,
) -> list[dict[str, Any]]:
    """Find meaningful rendered ink not covered by OCR blocks, with no model call."""

    width, height = _dimensions(page)
    if not width or not height:
        return []
    target_size = (max(1, round(width)), max(1, round(height)))
    with Image.open(BytesIO(image_bytes)) as source:
        gray = source.convert("L").resize(target_size, Image.Resampling.BILINEAR)
    try:
        mask = gray.point(lambda value: 0 if value < 185 else 255, mode="1").convert("L")
        draw = ImageDraw.Draw(mask)
        for raw in page.get("blocks") or []:
            if not isinstance(raw, Mapping):
                continue
            box = _bbox(raw)
            if box is None:
                continue
            x0, y0, x1, y1 = box
            if x1 <= 1 and y1 <= 1:
                x0, x1 = x0 * width, x1 * width
                y0, y1 = y0 * height, y1 * height
            left = max(0, int(x0) - padding_px)
            top = max(0, int(y0) - padding_px)
            right = min(target_size[0] - 1, int(x1) + padding_px)
            bottom = min(target_size[1] - 1, int(y1) + padding_px)
            draw.rectangle((left, top, right, bottom), fill=255)
        draw.rectangle((0, 0, target_size[0] - 1, int(target_size[1] * 0.09)), fill=255)
        pixels = mask.load()
        seen: set[tuple[int, int]] = set()
        candidates: list[dict[str, Any]] = []
        image_width, image_height = target_size
        for y in range(image_height):
            for x in range(image_width):
                if (x, y) in seen or pixels[x, y] != 0:
                    continue
                stack = [(x, y)]
                seen.add((x, y))
                minx = maxx = x
                miny = maxy = y
                ink = 0
                while stack:
                    cx, cy = stack.pop()
                    ink += 1
                    minx, maxx = min(minx, cx), max(maxx, cx)
                    miny, maxy = min(miny, cy), max(maxy, cy)
                    for nx in range(max(0, cx - 1), min(image_width, cx + 2)):
                        for ny in range(max(0, cy - 1), min(image_height, cy + 2)):
                            if (nx, ny) in seen or pixels[nx, ny] != 0:
                                continue
                            seen.add((nx, ny))
                            stack.append((nx, ny))
                component_width = maxx - minx + 1
                component_height = maxy - miny + 1
                if (
                    component_width < min_width_px
                    or component_height < min_height_px
                    or ink < min_ink_pixels
                ):
                    continue
                if (
                    component_width / max(1, component_height) > 18
                    or component_height / max(1, component_width) > 18
                ):
                    continue
                if (
                    component_width >= int(image_width * 0.80)
                    and component_height >= int(image_height * 0.60)
                ):
                    continue
                candidates.append(
                    {
                        "bbox": [
                            minx / image_width,
                            miny / image_height,
                            (maxx + 1) / image_width,
                            (maxy + 1) / image_height,
                        ],
                        "inkPixels": ink,
                        "widthPx": component_width,
                        "heightPx": component_height,
                    }
                )
        return sorted(candidates, key=lambda candidate: candidate["inkPixels"], reverse=True)[:50]
    finally:
        gray.close()
