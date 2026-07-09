# Teacher Save-and-Process Workflows

Last updated: 2026-07-08

## Scope

This document records the July 2026 shift from teacher-side "stay on the page and wait"
flows to durable background processing for:

- class creation
- exam-prep creation
- optional embedded exercise intake during class creation

Publish remains explicit and manual.

## What Changed

### Durable workflow state on `ClassCreationSession`

`ClassCreationSession` now persists:

- `workflow_state`
- `review_ready_notified_at`
- `pending_exercises`

Frontend polling for class and exam-prep now reads backend workflow fields instead of inventing
progress locally from status + timers.

Response contract exposed on step-1/list/detail serializers:

- `workflowStage`
- `workflowMessage`
- `progressPercent`
- `workflowWarnings`
- `readyForReview`
- `reviewReadyNotifiedAt`
- `pendingExercises`

### Save-and-process flow

Teacher flow is now:

1. enter class or exam-prep information
2. upload the lesson source
3. optionally define embedded exercise drafts (class only)
4. press `ذخیره و پردازش`
5. leave the page safely
6. return later from the class/exam list into the draft detail page for `بازبینی و انتشار`

### Embedded exercises in create-class

When `برای این کلاس تمرین هم می‌سازم` is enabled:

- frontend sends `pendingExercises[]` in the class step-1 multipart request
- each embedded source file is attached as `exercise_<exerciseKey>__file_<sourceKey>`
- backend stores a normalized snapshot on the class session
- once the class reaches review-ready, child `ClassExercise` drafts are materialized automatically
- each child exercise enters the existing async extraction pipeline

### Ready notifications

When a class or exam-prep reaches review-ready:

- `review_ready_notified_at` is set once
- a teacher SMS is queued once
- a virtual teacher notification feed item becomes visible

Notification ids:

- `class-ready-<session_id>`
- `exam-ready-<session_id>`

## Guardrails

### Idempotency

Class step-1 idempotency is now content-aware across both:

- the main lesson upload
- embedded `pending_exercises` payload

Same `client_request_id` + same lesson file + same embedded exercise payload:

- dedupe to the existing session

Same `client_request_id` + changed lesson file or changed embedded exercise payload:

- do **not** reuse the old session
- create a fresh session instead

This prevents stale embedded exercise drafts from being silently reused.

### Pending-exercise validation

Backend validation now rejects malformed embedded exercise payloads earlier, including:

- invalid JSON
- duplicate `clientExerciseKey`
- duplicate `clientFileKey` within one exercise
- invalid enum values
- malformed deadline values
- missing uploaded source files

### Storage cleanup

If session creation fails after embedded exercise source files were stored, the temporary stored
files are deleted before returning the error response.

## Teacher UI Notes

### Jalali picker

The shared Jalali picker now:

- anchors from the RTL end
- keeps date selection open until the teacher confirms
- uses an explicit `تایید` action
- uses the current `react-day-picker` class contract (`weekdays`/`week`) so weekday labels and day
  numbers stay in a stable 7-column grid
- avoids the previous clipped / half-empty popover layout

### CTA placement

`ذخیره و پردازش` is the single final action at the bottom of the whole authoring surface, after
all blocking teacher inputs. The intermediate "ثبت نهایی" card is explanatory only and does not
render its own submit button.

When processing is active, the same bottom action slot becomes `لغو پردازش`; there is no separate
bottom `انصراف` button competing with the final workflow action.

`بازبینی و انتشار` is intentionally not rendered on the create-class/create-exam page. After
processing, the teacher returns through the class or exam list and publishes from the draft detail
surface where the generated content can be reviewed.

### Progress durability

Class/exam progress remains backend-owned. During long chunked transcription, the Celery heartbeat
now also persists intra-step progress and a chunk message instead of only bumping `updated_at`; if a
new session stays at `queued`/5%, that means the worker has not picked up the task yet.

## Verification

### Completed

- targeted backend regression tests on sqlite fast lane:
  - `backend/apps/classes/test_step1_idempotency.py`
  - `backend/apps/classes/test_session_workflow.py`
- frontend typecheck checked for regressions introduced by this work

### Still blocked locally

Repository-wide backend pytest still expects the project PostgreSQL instance on `localhost:5432`.
That local service was not running during this pass, so full Postgres-backed verification remains
pending.

Current pre-existing frontend `tsc` baseline errors also remain outside this feature's scope.
