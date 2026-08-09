from __future__ import annotations

import ast
import inspect

import pytest

from apps.classes.services import exam_prep_mistral_production as production


_FORBIDDEN_IMPORT_FRAGMENTS = (
    "management.commands",
    "exam_prep_v4",
    "_benchmark",
    "_gold_",
    "_run_comparison",
    "probe_exam_prep",
)


def _imported_modules(module) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    return modules


def test_production_entrypoint_has_no_v4_probe_or_benchmark_dependency():
    imported = _imported_modules(production)
    offenders = [
        module
        for module in imported
        if any(fragment in module for fragment in _FORBIDDEN_IMPORT_FRAGMENTS)
    ]
    assert offenders == []


def test_deterministic_evidence_uses_only_frozen_runtime_primitives(monkeypatch):
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        production,
        "analyze_ocr_document",
        lambda root, original_page_numbers=None: (
            calls.append(("layout", original_page_numbers)) or {"pages": 2}
        ),
    )
    monkeypatch.setattr(
        production,
        "extract_booklet_ranges",
        lambda root, original_page_numbers=None: (
            calls.append(("ranges", original_page_numbers)) or {"rangeCount": 1}
        ),
    )
    monkeypatch.setattr(
        production,
        "audit_solution_headings",
        lambda root, original_page_numbers=None: (
            calls.append(("solutions", original_page_numbers))
            or {"acceptedHeadingCount": 10}
        ),
    )

    evidence = production.analyze_mistral_document_evidence(
        {"pages": []},
        original_page_numbers=[1, 2],
    )

    assert evidence.layout == {"pages": 2}
    assert evidence.booklet_ranges == {"rangeCount": 1}
    assert evidence.solution_headings == {"acceptedHeadingCount": 10}
    assert calls == [
        ("layout", [1, 2]),
        ("ranges", [1, 2]),
        ("solutions", [1, 2]),
    ]


def test_stage_one_entrypoint_cannot_be_accidentally_deployed():
    with pytest.raises(production.MistralProductionNotReady):
        production.run_exam_prep_mistral_pipeline(
            data=b"%PDF-stage-one",
            title="test",
        )


def test_final_entrypoint_keeps_existing_exam_prep_result_contract():
    signature = inspect.signature(production.run_exam_prep_mistral_pipeline)
    assert signature.return_annotation in {
        production.ExamPrepPipelineResult,
        "ExamPrepPipelineResult",
    }
    assert list(signature.parameters) == [
        "data",
        "title",
        "model",
        "scope_hint",
        "on_page_complete",
        "should_cancel",
    ]
