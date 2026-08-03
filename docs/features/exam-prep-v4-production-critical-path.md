# Exam Prep V4 — Production Critical Path

> This is the execution overlay for finishing V4 quickly. The canonical architecture remains `exam-prep-v4-source-aware-split-pipeline.md`. Real provider validation is performed manually by the owner in the deployed production environment; development and CI must not make live AvalAI calls.

## Goal

Move the existing V4 source-aware engine from a benchmark/test-callable implementation to a production-callable teacher workflow:

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
→ projection/publication
```

## Non-goals for the critical path

- no live provider smoke or benchmark from CI;
- no provider-quality gate that blocks coding;
- no rewrite of V3 infrastructure;
- no broad refactor unrelated to the teacher workflow;
- no hidden provider/model fallback;
- no raw source text, image bytes, prompts, model output or credentials in logs.

## Execution rules

1. Update `exam-prep-v4-status.md` before each implementation slice.
2. Keep V4 behind `EXAM_PREP_V4_ENABLED`.
3. All heavy work runs on the `pipeline` Celery queue.
4. Source-map confirmation is the only automatic extraction trigger.
5. Every run has a stable `runId` and Celery `taskId` visible in the API and logs.
6. Retries reuse accepted blocks/records and never overwrite accepted history.
7. Production logs are structured, content-free and correlation-friendly.
8. CI uses fake providers and contract tests only; the owner validates real accuracy in deployment.

## Production log contract

Every V4 production event is emitted as one JSON object in the log message with these common fields:

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

Optional safe counters:

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
original filename or object key
PDF/image bytes or base64
native/OCR text
question/option/solution text
raw model response
prompt body
API key or authorization header
full traceback returned to the client
```

Required production events:

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

## Slice P1 — Production orchestration and observability

**State: active**

Deliverables:

- add a production extraction Celery task;
- dispatch it after exact Source Map confirmation;
- keep dispatch idempotent for one document revision/fingerprint;
- support optional OCR evidence only through existing environment configuration;
- add structured run/stage/provider logs;
- put `runId`, `taskId`, stage and safe counters in `workflow_state`;
- route the task explicitly to the `pipeline` queue;
- preserve warm reuse and current revision/fingerprint guards;
- mark failures with stable safe error codes and retain retryability.

Exit condition:

- confirmation returns an extraction correlation ID;
- project polling shows queued/running/completed/failed state;
- deployment logs can reconstruct one run without exposing source content.

## Slice P2 — Status and controlled retry API

**State: queued after P1**

Deliverables:

- owner-scoped extraction status endpoint;
- owner-scoped retry endpoint;
- retry only the current confirmed revision;
- return existing active run instead of creating duplicate work;
- expose safe stage counters and issue codes;
- frontend polls while the project is in a running state;
- failed projects show a retry action and correlation ID.

Exit condition:

- the owner can start, observe and retry production extraction without shell access.

## Slice P3 — Exception review

**State: not started**

Deliverables:

- issue read model/API for invalid/missing block records and matcher exceptions;
- exception-only teacher UI;
- teacher decisions: match, ignore, out-of-scope, retry record;
- decisions bound to current question/answer set fingerprints;
- no accepted historical record mutation.

Exit condition:

- a teacher can resolve all unresolved/ambiguous/conflict cases and reach a review-complete state.

## Slice P4 — Final projection and publication

**State: not started**

Deliverables:

- backward-compatible projection into the current Exam Prep student domain;
- projection fingerprint bound to current V4 revisions;
- exclude provenance and solution content from unauthorized responses;
- final teacher confirmation;
- publish/cancel API and UI;
- idempotent publication and rollback-safe failure handling.

Exit condition:

- one V4 project can be published and used by a student through the existing product flow.

## Slice P5 — Production hardening

**State: not started**

Deliverables:

- stale task recovery;
- cancellation checkpoints between stages/batches;
- orphan/private-artifact cleanup;
- queue/concurrency/worker-memory controls;
- aggregate operational metrics;
- safe error taxonomy and operator runbook;
- limited-cohort feature-flag rollout and rollback.

Exit condition:

- V4 can run repeatedly in production without manual database repair.

## Manual production validation checklist

The owner performs these checks in deployment. They do not block implementation commits:

1. upload each real PDF;
2. confirm the proposed Source Map;
3. record `runId` and `taskId`;
4. follow logs by `runId`;
5. verify stage progression and final counters;
6. inspect question, answer-solution and matching output in the review UI/API;
7. retry one failed or partial run;
8. verify warm reuse does not repeat accepted work;
9. record observed latency, provider calls and corrections;
10. report only concrete failed cases for the next patch.

## Immediate continuation point

Implement Slice P1, then P2. Do not run the temporary three-PDF live benchmark and do not start Phase 8 review UI until the production extraction task, status/retry controls and observability are callable end to end.
