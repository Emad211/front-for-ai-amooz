# 2026-07-19 — Stable Exercise Resubmission Grading

- **Status:** Ready for coordinated deploy
- **Created:** 2026-07-19
- **Last verified:** 2026-07-19
- **Owner:** release-manager

## Commit and scope

- Intended commit: `feat(exercise): stabilize resubmission grading with attempts`
- Backend scope: attempt schema/backfill, grading reuse, task concurrency, owner-scoped history APIs.
- Frontend scope: teacher/student attempt history and unchanged-answer warning.
- Documentation scope: ADR-0008, Exercise Hub living spec/build log, and this release note.

## Shipped

- Append-only `StudentExerciseAttempt` history with a compatibility projection on Submission.
- Immutable question/rubric snapshots keep grading and historical display tied to the submitted
  contract even when the teacher later edits the exercise.
- Per-question grading/OCR reuse for unchanged answers and partial regrade for changed questions.
- Image reuse keys include SHA-256 content identity; new answer images use UUID object names, and
  transient vision failures retry instead of becoming reusable empty OCR/zero grades.
- Attempt history for teacher and student, read-only historical teacher views, and unchanged-answer
  warning before student resubmission.
- `grading_notes` now reaches the private grader; grading and handwriting OCR use temperature 0.
- Latest graded attempt is the report-card source of truth.
- Exercise grading usage is attributed to the owning teacher/session in LLM usage logs.
- Redo-safe reveal and projection guards: an open redo hides no-deadline reference answers, stale
  grading completion cannot close the redo, and historical attempts cannot be overridden.
- Before reveal, student feedback is fixed label-based copy rather than model-authored text, preventing
  private reference answers or grading notes from leaking through feedback fields.
- Backfill is repeat-safe, and teacher overrides read/merge result JSON only while holding the
  Submission/Attempt row locks.
- Attempt finalization and Submission projection now commit in one transaction. A teacher override
  cannot land between those writes and then be replaced by an older AI result; duplicate delivery
  projects only the already-persisted Attempt result.
- Fingerprints contain only configuration that can affect that question: text-only answers ignore
  vision-model changes, while photo answers include the OCR algorithm/prompt/model versions.
- Temporary object-storage read failures retry the grading task instead of being cached as an
  unreadable image and a reusable empty answer.
- Teacher grading distinguishes the latest historical Attempt from the current editable Attempt, so
  opening a redo draft cannot leave stale override controls enabled.

## Deploy order

1. Drain and stop workers consuming the `pipeline` queue.
2. Deploy the backend image and run migrations `0032` then `0033`.
3. Start backend and pipeline workers from the same image; verify queue health.
4. Deploy the frontend.

Do not run old and new grading workers concurrently during this migration. No new environment
variable is required.

## Migrations and risk

- `classes/0032_studentexerciseattempt` is DDL: it creates the attempt table, constraints/index, and
  nullable Submission pointer.
- `classes/0033_backfill_exercise_attempts` is repeat-safe DML: it snapshots finalized existing
  submissions as attempt 1 and links only compatible rows. It may lengthen backend startup in proportion
  to existing finalized submissions/questions, so apply it while pipeline workers are drained.
- `0033` has a no-op reverse and does not delete backfilled data. Reverting application code while
  retaining `0032`/`0033` leaves the new table unused. Migrating back through `0032` drops attempt history;
  use a database backup/restore if that history must be retained.

## Rebuild set

- `ai-amooz-backend` web deployment.
- Celery worker deployment, using the exact same backend image.
- `front` Next.js deployment.
- No Celery Beat change and no new environment variables.

## Verification

- Mandatory reviews completed on the final diff: database-engineer, AI engineer, security auditor, and
  code reviewer all approved after their findings were resolved. The release-manager gate identified
  and required the documentation corrections recorded in this note.
- Exercise/LLM regression suite on SQLite without migrations after the verification fixes:
  `305 passed, 1 skipped, 127 warnings`. The skipped test is PostgreSQL-only concurrency coverage.
- Fresh PostgreSQL 16 migration through `classes/0033`: passed.
- Full Exercise/LLM regression suite on PostgreSQL 16 with real migrations: `306 passed`.
- Focused finalization/override, fingerprint, storage-retry, and current-Attempt regressions passed on
  both SQLite and PostgreSQL (`5 passed` on each focused run).
- Focused final grading suite after image-identity hardening: `37 passed`.
- Prompt contract is included in the 301-test run and passed.
- `python manage.py check`: `System check identified no issues (0 silenced)`.
- `python manage.py makemigrations --check --dry-run`: `No changes detected` (the command also emitted
  the expected local migration-history warning when its default PostgreSQL endpoint was unavailable;
  migrations were separately applied to a real PostgreSQL 16 instance).
- `git diff --check`: passed; Git reported line-ending conversion warnings only.
- `npm run typecheck`: 11 existing errors in unchanged admin/exam/mock-message files; no error in a
  changed Exercise Hub file.
- `npm run build`: production build compiled successfully and generated all 55 routes.
- `npm run lint`: the pre-existing ESLint configuration crashes before linting files with
  `Converting circular structure to JSON`; no lint result is claimed for this release.
- Full backend regression suite on SQLite after the verification fixes: `1349 passed, 5 skipped`.
  The skips are two PostgreSQL-only auth races, two opt-in real-LLM PDF benchmarks, and one
  PostgreSQL-only row-lock test. PostgreSQL-specific Exercise Hub coverage was run separately above.

## Rollback

1. Drain `pipeline` workers again and stop the new worker.
2. Revert the application commit and redeploy the matching backend/worker/frontend images.
3. Prefer leaving migrations `0032`/`0033` applied; old code ignores the additive table and nullable
   pointer. This preserves attempt history.
4. Only migrate to `classes/0031` when loss of attempt history is explicitly accepted or a backup has
   been captured and validated.
