from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any, Mapping, Sequence

_DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_STANDARD_HEADERS = {
    "مواد امتحانی",
    "تعداد سؤال",
    "از شماره",
    "تا شماره",
}
_ALT_RANGE_HEADERS = {
    "تعداد سؤال",
    "شماره سؤال",
}
_ALT_SUBJECT_HEADERS = ("نام درس", "مواد امتحانی")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _integer(value: Any) -> int | None:
    match = re.search(r"\d+", _clean(value).translate(_DIGIT_TRANS))
    return int(match.group(0)) if match else None


def _integers(value: Any) -> list[int]:
    return [
        int(item)
        for item in re.findall(r"\d+", _clean(value).translate(_DIGIT_TRANS))
    ]


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


def _is_aggregate_subject(value: str) -> bool:
    cleaned = _clean(value)
    return cleaned.startswith("جمع") or cleaned.startswith("مجموع")


def _standard_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if _STANDARD_HEADERS.issubset({_clean(cell) for cell in row})
        ),
        None,
    )
    if header_index is None:
        return []
    header = [_clean(cell) for cell in rows[header_index]]
    positions = {name: header.index(name) for name in _STANDARD_HEADERS}
    output: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        if len(row) <= max(positions.values()):
            continue
        subject = _clean(row[positions["مواد امتحانی"]])
        count = _integer(row[positions["تعداد سؤال"]])
        start = _integer(row[positions["از شماره"]])
        end = _integer(row[positions["تا شماره"]])
        if (
            not subject
            or _is_aggregate_subject(subject)
            or count is None
            or start is None
            or end is None
        ):
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


def _alternate_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    """Parse Kانون's compact ``نام درس / شماره سؤال`` booklet tables.

    The range cell is often rendered RTL as ``۲۷۰ - ۲۵۱`` even though its
    semantic interval is 251..270, so endpoints are normalized with min/max.
    Aggregate rows such as ``جمع دروس`` are intentionally ignored.
    """

    header_index: int | None = None
    subject_header: str | None = None
    for index, row in enumerate(rows):
        cells = {_clean(cell) for cell in row}
        if not _ALT_RANGE_HEADERS.issubset(cells):
            continue
        subject_header = next((name for name in _ALT_SUBJECT_HEADERS if name in cells), None)
        if subject_header is not None:
            header_index = index
            break
    if header_index is None or subject_header is None:
        return []

    header = [_clean(cell) for cell in rows[header_index]]
    subject_pos = header.index(subject_header)
    count_pos = header.index("تعداد سؤال")
    range_pos = header.index("شماره سؤال")
    maximum = max(subject_pos, count_pos, range_pos)
    output: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        if len(row) <= maximum:
            continue
        subject = _clean(row[subject_pos])
        count = _integer(row[count_pos])
        endpoints = _integers(row[range_pos])
        if (
            not subject
            or _is_aggregate_subject(subject)
            or count is None
            or len(endpoints) < 2
        ):
            continue
        start, end = min(endpoints[0], endpoints[1]), max(endpoints[0], endpoints[1])
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


def parse_booklet_table(html: str) -> list[dict[str, Any]]:
    rows = _rows(html)
    if len(rows) < 2:
        return []
    standard = _standard_rows(rows)
    if standard:
        return standard
    return _alternate_rows(rows)


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

    # Exact duplicate rows commonly appear in both the booklet cover and the
    # following metadata page. Keep one source row so overlap/gap diagnostics
    # describe real intervals rather than duplicated declarations.
    deduped: dict[tuple[int, int, int, str], dict[str, Any]] = {}
    for item in rows:
        key = (
            int(item["start"]),
            int(item["end"]),
            int(item["questionCount"]),
            str(item["subject"]),
        )
        deduped.setdefault(key, item)
    rows = sorted(
        deduped.values(),
        key=lambda item: (int(item["start"]), int(item["end"]), str(item["subject"])),
    )

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
        "schemaVersion": 2,
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
