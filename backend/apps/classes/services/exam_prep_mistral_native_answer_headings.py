"""Deterministic answer-heading evidence from the PDF's own text layer.

Mistral OCR remains the authority for rich question/solution text and layout, but
embedded PDF text is a materially stronger source for one narrow fact when a
strict document-level contract passes: the printed question number and option
label in worked-answer headings.

The contract is deliberately fail-closed. Native labels are authoritative only
when answer-like pages contain anchored heading rows, every question number is
unique, labels are 1..4, and the resulting question-number set exactly matches
the OCR question anchors supplied by the caller. Coordinate overlay is even more
conservative: a page is rewritten only when every native answer heading on that
page has exactly one number-fragment coordinate.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import re
from typing import Any, Mapping, Sequence
import unicodedata

from pypdf import PdfReader

from .exam_prep_mistral_solution_headings import parse_solution_heading


_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
# Anchored heading observed in both independent Kanoon PDFs. Guillemets around
# the option label keep ordinary question lines/options out of this contract.
_HEADING_RE = re.compile(
    r"(?m)^\s*(?P<question>[0-9۰-۹٠-٩]{1,3})\s*[-–—]\s*"
    r".{0,48}?[»«]\s*(?P<option>[1-4۱-۴١-٤])\s*[«»]"
)
_NUMBER_FRAGMENT_RE = re.compile(
    r"^\s*(?P<question>[0-9۰-۹٠-٩]{1,3})\s*[-–—]\s*$"
)


def _integer(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or "").translate(_DIGITS))
    return int(match.group(0)) if match else None


@dataclass(frozen=True, slots=True)
class NativeAnswerHeading:
    question_number: int
    option_label: int
    physical_page_number: int
    side: str | None = None
    x: float | None = None
    y: float | None = None


@dataclass(frozen=True, slots=True)
class NativeAnswerEvidence:
    headings: tuple[NativeAnswerHeading, ...]
    answer_pages: tuple[int, ...]
    coordinate_complete_pages: tuple[int, ...]
    duplicate_question_numbers: tuple[int, ...]
    conflicting_question_numbers: tuple[int, ...]

    def trusted_for(self, expected_question_numbers: Sequence[int]) -> bool:
        expected = {int(value) for value in expected_question_numbers if int(value) > 0}
        observed = {item.question_number for item in self.headings}
        return bool(expected) and observed == expected and not self.duplicate_question_numbers and not self.conflicting_question_numbers

    def label_map(self) -> dict[int, str]:
        output: dict[int, str] = {}
        for item in self.headings:
            output[item.question_number] = str(item.option_label)
        return output

    def page_map(self) -> dict[int, int]:
        return {item.question_number: item.physical_page_number for item in self.headings}

    def safe_dict(self, *, trusted: bool) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "trusted": bool(trusted),
            "headingCount": len(self.headings),
            "answerPageCount": len(self.answer_pages),
            "answerPages": list(self.answer_pages),
            "coordinateCompletePages": list(self.coordinate_complete_pages),
            "duplicateQuestionNumbers": list(self.duplicate_question_numbers),
            "conflictingQuestionNumbers": list(self.conflicting_question_numbers),
        }


def _page_heading_pairs(text: str) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for match in _HEADING_RE.finditer(unicodedata.normalize("NFKC", str(text or ""))):
        question = _integer(match.group("question"))
        option = _integer(match.group("option"))
        if question is None or option not in {1, 2, 3, 4}:
            continue
        pairs.append((question, option))
    return pairs


def extract_native_answer_evidence(pdf_data: bytes) -> NativeAnswerEvidence:
    """Read only strict answer headings and optional coordinates from PDF text."""

    reader = PdfReader(io.BytesIO(pdf_data))
    headings: list[NativeAnswerHeading] = []
    answer_pages: list[int] = []
    coordinate_complete_pages: list[int] = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        pairs = _page_heading_pairs(text)
        distinct = {question for question, _option in pairs}
        # One isolated line can occur in normal prose/options. Require an answer
        # page to expose at least two independently numbered heading rows and no
        # repeated question number on that page.
        if len(distinct) < 2 or len(distinct) != len(pairs):
            continue
        answer_pages.append(page_number)

        coordinates: dict[int, list[tuple[float, float]]] = {
            question: [] for question in distinct
        }

        def visitor(text_value, _cm, tm, _font_dict, _font_size):
            match = _NUMBER_FRAGMENT_RE.match(str(text_value or ""))
            if not match:
                return
            question = _integer(match.group("question"))
            if question not in coordinates:
                return
            try:
                coordinates[question].append((float(tm[4]), float(tm[5])))
            except (TypeError, ValueError, IndexError):
                return

        try:
            page.extract_text(visitor_text=visitor)
        except Exception:
            pass

        coordinate_complete = all(len(coordinates[question]) == 1 for question in distinct)
        if coordinate_complete:
            coordinate_complete_pages.append(page_number)
        page_width = float(page.mediabox.width or 0)

        for question, option in pairs:
            side = None
            x = y = None
            if coordinate_complete:
                x, y = coordinates[question][0]
                if page_width > 0:
                    side = "right" if x >= page_width / 2 else "left"
            headings.append(
                NativeAnswerHeading(
                    question_number=question,
                    option_label=option,
                    physical_page_number=page_number,
                    side=side,
                    x=x,
                    y=y,
                )
            )

    by_question: dict[int, list[NativeAnswerHeading]] = {}
    for item in headings:
        by_question.setdefault(item.question_number, []).append(item)
    duplicates = sorted(
        question for question, values in by_question.items() if len(values) > 1
    )
    conflicts = sorted(
        question
        for question, values in by_question.items()
        if len({item.option_label for item in values}) > 1
    )
    return NativeAnswerEvidence(
        headings=tuple(headings),
        answer_pages=tuple(answer_pages),
        coordinate_complete_pages=tuple(coordinate_complete_pages),
        duplicate_question_numbers=tuple(duplicates),
        conflicting_question_numbers=tuple(conflicts),
    )


def overlay_native_solution_heading_blocks(
    root: Mapping[str, Any],
    *,
    pdf_data: bytes,
    evidence: NativeAnswerEvidence,
    trusted: bool,
) -> dict[str, Any]:
    """Replace OCR heading blocks only on coordinate-complete trusted pages.

    The synthetic block changes only heading number/label/position. Existing OCR
    body blocks remain untouched and are subsequently segmented by the normal
    layout analyzer. Pages with ambiguous native coordinates are left unchanged.
    """

    output = dict(root)
    raw_pages = [dict(page) for page in (root.get("pages") or []) if isinstance(page, Mapping)]
    output["pages"] = raw_pages
    if not trusted or not raw_pages:
        return output

    reader = PdfReader(io.BytesIO(pdf_data))
    complete_pages = set(evidence.coordinate_complete_pages)
    by_page: dict[int, list[NativeAnswerHeading]] = {}
    for item in evidence.headings:
        if item.physical_page_number in complete_pages:
            by_page.setdefault(item.physical_page_number, []).append(item)

    for position, page in enumerate(raw_pages):
        physical_page = int(page.get("sourcePhysicalPage") or int(page.get("index") or position) + 1)
        native = by_page.get(physical_page)
        if not native or physical_page < 1 or physical_page > len(reader.pages):
            continue
        pdf_page = reader.pages[physical_page - 1]
        page_height = float(pdf_page.mediabox.height or 0)
        if page_height <= 0 or any(item.y is None or item.side not in {"left", "right"} for item in native):
            continue

        blocks = [
            dict(block)
            for block in (page.get("blocks") or [])
            if isinstance(block, Mapping)
            and parse_solution_heading(str(block.get("content") or "")) is None
        ]
        # Fixed normalized x extents make the source column unambiguous. Vertical
        # position comes from the PDF baseline and therefore preserves ordering.
        for item in sorted(native, key=lambda value: (0 if value.side == "right" else 1, -(value.y or 0))):
            top = max(0.01, min(0.97, 1.0 - float(item.y) / page_height))
            x0, x1 = ((0.72, 0.97) if item.side == "right" else (0.22, 0.48))
            blocks.append(
                {
                    "type": "text",
                    "content": f"{item.question_number} - گزینه {item.option_label}",
                    "x0": x0,
                    "y0": max(0.01, top - 0.012),
                    "x1": x1,
                    "y1": min(0.99, top + 0.012),
                    "nativeAnswerHeading": True,
                }
            )
        page["blocks"] = blocks
        page["nativeAnswerHeadingOverlay"] = True

    return output


def authoritative_answer_labels(
    evidence: NativeAnswerEvidence,
    *,
    expected_question_numbers: Sequence[int],
) -> dict[int, str]:
    return evidence.label_map() if evidence.trusted_for(expected_question_numbers) else {}


__all__ = [
    "NativeAnswerEvidence",
    "NativeAnswerHeading",
    "authoritative_answer_labels",
    "extract_native_answer_evidence",
    "overlay_native_solution_heading_blocks",
]
