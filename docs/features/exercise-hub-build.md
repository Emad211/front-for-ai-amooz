# Exercise Hub — build progress (loop control file)

Governed by **ADR-0004** + the spec [`exercise-hub.md`](exercise-hub.md). One step per `/loop` iteration:
take the lowest unchecked `[ ]`, implement per the spec, test GREEN, tick here, commit `feat(exercise): E# …`,
push. Reuse existing machinery; new views ONLY in `views_exercises.py` (never `views.py`). Mandatory
team gates: **E1** database-engineer · **E5, E8** security-auditor · every non-trivial diff → code-reviewer.
Backend tests on the sqlite fast lane (`DATABASE_URL='sqlite:///test_run.sqlite3' … --no-migrations`);
Postgres/CI is migration-truth. LLM fully mocked (0 tokens).

## Backend
- [x] **E1** — ✅ 5 models (`ClassExercise`, `ClassExerciseAsset`, `ClassExerciseSection`,
  `ClassExerciseQuestion`, `StudentExerciseSubmission`) + migration `0024` (pure DDL) + 15 constraint/FK/reveal
  tests (green). **database-engineer gate PASSED** (ship-ready, no edits): Decimal precision sound, CASCADE
  graph correct, callable JSON defaults, indexes adequate for gradebook queries, no pending-trigger-events
  risk, `0025` free for E9. Rollback = `migrate classes 0023` (auto-reversible CreateModel).
- [x] **E2** — ✅ `services/exercise_ingest.py` (`structure_exercise_markdown`, env-only model chain
  `EXERCISE_STRUCTURE_MODEL→STRUCTURE_MODEL→MODEL_NAME`, `generate_structured` raise-not-silent) +
  `PROMPTS["exercise_structure"]["default"]` (byte-for-byte output contract + SAFETY_PREAMBLE +
  MATH block) + `ExerciseStructureOutput`/`ExerciseSectionOut`/`ExerciseQuestionOut` in `schemas.py` +
  5 new `LLMUsageLog.Feature` members (migration `commons/0006`, no-op AlterField) + contract test updated
  (LIVE_KEYS + OUTPUT_KEYS + safety list). Tests `test_exercise_ingest.py` (13: happy/repair/raise +
  env-only + schema) + full `test_prompts_contract.py` green (60). OCR reused from `pdf_extraction`.
- [x] **E3** — ✅ `extract_exercise_content` Celery task (`tasks.py`, routed to `pipeline` queue) — state
  machine {DRAFT,FAILED}→EXTRACTING→EXTRACTED/FAILED with a status guard + `cache.add` in-flight lock +
  persisted `extract_task_id`. OCR (`ocr_assets_to_markdown`: PDF via `extract_pdf_to_markdown`, photo via a
  standard `image_url` vision call, `EXERCISE_INGEST` feature) + `persist_exercise_structure` (clears old
  rows on re-run, coerces question_type/points/options) added to `exercise_ingest.py`. 7 eager tests
  (`test_exercise_extraction_task.py`): happy row-build, status guard, double-dispatch no-op, FAILED path,
  re-run clears stale rows, missing-safe, task-id persisted — all green, 0 tokens.
- [ ] **E4** — teacher endpoints (CRUD / extract / publish / toggles) in `views_exercises.py`. owner-404 +
  publish-validation (400/409) tests. **Follow-up from E1 db-gate:** the exercise/asset DELETE endpoint must
  GC the S3/MinIO blobs (FileField CASCADE removes rows, not storage objects).
- [ ] **E5** — student endpoints (list / detail / draft / submit / image) + deadline guard + no-leak
  serializers + the «پاسخ تمرین‌های تمام‌شده» answers browse (reveal gated on deadline). **security-auditor gate.**
- [ ] **E6** — grading service + task (`exercise_grading`, batch env, deterministic MCQ/fill-blank, retry
  idempotent, `EXERCISE_LLM_GRADING` kill-switch). Mocked grading + idempotent re-run + GRADING_FAILED.
- [ ] **E7** — result + report cards (per-exercise / per-course / overall) + teacher submissions list +
  override (llm_score immutable) + allow-redo + in-app notifications.
- [ ] **E8** — assistant endpoint + two-level server guard + context builder (structural reference-answer
  strip) + `PROMPTS["exercise_assistant_chat"]`. **security-auditor gate.** 403 + no-leak tests.
- [ ] **E9** — migration `0025` (`scheduled_at` on session) + `GET student/calendar/` aggregate endpoint.

## Frontend
- [ ] **E10** — teacher UI: service + upload wizard + gradebook + override + toggles. `tsc` clean.
- [ ] **E11** — student UI: exercises hub + solver (text/photo) + assistant widget + report cards +
  finished-answers browse. `tsc` clean; RTL/KaTeX.
- [ ] **E12** — calendar: remove mock, wire service + Jalali conversion + exam-prep events. `tsc` clean.

**Definition of done (every step):** GREEN on the sqlite fast lane (Postgres = CI truth); new code documented
in `exercise-hub.md` (docs law); auth/permission changes carry negative tests; commit `feat(exercise): E# …`
+ push; tick here + note in the roadmap table of `exercise-hub.md`.
