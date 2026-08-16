# Exam-Prep Mistral — Stage-3 facade kwarg migration fix (session 197 crash)

**Date:** 2026-08-16
**Area:** `apps/classes/services/exam_prep_mistral_visual_reconcile*.py` (Stage-3 visual reconciliation)
**Severity:** production-blocking (every PDF exam-prep run failed in Celery)

## Symptom

Live PDF exam-prep session 197 failed after ~77s in the `pipeline` Celery worker:

```
TypeError: reconcile_mistral_source_visuals() got an unexpected keyword argument 'storage_namespace'
```

## Root cause — a half-finished Stage-5 migration

The live Stage-3 delegation chain is:

```
production (Stage5)
  -> exam_prep_mistral_visual_reconcile        (facade: dedupe + policy stamp, *args/**kwargs passthrough)
    -> exam_prep_mistral_visual_reconcile_v3   (adds strong-local solution recovery)
      -> exam_prep_mistral_visual_reconcile_v2 (the real reconcile body; _plans_for_region is
                                                monkeypatched here by the full-width option policy)
        -> exam_prep_mistral_visual_runtime    (helper only: _harden_region_plans)
```

`v2` and `v3` are **not** dead "old versions" — they are on the live Stage-5 path
(the `_v*` suffix is misleading; per CLAUDE.md, the production facade's imports are
the source of truth for what's live, and `full_width_visual_option_policy` patches
`_plans_for_region` **inside v2**).

Commit `0cdf406` ("snapshot current Mistral Stage5 work") added two parameters —
`storage_namespace` and `should_cancel` — to `exam_prep_mistral_visual_runtime`
**and** made `exam_prep_mistral_production` pass both at the call site
(`production.py:431`). But those parameters were never threaded into `v2`/`v3`, the
modules actually invoked. The facade forwards `**kwargs` blindly, so the unknown
kwargs reached `v3.reconcile_mistral_source_visuals`, which rejected them.

Two bugs, one root cause:

1. **The crash** — `TypeError` on `storage_namespace` (and would be `should_cancel` next).
2. **A latent isolation bug** — even the runtime path aside, both v2 and v3's
   `_asset_from_payload(...)` calls omitted `storage_namespace`, so per-session
   visual assets would be saved into one empty namespace and could collide across
   sessions. (`should_cancel` was also silently absent, so a Stage-3 run could not
   be cancelled mid-reconciliation.)

## Fix

Thread both parameters down the live chain instead of repointing the facade to
`runtime` (repointing would drop v2's source-precise reconcile body + v3's
strong-local solution recovery + the full-width option policy that patches v2):

- **v2** `reconcile_mistral_source_visuals`: accept `storage_namespace` +
  `should_cancel`; pass `storage_namespace` into `v._asset_from_payload(...)`; add a
  cancellation checkpoint at the top and once per rendered page. Raise the sentinel
  `"Cancellation requested during Stage-3 visual reconciliation."` that production
  converts into `ExamPrepPipelineCancelled`.
- **v3** `reconcile_mistral_source_visuals`: accept both; forward both to
  `base.reconcile_mistral_source_visuals(...)` and to `_recover_solution_visuals(...)`.
- **v3** `_recover_solution_visuals`: accept both; pass `storage_namespace` into its
  own `v._asset_from_payload(...)`; add a per-page cancellation checkpoint.

`runtime` already had both parameters; no change there. The facade already forwards
`**kwargs`; no change there.

## Regression guard (zero-token, provider-free)

`apps/classes/test_exam_prep_mistral_visual_reconcile_contract.py`:

- production-shaped facade call must not raise `TypeError` on the two kwargs;
- `should_cancel` must be genuinely invoked and its `RuntimeError` must carry the
  substring production matches on;
- every live-chain impl (v2, v3, runtime) exposes both parameters;
- both asset-storage sites thread `storage_namespace` to the store;
- production still passes both kwargs (locks the caller side).

## Verification

- `python manage.py check` — 0 issues.
- New contract test — 8 passed.
- `test_exam_prep_mistral_visual_reconcile_v2/_v3`, `full_width_visual_option_policy`,
  `visual_runtime_hardening`, `cutover`, `production_core`, `production_boundary` —
  all green (no regression on the monkeypatched path).
- Live provider quality remains owner-validated in deployment (live LLM forbidden in
  dev/CI); this fix is deterministic Stage-3 wiring only.
