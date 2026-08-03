# Exam Prep V4 — Implementation Status Ledger

> Update this file before every V4 implementation slice. Canonical architecture: `exam-prep-v4-source-aware-split-pipeline.md`. Fast execution overlay: `exam-prep-v4-production-critical-path.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Production Critical Path
- **Current span:** production deployment/manual owner validation plus remaining Phase 9 hardening
- **Last completed slice:** source confirmation → extraction → status/retry/cancel → exception review → legacy projection → publication
- **Live validation owner:** manual validation by the project owner in the deployed environment
- **Development/CI live-provider calls:** forbidden for this path
- **Validated code head:** `d7b53393d77c50a53b81f0cba5e7d45367b6c6d8`
- **Validated merge ref:** `fd137cf8779eff5318cea23ca68fb7dc29f4cdb3`
- **Current documentation head before this ledger sync:** `95e67cdf053061f47bbf40f72b6908fad3affd88`
- **Focused workflow:** `30862683847`
- **Backend job:** `91847863122`
- **Frontend job:** `91847863181`
- **Result:** 261 backend tests passed; migration drift zero; frontend focused TypeScript/state validation passed
- **Structured model selection:** environment only
- **OCR model selection:** environment only; adapter remains disabled unless explicitly configured
- **Last updated:** 2026-08-04

## Production-callable flow now implemented

```text
independent PDF upload
→ private preparation/render/classification
→ teacher Source Map edit and exact confirmation
→ idempotent Celery extraction dispatch on pipeline queue
→ correlated block/question/answer stages
→ deterministic matching
→ exception-only teacher review
→ fingerprint-bound legacy student projection
→ publication through the existing Exam Prep student domain
```

Implemented production controls:

- automatic extraction dispatch after Source Map confirmation;
- one logical `runId` plus Celery `taskId` per execution;
- content-free JSON stage/batch/provider logs;
- owner-scoped status, retry and cancellation APIs;
- active-project frontend polling and runtime panel;
- bounded transient retry and explicit terminal task failure;
- cooperative cancellation before/after provider stage and batch boundaries;
- stale active-run recovery task and management command;
- immutable teacher review decisions: match, out-of-scope and ignore;
- exception-only review UI and fingerprint-bound finalization;
- backward-compatible `ClassCreationSession.exam_prep_json` projection;
- opaque projected question IDs and no V4 provenance/raw payload projection;
- idempotent publication into the existing student, invitation, scoring and result flow;
- production environment and operator validation runbook.

## Canonical progress

The established denominator remains 77 deliverables. No real-provider quality item receives credit before the owner measures it in deployment.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains open. |
| Phase 2 | 8 | 9 | Real production structural/latency/usage evidence remains owner-run. |
| Phase 3 | 4 | 7 | Explicit split/group controls and browser accessibility evidence remain open. |
| Phase 4 | 4 | 8 | Column detection, RTL reading order, dedup and real layout evidence remain open. |
| Phase 5 | 6 | 7 | Real precision/recall remains owner-run. |
| Phase 6 | 4 | 7 | Real numbered-heading, compact-key and inline-answer evidence remains open. |
| Phase 7 | 6 | 7 | Complete option/solution semantic consistency remains open. |
| Phase 8 | 5 | 6 | Review UI/decisions/projection/privacy/final binding complete; dedicated persisted issue model remains open. |
| Phase 9 | 2 | 6 | Stale recovery and audit-safe observability complete. |
| Phase 10 | 0 | 8 | Production measurements, cohort rollout and rollback remain owner-run/open. |

- **Overall:** **50/77 = 64.9%**
- **Phase 8:** **5/6 = 83.3%**
- **Phase 9:** **2/6 = 33.3%**

Additional completed reliability work—production dispatch, retry and cooperative cancellation—is required for the flow but is not counted as a new canonical denominator item.

## CI evidence

```text
validated code head: d7b53393d77c50a53b81f0cba5e7d45367b6c6d8
validated merge ref: fd137cf8779eff5318cea23ca68fb7dc29f4cdb3
workflow: 30862683847
backend job: 91847863122
frontend job: 91847863181
Django system check: passed
classes migration drift: none
backend: 261 passed, 49 warnings in 26.03s
frontend focused TypeScript: passed
source-map state tests: passed
live provider requests: 0
```

Commits after the validated code checkpoint are documentation-only roadmap/runbook synchronization. CI covers fake-provider/unit/contract behavior only. It does not claim real PDF accuracy, provider latency, token usage or cost.

## Production observability contract

Every extraction run exposes and logs:

```text
runId
taskId
projectId
documentId
sourceMapRevision
sourceMapFingerprintPrefix
attempt
stage
elapsedMs
providerCalls
issueCount
status
errorCode
```

Safe aggregate counters include page, block, fragment, question, answer-solution, match, exception and OCR call/retry/fallback counts.

Forbidden log data includes source/OCR text, question/option/solution text, images/base64, prompts, raw provider payloads, object keys and credentials.

Primary logger:

```text
apps.classes.exam_prep_v4
```

Operator runbook:

```text
docs/runbooks/exam-prep-v4-production-validation.md
```

## Deployment requirements

Apply additive migrations:

```text
0045_exam_prep_v4_review_decisions
0046_exam_prep_v4_legacy_projection
```

Ensure the worker consumes `pipeline`:

```bash
celery -A core worker \
  --loglevel=info \
  -Q default,pipeline,interactive \
  --concurrency=2 \
  --prefetch-multiplier=1 \
  --max-tasks-per-child=50
```

Set the V4 model and runtime environment values documented in `backend/.env.production.example` and keep `EXAM_PREP_V4_OCR_EVIDENCE_ENABLED=False` unless the OCR adapter is intentionally enabled for the deployment test.

Schedule or invoke stale recovery:

```bash
python backend/manage.py recover_exam_prep_v4_stale_runs \
  --max-age-minutes 120 \
  --limit 200
```

## Manual production validation owned by the user

1. upload a real PDF;
2. verify/correct and confirm the Source Map;
3. copy `runId` and `taskId` from the runtime panel;
4. trace logs by `runId`;
5. inspect stage timings, provider/OCR counters and final record counts;
6. resolve exception items;
7. finalize review;
8. build projection and publish;
9. run the existing student exam flow;
10. cancel one active run and retry one terminal run;
11. report concrete page/question failures with correlation IDs.

## Remaining code roadmap

Critical before broad rollout:

1. dedicated persisted issue model/read API for non-match parser and integrity issues;
2. retention/orphan sweeps for superseded V4 evidence and projection artifacts;
3. fail-closed project deletion across all V4 storage objects;
4. private-media denial tests for every new artifact path;
5. load/concurrency/worker-memory tests and production queue sizing;
6. limited-cohort feature flag, monitoring dashboard and rollback procedure.

Accuracy/layout improvements continue from the first failure observed by the owner, especially column/RTL ordering, page deduplication, continuation boundaries, compact answer keys and inline question-answer documents.

## Exact continuation point

Deploy this branch with migrations `0045` and `0046`, a worker consuming `pipeline`, and the documented V4 environment variables. The owner performs the real production test. Continue coding from the first concrete correlated failure while independently completing the remaining Phase 9 cleanup/load/rollout items. Do not run CI/live benchmarks against AvalAI.
