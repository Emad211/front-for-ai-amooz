from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any, Mapping, Sequence

_DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_REQUIRED_HEADERS = {
    "مواد امتحانی",
    "تعداد سؤال",
    "از شماره",
    "تا شماره",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _integer(value: Any) -> int | None:
    match = re.search(r"\d+", _clean(value).translate(_DIGIT_TRANS))
    return int(match.group(0)) if match else None


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        del attrs
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_clean("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def _rows(html: str) -> list[list[str]]:
    parser = _TableParser()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:
        return []
    return parser.rows


def parse_booklet_table(html: str) -> list[dict[str, Any]]:
    rows = _rows(html)
    if len(rows) < 2:
        return []
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if _REQUIRED_HEADERS.issubset({_clean(cell) for cell in row})
        ),
        None,
    )
    if header_index is None:
        return []
    header = [_clean(cell) for cell in rows[header_index]]
    positions = {name: header.index(name) for name in _REQUIRED_HEADERS}
    output: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        if len(row) <= max(positions.values()):
            continue
        subject = _clean(row[positions["مواد امتحانی"]])
        count = _integer(row[positions["تعداد سؤال"]])
        start = _integer(row[positions["از شماره"]])
        end = _integer(row[positions["تا شماره"]])
        if not subject or count is None or start is None or end is None:
            continue
        if start < 1 or end < start:
            continue
        output.append(
            {
                "subject": subject,
                "questionCount": count,
                "start": start,
                "end": end,
                "countMatchesRange": count == end - start + 1,
            }
        )
    return output


def extract_booklet_ranges(
    root: Mapping[str, Any],
    *,
    original_page_numbers: Sequence[int] | None = None,
) -> dict[str, Any]:
    raw_pages = [
        page for page in (root.get("pages") or []) if isinstance(page, Mapping)
    ]
    raw_pages.sort(key=lambda page: int(page.get("index") or 0))
    mapping = list(original_page_numbers or [])
    rows: list[dict[str, Any]] = []
    for position, page in enumerate(raw_pages):
        provider_index = int(page.get("index") or 0)
        physical_page = (
            int(mapping[position]) if position < len(mapping) else provider_index + 1
        )
        page_rows: list[dict[str, Any]] = []
        for block in page.get("blocks") or []:
            if not isinstance(block, Mapping):
                continue
            kind = str(block.get("type") or "").strip().lower()
            if kind != "table":
                continue
            page_rows.extend(parse_booklet_table(str(block.get("content") or "")))
        for item in page_rows:
            rows.append({"physicalPageNumber": physical_page, **item})

    rows.sort(key=lambda item: (int(item["start"]), int(item["end"])))
    valid = [item for item in rows if item["countMatchesRange"]]
    overlaps: list[dict[str, int]] = []
    gaps: list[dict[str, int]] = []
    for previous, current in zip(valid, valid[1:]):
        previous_end = int(previous["end"])
        current_start = int(current["start"])
        if current_start <= previous_end:
            overlaps.append(
                {"previousEnd": previous_end, "nextStart": current_start}
            )
        elif current_start > previous_end + 1:
            gaps.append(
                {"start": previous_end + 1, "end": current_start - 1}
            )

    return {
        "schemaVersion": 1,
        "contentFree": True,
        "ranges": rows,
        "rangeCount": len(rows),
        "allCountsMatchRanges": all(item["countMatchesRange"] for item in rows),
        "overlaps": overlaps,
        "gaps": gaps,
        "overallStart": min((int(item["start"]) for item in valid), default=None),
        "overallEnd": max((int(item["end"]) for item in valid), default=None),
        "declaredQuestionCount": sum(
            int(item["questionCount"]) for item in valid
        ),
    }
