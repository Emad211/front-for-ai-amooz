from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping


@dataclass(frozen=True, slots=True)
class GoldTarget:
    kind: Literal["question", "solution"]
    question_number: int
    stratum: str

    @property
    def token(self) -> str:
        return f"{self.kind}:{self.question_number}"

    @property
    def item_id(self) -> str:
        prefix = "q" if self.kind == "question" else "s"
        return f"{prefix}-{self.question_number:03d}"


# This gold set is intentionally source-PDF-specific. Restricting questions and
# solutions to their known physical page bands prevents numbered lists inside
# worked solutions from being misclassified as duplicate question regions.
_QUESTION_CONTENT_PAGES = frozenset(
    (*range(2, 9), *range(10, 24), *range(25, 32))
)
_SOLUTION_CONTENT_PAGES = frozenset(range(33, 56))


# Deliberately mixes ordinary and adversarial regions. A gold set made only of
# previously discovered failures would badly underestimate real document accuracy,
# while a purely random set would under-sample formulas, diagrams, RTL columns and
# Persian scientific terminology. These targets are frozen for this source PDF so
# model comparisons stay paired and reproducible.
#
# Every ordinary transcription target below is required to resolve to exactly one
# region in the base full-document analysis after source-page constraints. Targets
# whose base analysis is duplicated/missing belong in separate boundary-recovery
# evaluation rather than this transcription gold set.
_GOLD_TARGETS: tuple[GoldTarget, ...] = (
    GoldTarget("question", 1, "biology_prose"),
    GoldTarget("question", 7, "biology_prose"),
    GoldTarget("question", 18, "biology_visual"),
    GoldTarget("question", 23, "biology_prose"),
    GoldTarget("question", 33, "biology_prose"),
    GoldTarget("question", 45, "biology_boundary"),
    GoldTarget("question", 46, "physics_diagram"),
    GoldTarget("question", 52, "physics_formula"),
    GoldTarget("question", 57, "physics_formula"),
    GoldTarget("question", 65, "physics_circuit"),
    GoldTarget("question", 74, "physics_formula"),
    GoldTarget("question", 79, "chemistry_visual"),
    GoldTarget("question", 81, "chemistry_table_visual"),
    GoldTarget("question", 89, "chemistry_table_visual"),
    GoldTarget("question", 94, "chemistry_structure"),
    GoldTarget("question", 105, "chemistry_prose"),
    GoldTarget("question", 110, "chemistry_boundary"),
    GoldTarget("question", 111, "math_formula"),
    GoldTarget("question", 113, "math_formula"),
    GoldTarget("question", 116, "math_formula"),
    GoldTarget("question", 120, "math_graph_formula"),
    GoldTarget("question", 122, "math_formula"),
    GoldTarget("question", 129, "math_formula"),
    GoldTarget("question", 140, "math_boundary"),
    GoldTarget("question", 150, "geology_graph_options"),
    GoldTarget("question", 155, "geology_boundary"),
    GoldTarget("solution", 1, "solution_prose"),
    GoldTarget("solution", 12, "solution_prose"),
    GoldTarget("solution", 18, "solution_prose"),
    GoldTarget("solution", 33, "solution_prose"),
    GoldTarget("solution", 45, "solution_formula"),
    GoldTarget("solution", 46, "solution_formula"),
    GoldTarget("solution", 50, "solution_diagram_formula"),
    GoldTarget("solution", 55, "solution_formula"),
    GoldTarget("solution", 56, "solution_formula"),
    GoldTarget("solution", 57, "solution_source_font_corruption"),
    GoldTarget("solution", 65, "solution_formula"),
    GoldTarget("solution", 73, "solution_formula"),
    GoldTarget("solution", 81, "solution_formula"),
    GoldTarget("solution", 89, "solution_formula"),
    GoldTarget("solution", 93, "solution_formula"),
    GoldTarget("solution", 95, "solution_formula"),
    GoldTarget("solution", 115, "solution_math"),
    GoldTarget("solution", 116, "solution_math"),
    GoldTarget("solution", 120, "solution_math"),
    GoldTarget("solution", 133, "solution_geometry"),
    GoldTarget("solution", 140, "solution_math"),
    GoldTarget("solution", 150, "solution_visual"),
)


