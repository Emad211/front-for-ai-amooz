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

## 3. Manual test flow

1. Upload a PDF through the V4 teacher flow.
2. Wait for page preparation and classification.
3. Review page roles, rotation and virtual order.
4. Confirm the exact Source Map.
5. Confirmation automatically creates an extraction run.
6. Open the **Production extraction status** panel.
7. Copy `Run ID` and `Celery Task ID`.
8. Follow backend/worker logs by `runId`.
9. Wait until project status becomes `awaiting_review` or `failed`.
10. Record counters and inspect the extracted records.

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

## 5. Retry API

```text
POST /api/classes/exam-prep-v4/projects/{projectId}/documents/{documentId}/extraction/retry/
```

Behavior:

- requires teacher ownership;
- requires the exact current Source Map to remain confirmed;
- returns the existing active run instead of duplicating it;
- creates a new `runId` after a terminal run when retry is requested;
- preserves accepted block and record history;
- warm/partial reuse is handled by the existing fingerprint contracts.

## 6. Log filtering

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

Search stage timings:

```text
"event":"exam_prep_v4.extraction.stage_completed"
```

## 7. Expected event order

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
```

The stage events can repeat because block and semantic extraction are batched. Use `batchIndex`, `batchSize`, `segmentOrder`, `elapsedMs` and `providerCallsDelta` to diagnose slow or incomplete slices.

## 8. Reading the counters

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
issueCount              tolerant parse/pipeline warnings
providerCalls          structured + OCR adapter provider calls observed by the run
ocrCalls                direct OCR calls when the adapter is enabled
ocrRetries              transient OCR retries
ocrFallbackCount        segments sent to the structured detector fallback
```

## 9. Failure handling

On terminal failure:

- project status becomes `failed`;
- `workflow_state.stage` becomes `extraction_failed`;
- API exposes a stable `errorCode` and correlation IDs;
- no raw exception or source content is returned to the client;
- use the retry action after correcting environment/provider/worker issues.

For transient provider errors, Celery retries with bounded exponential delay and keeps the same logical `runId` while incrementing `attempt`.

## 10. What to report after production testing

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
