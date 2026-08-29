from __future__ import annotations

import ast
import inspect

from apps.classes.services import exam_prep_mistral_ocr_transport as transport
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
    imported = [*_imported_modules(production), *_imported_modules(transport)]
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


def test_stage_two_runner_contains_no_general_llm_call_site():
    source = inspect.getsource(production.run_exam_prep_mistral_pipeline)
    assert "generate_structured(" not in source
    assert "verify_suspicious_questions(" not in source
    assert "verify_all_questions(" not in source
    assert "repair_suspicious_questions(" not in source


def test_production_uses_stage5_as_the_only_paid_region_verifier():
    source = inspect.getsource(production.run_exam_prep_mistral_pipeline)
    assert "score_region_risks(" in source
    assert "finalize_stage5_regions(" in source
    assert "verify_and_repair_risky_regions(" not in source
    assert "verify_and_repair_risky_regions_page_batched(" not in source


def test_production_applies_native_answer_overlay_only_through_its_strict_contract():
    source = inspect.getsource(production.run_exam_prep_mistral_pipeline)
    assert "native.trusted_for(question_numbers)" in source
    assert "overlay_native_solution_heading_blocks(" in source
    assert "authoritative_answer_labels=" in source


def test_production_engine_name_does_not_claim_page_first_or_source_map_v4():
    engine = production.PRODUCTION_ENGINE.lower()
    assert "page_first" not in engine
    assert "source_map" not in engine
    assert not engine.endswith("_v4")
    assert "stage5" in engine
    assert "page_first" not in inspect.getsource(
        production.run_exam_prep_mistral_pipeline
    ).lower()


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
        "on_region_complete",
        "should_cancel",
        "asset_namespace",
    ]


def test_solution_is_resolved_only_after_exact_target_binding():
    audit = {
        "regions": [
            {"kind": "solution", "questionNumber": 1, "status": "verified_source"},
            {
                "kind": "solution",
                "questionNumber": 2,
                "status": "repaired_source",
                "resolutionTargetConfirmed": False,
            },
            {
                "kind": "solution",
                "questionNumber": 3,
                "status": "verified_source_main",
                "resolutionTargetConfirmed": True,
            },
        ]
    }

    assert production._resolved_solution_numbers(audit) == {3}
