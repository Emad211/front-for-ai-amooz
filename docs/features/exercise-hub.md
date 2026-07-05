# Exercise Hub («بخش تمرین») — per-class teacher-authored exercises with LLM grading, a toggleable AI assistant, report cards, and a real calendar

- **Status:** Approved (council 2026-07-05) · **Created:** 2026-07-05 · **Last-verified:** 2026-07-05
- **Owner:** product-manager · **Spec by:** council (product-manager, tech-lead [chair], ai-engineer, ux-designer) · **Built by:** E1–E12 roadmap below
- **ADR:** [ADR-0004](../adr/ADR-0004-exercise-hub.md)

## Problem
Teachers (TEACHER) have no way to assign real homework/exercises inside a class: today the platform only
has auto-generated quizzes/final exams (adaptive) and the separate exam-prep pipeline. Students (STUDENT)
have no per-class exercise area, no report card, and the dashboard calendar renders **mock data**
(`MOCK_CALENDAR_EVENTS` in `dashboard-service.ts` — no backend endpoint, no deadline field anywhere).

**Mental model (important):** an exercise is **teacher-authored, static content** (uploaded PDF/photos →
LLM extraction → teacher edits → publish). It is NOT a quiz — there is **no adaptive regenerate loop**
here, deliberately.

## Stories & acceptance criteria (condensed — testable)
- **T1 ساخت تمرین:** teacher uploads PDF/images → structured questions extracted, **editable before
  publish**; corrupt file → Persian error, no half-created exercise.
- **T2 پاسخ‌مرجع:** publish is **blocked (400)** while any question lacks `reference_answer_markdown`
  or `max_points` — reference answers are the grading rubric; without them grading is meaningless.
- **T3 مهلت:** deadline set → appears in student list + calendar; no-deadline exercises are allowed
  (always open, no calendar event).
- **T4 toggle دستیار:** assistant off (exercise-level OR section-level) → student chat request gets
  **403 `assistant_disabled` server-side** (UI hiding alone is not enforcement).
- **T5 کارنامه + override:** teacher can override any grade; override labeled «بازبینی‌شده توسط مدرس»;
  the original LLM score is **kept (audit, teacher-only)**; student gets a notification.
- **S2 ارسال:** text and/or handwriting photos per question; unanswered questions → non-blocking
  Persian warning; submit after deadline → **409 server-side**; one final submission
  (unique(exercise, student)); resubmission only if the teacher explicitly allows (reset pattern).
- **S4 دستیار:** before grading the assistant gives hints but **cannot reveal the answer even under
  prompt injection** — structurally impossible: reference answers are stripped from its context.
- **S5/S6 کارنامه + تقویم:** per-exercise report + per-class average (own data only); calendar shows
  real exercise deadlines (+ scheduled exam-preps) instead of mock.

