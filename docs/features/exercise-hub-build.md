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
- [x] **E6** — ✅ grading `services/exercise_grading.py` + task `grade_exercise_submission` (pipeline queue) +
  dispatch wired into `StudentExerciseSubmitView` (`transaction.on_commit`). `PROMPTS["exercise_grading"]`
  (single `{grading_items_json}` placeholder, `per_question` output = final-exam score shape) +
  `ExerciseGradingOutput` schema + contract test updated. **MCQ/fill-blank graded deterministically (no LLM)**,
  descriptive batched by `EXERCISE_GRADING_BATCH_SIZE` (5), totals via `sum()`, model env-only
  `EXERCISE_GRADING_MODEL→MODEL_NAME`, `cache.add`+status-guard idempotency, `EXERCISE_LLM_GRADING` kill-switch
  (off→stays SUBMITTED), SUBMITTED→GRADING→GRADED/GRADING_FAILED. **E5 carry-ins done:** Low-1 — reference
  answer/grading_notes NEVER written into `result['per_question']` (test locks it); Low-2 — `is_real_image`
  Pillow magic-byte sniff. 13 tests (happy sum, MCQ-no-LLM, idempotent, GRADING_FAILED, kill-switch, no-leak,
  image sniff) + contract green (62).
- [x] **E7** — ✅ teacher gradebook + student report cards in `views_exercises.py`: `GET exercises/<eid>/
  submissions/` (owner-scoped list) + `GET submissions/<id>/` (detail) + `PATCH submissions/<id>/override/`
  (**writes teacher_score/teacher_feedback beside an IMMUTABLE llm_score**; recomputes effective `score_points`
  = teacher_score-if-set-else-llm_score; `overridden_at`) + `POST submissions/<id>/allow-redo/` (reset→DRAFT,
  keeps answers). Student: `GET student/courses/<sid>/report-card/` + `GET student/report-card/` — average =
  mean of the student's GRADED-exercise percentages (no-submission past-deadline excluded, not zeroed). No
  model change → no migration. 12 api tests (override-keeps-llm + recompute-8.00, owner/phone negatives,
  allow-redo owner-only, course/overall averages). **In-app notifications DEFERRED** to a thin follow-up
  (reusing `TeacherNotification`/`ClassAnnouncement` + phone-recipient resolution is non-trivial; kept out to
  avoid a rushed half-build — tracked as E7b / phase-2 candidate).
- [x] **E8** — ✅ assistant chat: `services/exercise_assistant.py` (`build_question_context(reveal=…)` —
  reference answer enters context ONLY post-reveal; MemoryService per (exercise,question,student); env-only
  `EXERCISE_CHAT_MODEL→CHAT_MODEL→MODEL_NAME`, graceful fallback) + `POST …/exercises/<eid>/assistant/` in
  `views_exercises.py` (phone-scope + **two-level server toggle** `exercise AND section` → 403
  `assistant_disabled`) + `PROMPTS["exercise_assistant_chat"]` ({content,suggestions}) + `AssistantChatOutput`
  schema + contract test. **security-auditor gate PASSED** (structural leak guard + toggle + phone-scope +
  injection posture verified); Low-1 fixed (model-unset → graceful, not 500) + 2 negatives added
  (cross-exercise IDOR, model-unset). 15 tests (incl. context-guard both directions) + contract green.
- [ ] **E9** — migration `0025` (`scheduled_at` on session) + `GET student/calendar/` aggregate endpoint.

## Frontend
- [ ] **E10** — teacher UI: service + upload wizard + gradebook + override + toggles. `tsc` clean.
- [ ] **E11** — student UI: exercises hub + solver (text/photo) + assistant widget + report cards +
  finished-answers browse. `tsc` clean; RTL/KaTeX.
- [ ] **E12** — calendar: remove mock, wire service + Jalali conversion + exam-prep events. `tsc` clean.

**Definition of done (every step):** GREEN on the sqlite fast lane (Postgres = CI truth); new code documented
in `exercise-hub.md` (docs law); auth/permission changes carry negative tests; commit `feat(exercise): E# …`
+ push; tick here + note in the roadmap table of `exercise-hub.md`.
