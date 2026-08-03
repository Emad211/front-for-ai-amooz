# Exam Prep V4 — Production Critical Path

> This execution overlay prioritizes a production-callable teacher flow. Real provider validation is performed manually by the owner in the deployed environment; development and CI make no live AvalAI calls.

## Goal

```text
upload PDF
→ prepare/render/classify
→ teacher edits and confirms Source Map
→ production extraction task is queued automatically
→ block detection
→ question extraction
→ answer-solution extraction
→ deterministic matching
→ exception-only review
→ backward-compatible projection
→ publication through the existing student Exam Prep flow
```

## Execution rules

1. Keep V4 behind `EXAM_PREP_V4_ENABLED`.
2. Select structured/OCR models from environment only.
3. Run heavy work on the `pipeline` Celery queue.
4. Source Map confirmation dispatches only the exact current revision/fingerprint.
5. Every extraction run exposes `runId` and Celery `taskId` in API/state/logs.
6. Accepted blocks/records are reused and historical accepted evidence is not overwritten.
7. Logs are structured, content-free and correlation-friendly.
8. CI uses fake providers and contract tests only.
9. The owner measures real accuracy, latency, calls and cost in deployment.

## Production log contract

Common safe fields:

```text
event
runId
taskId
projectId
documentId
sourceMapRevision
sourceMapFingerprintPrefix
stage
attempt
elapsedMs
providerCalls
issueCount
status
errorCode
```

Safe counters:

```text
pageCount
segmentCount
blockCount
fragmentCount
questionCount
answerSolutionCount
matchedCount
outOfScopeCount
unresolvedCount
ambiguousCount
conflictCount
ocrCalls
ocrRetries
ocrFallbackCount
```

Forbidden log data:

```text
filename or object key
PDF/image bytes or base64
native/OCR text
question/option/solution text
prompt or raw model response
API key or authorization header
private exception detail returned to clients
```

Logger:

```text
apps.classes.exam_prep_v4
```

## Slice P1 — Production orchestration and observability

**State: complete**

Completed:

- production extraction Celery task;
- automatic dispatch after exact Source Map confirmation;
- revision/fingerprint idempotency;
- optional OCR evidence through environment only;
- structured run/stage/batch/provider events;
- `runId`, `taskId`, stage and safe counters in `workflow_state`;
- explicit `pipeline` queue routing;
- warm/partial reuse;
- bounded transient retries and explicit terminal Celery failures;
- safe error codes and deployment configuration.

## Slice P2 — Status, retry and cancellation

**State: complete**

Completed:

- owner-scoped extraction status API;
- owner-scoped retry API for the current confirmed revision;
- duplicate active-run refusal/reuse;
- active frontend polling;
- runtime panel with Run ID, Task ID, stage, progress and counters;
- failed/cancelled-state retry;
- cooperative cancellation API/UI;
- cancellation checkpoints before and after provider stages/batches;
- non-terminating Celery revoke request.

## Slice P3 — Exception review

**State: complete for the production flow; dedicated persisted issue rows remain a canonical hardening item**

Completed:

- exception read queue/API derived from current match decisions;
- immutable teacher review-decision model;
- exception-only teacher UI;
- match, ignore and out-of-scope decisions;
- exact question/answer/match fingerprint binding;
- stale-review refusal;
- review finalization and `ready_to_publish` transition.

Remaining hardening:

- separately persisted issue rows for parser/integrity problems beyond match exceptions;
- record-specific retry controls in the review UI.

## Slice P4 — Final projection and publication

**State: complete**

Completed:

- projection into existing `ClassCreationSession` Exam Prep domain;
- fingerprint-bound, idempotent projection;
- opaque student question IDs;
- no V4 provenance/raw payload projection;
- existing authorized student serializer strips teacher answers/solutions from question delivery;
- final review/projection binding;
- projection and publication APIs/UI;
- existing invitation, scoring and result flow reuse;
- post-commit roster/SMS hooks with safe failure logging.

## Slice P5 — Production hardening

**State: partially complete**

Completed:

- stale active-run recovery task and management command;
- cooperative cancellation checkpoints;
- safe error taxonomy and operator runbook;
- audit-safe correlated operational events;
- bounded queue/task/runtime configuration;
- fake-provider production orchestration/review/projection/publication contracts.

Remaining:

- retention and orphan sweeps;
- fail-closed project deletion across every V4/projection artifact;
- private-media denial tests for every artifact path;
- load/concurrency/worker-memory sizing;
- limited-cohort monitoring and rollback controls.

## Contract evidence

```text
feature head: d7b53393d77c50a53b81f0cba5e7d45367b6c6d8
validated merge ref: fd137cf8779eff5318cea23ca68fb7dc29f4cdb3
workflow: 30862683847
backend job: 91847863122
frontend job: 91847863181
Django system check: passed
migration drift: none
backend: 261 passed, 49 warnings in 26.03s
frontend focused TypeScript/state validation: passed
live provider calls: 0
```

## Manual production validation

The owner performs:

1. deploy migrations `0045` and `0046`;
2. ensure a worker consumes `pipeline`;
3. upload a real PDF;
4. confirm Source Map;
5. copy `runId` and `taskId`;
6. inspect stage logs and counters;
7. verify extracted questions, answers and matches;
8. resolve exception items;
9. finalize review, build projection and publish;
10. run the student exam flow;
11. cancel one active run and retry one terminal run;
12. report concrete failures with page/question and correlation IDs.

Full operator details:

```text
docs/runbooks/exam-prep-v4-production-validation.md
```

## Immediate continuation point

The coding critical path is production-callable through publication. Deploy it and let the owner perform real validation. Patch the first concrete correlated production failure without reintroducing a live CI gate. In parallel, complete the remaining P5 cleanup/deletion/media-denial/load/rollout items.
