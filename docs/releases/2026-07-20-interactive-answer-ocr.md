# 2026-07-20 - Interactive handwritten-answer OCR

Scope: backend, frontend, worker infrastructure

## Changes

- Students can upload images for one answer or a multi-page image/PDF answer bundle and review the extracted math-aware text before submission.
- Whole-exercise OCR uses a two-phase page transcription and question-matching pipeline without reference answers or grading notes.
- Raw OCR, student-reviewed text, source revisions, and original assets remain separate and auditable.
- Final grading freezes the selected OCR revision and reuses its confirmed transcript without a second vision request.
- OCR uncertainty reports readability only; it does not judge answer correctness.

## Migrations

- `classes/0034_student_exercise_answer_ocr.py`: pure DDL; creates `StudentExerciseAnswerSource` and `StudentExerciseAnswerAsset` with scope, revision, ownership, and ordering constraints.
- The migration does not rewrite or delete existing submission data.
- Rollback: disable the feature flag, drain the `interactive` queue, deploy the previous backend/frontend, then reverse migration `0034` only if no answer-source records must be retained.

## Env / config

- `EXERCISE_ANSWER_OCR_PREVIEW_ENABLED=0` by default. Set to `1` only after the interactive worker is healthy.
- Optional limits: `EXERCISE_ANSWER_OCR_MAX_PAGES=20`, `EXERCISE_ANSWER_OCR_MAX_BYTES=31457280`, `EXERCISE_ANSWER_OCR_PAGES_PER_CALL=4`, `EXERCISE_ANSWER_OCR_SETTLE_SECONDS=2`.
- Optional env-only model overrides: `EXERCISE_ANSWER_OCR_MODEL`, `EXERCISE_ANSWER_MAPPING_MODEL`.
- No secret values are added.

## Rebuild and deploy

1. Keep `EXERCISE_ANSWER_OCR_PREVIEW_ENABLED=0`.
2. Rebuild and deploy the shared backend/worker image; let the backend apply migration `0034`.
3. Apply `k8s/celery-interactive-worker-deployment.yaml` (or the equivalent Hamravesh app) and verify it consumes only `interactive` with concurrency `2`.
4. Rebuild and deploy the frontend.
5. Enable the feature flag for backend and interactive worker, then restart both services.

## Verification

- Exercise Hub + prompt contracts: `297 passed, 1 skipped`.
- OCR + prompt contracts against PostgreSQL with migrations: `81 passed`; the same final set on SQLite also passed (`81 passed`).
- Django system check: no issues.
- `makemigrations --check --dry-run`: no changes detected.
- `docker compose config --quiet`: passed.
- `docker compose build celery-interactive-worker`: passed.
- Interactive worker boot: connected to Redis, registered `process_student_answer_source`, and reported ready.
- `npm run build`: passed; all 55 routes generated.
- `npm run typecheck`: still exits with the existing 11 errors in admin tickets, exam edit, and mock message fixtures; no changed OCR/exercise file reports a TypeScript error.
- `npm run lint`: blocked by the existing Next 15/ESLint circular-config failure before linting source files.
- Full backend `pytest` was attempted but exceeded the 300-second command limit; it is not claimed as passed.

## Known limitations

- Feature flag remains off until the dedicated worker is deployed.
- A provider-level OCR failure leaves the original image available for teacher review and marks grading failed instead of assigning a false zero.
- OCR does not validate mathematical correctness, suggest solutions, or compare against reference answers.

## Rollback

- Set `EXERCISE_ANSWER_OCR_PREVIEW_ENABLED=0` first; this restores the legacy upload/grading path without deleting stored OCR records.
- Revert the release commit and redeploy backend/frontend. Keep migration `0034` applied for a non-destructive rollback, or reverse it only after confirming no source history must be retained.
