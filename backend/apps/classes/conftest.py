"""Narrow compatibility fixtures for legacy focused pipeline unit tests."""
from __future__ import annotations

import pytest

from apps.classes.services import exam_prep_pipeline


_PAGE_ONLY_PIPELINE_TESTS = {
    'test_pipeline_calls_extractor_once_per_page_and_assembles',
    'test_pipeline_retries_only_the_invalid_page',
    'test_pipeline_skips_exhausted_page_and_blocks_partial_publication',
}


@pytest.fixture(autouse=True)
def _isolate_page_only_pipeline_tests(request, monkeypatch):
    """Keep old tests scoped to page extraction/assembly.

    Targeted source verification has dedicated source-crop tests. These
    pre-existing tests use fake non-image bytes and intentionally assert only
    page call order, retry, partial-result, and assembly behavior, so they
    receive a deterministic verification result rather than attempting a
    provider call.
    """

    if request.node.name not in _PAGE_ONLY_PIPELINE_TESTS:
        return

    def verified(result, **_kwargs):
        count = int(result.question_count or 0)
        return result, {
            'attempted': count,
            'verified': count,
            'repaired': 0,
            'retried': 0,
            'unresolved': 0,
            'visuals_attached': 0,
            'tables_verified': 0,
            'skipped': 0,
            'cancelled_before_call': 0,
        }

    monkeypatch.setattr(exam_prep_pipeline, 'verify_suspicious_questions', verified)