## Scope
- **In (MVP):** create/extract/edit/publish flow (PDF + photos); reference answers (extracted-if-present,
  teacher-edited, mandatory); deadlines; **assistant toggle at BOTH exercise and section level** (chair
  ruling — explicit owner requirement; PM's defer-to-phase-2 dissent recorded); text + handwriting-photo
  submissions; async LLM grading with teacher rubric + deterministic grading for MCQ/fill-blank; teacher
  override with audit; per-exercise + per-class report cards (simple average); teacher gradebook matrix;
  in-app notifications (publish, graded); real calendar endpoint + frontend wiring.
- **Out (explicitly):** adaptive/regenerate loop for exercises; live proctoring; class-session events in
  the calendar (no meeting model exists); cross-student comparisons shown to students.
- **Later phases (named, deferred):** weighted combined report card (exercise+quiz+final exam) — weighting
  policy is a real product decision; SMS deadline reminders (Mediana cost + Celery beat scheduling);
  per-student deadline extensions; per-exercise grade weights; teacher review-gate before grade release;
  separate answer-key upload (`exercise_structure.answer_key` strategy); report-card PDF export
  (WeasyPrint); auto late-penalty.

## Policies (product — decided in council)
- **Late submissions:** closed at deadline by default; per-exercise toggle «پذیرش ارسال با تأخیر» →
  allowed but flagged «ارسال با تأخیر» on both sides. Auto-penalty = phase 2.
- **Resubmission:** one final submission; drafts editable until final submit; after grading only the
  teacher can grant a redo (exam-prep reset pattern). Free resubmit = LLM cost × gaming.
- **Partial answers:** allowed with warning; unanswered questions score 0 for that question only.
- **Mid-progress join:** past-deadline exercises show «مهلت گذشته» and are **excluded from that
  student's average** (an unfair 0 kills trust); teacher can reopen by extending.
- **Assistant default: ON** (differentiator; opt-out for strict teachers, not opt-in). Toggling mid-work
  applies from the next message (per-request server check); chat history kept; banner shown.
- **Grades visible immediately** with the «نمره‌دهی هوشمند» label + teacher override afterwards
  (fast feedback is the core value); optional per-exercise review-gate = phase 2.
- **Reference answers revealed only after the deadline passes** (owner decision 2026-07-05): the
  student's own score + feedback show immediately on grading, but the correct/reference answers unlock
  when `deadline < now` (for a no-deadline exercise: on the student's own GRADED submission). This closes
  the leak window — an early submitter cannot see the answers while classmates are still within the
  deadline. A dedicated **«پاسخ تمرین‌های تمام‌شده»** area lets students browse the answers of past
  (deadline-passed) exercises.
- **Report-card formula (MVP):** simple average (normalized 0–100) of graded exercises of that class.
  Teacher-only extras: class distribution/average, override history + raw LLM scores, late flags,
  full LLM rationale, non-submitters list.

## Design (technical) — see ADR-0004
- **Models live in `apps/classes`** (FK to `ClassCreationSession`; ownership/phone-scope/publish-gate all
  derive from the parent session). God-file guard: all new views in **`views_exercises.py`**, services in
  `services/exercise_*.py` — not one line added to `views.py`.
- **Ingest is async** on the **`pipeline`** queue: upload → DRAFT → `POST /extract/` → EXTRACTING →
  EXTRACTED → teacher review/edit → reference answers → publish. `cache.add` idempotency + status guards;
  failure → FAILED + re-runnable.
- **Grading is on-submit async** on the `pipeline` queue (not sync = timeout; not nightly batch =
  pointless UX delay). One `generate_structured` call per batch of `EXERCISE_GRADING_BATCH_SIZE`
  (default 5) questions; **MCQ/fill-blank graded deterministically without LLM**; totals computed with
  `sum()` never by the model; retries idempotent (status-guard + persisted `grading_task_id`);
  kill-switch env `EXERCISE_LLM_GRADING` (default on) → submissions stay SUBMITTED for manual grading.
- **Override:** `teacher_score`/`teacher_feedback` written alongside `llm_score` inside
  `result['per_question']`; `llm_score` never overwritten; final `score_points` recomputed.
- **Assistant leak guard is structural:** before grading the reference answer is **not in the model's
  context at all** (server strips it) — a model that never saw the answer cannot leak it under
  injection. After grading (`{phase}=graded`) reference+feedback enter the context so the assistant can
  teach the solution (adaptive-loop reveal precedent).
- **Toggle semantics:** effective = `exercise.assistant_enabled AND section.assistant_enabled`
  (simple AND, no nullable-inherit).

## Data
| Model | Key fields | Constraints |
|---|---|---|
| `ClassExercise` | session FK CASCADE · title · description · Status{DRAFT,EXTRACTING,EXTRACTED,PUBLISHED,FAILED} · `deadline` (DateTime, null — first real deadline field in the platform) · `allow_late` (bool, default False) · `assistant_enabled` (bool, default True) · `extract_task_id` | index (session, status) |
| `ClassExerciseAsset` | exercise FK · kind{pdf,image} · file · order | — |
| `ClassExerciseSection` | exercise FK · order · title · `assistant_enabled` (bool, default True) | uniq (exercise, order) |
| `ClassExerciseQuestion` | section FK · order · `question_markdown` · `question_type{descriptive,multiple_choice,fill_blank}` · `options` JSON null · `reference_answer_markdown` · `max_points` Decimal · `grading_notes` | uniq (section, order) |
| `StudentExerciseSubmission` | exercise FK · student FK · Status{SUBMITTED,GRADING,GRADED,GRADING_FAILED} · `answers` JSON (text + image storage paths per question) · `result` JSON (`per_question`: llm_score/llm_feedback/teacher_score/teacher_feedback) · `score_points` · `max_points` snapshot · `is_late` · `grading_task_id` · `graded_at` · `overridden_at` | **uniq (exercise, student)** |

Migrations (all pure DDL, DML/DDL split respected, reversible with no backfill): `classes/0024_exercises`
(CreateModel + constraints), `classes/0025_exercise_submission_draft` (adds `DRAFT` to the submission
status — no-op AlterField), `classes/0026_session_scheduled_at` (adds nullable `scheduled_at` to
`ClassCreationSession` for timed exam-prep calendar events — **database-engineer approved**: metadata-only
add on Postgres, no rewrite/long lock, no index needed since the calendar query is pre-filtered by
`invites__phone` + indexed `pipeline_type`; rollback = `migrate classes 0025`). Feature-enum additions ride
`commons/0006` (no-op AlterField).
`LLMUsageLog.Feature` choices additions generate a no-op AlterField migration (coordinate with
database-engineer).

## API (contract-first; teacher = `[IsAuthenticated, IsTeacherUser]` + `session__teacher=request.user` → non-owner **404**; student = `[IsAuthenticated, IsStudentUser]` + `session__is_published=True, session__invites__phone, exercise.status=PUBLISHED` → **404**, no-phone → **400**)

**Teacher** (all under `/api/classes/…`, implemented in `views_exercises.py`):
- `POST creation-sessions/<sid>/exercises/` (+ asset upload) · `GET exercises/` · `GET exercises/<eid>/`
- `POST exercises/<eid>/extract/` (409 while EXTRACTING) · `POST exercises/<eid>/publish/` (400 if any
  question lacks reference answer/points; 409 wrong status)
- `PATCH exercises/<eid>/` (title/deadline/allow_late/**assistant_enabled**) ·
  `PATCH exercises/sections/<id>/` (**assistant_enabled**) · CRUD `exercises/<eid>/questions/`
  (content edits after PUBLISHED trigger the re-grade warning flow)
- `GET exercises/<eid>/submissions/` · `GET submissions/<id>/` · `PATCH submissions/<id>/override/`
- `POST submissions/<id>/allow-redo/` (teacher-granted resubmission)

**Student**:
- `GET student/courses/<sid>/exercises/` · `GET …/exercises/<eid>/` — serializers **never** include
  `reference_answer_markdown` (or LLM rationale) before that student's submission is GRADED (explicit
  leak tests)
- `PUT …/exercises/<eid>/draft/` (autosave) · `POST …/exercises/<eid>/questions/<qid>/image/` (type/size
  validated server-side) · `POST …/exercises/<eid>/submit/` (**409 after deadline** unless allow_late;
  duplicate → 409)
- `GET …/exercises/<eid>/result/` (after GRADED: own per-question score/feedback; **reference answers
  included only once the reveal condition holds — `deadline < now`, or no-deadline + own submission
  GRADED**) · `POST …/exercises/<eid>/assistant/` (server guard: both toggles AND; 403 code
  `assistant_disabled`; context never contains reference answers pre-grading)
- `GET student/courses/<sid>/report-card/` · `GET student/report-card/` (overall) ·
  `GET student/exercises/answers/` (the «پاسخ تمرین‌های تمام‌شده» browse — lists only deadline-passed
  exercises of enrolled classes with their reference answers + the student's own submission if any)
- `GET student/calendar/?from=&to=` — aggregate: published exercise deadlines of enrolled classes +
  invited exam-prep sessions with `scheduled_at`. Response items:
  `{id, kind: 'exercise_deadline'|'exam_prep', title, courseTitle, datetime (ISO, Tehran tz), isCompleted}`.
  **Jalali conversion happens in the frontend service layer** (`date-utils`), backend stays Gregorian.

Every row above ships with negative tests (anonymous/wrong-role/cross-teacher/cross-student/no-phone) —
security-auditor gates E5 and E8.

## LLM
**Prompt keys (PROMPTS — byte-for-byte contract; update `test_prompts_contract.py` LIVE_KEYS +
PLACEHOLDERS + OUTPUT_KEYS + safety-block list in the same commit):**
- `exercise_structure` / `default` — Markdown (from reuse of `pdf_extraction.default`, per-page for both
  PDF pages and photos) → structured exercise. Parsed with
  `generate_structured(schema=ExerciseStructureOutput)`. Output contract:
  `exercise_title, sections[{section_id,title,questions[{question_id,question_text_markdown,question_type,options,points,reference_answer_markdown}]}]`
  (`points`/`reference_answer_markdown` nullable — extracted if present, teacher always wins).
  Phase 2: strategy `answer_key` (`{questions_json}` placeholder).
- `exercise_grading` / `default` — placeholder **`{grading_items_json}`** =
  `[{question_id, question_text, reference_answer, max_points, student_answer}]`; +`SAFETY_PREAMBLE` +
  student-answer-is-DATA injection guard. Output:
  `per_question[{question_id, score_points, max_points, label(correct|partially_correct|incorrect), feedback, missing_points}]`
  — deliberately the **same score shape as the final exam**, so `compute_weak_points_from` and report
  aggregation reuse without new parsers. (`text_grading` was evaluated and is insufficient: 0–100
  single-question scale, hard no-reveal rule, no batching.)
- `exercise_assistant_chat` / `default` — placeholders `{question_context} {student_work} {phase}
  {history} {user_message}`; output `{content, suggestions}` (frontend chat widget unchanged).
- **Reused verbatim (no new keys):** `pdf_extraction.default` (PDF pages AND uploaded photos — a photo
  is a page) and `exam_prep_handwriting_vision` (student handwriting photos → two-phase: vision extract →
  text grading; `unclear_parts` → UI asks the student to type the unclear part before submit; cost
  attributed via the `feature` call-site parameter, no prompt fork).

**Env (models are env-only; missing chain → raise, never a hardcoded name):**
`EXERCISE_STRUCTURE_MODEL→STRUCTURE_MODEL→MODEL_NAME` · `EXERCISE_GRADING_MODEL→MODEL_NAME` ·
`EXERCISE_VISION_MODEL→(handwriting chain)→MODEL_NAME` · `EXERCISE_CHAT_MODEL→CHAT_MODEL→MODEL_NAME` ·
`EXERCISE_GRADING_BATCH_SIZE=5` · `EXERCISE_MAX_IMAGES_PER_CALL` · `EXERCISE_LLM_GRADING=1` (kill-switch).
New `LLMUsageLog.Feature` members: `EXERCISE_INGEST, EXERCISE_STRUCTURE, EXERCISE_GRADING,
EXERCISE_HANDWRITING_VISION, CHAT_EXERCISE`.

**Cost model (10-page PDF, 20 questions, 30 students):** ingest ~15–25k + structure ~10–15k (once per
exercise); grading ~14k/student → **~420k tokens per class round = the dominant, recurring cost**.
Mitigations baked in: deterministic MCQ/fill-blank grading (up to ~80% saved on objective-heavy
exercises), grading only on final submit, answer-length env cap, report cards = pure aggregation over
stored `per_question` (zero tokens), **no pregeneration** (nothing to pre-build).

## UX (owner: ux-designer)
- **Entry points — AS BUILT (2026-07-05, post-E12 wiring fix):** the pages shipped in E10/E11 initially
  had NO navigation entry (user-reported). Wired now:
  - **Student:** «تمرین‌ها» item in `DASHBOARD_NAV_LINKS` (`constants/navigation.ts`) → `/exercises`;
    renders in the desktop header AND the mobile bottom nav (4 items; active state matches subroutes).
    The hub lists the **complete per-class catalog** via `listStudentExercises` (exercises without a
    deadline are visible — «بدون مهلت») + open future deadlines agenda + overall report card. Backend
    list now carries `allowLate`; window-closed exercises (deadline passed, no late) route to
    «مشاهدهٔ پاسخ‌ها» instead of a dead-end solver.
  - **Teacher:** «تمرین‌ها» button (NotebookPen) in `ClassDetailHeader` + a «تمرین‌ها» item in the
    my-classes `class-card` dropdown — both **guarded `basePath === '/teacher'`** (admin has no
    exercises route). The old create-class «بارگذاری تمرین / کامینگ سون» placeholder was REMOVED
    (`FileUploadSection` is lesson-only now; step pill = «۲. فایل درسی»).
  - Original design below said "tabs inside my-classes/[classId]" and an open-count class-card badge —
    the tab layout and count badge remain **unbuilt follow-ups**, as do: in-class student entry on the
    course page, `/exercises/answers?exercise=<id>` deep-link, «نمره‌دهی» wording unification.
- **Teacher nav (original design):** tabs inside `my-classes/[classId]`: «محتوا · تمرین‌ها · دانش‌آموزان ·
  اطلاعیه‌ها» (no new top-level menu). **Student nav:** standalone routes `(dashboard)/exercises`,
  `exercises/[exerciseId]`, `exercises/[exerciseId]/result` — URL-stable for calendar/home deep links;
  entry points: learn sidebar item, open-count badge on class cards, calendar/home.
- **Teacher wizard (4 steps, server-side draft, resumable):** ① info+upload (multi-file drag&drop) →
  ② extraction review (pipeline-tracker-style progress; accordion edit; merge/split/delete/add-manual;
  extraction error → retry OR **manual question entry fallback**) → ③ reference answers + points (live
  «جمع بارم» total) → ④ assistant toggles (whole + per-section switches; per-section disabled state when
  whole is off) + Jalali deadline + publish. After publish: deadline/toggles freely editable; content
  edits behind an AlertDialog re-grade warning.
- **Student solver:** sticky header (title, deadline badge with <24h countdown, draft-saved indicator);
  mobile = horizontal section chips (fade edge on the LEFT for RTL), desktop = side section list;
  per-question text/photo tabs (camera `capture` on mobile, client-side compression); autosave; sticky
  submit bar + confirm dialog; assistant = side panel (desktop) / bottom Sheet (mobile); assistant-off →
  informative lock chip («دستیار برای این بخش غیرفعال است»), never silently hidden; past-deadline →
  read-only + banner.
- **Report cards:** student per-exercise result (summary card + per-question own answer/reference/score/
  feedback, green/red start-bars from tokens); overall trend chart (recharts, Persian digits, Jalali);
  teacher gradebook matrix (row=student, column=exercise, **sticky name column on the RIGHT** —
  `right-0` not `left-0`), mobile = expandable list; cell click → submission detail with zoomable photos +
  override panel; overridden grades always badged «ویرایش معلم».
- **Calendar:** event kinds `exercise_deadline` (suggested `hsl(var(--chart-2))`) and `timed_exam`
  (`hsl(var(--destructive))`) — **verify `--chart-*` tokens exist in BOTH `:root` and `.dark` before
  build** (the `--primary-rgb` phantom-token lesson); status badges امروز/گذشته/آینده + «انجام نشد»;
  event modal CTA deep-links to the exercise/result.
- **Microcopy table (key strings):** empty.teacher «هنوز تمرینی برای این کلاس نساخته‌اید. اولین تمرین را با
  بارگذاری PDF یا عکس بسازید.» · empty.student «فعلاً تمرینی برای این کلاس ثبت نشده است.» ·
  extract.processing «در حال استخراج سوال‌ها از فایل شما… این کار ممکن است چند دقیقه طول بکشد.» ·
  extract.error «استخراج سوال‌ها ناتمام ماند. دوباره تلاش کنید یا سوال‌ها را دستی وارد کنید.» ·
  assistant.off.section «دستیار برای این بخش غیرفعال است» · assistant.off.all «دستیار هوشمند برای این
  تمرین در دسترس نیست» · deadline.badge «مهلت ارسال: ۱۵ تیر، ساعت ۲۳:۵۹» · deadline.passed «مهلت ارسال
  این تمرین گذشته است» · submit.confirm.body «پس از ارسال، امکان ویرایش پاسخ‌ها را نخواهید داشت. مطمئن
  هستید؟» · grading.pending «پاسخ شما ارسال شد. نتیجه پس از نمره‌دهی در همین‌جا نمایش داده می‌شود.» ·
  statuses «ارسال‌نشده / در انتظار نمره‌دهی / نمره‌دهی‌شده / ارسال با تأخیر / مهلت گذشته / بدون مهلت» ·
  grade labels «نمره‌دهی هوشمند» / «بازبینی‌شده توسط مدرس» · override.cta «ثبت نمرهٔ دستی» ·
  edit.regrade.warn «با تغییر سوال‌ها یا بارم، پاسخ‌های ثبت‌شده دوباره نمره‌دهی می‌شوند.» — all Persian
  digits + Jalali via `date-utils`.
- **New frontend files:** teacher routes `(teacher)/teacher/my-classes/[classId]/exercises/{page,new/page,[exerciseId]/page,[exerciseId]/submissions/[studentId]/page}.tsx`;
  student routes `(dashboard)/exercises/{page,answers/page,[exerciseId]/page,[exerciseId]/result/page}.tsx`
  (the `answers/` route = «پاسخ تمرین‌های تمام‌شده»);
  components `components/teacher/exercises/{exercise-list,exercise-wizard,extraction-review,rubric-editor,assistant-deadline-settings,class-gradebook-table,submission-grading-panel}.tsx`
  and `components/dashboard/exercises/{exercise-list,exercise-solver,section-nav,answer-input,exercise-assistant,exercise-report-card,grades-trend-chart}.tsx`;
  `services/exercises-service.ts`; hooks `use-exercises.ts, use-exercise-solver.ts, use-gradebook.ts`.
  Calendar: type + data wiring only (components exist).

## Roadmap — E1…E12 (one step per iteration; each committable + tested; docs updated in the same commit)

| # | Owner (+gate) | Scope | DoD |
|---|---|---|---|
| **E1** | backend (+database-engineer review) | 5 models + migration `0024` (pure DDL) + constraint/FK-behavior tests | migrations apply on fresh Postgres & sqlite; uniq/index/CASCADE tests green |
| **E2** | ai-engineer | `services/exercise_ingest.py` + `PROMPTS["exercise_structure"]` + Pydantic schemas + contract-test update | ✅ DONE — `structure_exercise_markdown` + `exercise_structure` prompt + `ExerciseStructureOutput` + 5 Feature enums (`commons/0006`) + contract test; 13 ingest tests + 60 contract green |
| **E3** | backend | `extract_exercise_content` task (pipeline queue) + state machine + `cache.add` idempotency | ✅ DONE — task + OCR (`ocr_assets_to_markdown`) + `persist_exercise_structure`; 7 eager tests (transitions/double-dispatch/FAILED/re-run/task-id) green |
| **E4** | backend | teacher endpoints (CRUD/extract/publish/toggles) in `views_exercises.py` | ✅ DONE — `views_exercises.py` + `serializers_exercises.py` + routes; create/list/detail/patch/delete(+S3 GC)/extract/publish/section-toggle/question-CRUD; 17 api tests (owner-404 + role + publish-gate) green |
| **E5** | backend (**security-auditor gate**) | student endpoints (list/detail/draft/submit/image) + deadline guard + no-leak serializers | ✅ DONE — 7 endpoints + `_reveal_open` + finished-answers browse + `DRAFT` status (mig 0025); 22 api tests; security gate PASSED (Low-1 fixed proactively, Low-2→E6) |
| **E6** | ai-engineer + backend | grading service+task (`exercise_grading`, batch env, deterministic MCQ/fill-blank, retry idempotent, kill-switch) | ✅ DONE — `exercise_grading.py` + `grade_exercise_submission` task + dispatch wired; deterministic MCQ + LLM batch + sum + kill-switch; E5 Low-1/Low-2 closed; 13 tests + contract green |
| **E7** | backend | result + report cards (per-exercise/per-course/overall) + teacher submissions list + override + allow-redo + in-app notifications (publish/graded) | ✅ DONE — gradebook (list/detail/override/allow-redo) + student course/overall report cards; override keeps `llm_score`, recomputes effective; 12 tests. **In-app notifications deferred to E7b** (recorded) |
| **E8** | ai-engineer (**security-auditor gate**) | assistant endpoint + two-level server guard + context builder (structural strip of reference answers) + `exercise_assistant_chat` | ✅ DONE — assistant chat + `build_question_context(reveal)` + two-level 403 toggle; security gate PASSED (Low-1 fixed); 15 tests + contract green |
| **E9** | backend (+database-engineer) | migration `0026` (`scheduled_at`) + `GET student/calendar/` aggregate | ✅ DONE — nullable `scheduled_at` (db-eng approved) + calendar endpoint (both kinds, Tehran-tz, isCompleted, from/to); 9 tests green. **Backend complete.** |
| **E10** | frontend-engineer | teacher UI: service + wizard + gradebook + override + toggles | ✅ DONE — exercises-service.ts + exercise-manager (create/extract-poll/edit/publish) + gradebook-table (override/allow-redo) + route page; tsc clean (baseline unchanged) |
| **E11** | frontend-engineer | student UI: exercises hub + solver (text/photo) + assistant widget + report cards | ✅ DONE — service (student endpoints) + hub/solver/result/answers pages + assistant/report-card; disabled-assistant chip; solver never fetches reference; tsc clean |
| **E12** | frontend-engineer | calendar: remove mock, wire service + Jalali conversion + exam-prep events | ✅ DONE — `getCalendarEvents` → real `getStudentCalendar` (E9); `toCalendarEvent` maps Tehran-tz ISO → Jalali `YYYY-MM-DD`+`HH:MM` (`Intl` persian/Asia-Tehran/latn) + kind→type/priority + isCompleted; mock + fake delay deleted; tsc clean; conversion Node-verified. **Exercise Hub feature COMPLETE (E1–E12).** |

Cross-cutting gates: `code-reviewer` on every non-trivial diff; `release-manager` at pushes; every step
updates this doc (docs law). Backend steps follow the sqlite-fast-lane/Postgres-truth test protocol of
ADR-0003.

## Testing
Per-step DoD above; patterns reused from the ADR-0003 suite: mock the module-bound `generate_text`
(0 tokens), negative permission tests for every endpoint row, eager-Celery orchestration tests, prompt
contract test updated with the three new keys. Avalai extraction accuracy on low-quality scans is
**deliberately untested locally** (VPN) — opt-in `benchmark`-marker test later.

## Security notes
**E5 security-auditor gate (2026-07-05): PASSED, cleared to commit.** Verified: the
reveal gate is single-sourced in `_reveal_open`; phone-scope on all 7 student
endpoints; cross-student IDOR closed (every submission scoped `student=request.user`,
no client-supplied ids); deadline + duplicate-submit enforced server-side (409,
`uniq_exercise_submission_student` race-safe); image upload path-safe (overwrite +
traversal closed by `AWS_S3_FILE_OVERWRITE=False` + per-student `exercise/user`
path). Findings: **Low-1** — the `result` field is student-echoed, so nothing secret
may be persisted into `result['per_question']`; **fixed proactively** by
`_result_for_student` stripping `reference_answer`/`reference_answer_markdown`/
`grading_notes` while reveal is closed (defense-in-depth before E6), locked by
`test_result_passthrough_strips_reference_before_reveal`. **Low-2** (carry to E6) —
image MIME type trusts the client `content_type`; add magic-byte sniffing when E6
feeds answer images to the LLM. **E6 pre-condition:** the grader must NOT write
`reference_answer`/`grading_notes` into `result['per_question']`.

**E8 assistant security-auditor gate (2026-07-05): PASSED, cleared.** Verified: the
reference answer reaches the model ONLY via `build_question_context(reveal=True)`
(structural guard — pre-reveal the model never sees it, so no jailbreak can extract
it); the two-level assistant toggle is server-enforced (`exercise AND section` → 403
`assistant_disabled`, deny-by-default); cross-exercise question smuggling blocked by
`section__exercise` scoping (404); phone-scope + per-student memory thread (no
cross-student bleed); `SAFETY_PREAMBLE` + DATA-fenced `user_message`/`student_work`;
env-only model with a graceful fallback (Low-1 fixed: `_select_model` moved inside the
try so a full model-misconfig degrades to a friendly message, not a 500). Two negatives
added (cross-exercise IDOR, model-unset fallback).

Owner-404 (teacher) / phone-scope-404/400 (student) matrices above; **reference answers are withheld by
the serializer until the reveal condition holds (`deadline < now`, or no-deadline + own GRADED)** — leak
tests at E5 (result + list serializers) and E8 (assistant context); deadline + duplicate-submission
enforced server-side (409);
image upload type/size validated server-side; assistant disable enforced server-side (403
`assistant_disabled`); `{grading_items_json}` injection guard (student answer = DATA). security-auditor
formally gates E5 + E8.

## Metrics (data-analyst, Asia/Tehran)
Exercises published/week · submission rate before deadline · median time-to-grade · override rate
(proxy for LLM grading trust) · assistant messages per submission · grading token cost per class round
(from `LLMUsageLog` features) · notification→submission conversion (informs the phase-2 SMS decision).

## Rollout
E1–E9 = backend image rebuild (migrations `0024`,`0025` auto-run in order on container start);
E10–E12 = frontend rebuild. New env (all optional): `EXERCISE_LLM_GRADING` (+ model/batch knobs above).
No domain/CORS changes. Kill-switch documented for the worker-down scenario: grading halts gracefully in
SUBMITTED, exercises stay usable.

## Risks (accepted, monitored)
1. `pipeline` queue congestion at deadlines (mass grading behind ingest) → monitor; dedicated `grading`
   queue is the named phase-2 escape hatch; kill-switch works today.
2. Grading output truncation on long exercises → per-section/batch chunking from day one (E6).
3. Reference-answer leak (serializer or assistant context) → explicit tests E5/E8 + structural strip.
4. Teacher trust in LLM grades → override + audit history is MVP-mandatory, not optional.
5. OCR quality on poor scans/handwriting via Avalai → unknown until opt-in benchmark; manual-entry
   fallback in the wizard is the product-level mitigation.
6. God-file growth → all new views in `views_exercises.py`; reviewer rejects additions to `views.py`.

## Resolved decisions (product owner, 2026-07-05)
1. **Reference-answer reveal is gated on the DEADLINE, not on grading.** Reference answers unlock when
   `deadline < now` (no-deadline exercise → on the student's own GRADED submission). Prevents the
   early-submitter leak window. A dedicated **«پاسخ تمرین‌های تمام‌شده»** student area
   (`GET student/exercises/answers/`) browses past exercises' answers. The assistant may teach from the
   reference answer only once that same reveal condition holds.
2. **LLM grade shown immediately** (labeled «نمره‌دهی هوشمند», override later); review-gate = phase 2
   per-exercise option.

## Dissent (recorded)
product-manager proposed deferring the **per-section** assistant toggle to phase 2 (exercise-level covers
~80%). Chair kept it in MVP: it is an explicit owner requirement and costs one bool field + one AND in
the server guard given the section model already exists.
