"""Regression guard for the Stage-5 visual-reconcile facade contract.

Production (`exam_prep_mistral_production.run_exam_prep_mistral_pipeline`) calls the
Stage-3 facade `reconcile_mistral_source_visuals(...)` with two keyword arguments:

    storage_namespace=str(asset_namespace or ""),
    should_cancel=should_cancel,

The facade delegates through the live chain ``facade -> v3 -> v2`` (with the
full-width option policy monkeypatched onto v2). A prior half-finished Stage-5
migration added both kwargs to ``exam_prep_mistral_visual_runtime`` and to the
production caller, but NOT to v2/v3 — so the real request crashed in Celery with
``TypeError: reconcile_mistral_source_visuals() got an unexpected keyword argument
'storage_namespace'`` (session 197).

These tests are deterministic and provider-free (no live LLM):

* the production-shaped call must not raise ``TypeError`` on the two kwargs;
* ``should_cancel`` must be genuinely *invoked* (accepted-and-ignored is a bug),
  and its cancellation ``RuntimeError`` must carry the substring production
  matches on;
* every implementation in the live chain must expose both parameters;
* both asset-storage call sites must thread ``storage_namespace`` through to the
  store, so per-session assets stay isolated instead of colliding in one bucket.
"""
from __future__ import annotations

import inspect

import pytest

from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_visual_reconcile as facade
from apps.classes.services import exam_prep_mistral_visual_reconcile_v2 as v2
from apps.classes.services import exam_prep_mistral_visual_reconcile_v3 as v3
from apps.classes.services import exam_prep_mistral_visual_runtime as runtime


# The exact phrase production greps for when converting a Stage-3 abort into
# ``ExamPrepPipelineCancelled`` (exam_prep_mistral_production.py).
_CANCEL_SUBSTRING = "Cancellation requested during Stage-3"


def test_facade_accepts_production_stage5_kwargs_without_typeerror():
    """The exact production kwargs must not raise ``TypeError`` at the facade."""

    # Nonsense PDF bytes so the call fails at value validation, never at the
    # signature layer. A TypeError here is the regression we are guarding.
    with pytest.raises(ValueError):
        facade.reconcile_mistral_source_visuals(
            None,
            pdf_data=b"not-a-pdf",
            ocr_pages=[],
            layout={},
            source_sha256="deadbeef",
            storage_namespace="session-197",
            should_cancel=lambda: False,
        )


def test_should_cancel_is_actually_invoked_through_chain():
    """A truthy ``should_cancel`` must abort with production's sentinel message."""

    calls = {"count": 0}

    def cancel() -> bool:
        calls["count"] += 1
        return True

    with pytest.raises(RuntimeError) as excinfo:
        facade.reconcile_mistral_source_visuals(
            None,
            pdf_data=b"%PDF-1.4\n",  # passes the %PDF header gate
            ocr_pages=[],
            layout={},
            source_sha256="deadbeef",
            storage_namespace="session-197",
            should_cancel=cancel,
        )

    assert _CANCEL_SUBSTRING in str(excinfo.value)
    assert calls["count"] >= 1, "should_cancel was accepted but never called"


@pytest.mark.parametrize("module", [v2, v3, runtime])
def test_live_chain_signatures_expose_both_kwargs(module):
    params = inspect.signature(module.reconcile_mistral_source_visuals).parameters
    assert "storage_namespace" in params
    assert "should_cancel" in params


def test_facade_delegates_by_passthrough():
    """The facade forwards ``*args, **kwargs`` — no fixed signature to drift."""

    params = inspect.signature(facade.reconcile_mistral_source_visuals).parameters
    assert any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def test_store_calls_thread_storage_namespace():
    """Both live asset-storage sites must pass storage_namespace to the store.

    Guards the latent per-session isolation bug: without this, assets from
    different sessions land in one empty namespace and can collide.
    """

    v2_source = inspect.getsource(v2.reconcile_mistral_source_visuals)
    assert "storage_namespace=storage_namespace" in v2_source

    recover_source = inspect.getsource(v3._recover_solution_visuals)
    assert "storage_namespace=storage_namespace" in recover_source


def test_production_still_passes_both_kwargs():
    """Lock the caller side so the contract can't silently regress upstream."""

    source = inspect.getsource(production)
    assert "storage_namespace=str(asset_namespace or \"\")" in source
    assert "should_cancel=should_cancel," in source
