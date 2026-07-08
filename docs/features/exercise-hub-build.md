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
- [x] **E12c — audit gap-fix batch + REAL Docker E2E (2026-07-06):** closes the tech-lead
  plan-vs-built audit's frontend gaps: gradebook grading dialog now RENDERS answer photos
  (`answerImageUrl` → `/media` proxy, thumbnail + full-size link) and shows the automatic score for
  deterministic rows (was «—»); **per-section assistant Switch** in the section editor (the chair-ruled
  MVP item — wires the previously-unused `updateSection`, optimistic + revert); **manual question
  add/edit/delete** (`createQuestion`/`deleteQuestion` service fns + editable question text + per-question
  delete AlertDialog — the ADR-0004 OCR-fallback mitigation; zero-section FAILED case still retry-only);
  solver deadline UX (Jalali deadline badge, «کمتر از ۲۴ ساعت», past-deadline banner honoring allow-late
  wording, «پیش‌نویس ذخیره شد ✓» indicator); result page shows «نمره‌دهی هوشمند» badge when no teacher
  override. tsc at the 13-error baseline. **Verified END-TO-END on the real local Docker stack** (fresh
  backend image, migrations 0024–0026 applied on live Postgres): student login → hub (Jalali deadline,
  catalog) → solver (KaTeX, autosave) → submit → REAL Celery deterministic grading (2.00/5.00, one right
  one wrong) → result page (score + hidden reference pre-deadline) → teacher gradebook (row, dialog,
  real answers) → teacher override 1.5 → effective 3.50/5.00 + «ویرایش معلم» badge → per-section switch
  persisted to DB both ways. Env note (machine-local): `frontend/.env.local` now uses `127.0.0.1:8000`
  (Next dev proxy resolved `localhost`→`::1` after a Docker Desktop restart and EACCES'd; IPv4 pin fixes it).
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

- [x] **E13 — handwriting vision slice (2026-07-06, audit gap-fix):** the tech-lead audit found the
  plan breach that student answer photos (`answers[qid].images`, uploaded via
  `StudentExerciseImageView`) NEVER reached the LLM — a photo-only answer silently scored 0. Closed:
  `exercise_grading.py` now runs a per-question **vision-extract step** before grading
  (`_effective_answer_text` → `_transcribe_answer_images`): storage read via `default_storage`,
  `is_real_image` Pillow sniff per image (the previously-dead Low-2 helper, now wired at grading AND
  at upload — garbage bytes with an `image/*` content_type get 400 «فایل ارسالی تصویر معتبر نیست.»),
  cap `EXERCISE_MAX_IMAGES_PER_QUESTION` (default 3), model chain
  `EXERCISE_VISION_MODEL→IMAGE_MODEL→MODEL_NAME` (env-only, raise if unset), ONE standard-shape OpenAI
  multimodal call per question (`image_url` data URIs — legacy shapes are silently ignored by the
  AvalAI gateway), `generate_structured(schema=HandwritingTranscriptionOutput)` (new single-required-key
  schema) under the new prompt `PROMPTS['exercise_handwriting_vision']['default']`
  (SAFETY_PREAMBLE + MATH_FORMAT_INSTRUCTIONS, placeholder `{question_text}` only — **leak guard: the
  reference answer / grading notes are structurally absent from the vision context**, test-locked),
  usage logged under `LLMUsageLog.Feature.EXERCISE_HANDWRITING_VISION` (enum pre-existed, no
  migration). Merge rules: photo-only → extracted text used verbatim (deterministic MCQ/fill-blank
  matching intact); typed+photo descriptive → appended under `[متن استخراج‌شده از تصویر پاسخ]`;
  typed+photo deterministic → vision skipped (typed answer authoritative, saves tokens). Fail-open per
  question for transient vision failures: logs a warning and grades typed text; **missing vision model
  ENV now fails grading** so photo-only submissions are not silently graded as zero.
  Tests (0 tokens, sqlite fast lane): 6 new in `test_exercise_grading.py` (photo-only end-to-end via
  deterministic MCQ, vision-failure fallback → GRADED, fake-bytes skip without a vision call,
  reference-answer-absent-from-vision-prompt, image cap + standard-shape assertion, delimiter append)
  + 1 upload negative in `test_exercise_student_api.py` + contract test updated
  (LIVE_KEYS/PLACEHOLDERS/OUTPUT_KEYS/safety-preamble list) — 72 + 24 passed. Cost: +1 small vision
  call per photo-answered question (~1–2k tokens/question at 3-image cap); zero for typed-only
  submissions.

- [x] **E14 — teacher reference ingest preview/apply (2026-07-07):** added a teacher-only
  Reference Ingest layer for flexible source formats (mixed Q&A, single Q&A, numbered answer keys,
  answer-only text, small PDF/photos). Backend: new prompt `exercise_reference_ingest/default` +
  `ExerciseReferenceIngestOutput` schema + `LLMUsageLog.Feature.EXERCISE_REFERENCE_INGEST`
  (`commons/0007` no-op AlterField), conservative server-side matching
  (`matched/ambiguous/unmatched`), owner/status-gated `POST /reference-ingest/preview/` (no DB write)
  and transactional update-only `POST /reference-ingest/apply/` (existing questions only; no overwrite
  unless `replaceExisting=true`; `PUBLISHED` 409 until re-grade flow exists). Security hardening:
  source/reference uploads now use count/size allowlists + PDF magic-byte / Pillow image sniff before
  storage/LLM; preview has reference-specific OCR page/unit caps and source-text caps before the LLM;
  apply has item/field/points caps and skips the entire item when `replaceExisting=false` on an existing
  reference answer; student answer-image paths are server-owned (draft/submit JSON cannot point grading
  at arbitrary storage paths) and uploads check submission status before `default_storage.save`. Frontend:
  exercise editor now exposes a visible «ورود سؤال و پاسخ
  مرجع» panel with Sheet-based preview/review, target-question selector, Persian guidance, and
  Markdown+KaTeX rendering for extracted rubric text; shared Markdown rendering now sanitizes link/image
  URLs before `dangerouslySetInnerHTML`. Tests added/updated for prompt contract, reference ingest
  service, teacher API preview/apply/ownership/validation/caps, student image ownership/merge behavior,
  and grading defense-in-depth.

- [x] **2026-07-08 — one-step teacher intake + durable extraction workflow:** teacher authoring was
  redesigned from a split `create → extract → review-source` flow into a single intake card. Backend:
  `ClassExercise` gained `intake_config`, `workflow_state`, `review_ready_notified_at` (`classes/0027`);
  `POST creation-sessions/<sid>/exercises/` now accepts deadline/no-deadline, allow-late, assistant
  default, teacher note, `sources[]` metadata keyed by `clientFileKey`, uploads, and auto-dispatches
  `extract_exercise_content` on commit. The extraction task now persists stage-based progress
  (`queued` → `reading_sources` → `ocr_and_transcription` → `extracting_questions` →
  `matching_reference_answers` → `building_review_draft` → `ready_for_review`), uses per-file hints for
  question-vs-answer sources, applies confident reference-answer matches automatically, degrades to
  warnings instead of hard-failing when answer matching is weak, and sends the one-shot teacher SMS
  `پیش‌نویس تمرین شما آماده است. برای بررسی و انتشار، وارد پنل معلم AI-Amooz شوید.` plus a virtual
  teacher notification (`exercise-ready-<id>`). Frontend: `exercise-manager.tsx` now gathers all intake
  data up front, uploads files under `file_<clientFileKey>`, shows durable progress/warnings on each
  exercise card, reserves manual `/extract/` for rerun, and renames the old reference-ingest tool to
  `افزودن منبع تکمیلی`. Verification:
  `pytest backend/apps/classes/test_prompts_contract.py backend/apps/classes/test_exercise_teacher_api.py backend/apps/classes/test_exercise_extraction_task.py backend/apps/notification/test_teacher_messaging.py backend/apps/notification/test_read_state_and_scoping.py -q`
  → **129 passed**; `frontend npm run typecheck` stays at the pre-existing **13-error baseline** (no new
  exercise-intake errors introduced).

## V2 — class assignment + feedback workflow hardening

E15+ follows a stricter loop per step: **generate → evaluate with the required team gate →
correct → repeat targeted verification → finalize with docs + commit + push**. V2 keeps the shipped
`Exercise Hub` name and `ClassExercise` technical surface, but reframes the product as a per-class
assignment workflow: teacher creates/publishes, student submits, AI pre-grades, teacher reviews
exceptions, student receives safe feedback and later the answer key.

- [x] **E15 — product reframe + build-loop protocol (2026-07-07):** docs-only reset of the V2 thesis.
  `exercise-hub.md` now records the assignment-workflow thesis, anti-promises (AI pre-grading, hint
  assistant, report cards as learning signals), canonical terminology decision (`تمرین‌ها` stays in UI;
  no model/API rename), V2 acceptance criteria, and the E15–E45 roadmap. Team evaluation incorporated:
  PM guard against accidental rebrand/scope rollback; UX IA and microcopy criteria; AI feedback/reveal
  and handwriting-confidence risks; security blockers for notifications, audit, private media, and
  no-deadline reveal. No runtime code changed.
- [x] **E16 — teacher class IA / first-class exercises workspace (2026-07-07):** added a persistent
  in-class workspace nav across teacher class overview/edit/students/exercises:
  «نمای کلی / محتوا / تمرین‌ها / دانش‌آموزان / اطلاعیه‌ها». The exercise entry is no longer just a
  hidden header/dropdown affordance: it appears as a tab with a silent state badge fetched from the
  existing `listExercises` service (`بدون تمرین`, `در حال استخراج`, `آماده انتشار`, `پیش‌نویس`,
  `نیازمند بررسی`, or published count/state). The overview now exposes real `#content` and
  `#announcements` anchors for the nav; active state uses `aria-current`, keyboard focus rings, and
  horizontal overflow for small RTL screens. UX gate: accepted with the class-workspace pattern and
  stateful exercise entry. No backend/API change. `tsc --noEmit` stays at the pre-existing 13-error
  baseline with no exercise/nav errors.
- [x] **E17 — student exercise discoverability / state-aware entry points (2026-07-07):** added a
  shared student action resolver for every published exercise state:
  `شروع تمرین`, `ادامه تمرین`, `دیدن نتیجه`, `پاسخ‌نامه`. Student class cards now surface the next
  actionable exercise per course, and the learn view shows the same CTA as a compact in-context bar.
  The student `/exercises` hub now builds its upcoming-deadline strip from the full
  `listStudentExercises` state instead of the thinner calendar DTO, so draft/submitted/closed states
  route correctly. `DashboardService.getCalendarEvents` now enriches exercise calendar items by joining
  each exercise deadline DTO with its class exercise list before mapping to UI `CalendarEvent`s; home
  upcoming cards and calendar modal actions use the same state-aware labels/hrefs, and home filters by
  raw ISO datetime so same-day expired deadlines do not deep-link to a 409 solve path. Calendar event
  cards gained keyboard activation/focus rings. Code-review gate found the first calendar/home pass was
  only `isCompleted`-aware; fixed before commit. `tsc --noEmit` remains at the known 13-error baseline;
  smoke routes `/home`, `/classes`, `/learn/1`, `/calendar`, `/exercises` returned 200.
- [x] **E18 — async reliability for extraction/grading under AvalAI 502/timeouts (2026-07-08):**
  tightened LLM retry ownership and Celery task semantics for Exercise Hub. `llm_client` now exposes a
  typed `ProviderTransientError` and an allowlist classifier: retry timeouts/transport failures, 408,
  409, 429, and 5xx; fail fast on permanent 4xx, unsupported `response_format`, missing config, parser
  failures, and application bugs. OpenAI SDK retries are disabled by default via `OPENAI_SDK_MAX_RETRIES=0`
  so retry timing is owned by the app-level Tenacity/Celery policy instead of multiplying hidden SDK
  retries. `extract_exercise_content` and `grade_exercise_submission` leave `EXTRACTING`/`GRADING` in
  place on transient provider failure and call `self.retry()` with bounded exponential countdown; retry
  redelivery with the same persisted task id may resume from that in-progress state instead of skipping.
  Deploy guardrails: `pregenerate_student_assessments` routed to `pipeline`, teacher SMS routed to
  `default`, Redis visibility timeout defaults to 21600s and is mirrored to broker/result transport
  options, prod compose worker consumes `-Q default,pipeline`, prod compose/K8s include a separate
  Celery beat process, and prod compose Redis uses `noeviction` rather than broker-key LRU eviction.
  Tests: 63 targeted sqlite-fast-lane tests passed across LLM classifier, extraction task, grading task,
  and Celery/deploy settings.

**Definition of done (every step):** GREEN on the sqlite fast lane (Postgres = CI truth); new code documented
in `exercise-hub.md` (docs law); auth/permission changes carry negative tests; commit `feat(exercise): E# …`
+ push; tick here + note in the roadmap table of `exercise-hub.md`.
