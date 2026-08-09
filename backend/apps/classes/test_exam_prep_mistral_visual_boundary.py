from __future__ import annotations

import inspect

from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_stage2_core as stage2
from apps.classes.services import exam_prep_mistral_visuals as visuals


def test_visual_stage_has_no_general_llm_or_v4_dependency():
    source = inspect.getsource(visuals)
    forbidden = (
        "generate_structured(",
        "part_from_bytes(",
        "llm_client",
        "exam_prep_v4",
        "management.commands",
    )
    assert all(value not in source for value in forbidden)


def test_stage2_core_is_not_visual_runtime():
    source = inspect.getsource(stage2.run_exam_prep_mistral_pipeline)
    assert "reconcile_mistral_source_visuals" not in source
    assert "visuals_attached" in source  # old output contract remains intact


def test_stable_production_facade_wires_stage3_once():
    source = inspect.getsource(production.run_exam_prep_mistral_pipeline)
    assert source.count("reconcile_mistral_source_visuals(") == 1
    assert "generalLlmCalls" in source
    assert "generate_structured(" not in source


def test_all_visual_sanity_failures_are_production_critical():
    assert visuals.VISUAL_CRITICAL_ISSUE_CODES
    assert visuals.VISUAL_CRITICAL_ISSUE_CODES <= production._OWN_CRITICAL_CODES


def test_visual_storage_namespace_is_private_exam_source_namespace():
    assert visuals.MISTRAL_VISUAL_STORAGE_PREFIX.startswith("exam-prep/source/")
