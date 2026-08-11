from __future__ import annotations

import inspect

from apps.classes.management.commands import plan_exam_prep_mistral_stage4 as planner
from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_stage5 as stage5


def test_production_wires_free_stage4_scoring_then_targeted_stage5():
    source = inspect.getsource(production.run_exam_prep_mistral_pipeline)
    assert "score_region_risks(" in source
    assert "finalize_stage5_regions(" in source
    assert "verify_and_repair_risky_regions(" not in source
    assert "verify_all_questions(" not in source
    assert "repair_suspicious_questions(" not in source
    assert "generate_structured(" not in source


def test_stage5_unresolved_is_static_production_critical_code():
    assert "stage5_finalization_blocked" in production._OWN_CRITICAL_CODES
    assert (
        "stage5_finalization_blocked"
        in production.exam_prep_page_output.CRITICAL_ISSUE_CODES
    )


def test_stage5_defaults_to_cheap_primary_and_requested_main_model():
    assert stage5.DEFAULT_PRIMARY_MODEL == "gpt-5.4-mini"
    assert stage5.DEFAULT_MAIN_MODEL == "gemini-3.6-flash"


def test_risk_planner_contains_no_provider_transcription_call():
    source = inspect.getsource(planner.Command.handle)
    assert "transcribe_source_region" not in source
    assert "chat.completions" not in source
    assert "requests.post" not in source
    assert '"providerRequests": 0' in source
