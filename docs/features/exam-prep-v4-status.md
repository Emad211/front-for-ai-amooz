# Exam Prep V4 — Implementation Status Ledger

> Update this file before every V4 implementation slice. Canonical architecture: `exam-prep-v4-source-aware-split-pipeline.md`. Fast execution overlay: `exam-prep-v4-production-critical-path.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Production Critical Path
- **Current span:** production orchestration and observability, then status/retry controls
- **Last completed slice:** optional OCR adapter, OCR-aware benchmark guard and bounded manual workflow
- **Active gate:** connect the existing V4 semantic pipeline to the real teacher confirmation flow without making live provider calls from development or CI
- **Live validation owner:** manual validation by the project owner in the deployed environment
- **Structured model selection:** environment only
- **OCR model selection:** environment only; default adapter remains disabled unless explicitly configured
- **Last updated:** 2026-08-04

## Current production reality

Implemented and callable:

- independent private PDF upload projects;
- render, thumbnail and fast page-role classification;
- revision-bound Source Map API and RTL teacher editor;
- exact teacher confirmation by revision and fingerprint;
- SourceBlock/Fragment persistence with crops and continuations;
- typed QuestionRecord and unified AnswerSolutionRecord persistence;
- deterministic matching and warm zero-call reuse;
- optional AvalAI OCR evidence adapter and structured detector fallback;
- aggregate benchmark tooling and focused fake-provider tests.

Missing from the user flow before this slice:

- confirmation does not dispatch semantic extraction;
- no production extraction Celery task;
- no run/task correlation visible to the API;
- no owner-controlled retry endpoint;
- no production stage/provider log contract;
- no exception review or final projection/publication.

## Progress

The existing 77-item canonical denominator remains unchanged. Production orchestration work is an execution overlay and receives no artificial accuracy credit.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real production behavior will be validated by the owner after deployment. |
| Phase 3 | 4 | 7 | Split/group controls and browser accessibility evidence remain open. |
| Phase 4 | 4 | 8 | Column/RTL/dedup work remains open. |
| Phase 5 | 6 | 7 | Real precision/recall will be measured by the owner in deployment. |
| Phase 6 | 4 | 7 | Compact key and inline-answer paths remain open. |
| Phase 7 | 6 | 7 | Complete option/solution consistency remains open. |
| Phases 8–10 | 0 | 20 | Review, projection, hardening and rollout remain open. |

- **Overall:** **43/77 = 55.8%**

## Live validation policy

Development and CI must not call live AvalAI endpoints for this critical path.

Allowed during coding:

- static checks;
- fake-provider/unit/contract tests;
- migration checks;
- deterministic reuse and permission tests.

Performed manually by the owner after deployment:

- real PDF upload;
- real provider extraction;
- output inspection and corrections;
- observed latency, call count and cost;
- worker/process log inspection;
- retry and warm-reuse behavior.

The temporary three-PDF live benchmark is no longer the next implementation gate and must not block coding.

## Production observability contract

Every extraction run receives:

```text
runId: stable UUID for the logical extraction run
taskId: Celery task id for one execution attempt
projectId
documentId
sourceMapRevision
sourceMapFingerprintPrefix
attempt
```

Required log events:

```text
exam_prep_v4.extraction.dispatch_requested
exam_prep_v4.extraction.dispatch_reused
exam_prep_v4.extraction.task_started
exam_prep_v4.extraction.stage_started
exam_prep_v4.extraction.stage_completed
exam_prep_v4.extraction.task_completed
exam_prep_v4.extraction.task_failed
exam_prep_v4.extraction.task_retried
exam_prep_v4.extraction.task_skipped
```

Logs may contain identifiers, timings, models, provider-call counts, issue codes and aggregate record counts. Logs must not contain PDF/image bytes, OCR/source text, questions, answers, solutions, prompts, raw provider payloads, object keys or credentials.

## Active slice P1 — production extraction task

Implementation order:

1. add content-free structured observability helpers;
2. add an observed production provider wrapper;
3. add an idempotent extraction Celery task on queue `pipeline`;
4. create/retain `runId` and expose Celery `taskId`;
5. dispatch after exact Source Map confirmation;
6. store safe current stage and counters in `project.workflow_state`;
7. preserve current revision/fingerprint checks and warm reuse;
8. mark failures with stable safe error codes;
9. add explicit Celery route and deployment env/runbook notes.

P1 exit condition:

- teacher confirmation queues semantic extraction;
- project API exposes correlation and progress;
- production logs reconstruct each stage without private source content.

## Next slice P2 — status and retry

Implementation order:

1. owner-scoped extraction status endpoint;
2. owner-scoped retry endpoint for the current confirmed revision;
3. return an existing active run instead of duplicate dispatch;
4. frontend polling while status is active;
5. display run ID, task ID, stage, progress and safe counters;
6. failed-state retry action.

P2 exit condition:

- production testing can be performed from the UI/API without shell or direct database access.

## After P2

Continue directly through:

```text
P3 exception-only review
→ P4 backward-compatible projection and publication
→ P5 stale recovery, cancellation, cleanup and limited rollout
```

## Exact continuation point

Implement P1 now. Do not execute a real provider benchmark. After P1, implement P2 immediately, then continue from exception review rather than pausing for external benchmark approval.