# These are evaluated separately because the full-page OCR missed or corrupted the
# heading itself. They test boundary recovery rather than ordinary transcription.
_BOUNDARY_RECOVERY_QUESTIONS = (4, 5, 6, 10, 15, 26, 30, 57, 74)


def gold_targets() -> tuple[GoldTarget, ...]:
    return _GOLD_TARGETS


def gold_target_tokens() -> tuple[str, ...]:
    return tuple(target.token for target in _GOLD_TARGETS)


def boundary_recovery_questions() -> tuple[int, ...]:
    return _BOUNDARY_RECOVERY_QUESTIONS


def _allowed_pages(kind: str) -> frozenset[int]:
    if kind == "question":
        return _QUESTION_CONTENT_PAGES
    if kind == "solution":
        return _SOLUTION_CONTENT_PAGES
    return frozenset()


def resolve_gold_target_regions(
    analysis: Mapping[str, Any],
    *,
    targets: Iterable[GoldTarget] | None = None,
) -> list[dict[str, Any]]:
    """Resolve frozen gold targets against source-appropriate physical pages.

    The generic fidelity resolver intentionally knows nothing about this source
    document. Here we do: question content is on pages 2-8, 10-23 and 25-31,
    while worked solutions are on pages 33-55. Applying those physical-page
    constraints prevents numbered lists in solutions from masquerading as
    duplicate question regions and keeps the gold pack deterministic.
    """

    rows = tuple(targets or _GOLD_TARGETS)
    selected: list[dict[str, Any]] = []
    pages = [page for page in (analysis.get("pages") or []) if isinstance(page, Mapping)]

    for target in rows:
        allowed_pages = _allowed_pages(target.kind)
        matches: list[tuple[int, Mapping[str, Any]]] = []
        for page in pages:
            physical_page = int(page.get("originalPageNumber") or 0)
            if physical_page not in allowed_pages:
                continue
            for region in page.get("regions") or []:
                if not isinstance(region, Mapping):
                    continue
                if str(region.get("kind") or "") != target.kind:
                    continue
                try:
                    number = int(region.get("questionNumber"))
                except (TypeError, ValueError):
                    continue
                if number == target.question_number:
                    matches.append((physical_page, region))

        if len(matches) != 1:
            raise ValueError(
                f"Gold target {target.token} resolved to {len(matches)} source-valid regions; "
                "expected exactly one."
            )

        physical_page, region = matches[0]
        bbox = region.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            raise ValueError(f"Gold target {target.item_id} has no usable bbox.")
        try:
            normalized_bbox = [float(value) for value in bbox]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Gold target {target.item_id} bbox is invalid.") from exc
        if not (
            0.0 <= normalized_bbox[0] < normalized_bbox[2] <= 1.0
            and 0.0 <= normalized_bbox[1] < normalized_bbox[3] <= 1.0
        ):
            raise ValueError(f"Gold target {target.item_id} bbox is outside the page.")

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


def validate_gold_target_spec(targets: Iterable[GoldTarget] | None = None) -> None:
    rows = tuple(targets or _GOLD_TARGETS)
    if len(rows) != 48:
        raise ValueError(f"Gold target spec must contain exactly 48 regions; got {len(rows)}.")
    keys = [(row.kind, row.question_number) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Gold target spec contains duplicate kind/question pairs.")
    question_count = sum(row.kind == "question" for row in rows)
    solution_count = sum(row.kind == "solution" for row in rows)
    if question_count != 26 or solution_count != 22:
        raise ValueError(
            "Gold target spec must contain 26 question and 22 solution regions; "
            f"got {question_count}/{solution_count}."
        )
    if any(not 1 <= row.question_number <= 155 for row in rows):
        raise ValueError("Gold target question numbers must stay within 1..155.")
    required_strata = {
        "physics_circuit",
        "chemistry_structure",
        "math_graph_formula",
        "solution_source_font_corruption",
        "solution_geometry",
        "geology_graph_options",
    }
    present = {row.stratum for row in rows}
    missing = sorted(required_strata - present)
    if missing:
        raise ValueError(f"Gold target spec is missing required adversarial strata: {missing}")
