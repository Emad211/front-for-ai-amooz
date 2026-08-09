"""Stable production boundary for the researched Mistral OCR4 Exam Prep engine.

This module is the ONLY supported production-facing import for the Mistral
research pipeline.  Research probes/benchmarks remain in the repository for
reproducibility, but production code must not import them directly.

Stage 1 intentionally does not wire this entrypoint into Celery yet.  Stage 2
will implement the live OCR/runtime coordinator behind the stable
``run_exam_prep_mistral_pipeline`` signature and only then replace the existing
simple pipeline runner.

Hard architectural rules for this boundary:
- no Exam Prep V4 dependency;
- no imports from ``management.commands``;
- no benchmark/gold/probe dependency;
- final return type is the existing ``ExamPrepPipelineResult`` so the normal
  ``ClassCreationSession -> exam_prep_json`` product contract stays unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .exam_prep_mistral_booklet_ranges import extract_booklet_ranges
from .exam_prep_mistral_layout_analysis import analyze_ocr_document
from .exam_prep_mistral_solution_headings import audit_solution_headings
from .exam_prep_pipeline import ExamPrepPipelineResult


ProgressCallback = Callable[[int, int], None]
CancelCheck = Callable[[], bool]

PRODUCTION_ENGINE = "mistral_ocr4_document"
PRODUCTION_ENTRYPOINT = (
    "apps.classes.services.exam_prep_mistral_production."
    "run_exam_prep_mistral_pipeline"
)


class MistralProductionNotReady(RuntimeError):
    """Raised while the frozen production entrypoint is not runtime-wired yet."""


@dataclass(frozen=True, slots=True)
class MistralDocumentEvidence:
    """Deterministic, source-numbered evidence derived from one OCR4 response."""

    layout: dict[str, Any]
    booklet_ranges: dict[str, Any]
    solution_headings: dict[str, Any]


def analyze_mistral_document_evidence(
    root: Mapping[str, Any],
    *,
    original_page_numbers: Sequence[int] | None = None,
) -> MistralDocumentEvidence:
    """Run only production-safe deterministic research primitives.

    ``root`` is an already-fetched OCR4 document response.  Transport, precise
    visual reconciliation, verifier escalation and final assembly are added in
    later productionization stages.  Keeping this function usable now gives us
    one explicit dependency boundary without importing any probe command.
    """

    mapping = list(original_page_numbers or []) or None
    return MistralDocumentEvidence(
        layout=analyze_ocr_document(
            root,
            original_page_numbers=mapping,
        ),
        booklet_ranges=extract_booklet_ranges(
            root,
            original_page_numbers=mapping,
        ),
        solution_headings=audit_solution_headings(
            root,
            original_page_numbers=mapping,
        ),
    )


def run_exam_prep_mistral_pipeline(
    *,
    data: bytes,
    title: str,
    model: str | None = None,
    scope_hint: str = "default",
    on_page_complete: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> ExamPrepPipelineResult:
    """Stable final runner signature for the normal Exam Prep product flow.

    Stage 1 freezes the contract but deliberately refuses execution.  This
    prevents an incomplete research coordinator from being deployed by accident.
    Stage 2 will implement the body without changing this public signature.
    """

    del data, title, model, scope_hint, on_page_complete, should_cancel
    raise MistralProductionNotReady(
        "Mistral OCR4 production runtime is frozen but not wired yet; complete "
        "productionization stage 2 before enabling this entrypoint."
    )


__all__ = [
    "MistralDocumentEvidence",
    "MistralProductionNotReady",
    "PRODUCTION_ENGINE",
    "PRODUCTION_ENTRYPOINT",
    "analyze_mistral_document_evidence",
    "run_exam_prep_mistral_pipeline",
]
