from __future__ import annotations

import inspect

from django.urls import resolve

from apps.classes import tasks_exam_prep
from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.views_exam_prep import ExamPrepPdfStep1View


STEP1_URL = "/api/classes/exam-prep-sessions/step-1/"


def test_standard_intake_routes_directly_to_mistral_stage5():
    match = resolve(STEP1_URL)

    assert match.func.view_class is ExamPrepPdfStep1View
    assert tasks_exam_prep.PIPELINE_ENGINE == production.PRODUCTION_ENGINE
    assert tasks_exam_prep.run_exam_prep_mistral_pipeline is (
        production.run_exam_prep_mistral_pipeline
    )


def test_standard_task_has_no_simple_page_first_runner_dependency():
    source = inspect.getsource(tasks_exam_prep)

    assert "run_exam_prep_mistral_pipeline(" in source
    assert "run_exam_prep_pdf_pipeline(" not in source
    assert "PAGE_FIRST_ENGINE" not in source


def test_root_urls_do_not_expose_runtime_switch_or_v4_intake():
    from core import urls

    source = inspect.getsource(urls)

    assert "EXAM_PREP_SIMPLE_PIPELINE_ENABLED" not in source
    assert "ExamPrepSourceAwareStep1View" not in source
    assert "api/classes/exam-prep-v4/" not in source
