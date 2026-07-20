# 2026-07-20 - Interactive handwritten-answer OCR

Scope: backend, frontend, worker infrastructure

## Changes

- Students can upload images for one answer or a multi-page image/PDF answer bundle and review the extracted math-aware text before submission.
- Whole-exercise OCR uses a two-phase page transcription and question-matching pipeline without reference answers or grading notes.
- Raw OCR and the student-reviewed projection are stored separately. Each final Attempt snapshots the
  applied projection; the mutable draft Source itself is not an append-only revision ledger.
- Final grading freezes the selected OCR revision and reuses its confirmed transcript without a second vision request.
- OCR uncertainty reports readability only; it does not judge answer correctness.
- Source assets are served through an authenticated owner/teacher endpoint, not by serializing raw media URLs.
- Originals use the dedicated private `answer_sources` storage alias in the existing application media bucket. The generic
  `/media/exercises/answers/sources/` path is denied, unsigned object-store reads are forbidden, and API
  responses omit storage keys.
- Teachers can read only the exact asset IDs frozen into one of their students' Attempts; mutable draft
  assets remain private to the student.
- Successful page chunks survive a mapping/provider retry, so a retry does not repay completed vision work.
- PDF pages are scaled before rasterization and image payloads are bounded before entering the provider request.
- Queue dispatch claims a pre-generated Celery task ID in the database before publishing. Recovery only
  republishes unclaimed queued rows or stale in-progress rows, preventing duplicate provider calls.

## Migrations

- `classes/0034_student_exercise_answer_ocr.py`: pure DDL; creates `StudentExerciseAnswerSource` and `StudentExerciseAnswerAsset` with scope, revision, ownership, and ordering constraints.
- `classes/0035_answer_asset_deactivated_at.py`: pure DDL; records when an asset becomes inactive so retention starts at replacement/removal time.
- `classes/0036_backfill_attempt_answer_asset_ids.py`: DML-only; backfills exact asset IDs only when the
  source/submission/revision relationship is provable. Ambiguous legacy references remain untouched.
- `classes/0037_answer_asset_private_storage.py`: state-only `AlterField`; answer originals use the private
  storage alias without moving objects or creating another bucket.
- No migration moves or deletes existing submission, Attempt, or object data.

## Env / config

- `EXERCISE_ANSWER_OCR_PREVIEW_ENABLED=0` by default. Set to `1` only after the interactive worker is healthy.
- The existing `AWS_STORAGE_BUCKET_NAME` must remain private. Media is served through Django's `/media/` proxy;
  no second bucket or new storage environment variable is required.
- Recommended limits: `EXERCISE_ANSWER_OCR_MAX_PAGES=20`, `EXERCISE_ANSWER_OCR_MAX_BYTES=31457280`, `EXERCISE_ANSWER_OCR_REQUEST_MAX_BYTES=33554432`, `EXERCISE_ANSWER_OCR_PAGES_PER_CALL=4`, `EXERCISE_ANSWER_OCR_SETTLE_SECONDS=2`.
- Provider/task limits: `EXERCISE_ANSWER_OCR_TIMEOUT_SECONDS=180`,
  `EXERCISE_ANSWER_OCR_SOFT_TIME_LIMIT=2400`, `EXERCISE_ANSWER_OCR_TIME_LIMIT=2700`.
- Image bounds: `EXERCISE_ANSWER_OCR_IMAGE_MAX_BYTES=3145728`,
  `EXERCISE_ANSWER_OCR_IMAGE_MAX_DIMENSION=2400`, `EXERCISE_ANSWER_OCR_IMAGE_MAX_PIXELS=30000000`.
- Abuse/retention controls: `THROTTLE_RATE_ANSWER_OCR_UPLOAD=12/hour`,
  `EXERCISE_ANSWER_OCR_MAX_PAGES_PER_HOUR=60`, `EXERCISE_ANSWER_OCR_MAX_BYTES_PER_HOUR=134217728`,
  and `EXERCISE_ANSWER_OCR_ASSET_RETENTION_DAYS=30`. Request middleware stops oversized multipart
  bodies while streaming; the edge proxy should enforce the same 32 MiB route cap. Celery Beat
  preserves exact asset IDs frozen by historical Attempts.
- Optional env-only model overrides: `EXERCISE_ANSWER_OCR_MODEL`, `EXERCISE_ANSWER_MAPPING_MODEL`.
- No secret values are added.

## Rebuild and deploy

1. Keep `EXERCISE_ANSWER_OCR_PREVIEW_ENABLED=0`.
2. Run `python manage.py setup_s3_bucket` for the existing bucket and verify an unsigned GET is denied.
3. Rebuild and deploy one immutable shared backend/worker image; apply migrations `0034` through `0037`.
4. Apply `k8s/celery-interactive-worker-deployment.yaml` (or the equivalent Hamravesh app) and verify
   it consumes only `interactive` with concurrency `1`, 1 GiB requested memory and 2 GiB limit.
5. Deploy the frontend and verify the worker hostname `interactive@...` responds to Celery ping.
6. Run owner/non-owner, single-image, multi-page PDF, Attempt-freeze, and direct-bucket smoke tests.
7. Enable the feature flag for both backend and interactive worker, then restart both services.
8. Start with one worker/pilot traffic. Scale replicas from observed queue latency and provider p95;
   do not raise per-pod concurrency before measuring memory under 20-page PDF load.

## Verification

- OCR + prompt contracts: `112 passed` on the SQLite fast lane.
- OCR + student API + prompt contracts: `141 passed` on the SQLite fast lane.
- Django system check: no issues.
- `makemigrations --check --dry-run`: no changes detected.
- `docker compose config --quiet`: passed.
- `npm run build`: passed; all 55 routes generated.
- `npm run typecheck`: still exits with the existing 11 errors in admin tickets, exam edit, and mock message fixtures; no changed OCR/exercise file reports a TypeScript error.
- `npm run lint`: blocked by the existing Next 15/ESLint circular-config failure before linting source files.
- Full backend suite: final count recorded after the release gate; PostgreSQL remains the migration-truth gate.

## Known limitations

- Feature flag remains off until the dedicated worker is deployed.
- A provider-level OCR failure leaves the original image available for teacher review and marks grading failed instead of assigning a false zero.
- OCR does not validate mathematical correctness, suggest solutions, or compare against reference answers.
- Draft Source rows are mutable. Historical Attempts preserve the OCR projection used for grading, but
  reconstructing every intermediate draft revision would require a future append-only revision model.
- One worker with concurrency 1 intentionally favors memory safety over throughput. Broad rollout needs
  queue-latency and provider-duration measurements before replica sizing.
- Storage deletion is best-effort after database deletion and emits an error log on provider failure. A future
  durable deletion outbox would be required for guaranteed cleanup during a prolonged object-store outage.

## Rollback

- Set `EXERCISE_ANSWER_OCR_PREVIEW_ENABLED=0` on backend and interactive worker first. New preview work
  stops; already-applied/frozen OCR remains valid for submission and grading.
- Stop or drain the interactive worker and roll back the frontend if needed. Keep migrations `0034` through
  `0037` and the existing media bucket. No object migration or bucket rollback is required.
