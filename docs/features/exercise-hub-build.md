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
- [x] **E4** — ✅ teacher endpoints in `views_exercises.py` (+ `serializers_exercises.py`, routes in `urls.py`;
  `views.py` untouched): create+asset-upload / list / detail / PATCH (title/deadline/allow_late/
  assistant_enabled) / DELETE (with **S3/MinIO blob GC** — E1 follow-up done) / extract-dispatch (409 while
  EXTRACTING) / publish (400 if any question lacks reference-answer or max_points, 409 wrong status) /
  section-toggle / question CRUD. All owner-scoped (`session__teacher=request.user` → non-owner 404). 17 api
  tests (`test_exercise_teacher_api.py`): happy CRUD + publish gate + full negative matrix (anon→401,
  student→403, cross-teacher→404) green. Self-reviewed vs the code-reviewer checklist; security-auditor budget
  reserved for the E5/E8 gates.
- [x] **E5** — ✅ student endpoints in `views_exercises.py` (7): list / detail(solving, never reveals) /
  draft(autosave, `DRAFT` status, migration `0025`) / image(type+size, path-safe) / submit(deadline+duplicate
  409, race-safe) / result(reveal-gated) / «پاسخ تمرین‌های تمام‌شده» answers browse. Reveal rule single-sourced
  in `_reveal_open` (deadline-passed OR no-deadline+own-GRADED); leak-safe serializers (`_q_for_solving` never
  carries the reference answer). 22 api tests (phone-scope 404/400, anon 401, leak guards on detail/list/result/
  browse, submit/deadline/duplicate). **security-auditor gate PASSED** (cleared, no blocking findings); Low-1
  (`result` passthrough) closed proactively via `_result_for_student` + test; **Low-2 (image MIME sniffing)
  carried to E6** — add magic-byte check when the grader feeds answer images to the LLM; **E6 pre-condition:
  grader must not write reference_answer/grading_notes into `result['per_question']`.**
- [ ] **E6** — grading service + task (`exercise_grading`, batch env, deterministic MCQ/fill-blank, retry
  idempotent, `EXERCISE_LLM_GRADING` kill-switch). Mocked grading + idempotent re-run + GRADING_FAILED.
  **Carry-ins from E5 security gate:** (Low-1) the grader must NOT persist `reference_answer`/`grading_notes`
  into `result['per_question']` (it is student-echoed); (Low-2) add magic-byte image sniffing before feeding
  answer images to the LLM. Also wire the grading dispatch into `StudentExerciseSubmitView` (hook is marked).
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
