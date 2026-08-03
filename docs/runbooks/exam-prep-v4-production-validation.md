# Exam Prep V4 — Production Validation Runbook

This runbook is for manual validation in the deployed environment. Development and CI do not make live AvalAI calls.

## 1. Required deployment configuration

Backend and pipeline worker must share the same database, Redis and private storage configuration.

```env
EXAM_PREP_V4_ENABLED=True

EXAM_PREP_V4_BLOCK_MODEL=gemini-2.5-flash
EXAM_PREP_V4_QUESTION_MODEL=gemini-2.5-flash
EXAM_PREP_V4_ANSWER_MODEL=gemini-2.5-flash

EXAM_PREP_V4_EXTRACTION_TIMEOUT_SECONDS=180
EXAM_PREP_V4_EXTRACTION_MAX_RETRIES=2
EXAM_PREP_V4_TASK_SOFT_LIMIT_SECONDS=3300
EXAM_PREP_V4_TASK_HARD_LIMIT_SECONDS=3600
EXAM_PREP_V4_STALE_RUN_MINUTES=120

EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BLOCKS=4
EXAM_PREP_V4_EXTRACTION_BATCH_MAX_IMAGES=12
EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BYTES=12582912

LOG_LEVEL=INFO
```

Optional OCR evidence adapter:

```env
EXAM_PREP_V4_OCR_EVIDENCE_ENABLED=True
EXAM_PREP_V4_OCR_EVIDENCE_MODEL=mistral-ocr-4-0
EXAM_PREP_V4_OCR_EVIDENCE_MAX_ATTEMPTS=2
EXAM_PREP_V4_OCR_EVIDENCE_RETRY_BACKOFF_SECONDS=0.25
EXAM_PREP_V4_OCR_EVIDENCE_MIN_CONFIDENCE=0.65
EXAM_PREP_V4_OCR_EVIDENCE_BBOX_FOR_DIAGRAMS=True
```

When OCR evidence is disabled, the existing structured block detector remains authoritative.

## 2. Worker command

The worker must listen to `pipeline` in addition to lightweight queues.

```bash
celery -A core worker \
  --loglevel=info \
  -Q default,pipeline,interactive \
  --concurrency=2 \
  --prefetch-multiplier=1 \
  --max-tasks-per-child=50
```

A deployment with no worker consuming `pipeline` will accept confirmation and show `extraction_queued`, but no extraction stage will start.

## 3. Manual end-to-end test flow

1. Upload a PDF through the V4 teacher flow.
2. Wait for page preparation and classification.
3. Review page roles, rotation and virtual order.
4. Confirm the exact Source Map.
5. Confirmation automatically creates an extraction run.
6. Open the **Production extraction status** panel.
7. Copy `Run ID` and `Celery Task ID`.
8. Follow backend/worker logs by `runId`.
9. Wait until project status becomes `awaiting_review`, `failed` or `cancelled`.
10. Resolve every item in the exception-only review panel.
11. Finalize review.
12. Build the backward-compatible student projection.
13. Publish the exam.
14. Open the generated existing Exam Prep session and test the student flow.

## 4. Status API

```text
GET /api/classes/exam-prep-v4/projects/{projectId}/documents/{documentId}/extraction/status/
```

Safe response fields include:

```text
projectStatus
documentStatus
active
terminal
retryable
cancellationRequested
runId
taskId
attempt
stage
progressPercent
warningCount
sourceMapRevision
sourceMapFingerprintPrefix
lastEventAt
counters
errorCode
updatedAt
```

No source text, filename, storage key, prompt or provider payload is returned.

## 5. Retry and cancellation APIs

Retry:

```text
POST /api/classes/exam-prep-v4/projects/{projectId}/documents/{documentId}/extraction/retry/
```

Cancellation:

```text
POST /api/classes/exam-prep-v4/projects/{projectId}/documents/{documentId}/extraction/cancel/
```

Behavior:

- both require teacher ownership;
- retry requires the exact current Source Map to remain confirmed;
- an existing active run is returned instead of duplicated;
- a terminal retry creates a new `runId` and clears cancellation state;
- cancellation is cooperative and checked before and after each provider stage/batch;
- Celery revoke is requested without forcibly terminating the worker process;
- accepted block and record history remains immutable;
- warm/partial reuse is handled by existing fingerprints.

## 6. Exception review APIs

Queue:

```text
GET /api/classes/exam-prep-v4/projects/{projectId}/review/
```

Save one decision:

```text
POST /api/classes/exam-prep-v4/projects/{projectId}/review/decisions/
```

Supported decisions:

```text
match
out_of_scope
ignore
```

Finalize review:

```text
POST /api/classes/exam-prep-v4/projects/{projectId}/review/finalize/
```

