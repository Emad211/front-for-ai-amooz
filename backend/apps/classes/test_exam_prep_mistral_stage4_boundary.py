from __future__ import annotations

import inspect

from apps.classes.management.commands import plan_exam_prep_mistral_stage4 as planner
from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_region_transcriber as transcriber


def test_production_wires_targeted_stage4_not_broad_verifiers():
    source = inspect.getsource(production.run_exam_prep_mistral_pipeline)
    assert "verify_and_repair_risky_regions(" in source
    assert "verify_all_questions(" not in source
    assert "repair_suspicious_questions(" not in source
    assert "generate_structured(" not in source


def test_stage4_unresolved_is_static_production_critical_code():
    assert "stage4_verification_unresolved" in production._OWN_CRITICAL_CODES
    assert "stage4_verification_unresolved" in production.exam_prep_page_output.CRITICAL_ISSUE_CODES


def test_region_transcriber_defaults_to_requested_models():
    assert transcriber.DEFAULT_PRIMARY_MODEL == "gemini-3-flash-preview"
    assert transcriber.DEFAULT_SECONDARY_MODEL == "gpt-5.4-mini"


def test_risk_planner_contains_no_provider_transcription_call():
    source = inspect.getsource(planner.Command.handle)
    assert "transcribe_source_region" not in source
    assert "chat.completions" not in source
    assert "requests.post" not in source
    assert '"providerRequests": 0' in source
