from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


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


# Deliberately mixes ordinary and adversarial regions. A gold set made only of
# previously discovered failures would badly underestimate real document accuracy,
# while a purely random set would under-sample formulas, diagrams, RTL columns and
# Persian scientific terminology. These targets are frozen for this source PDF so
# model comparisons stay paired and reproducible.
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
    GoldTarget("solution", 8, "solution_prose"),
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
    GoldTarget("solution", 111, "solution_math"),
    GoldTarget("solution", 113, "solution_math"),
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