Teacher decisions are immutable revisions bound to the exact question, answer and source-match fingerprints. A changed extraction set makes old review decisions stale instead of silently applying them.

## 7. Projection and publication APIs

Build the existing student-domain projection:

```text
POST /api/classes/exam-prep-v4/projects/{projectId}/projection/
```

Publish:

```text
POST /api/classes/exam-prep-v4/projects/{projectId}/publish/
```

Projection behavior:

- creates or reuses one legacy `ClassCreationSession` with `pipeline_type=exam_prep`;
- converts accepted V4 questions and resolved answer-solutions to `exam_prep_json`;
- uses opaque question IDs;
- does not project SourceBlock IDs, raw provider payloads or provenance;
- requires every publishable question to have exactly one answer;
- publication reuses the current student, invitation, scoring and result flows;
- publication is fingerprint-bound and idempotent.

## 8. Log filtering

All V4 extraction logs use logger:

```text
apps.classes.exam_prep_v4
```

Each event is one JSON object inside the log message.

Search one logical run:

```text
"runId":"<RUN_ID>"
```

Search one Celery attempt:

```text
"taskId":"<TASK_ID>"
```

Search failures:

```text
"event":"exam_prep_v4.extraction.task_failed"
```

Search retries:

```text
"event":"exam_prep_v4.extraction.task_retried"
```

Search cancellation:

```text
"event":"exam_prep_v4.extraction.cancellation_requested"
"event":"exam_prep_v4.extraction.task_cancelled"
```

Search stale recovery:

```text
"event":"exam_prep_v4.extraction.stale_run_recovered"
```

Search stage timings:

```text
"event":"exam_prep_v4.extraction.stage_completed"
```

Search projection/publication:

```text
"event":"exam_prep_v4.projection.ready"
"event":"exam_prep_v4.projection.published"
```

## 9. Expected event order

Typical successful run:

```text
exam_prep_v4.extraction.dispatch_requested
exam_prep_v4.extraction.task_started
exam_prep_v4.extraction.stage_started       stage=block_detection
exam_prep_v4.extraction.stage_completed     stage=block_detection
exam_prep_v4.extraction.stage_started       stage=question_extraction
exam_prep_v4.extraction.stage_completed     stage=question_extraction
exam_prep_v4.extraction.stage_started       stage=answer_solution_extraction
exam_prep_v4.extraction.stage_completed     stage=answer_solution_extraction
exam_prep_v4.extraction.task_completed
exam_prep_v4.projection.ready
exam_prep_v4.projection.published
```

Stage events can repeat because block and semantic extraction are batched. Use `batchIndex`, `batchSize`, `segmentOrder`, `elapsedMs` and `providerCallsDelta` to diagnose slow or incomplete slices.

## 10. Reading the counters

```text
blockCount             accepted source blocks
fragmentCount          accepted page/crop evidence fragments
questionCount          accepted typed questions
answerSolutionCount    accepted unified answer-solution records
matchedCount           deterministic successful matches
outOfScopeCount        numbered answers outside the project inventory
unresolvedCount        answers lacking a deterministic target
ambiguousCount         duplicate candidate matches
conflictCount          integrity conflicts such as invalid option label
issueCount             tolerant parse/pipeline warnings
providerCalls          structured + OCR adapter provider calls observed by the run
ocrCalls               direct OCR calls when the adapter is enabled
ocrRetries             transient OCR retries
ocrFallbackCount       segments sent to the structured detector fallback
```

## 11. Stale-run recovery

Run periodically, for example every 30 minutes through a scheduler or operational cron:

```bash
python backend/manage.py recover_exam_prep_v4_stale_runs \
  --max-age-minutes 120 \
  --limit 200
```

A stale active run is marked `failed` with `errorCode=stale_extraction_run`, `cancel_requested=True` is set so an old worker stops at its next checkpoint, and correlation IDs remain in workflow state and logs.

The same recovery logic is also available as Celery task:

```text
apps.classes.tasks_v4_recovery.recover_exam_prep_v4_stale_runs
```

## 12. Failure handling

On terminal failure:

- project status becomes `failed`;
- `workflow_state.stage` becomes `extraction_failed` or `stale_extraction_recovered`;
- API exposes a stable `errorCode` and correlation IDs;
- no raw exception or source content is returned to the client;
- use retry after correcting environment/provider/worker issues.

For transient provider errors, Celery retries with bounded exponential delay and keeps the same logical `runId` while incrementing `attempt`.

## 13. What to report after production testing

For each failed or incorrect case, provide:

```text
Run ID
Task ID
project status and stage
safe counters
errorCode or issue codes
page number / printed question number involved
expected behavior
observed behavior
```

Do not paste API keys, raw PDF bytes or full private provider payloads.
