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
- [x] **E9** — ✅ **BACKEND COMPLETE.** migration `0026` (nullable `scheduled_at` on `ClassCreationSession`,
  pure DDL — **database-engineer approved**: metadata-only Postgres add, no index needed) + `GET
  student/calendar/` aggregate in `views_exercises.py`: phone-scoped events = published exercise deadlines of
  enrolled classes + scheduled exam-prep sessions; Tehran-tz ISO datetime (Jalali in frontend), `isCompleted`
  from submission/attempt, `from`/`to` window filter. 9 api tests (both kinds, excludes-non-enrolled,
  isCompleted both ways, from/to filter, no-phone 400, anon 401, no-deadline excluded) green.

## Frontend
- [x] **E10** — ✅ teacher UI: `src/services/exercises-service.ts` (fully typed — all E4/E7 teacher endpoints
  via the service layer, `NEXT_PUBLIC_API_URL` guard, 401-refresh, multipart upload) + `components/teacher/
  exercises/exercise-manager.tsx` (list + create/upload + extraction **polling** + per-question
  reference-answer/points editor + assistant/deadline settings + publish/delete with AlertDialog) +
  `gradebook-table.tsx` (submissions matrix, **sticky name column right** for RTL, override dialog with
  llm-score-shown + teacher override + allow-redo) + route `my-classes/[classId]/exercises/page.tsx`. Persian
  microcopy from the spec; empty/loading/error states. **`tsc --noEmit` clean** for all exercise files (total
  stays at the pre-existing 13-error baseline — none introduced). Runtime preview deferred to E12/final.
- [x] **E11** — ✅ student UI: `exercises-service.ts` extended with all student endpoints (list/detail/draft/
  submit/image/result/report-card/finished-answers/assistant/calendar, fully typed) + `components/dashboard/
  exercises/{exercise-solver,exercise-assistant,exercise-report-card}.tsx` + routes `(dashboard)/exercises/
  {page (hub: overall report card + upcoming deadlines from calendar), [exerciseId]/page (solver: per-section
  chips, text + camera-capture image answer, debounced draft autosave, section-aware assistant widget with
  «دستیار برای این بخش غیرفعال است», submit AlertDialog), [exerciseId]/result/page (own scores/feedback;
  reference answers only when `answersRevealed`), answers/page (finished-answers browse)}`. Question text via
  `MarkdownWithMath` (KaTeX). **Client leak guard:** the solver never requests/renders the reference answer
  (backend withholds it); only result/answers show it post-reveal. **`tsc --noEmit` clean** for all exercise
  files (total stays at the 13-error baseline). Runtime preview deferred to E12/final.
- [x] **E12** — ✅ **FRONTEND + FEATURE COMPLETE.** Dashboard homepage calendar wired from mock to the
  real `getStudentCalendar` endpoint (E9): `DashboardService.getCalendarEvents` now fetches
  `CalendarEventDto[]` and maps each to the UI `CalendarEvent` via a new `toCalendarEvent` helper —
  Tehran-tz ISO → zero-padded **Jalali** `YYYY-MM-DD` + `HH:MM` (`Intl` `calendar:'persian'`,
  `timeZone:'Asia/Tehran'`, `numberingSystem:'latn'` so days never drift & lexical date compare stays
  chronological), `kind` → `type`/`priority` (`exam_prep`→exam/high, `exercise_deadline`→assignment/med,
  completed→low), `isCompleted` passed through; undated events dropped; empty-safe when
  `NEXT_PUBLIC_API_URL` unset. `MOCK_CALENDAR_EVENTS` import + fake 500ms delay removed. No new CSS
  tokens (events reuse existing type/priority styles). **`tsc --noEmit` clean** (stays at the 13-error
  baseline — none introduced); conversion verified in Node against 4 cases incl. tz day-boundary + Nowruz
  1405. No backend/model change.
- [x] **E12b — navigation wiring fix (2026-07-05, user-reported):** E10/E11 pages existed but were linked
  from NO menu. Added: student «تمرین‌ها» in `DASHBOARD_NAV_LINKS` (desktop header + mobile bottom nav,
  subroute-aware active state) · teacher «تمرین‌ها» button in `ClassDetailHeader` **and** class-card
  dropdown (both guarded `basePath === '/teacher'` — admin has no exercises route) · student hub rebuilt
  with the complete per-class catalog (`listStudentExercises` — no-deadline exercises now visible) +
  `allowLate` added to the backend student list (+regression test) so window-closed exercises route to
  «مشاهدهٔ پاسخ‌ها» not a 409 dead-end · GRADING_FAILED result now returns failure-specific Persian detail ·
  REMOVED the legacy create-class «بارگذاری تمرین / کامینگ سون» placeholder (FileUploadSection lesson-only,
  step pill «۲. فایل درسی», subtitle updated) · reviewed by ux-designer + code-reviewer (all must/should-fix
  applied). tsc at 13-error baseline; student-api+reportcard tests green on real Postgres.

**Definition of done (every step):** GREEN on the sqlite fast lane (Postgres = CI truth); new code documented
in `exercise-hub.md` (docs law); auth/permission changes carry negative tests; commit `feat(exercise): E# …`
+ push; tick here + note in the roadmap table of `exercise-hub.md`.
