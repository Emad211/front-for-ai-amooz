# Exercise Hub («بخش تمرین») — class assignment and feedback workflow with AI-assisted grading

- **Status:** V1 shipped through E14; V2 build loop active from E15 (2026-07-07)
- **Created:** 2026-07-05 · **Last-verified:** 2026-07-07
- **Owner:** product-manager · **Spec by:** council (product-manager, tech-lead [chair], ai-engineer, ux-designer) · **Built by:** E1–E14; V2 roadmap E15–E45 below
- **ADR:** [ADR-0004](../adr/ADR-0004-exercise-hub.md)

## V2 product thesis (E15 decision)
Exercise Hub is **not** an "AI homework universe" and not a generic chat surface. It is a
classroom assignment workflow:

> AI-Amooz helps teachers turn real class homework into trackable, feedback-rich assignments without
> manually grading every answer.

The feature must therefore optimize for three daily jobs:

1. **Teacher:** create/publish an assignment quickly, then review only the submissions that need human
   attention.
2. **Student:** know what is due now, submit text or handwriting photos without friction, and understand
   what to fix next.
3. **Platform:** keep rubrics/reference answers private until the reveal gate, keep student answer media
   private, and make AI cost/trust observable.

V2 deliberately narrows the product language:

- Say **AI pre-grading / نمره‌دهی هوشمند** with teacher authority, not "fully automatic grading".
- Say **hint-oriented assistant / راهنمایی بدون نمایش پاسخ نهایی**, not "the assistant cannot reveal the
  answer" as an absolute guarantee. The reference answer can be structurally hidden, but the model can
  still solve many questions from the question text.
- Treat **reference answers as rubrics**: sample answer + acceptable variants + scoring notes + common
  mistakes + points.
- Treat **report cards as learning signals**, not official grade averages. Averages are secondary to
  weak points, missed concepts, completion, late/missing work, and recommended next action.

**Terminology decision:** product UI keeps «تمرین‌ها» because it is already shipped, friendlier for
students, and consistent with the platform tone. The spec may use "assignment workflow" in English to
clarify the operational model. E15 does **not** authorize model/API/component renames (`ClassExercise`,
routes, and service names stay as-is until a separate explicit refactor).

## V2 build loop protocol
Each E15+ step follows the same loop:

1. **Generate:** implement the smallest coherent slice (code/docs/tests together).
2. **Evaluate:** run the mandatory team gate for the slice and self-review against this spec.
3. **Correct:** apply findings before calling the step done.
4. **Repeat if needed:** rerun the targeted tests/typechecks/review until the slice is stable.
5. **Finalize:** update this spec + build log, commit, push, and record remaining risks.

Mandatory gates continue to apply: schema → `database-engineer`; auth/permission/private media →
`security-auditor`; LLM/prompt/grading → `ai-engineer` + prompt contract test; meaningful UI/IA →
`ux-designer`; non-trivial diff → `code-reviewer`; push → release gate.

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
- **T4 toggle دستیار:** assistant off at exercise intake → student chat request gets
  **403 `assistant_disabled` server-side** (UI hiding alone is not enforcement).
- **T5 کارنامه + override:** teacher can override any grade; override labeled «بازبینی‌شده توسط مدرس»;
  the original LLM score is **kept (audit, teacher-only)**. Review-ready notifications for the teacher
  authoring flow are now shipped (SMS + in-app teacher feed); publish/graded/override notifications are
  still not shipped yet and remain under E35.
- **S2 ارسال:** text and/or handwriting photos per question; unanswered questions → non-blocking
  Persian warning; submit after deadline → **409 server-side**; one final submission
  (unique(exercise, student)); resubmission only if the teacher explicitly allows (reset pattern).
- **S4 دستیار:** before reveal the assistant receives no teacher reference answer or grading notes and
  must act as a hint-oriented tutor. This is a structural reference-answer guard, **not** a promise that
  a general LLM can never solve the question from the question text.
- **S5/S6 کارنامه + تقویم:** per-exercise report + per-class average (own data only); calendar shows
  real exercise deadlines (+ scheduled exam-preps) instead of mock.

### V2 acceptance criteria (superseding product-quality bar)
- **Discoverability:** teacher exercise work is a first-class class tab/workspace, not a hidden button;
  student exercise work is visible from home, class, learn, calendar, and `/exercises` with state-aware
  CTAs.
- **Modes:** exercises have clear product modes: practice, homework, and assessment. Feedback, retry,
  reveal, and review behavior derive from the selected mode.
- **Trust:** every AI grade can be audited; low-confidence, unreadable, missing, high-value, or disputed
  answers route to a teacher review queue.
- **Privacy:** student answer photos and teacher answer-key assets are private records, not generic public
  media. Reference answers, grading notes, and teacher rationale never leak before the reveal gate.
- **Learning loop:** grading is not the end state. Results must support correction/reflection, weak-point
  insight, and teacher reteaching decisions.
- **Operational value:** teacher dashboard answers "what needs my attention today?" before it shows broad
  analytics.

## Scope
- **In (V1 shipped through E14):** create/extract/edit/publish flow (PDF + photos); reference answers (extracted-if-present,
  teacher-edited, mandatory); deadlines; **one exercise-level assistant toggle, initialized at intake
  and mutable from the owner-scoped settings panel** (ADR-0006); text + handwriting-photo
  submissions; async LLM grading with teacher rubric + deterministic grading for MCQ/fill-blank; teacher
  override with audit; per-exercise + per-class report cards (simple average); teacher gradebook matrix;
  real calendar endpoint + frontend wiring; handwriting-photo grading; teacher reference-ingest preview/apply.
- **Out (explicitly):** adaptive/regenerate loop for exercises; live proctoring; class-session events in
  the calendar (no meeting model exists); cross-student comparisons shown to students.
- **Later phases (named, deferred):** weighted combined report card (exercise+quiz+final exam) — weighting
  policy is a real product decision; SMS deadline reminders (Mediana cost + Celery beat scheduling);
  per-student deadline extensions; per-exercise grade weights; teacher review-gate before grade release;
  report-card PDF export (WeasyPrint); auto late-penalty.
- **Unresolved V2 contract gaps:** in-app notifications (E35), the remaining actor/reason event log portion of E22, private
  answer media serving (E23), explicit no-deadline reveal policy (E21), confidence/review routing (E26),
  and post-publish regrade story (E36).

## Policies (product — decided in council)
- **Late submissions:** closed at deadline by default; per-exercise toggle «پذیرش ارسال با تأخیر» →
  allowed but flagged «ارسال با تأخیر» on both sides. Auto-penalty = phase 2. A newly supplied deadline
  must be in the future in both standalone and embedded class creation; editing another setting on an
  old exercise whose deadline has already passed remains valid.
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
- **V2 reveal tightening:** no-deadline + own-graded reveal is safe only for practice/self-study. Homework
  and assessment modes must use an explicit shared release (`answer_release_at` or manual release) before
  they are considered safe. E21 owns the schema/API/UI decision.
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
- **Reference Ingest layer (teacher-only, E14):** after questions exist, the teacher can paste text or
  upload small PDF/photos containing reference answers (or mixed Q+A) to
  `POST /reference-ingest/preview/`. The server OCRs the source, runs
  `exercise_reference_ingest`, and returns a **review-only** patch with
  `matched/ambiguous/unmatched` items. Nothing is saved during preview. The teacher then sends selected
  items to `POST /reference-ingest/apply/`, which updates only existing questions in a transaction.
  Ambiguous/low-confidence items never auto-apply; answer-only input without a clear target must be
  manually mapped by the teacher. MVP is pre-publish only (`PUBLISHED` → 409) until a re-grade/audit flow
  exists. The preview path is bounded by reference-specific file/page/OCR/source-text caps before the LLM;
  apply is bounded by item/field/points caps and never mutates an existing-reference question unless
  `replaceExisting=true`.
- **Grading is on-submit async** on the `pipeline` queue (not sync = timeout; not nightly batch =
  pointless UX delay). One `generate_structured` call per batch of `EXERCISE_GRADING_BATCH_SIZE`
  (default 5) questions; **MCQ/fill-blank graded deterministically without LLM**; totals computed with
  `sum()` never by the model; retries idempotent (status-guard + persisted `grading_task_id`);
  kill-switch env `EXERCISE_LLM_GRADING` (default on) → submissions stay SUBMITTED for manual grading.
  V2 E24 hardens retries/cost attribution; V2 E25 makes student-visible pre-reveal feedback structurally
  or deterministically safe, because the grader itself must see the reference answer.
- **Handwriting-photo answers (E13):** before grading, every answered question whose
  `answers[qid].images` carries storage paths gets a **vision-extract step**
  (`exercise_grading._effective_answer_text`): one standard-shape OpenAI multimodal call per question
  (`image_url` data URIs — the legacy `attachments` shape is silently ignored by the gateway), images
  sniffed with `is_real_image` (Pillow verify, Low-2) and capped at `EXERCISE_MAX_IMAGES_PER_QUESTION`
  (default 3); model chain `EXERCISE_VISION_MODEL→IMAGE_MODEL→MODEL_NAME` (raise if unset); usage logged
  under `LLMUsageLog.Feature.EXERCISE_HANDWRITING_VISION`. Text merge rules: photo-only → extracted text
  IS the answer (verbatim, so deterministic MCQ/fill-blank matching works); typed+photo descriptive →
  appended under the delimiter `[متن استخراج‌شده از تصویر پاسخ]`; typed+photo deterministic → typed text
  authoritative, vision skipped (cost). **Failure semantics:** unreadable image / missing file /
  transient vision exception logs a warning and grades whatever typed text exists, but a deployment
  misconfiguration (no vision model in ENV) raises and marks the submission `GRADING_FAILED` instead of
  silently grading a photo-only answer as zero. Leak guard: the vision prompt carries ONLY the question
  text — never `reference_answer_markdown`/`grading_notes` (test-locked). The same `is_real_image`
  sniff also rejects fake-image bytes at upload time (`StudentExerciseImageView`, 400).
- **Override:** `teacher_score`/`teacher_feedback` written alongside `llm_score` inside
  `result['per_question']`; `llm_score` never overwritten. A manual score must be finite and within
  `0..max_points` for its question; the API validates the whole override batch before writing, and
  effective per-question/final scores are defensively bounded to the same range. Migration `0031`
  repairs historical out-of-range overrides and recomputes their totals. Sending an explicit
  `teacher_score: null` removes the manual score and restores the immutable AI score as the effective
  score; omitting `teacher_score` leaves the current score unchanged. Saved `teacher_feedback` is
  returned by submission detail and hydrated into the teacher's gradebook editor, so reopening a
  submission never presents persisted feedback as an empty field.
- **Assistant leak guard is structural:** before grading the reference answer is **not in the model's
  context at all** (server strips it) — a model that never saw the answer cannot leak it under
  injection. After grading (`{phase}=graded`) reference+feedback enter the context so the assistant can
  teach the solution (adaptive-loop reveal precedent).
- **Toggle semantics:** effective = `exercise.assistant_enabled`; it is initialized during intake and
  remains editable by the teacher from «تنظیمات قابل تغییر» (ADR-0006). The legacy section flag is ignored.

## Data
| Model | Key fields | Constraints |
|---|---|---|
| `ClassExercise` | session FK CASCADE · title · description · Status{DRAFT,EXTRACTING,EXTRACTED,PUBLISHED,FAILED} · `deadline` (DateTime, null — first real deadline field in the platform) · `allow_late` (bool, default False) · `assistant_enabled` (bool, default True) · `intake_config` JSON (one-step teacher intake snapshot incl. per-file role/writing/layout) · `workflow_state` JSON (`stage`, `progressPercent`, `message`, `warnings`, `readyForReview`) — teacher-facing warnings stay as short Persian summaries; raw LLM diagnostics must not persist into the durable card state · `extract_task_id` · `review_ready_notified_at` | index (session, status) |
| `ClassExerciseAsset` | exercise FK · kind{pdf,image} · file · order | — |
| `ClassExerciseSection` | private compatibility container; new exercises receive exactly one untitled row. Not exposed as product grouping. | uniq (exercise, order) |
| `ClassExerciseQuestion` | section FK · order · `question_markdown` · `question_type{descriptive,multiple_choice,fill_blank}` · `options` JSON null · `reference_answer_markdown` · `max_points` Decimal · `grading_notes` | uniq (section, order) |
| `StudentExerciseSubmission` | exercise FK · student FK · mutable draft/current projection · Status{DRAFT,SUBMITTED,GRADING,GRADED,GRADING_FAILED} · `answers` JSON · latest `result`/score metadata · nullable `current_attempt` | **uniq (exercise, student)** |
| `StudentExerciseAttempt` | submission FK · immutable `attempt_number` · answer/question/rubric snapshots · per-question fingerprints/OCR · result and score snapshot · model/prompt metadata · grading status/timestamps | **uniq (submission, attempt_number)** · index (status, updated_at) |

Attempt grading is finalized atomically with the current Submission projection. Fingerprints include
only inputs that can affect a question's grade (including OCR versioning only for photo answers), and
temporary object-storage read failures are retried rather than persisted as empty answer evidence.
After `allow-redo`, the latest graded Attempt remains available as read-only history while no Attempt
is considered current/editable until the student submits the new draft.

Migrations keep DDL and DML separate. The original exercise schema uses `classes/0024_exercises`
(CreateModel + constraints), `classes/0025_exercise_submission_draft` (adds `DRAFT` to the submission
status — no-op AlterField), and `classes/0026_session_scheduled_at` (adds nullable `scheduled_at` to
`ClassCreationSession` for timed exam-prep calendar events — **database-engineer approved**: metadata-only
add on Postgres, no rewrite/long lock, no index needed since the calendar query is pre-filtered by
`invites__phone` + indexed `pipeline_type`; rollback = `migrate classes 0025`). Feature-enum additions ride
`classes/0027_classexercise_intake_config_and_more` (adds `intake_config`, `workflow_state`,
`review_ready_notified_at` for the one-step async authoring flow) +
`commons/0006` + `commons/0007_exercise_reference_ingest_feature` (no-op AlterField).
`LLMUsageLog.Feature` choices additions generate a no-op AlterField migration (coordinate with
database-engineer). Stable resubmission grading adds DDL migration
`classes/0032_studentexerciseattempt`, followed by repeat-safe DML migration
`classes/0033_backfill_exercise_attempts`, which snapshots existing finalized submissions as attempt 1
without deleting or rewriting their submission projection. Reversing `0033` is intentionally a no-op;
rolling back through `0032` drops attempt history and therefore requires a database backup/restore if
that history must be retained.

## API (contract-first; teacher = `[IsAuthenticated, IsTeacherUser]` + `session__teacher=request.user` → non-owner **404**; student = `[IsAuthenticated, IsStudentUser]` + `session__is_published=True, session__invites__phone, exercise.status=PUBLISHED` → **404**, no-phone → **400**)

**Teacher** (all under `/api/classes/…`, implemented in `views_exercises.py`):
- `POST creation-sessions/<sid>/exercises/` (+ full one-step intake: title, deadline/no-deadline,
  allow-late, assistant toggle, teacher note, file metadata `sources[]`, uploaded files keyed by
  `clientFileKey`) automatically creates the draft + assets AND enqueues extraction on commit. The
  response already includes the durable workflow fields:
  `{workflowStage, workflowMessage, progressPercent, workflowWarnings, readyForReview, reviewReadyNotifiedAt}`.
  `GET exercises/` and `GET exercises/<eid>/` return the same workflow contract for polling/re-entry.
- `GET creation-sessions/<sid>/` / class session detail returns `pendingExercises` for exercises embedded
  in the class-creation flow. Once a pending row has `exerciseId`, the serializer enriches that snapshot
  from the live `ClassExercise.workflow_state` in one batch query, adding `exerciseStatus`,
  `workflowStage`, `workflowMessage`, `progressPercent`, `workflowWarnings`, `readyForReview`, and
  `reviewReadyNotifiedAt`. The frontend must use this enriched session payload as the source of truth
  instead of separately joining against `GET exercises/`.
- `POST exercises/<eid>/extract/` (manual retry/rerun only; 409 while EXTRACTING and for PUBLISHED) ·
  `POST exercises/<eid>/publish/` (400 if any
  question lacks reference answer/points; 409 wrong status or when the parent class is not published yet).
  The class publish action itself is visible in the teacher class header while draft, but remains disabled
  until the class pipeline reaches `recapped` with structured content.
- `POST exercises/<eid>/reference-ingest/preview/` (multipart: `source_text`, `files[]`, `mode_hint`,
  optional `target_question_id`) → review-only `{modeDetected, items, warnings, counts}`; owner-scoped,
  status-gated, no DB write. `POST exercises/<eid>/reference-ingest/apply/` → transactional update of
  selected existing questions only; no new question creation and no overwrite of existing reference
  answers unless `replaceExisting=true`.
- `PATCH exercises/<eid>/` (title/deadline/allow_late/assistant_enabled) ·
  deprecated `PATCH exercises/sections/<id>/` (legacy title compatibility only) · CRUD `exercises/<eid>/questions/`
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
  GRADED**) · `POST …/exercises/<eid>/assistant/` (server guard: exercise toggle; 403 code
  `assistant_disabled`; context never contains reference answers pre-grading)
- `GET student/courses/<sid>/report-card/` · `GET student/report-card/` (overall) ·
  `GET student/exercises/answers/` (the «پاسخ تمرین‌های تمام‌شده» browse — lists only deadline-passed
  exercises of enrolled classes with their reference answers + the student's own submission if any)
- `GET student/calendar/?from=&to=` — aggregate: published exercise deadlines of enrolled classes +
  invited exam-prep sessions with `scheduled_at`. Response items:
  `{id, kind: 'exercise_deadline'|'exam_prep', title, courseTitle, datetime (ISO, Tehran tz), sessionId,
  exerciseId?, isCompleted}`.
  **Jalali conversion happens in the frontend service layer** (`date-utils`), backend stays Gregorian.

Every row above ships with negative tests (anonymous/wrong-role/cross-teacher/cross-student/no-phone) —
security-auditor gates E5 and E8.

## LLM
**Prompt keys (PROMPTS — byte-for-byte contract; update `test_prompts_contract.py` LIVE_KEYS +
PLACEHOLDERS + OUTPUT_KEYS + safety-block list in the same commit):**
- `exercise_structure` / `default` — Markdown (from reuse of `pdf_extraction.default`, per-page for both
  PDF pages and photos) → structured exercise. Parsed with
  `generate_structured(schema=ExerciseStructureOutput)`. Output contract:
  `exercise_title, questions[{question_id,question_text_markdown,question_type,options,points,reference_answer_markdown}]`.
  Legacy `sections[].questions[]` remains parser-only during the compatibility window.
  (`points`/`reference_answer_markdown` nullable — extracted if present, teacher always wins).
  Phase 2: strategy `answer_key` (`{questions_json}` placeholder).
- `exercise_reference_ingest` / `default` — placeholders **`{mode_hint}`**,
  **`{existing_questions_json}`**, **`{source_markdown}`**. Used for teacher-provided answer keys,
  mixed Q+A sheets, single Q+A, and answer-only sources after questions already exist. Output:
  `mode_detected, items[{item_id, question_number, question_text_markdown, question_type, options,
  points, reference_answer_markdown, confidence, notes}], warnings`. The model proposes candidates only;
  server-side matching decides `matched/ambiguous/unmatched`, and teacher review is mandatory before
  apply. +`SAFETY_PREAMBLE` + `MATH_FORMAT_INSTRUCTIONS`; source/OCR is DATA, not instructions.
- `exercise_grading` / `default` — placeholder **`{grading_items_json}`** =
  `[{question_id, question_text, reference_answer, max_points, student_answer}]`; +`SAFETY_PREAMBLE` +
  student-answer-is-DATA injection guard. Output:
  `per_question[{question_id, score_points, max_points, label(correct|partially_correct|incorrect), feedback, missing_points}]`
  — deliberately the **same score shape as the final exam**, so `compute_weak_points_from` and report
  aggregation reuse without new parsers. (`text_grading` was evaluated and is insufficient: 0–100
  single-question scale, hard no-reveal rule, no batching.)
- `exercise_assistant_chat` / `default` — placeholders `{question_context} {student_work} {phase}
  {history} {user_message}`; output `{content, suggestions}` (frontend chat widget unchanged).
- `exercise_handwriting_vision` / `default` (E13) — placeholder **`{question_text}`** (context only;
  by contract this prompt NEVER carries the reference answer or grading notes — the leak guard is
  structural, like the assistant's). Output: `{text}` (validated by
  `HandwritingTranscriptionOutput` — `text` deliberately **required** so a missing key triggers the
  `generate_structured` repair round-trip instead of a silent empty transcription). +`SAFETY_PREAMBLE`
  +`MATH_FORMAT_INSTRUCTIONS`; handwriting content = DATA, not instructions.
- **Reused verbatim (no new keys):** `pdf_extraction.default` (PDF pages AND uploaded photos — a photo
  is a page). *(The original plan reused `exam_prep_handwriting_vision` for student answer photos; the
  build (E13) added the dedicated single-key `exercise_handwriting_vision` instead — the exam-prep
  4-key output shape is tutoring-oriented and overweight for a pure transcription step.)*

**Env (models are env-only; missing chain → raise, never a hardcoded name):**
`EXERCISE_STRUCTURE_MODEL→STRUCTURE_MODEL→MODEL_NAME` · `EXERCISE_GRADING_MODEL→MODEL_NAME` ·
`EXERCISE_REFERENCE_INGEST_MODEL→EXERCISE_STRUCTURE_MODEL→STRUCTURE_MODEL→MODEL_NAME` ·
`EXERCISE_VISION_MODEL→IMAGE_MODEL→MODEL_NAME` (ingest OCR **and** the E13 handwriting step) ·
`EXERCISE_CHAT_MODEL→CHAT_MODEL→MODEL_NAME` · `EXERCISE_GRADING_BATCH_SIZE=5` ·
`EXERCISE_MAX_IMAGES_PER_QUESTION=3` (E13 vision cap) ·
`EXERCISE_MAX_SOURCE_FILES=10` / `EXERCISE_MAX_SOURCE_FILE_BYTES=20971520` ·
`EXERCISE_REFERENCE_MAX_FILES=5` / `EXERCISE_REFERENCE_MAX_FILE_BYTES=8388608` ·
`EXERCISE_REFERENCE_MAX_SOURCE_CHARS=50000` ·
`EXERCISE_REFERENCE_MAX_PDF_PAGES=20` / `EXERCISE_REFERENCE_MAX_OCR_UNITS=20` ·
`EXERCISE_REFERENCE_MAX_APPLY_ITEMS=100` / `EXERCISE_REFERENCE_MAX_MARKDOWN_CHARS=20000` ·
`EXERCISE_REFERENCE_MAX_OPTIONS=12` / `EXERCISE_REFERENCE_MAX_OPTION_CHARS=2000` ·
`EXERCISE_REFERENCE_MAX_POINTS=1000` ·
`EXERCISE_REFERENCE_CONTEXT_MAX_QUESTIONS=120` / `EXERCISE_REFERENCE_CONTEXT_QUESTION_CHARS=1200` ·
`EXERCISE_LLM_GRADING=1` (kill-switch).
New `LLMUsageLog.Feature` members: `EXERCISE_INGEST, EXERCISE_STRUCTURE, EXERCISE_GRADING,
EXERCISE_REFERENCE_INGEST, EXERCISE_HANDWRITING_VISION, CHAT_EXERCISE`.

**Retry/failure semantics (E18 reliability hardening):** Exercise extraction/grading treats only
provider/network-transient LLM failures as retryable: timeout/transport errors, 408, 409, 429, and 5xx
(including AvalAI 502). Permanent failures — malformed request shape, unsupported `response_format`,
missing env/model/key, 401/403/413/422, empty/parser/application failures — fail fast. The OpenAI SDK's
hidden retry layer is disabled by default (`OPENAI_SDK_MAX_RETRIES=0`) so app-level retry timing is
owned by Tenacity + Celery. On a retryable failure, `extract_exercise_content` and
`grade_exercise_submission` keep `EXTRACTING`/`GRADING` and call `self.retry()`; redelivery with the
same persisted task id may resume from that state instead of skipping itself. Deploy invariants are
test-locked: workers consume `-Q default,pipeline`, beat runs separately, Redis visibility timeout
exceeds hard task limits, and broker Redis uses `noeviction`.

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
- **Teacher authoring (current shipped shape):** one-step intake card, not a multi-step wizard. The
  teacher gives title + deadline mode + late policy + assistant default + teacher note + all source files
  up front; each file has optional hints (`role`, `writingMode`, `answerLayout`) with `auto` defaults.
  Deadline selection is now a **site-native Jalali date+time picker** (not browser-native Gregorian
  `datetime-local`), and the same picker is reused inside the post-extraction settings editor so stored
  UTC deadlines round-trip back to the teacher in local time correctly. A running or queued extraction
  can now be **cancelled safely from the teacher card**: the row flips to `cancelled`, Celery revoke is
  attempted, and a cooperative cancel flag prevents redelivery / resume from completing behind the
  teacher's back. CTA = `ساخت پیش‌نویس تمرین`. Extraction, OCR, question build, and answer-sheet
  matching run async on the backend; the teacher sees a **durable** stage/progress bar on the exercise
  card (`queued` →
  `reading_sources` → `ocr_and_transcription` → `extracting_questions` → `matching_reference_answers` →
  `building_review_draft` → `ready_for_review`) and can leave/re-enter safely. After review-ready, the
  teacher receives one SMS + one in-app teacher notification and then opens the flat question editor
  to review, patch references/points, add/delete manual questions, and
  publish. When an exercise is registered from the class-creation page, the class page shows the same
  stage/progress tracker from the enriched `pendingExercises` snapshot and keeps polling after the class
  reaches `recapped` until every embedded exercise is `ready_for_review`, `failed`, or `cancelled`. The
  reference ingest remains only as the secondary `اصلاح گروهی از روی منبع` action beside the
  question/reference-answer review list; its workflow opens in a sheet and no longer occupies a
  standalone card between settings and questions. Every question and reference-answer editor now
  includes a live KaTeX preview plus an optional visual math keyboard. The keyboard inserts standard
  Markdown/LaTeX at the textarea cursor (fractions, roots, powers, sets, Greek letters, and common
  operators), so storage and all student/grading render paths keep the existing text contract. Preview
  blocks choose direction per paragraph: Persian/mixed prose stays RTL while Latin-only, numeric, and
  math-only solutions are LTR, including standalone negative numbers. The keyboard uses Persian-labeled
  category tabs, adds common advanced structures, and detects whether the cursor is already inside math
  delimiters so subsequent keys insert valid LaTeX without nesting `$...$` wrappers. Display-math
  solutions are physically left-aligned (overriding KaTeX's centered default), and fenced/inline code is
  restored from escaped placeholders so renderer-owned `<code>` markup never appears as answer text.
  The standalone `ایجاد تمرین جدید` intake is collapsed by default, preserves an unfinished draft when
  toggled, and collapses again after successful submission.
- **Student solver:** sticky header (title, deadline badge with <24h countdown, draft-saved indicator);
  one ordered question list on every viewport; per-question text/photo inputs (camera `capture` on
  mobile, client-side compression); autosave; sticky
  submit bar + confirm dialog; assistant = side panel (desktop) / bottom Sheet (mobile); assistant-off →
  informative lock chip («دستیار این تمرین غیرفعال است»), never silently hidden; past-deadline →
  read-only + banner. Pending text is synchronously mirrored to a student/exercise-scoped local backup
  until the backend confirms it. Blur, tab hiding, page exit, and component unmount flush immediately
  with a keepalive request; a newer save aborts an older in-flight request. The local backup is restored
  after an interrupted visit and cleared only after confirmed autosave or final submission.
- **Report cards:** student per-exercise result (summary card + per-question own answer/reference/score/
  feedback, green/red start-bars from tokens); overall trend chart (recharts, Persian digits, Jalali);
  teacher gradebook matrix (row=student, column=exercise, **sticky name column on the RIGHT** —
  `right-0` not `left-0`), mobile = expandable list; cell click → submission detail with zoomable photos +
  override panel; overridden grades always badged «ویرایش معلم».
- **Calendar:** event kinds `exercise_deadline` (suggested `hsl(var(--chart-2))`) and `timed_exam`
  (`hsl(var(--destructive))`) — **verify `--chart-*` tokens exist in BOTH `:root` and `.dark` before
  build** (the `--primary-rgb` phantom-token lesson); status badges امروز/گذشته/آینده + «انجام نشد»;
  event modal CTA deep-links to the exercise/result.
- **Microcopy table (key strings):** empty.teacher «هنوز تمرینی برای این کلاس نساخته‌اید. فایل‌ها را یک‌بار
  بارگذاری کنید تا پیش‌نویس تمرین برای بازبینی آماده شود.» · empty.student «فعلاً تمرینی برای این کلاس ثبت نشده است.» ·
  extract.processing «پیش‌نویس تمرین در صف ساخت قرار گرفت. پس از آماده‌شدن برای بازبینی به شما اطلاع می‌دهیم.» ·
  extract.error «ساخت پیش‌نویس تمرین کامل نشد. دوباره تلاش کنید یا منبع تکمیلی بدهید.» ·
  assistant.off.all «دستیار این تمرین غیرفعال است» · assistant.context «دستیار این سوال» ·
  deadline.badge «مهلت ارسال: ۱۵ تیر، ساعت ۲۳:۵۹» · deadline.passed «مهلت ارسال
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

## Roadmap — E1…E14 (V1 foundation; one step per iteration; each committable + tested; docs updated in the same commit)

| # | Owner (+gate) | Scope | DoD |
|---|---|---|---|
| **E1** | backend (+database-engineer review) | 5 models + migration `0024` (pure DDL) + constraint/FK-behavior tests | migrations apply on fresh Postgres & sqlite; uniq/index/CASCADE tests green |
| **E2** | ai-engineer | `services/exercise_ingest.py` + `PROMPTS["exercise_structure"]` + Pydantic schemas + contract-test update | ✅ DONE — `structure_exercise_markdown` + `exercise_structure` prompt + `ExerciseStructureOutput` + 5 Feature enums (`commons/0006`) + contract test; 13 ingest tests + 60 contract green |
| **E3** | backend | `extract_exercise_content` task (pipeline queue) + state machine + `cache.add` idempotency | ✅ DONE — task + OCR (`ocr_assets_to_markdown`) + `persist_exercise_structure`; 7 eager tests (transitions/double-dispatch/FAILED/re-run/task-id) green |
| **E4** | backend | teacher endpoints (CRUD/extract/publish/toggles) in `views_exercises.py` | ✅ DONE — extended on 2026-07-08 to the one-step intake flow: create now captures deadline/settings + per-file metadata, stores `intake_config`, returns durable workflow fields, and auto-dispatches extraction on commit; manual `/extract/` remains retry/rerun-only. Follow-up: owner-only `/cancel/` now stops queued/running extraction safely via persisted `cancel_requested` + best-effort Celery revoke, moving the exercise to `cancelled` (rerunnable terminal). |
| **E5** | backend (**security-auditor gate**) | student endpoints (list/detail/draft/submit/image) + deadline guard + no-leak serializers | ✅ DONE — 7 endpoints + `_reveal_open` + finished-answers browse + `DRAFT` status (mig 0025); 22 api tests; security gate PASSED (Low-1 fixed proactively, Low-2→E6) |
| **E6** | ai-engineer + backend | grading service+task (`exercise_grading`, batch env, deterministic MCQ/fill-blank, retry idempotent, kill-switch) | ✅ DONE — `exercise_grading.py` + `grade_exercise_submission` task + dispatch wired; deterministic MCQ + LLM batch + sum + kill-switch; E5 Low-1/Low-2 closed; 13 tests + contract green |
| **E7** | backend | result + report cards (per-exercise/per-course/overall) + teacher submissions list + override + allow-redo + in-app notifications (publish/graded) | ✅ DONE — gradebook (list/detail/override/allow-redo) + student course/overall report cards; override keeps `llm_score`, recomputes effective; 12 tests. **Teacher review-ready notifications are now shipped** (2026-07-08, SMS + virtual teacher feed); publish/graded notifications remain deferred to E7b. |
| **E8** | ai-engineer (**security-auditor gate**) | assistant endpoint + server guard + context builder (structural strip of reference answers) + `exercise_assistant_chat` | ✅ DONE — originally shipped with two-level toggle; ADR-0005 removed section enforcement and ADR-0006 made the owner-scoped exercise-level setting mutable. |
| **E9** | backend (+database-engineer) | migration `0026` (`scheduled_at`) + `GET student/calendar/` aggregate | ✅ DONE — nullable `scheduled_at` (db-eng approved) + calendar endpoint (both kinds, Tehran-tz, isCompleted, from/to); 9 tests green. **Backend complete.** |
| **E10** | frontend-engineer | teacher UI: service + wizard + gradebook + override + toggles | ✅ DONE — evolved on 2026-07-08 from the earlier split flow into a single intake card: title + deadline/settings + teacher note + source files + per-file hints up front, then a single `ساخت پیش‌نویس تمرین` action and persistent workflow/progress cards until `بازبینی و انتشار`; 2026-07-08 follow-up added a site-native **Jalali deadline picker** for both intake and post-extraction settings, replaced the browser-native Gregorian control, tightened the popover footprint/anchoring, made the shared `Switch` RTL-safe, and added a teacher-side `لغو استخراج` action on active exercise cards. Reference ingest is now a compact `اصلاح گروهی از روی منبع` action in the question-review header rather than a standalone panel. |
| **E11** | frontend-engineer | student UI: exercises hub + solver (text/photo) + assistant widget + report cards | ✅ DONE — service (student endpoints) + hub/solver/result/answers pages + assistant/report-card; disabled-assistant chip; solver never fetches reference; tsc clean |
| **E12** | frontend-engineer | calendar: remove mock, wire service + Jalali conversion + exam-prep events | ✅ DONE — `getCalendarEvents` → real `getStudentCalendar` (E9); `toCalendarEvent` maps Tehran-tz ISO → Jalali `YYYY-MM-DD`+`HH:MM` (`Intl` persian/Asia-Tehran/latn) + kind→type/priority + isCompleted; mock + fake delay deleted; tsc clean; conversion Node-verified. **E1–E12 foundation complete; V1 continued with E13/E14 hardening.** |
| **E13** | ai-engineer | handwriting-photo grading slice (audit gap: `answers[qid].images` never reached the LLM — photo-only answers silently scored 0) | ✅ DONE — vision-extract step in `exercise_grading.py` (`exercise_handwriting_vision` prompt + `HandwritingTranscriptionOutput`; standard `image_url` shape; `is_real_image` sniff wired at grading **and** upload; `EXERCISE_MAX_IMAGES_PER_QUESTION=3`; fail-open per question; reference-answer leak guard test-locked); 6 new grading tests + 1 upload negative + contract — all green, 0 tokens |
| **E14** | ai-engineer + backend + frontend | teacher reference-ingest preview/apply for flexible answer-key sources | ✅ DONE — `exercise_reference_ingest` prompt/schema/feature; preview writes nothing; apply is transactional update-only on existing questions, no overwrite unless explicit; PUBLISHED rejected until regrade story; UI review Sheet with Markdown+KaTeX; caps, source validation, prompt trimming, and URL sanitization hardened |

## Roadmap — Exercise Hub V2 (E15…E45)

| # | Owner (+gate) | Scope | DoD |
|---|---|---|---|
| **E15** | product-manager + ux-designer + ai-engineer + security-auditor | Product reframe + build loop protocol | ✅ DONE when this spec states the V2 thesis, anti-promises, terminology decision, no-rename/no-code rule, acceptance criteria, and E15–E45 roadmap; team critique incorporated |
| **E16** | frontend-engineer + ux-designer | Teacher class IA: make exercises a first-class class workspace | ✅ DONE — persistent class workspace nav appears on overview/edit/students/exercises with «نمای کلی / محتوا / تمرین‌ها / دانش‌آموزان / اطلاعیه‌ها»; «تمرین‌ها» is active/stateful with exercise count/status badge from `listExercises`; overview exposes real content/announcements anchors |
| **E17** | frontend-engineer + ux-designer | Student exercise discoverability | ✅ DONE — shared `getStudentExerciseAction` drives class-card CTAs, learn-view CTA, `/exercises` catalog/upcoming deadlines, enriched calendar events, and home upcoming cards with state-aware routes: «شروع تمرین»، «ادامه تمرین»، «دیدن نتیجه»، «پاسخ‌نامه»; same-day expired deadlines are filtered from home/upcoming deep links |
| **E18** | ux-designer | Persian microcopy normalization | One vocabulary set across teacher/student: «پاسخ‌نامه»، «نمره‌دهی هوشمند»، «بازبینی مدرس»، «شروع/ادامه تمرین»; stale "3-step" or legacy upload copy absent |
| **E19** | backend + database-engineer | True unset points + publish gate | `max_points` can distinguish unset from teacher-confirmed; extraction never silently turns missing points into `1`; publish gate tests lock it |
| **E20** | backend + frontend + product-manager | Exercise modes | `practice/homework/assessment` policy exists; retry, grading visibility, reveal, assistant behavior, and UI labels derive from mode |
| **E21** | backend + security-auditor | Explicit reveal policy | `answer_release_at` or manual release prevents no-deadline graded homework from leaking answers; no-deadline self-study is labeled as such |
| **E22** | backend + security-auditor | Append-only grading audit trail | 🟡 Attempt history DONE (ADR-0008): immutable answer + question/rubric snapshots, stable fingerprint reuse, OCR cache, latest-attempt reports, teacher/student history. A separate actor/reason event log for each override remains. |
| **E23** | backend + security-auditor | Private answer media serving | Student answer images and answer-key/reference assets are served through authorized endpoints or scoped signed URLs, not raw public paths |
| **E24** | backend + ai-engineer | Exercise LLM reliability and cost attribution | Exercise extraction/grading tasks attribute usage to teacher/session, retry transient provider failures, and expose actionable failure states |
| **E25** | ai-engineer + security-auditor | Student-safe pre-reveal feedback | Pre-deadline grading feedback cannot reveal canonical answer phrasing; deterministic leak/redaction tests cover feedback, `missing_points`, stored `result`, serializers, and result UI; full solution feedback unlocks only after reveal or teacher review |
| **E26** | ai-engineer + backend | Confidence / needs-review routing | Handwriting vision returns confidence/warnings; missing LLM output, unreadable handwriting, borderline/high-value answers, and schema drift route to teacher review instead of silent zero |
| **E27** | frontend-engineer + ux-designer | Teacher exercise operations dashboard | Filters: همه، پیش‌نویس، نیازمند پاسخ‌نامه، منتشرشده، نیازمند تصحیح، تمام‌شده; each row/card has state counts and next action |
| **E28** | frontend-engineer + ux-designer | Real 4-step teacher wizard | Steps: مشخصات و فایل‌ها، بازبینی سؤال‌ها، پاسخ‌نامه و بارم، تنظیمات انتشار; progress visible; draft resumable |
| **E29** | frontend-engineer | Extraction review workspace | Add/delete/edit/reorder questions; split/merge if feasible; confidence warnings; LaTeX preview everywhere teacher edits scientific text |
| **E30** | frontend-engineer + backend | Rubric editor | Per-question answer, accepted variants, grading notes, points, total-points summary, validation errors near fields |
| **E31** | frontend-engineer + ai-engineer | Reference-ingest as rubric step | Review table shows source item, matched question, confidence, proposed answer/points, conflict warning, apply checkbox |
| **E32** | frontend-engineer + ux-designer | Publish settings | Jalali deadline, late policy, exercise mode, reveal policy, assistant policy, student preview, and publish checklist |
| **E33** | backend + frontend | Gradebook triage | Non-submitters, late, failed grading, low-confidence, needs-review, and override hotspots are visible and filterable |
| **E34** | frontend-engineer | Submission review workspace | Question, reference/rubric, student text/photos, AI score/feedback, manual score, teacher feedback, redo action in one review surface |
| **E35** | backend + security-auditor | In-app notifications (E7b) | Publish, due-soon, graded, override, redo, and answer-release notifications are idempotent, recipient-scoped, and secret-free |
| **E36** | backend + ai-engineer + product-manager | Regrade story | Post-publish content/rubric edits either trigger explicit regrade/audit flow or are blocked/limited with honest copy |
| **E37** | frontend-engineer + ux-designer | Student hub as action queue | Tabs: «برای انجام»، «در انتظار نمره»، «نتیجه‌ها»، «پاسخ‌نامه‌ها»; due-soon comes before report cards |
| **E38** | frontend-engineer + ai-engineer | Focused solver | Active question drives assistant context; unanswered warning lists count; past-deadline read-only; mobile assistant Sheet; safe bottom spacing |
| **E39** | frontend-engineer + security-auditor | Result/review mode | Per-question cards show question, student's own answer, score, safe feedback, reference answer if unlocked, and locked reveal copy otherwise |
| **E40** | backend + frontend + pedagogy review | Correction/reflection loop | After grading, student can submit non-scored correction/reflection; teacher can see whether feedback was acted on |
| **E41** | backend + frontend + data-analyst | Mastery-centered report cards | Averages are secondary; weak concepts, trend, missed work, late work, and recommended next practice are foregrounded |
| **E42** | frontend-engineer | LaTeX/Markdown audit | Every exercise scientific text path uses `MarkdownWithMath`/`MathText` as appropriate, with sanitized links/images and teacher preview |
| **E43** | frontend-engineer + ux-designer | Accessibility/mobile audit | 375px, 768px, RTL, keyboard nav, focus states, table/mobile card handling, contrast, and fixed footer overlap verified |
| **E44** | qa-engineer | Docker E2E | Real local stack: teacher creates/publishes; student submits text/photo; Celery grades; teacher overrides; reveal/result paths verified |
| **E45** | data-analyst + release-manager | Metrics and release gate | Publish rate, second-exercise retention, time-to-publish, submission rate, override delta, unreadable-photo rate, grading failure, cost/submission tracked |

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
it); ADR-0006 enforces the mutable exercise-level toggle (`exercise.assistant_enabled` → 403
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
Exercises published/week · second exercise within 14 days · median time from start/upload to publish ·
submission rate before deadline · median time-to-feedback · result/feedback view rate · override rate +
average override delta (proxy for LLM grading trust) · unreadable-photo / needs-review rate · grading
failure rate · assistant messages per submission · grading token cost per class round (from `LLMUsageLog`
features) · notification→submission conversion after E35.

## Rollout
Initial E1–E9 required the backend/worker image and migrations beginning at `0024`; E10–E12 required a
frontend rebuild. For ADR-0008, drain and stop workers consuming `pipeline`, deploy one backend image to
the web and worker services, apply DDL `0032` then DML `0033`, restart the worker from that same image,
and only then deploy the frontend. Do not run old and new grading workers concurrently. No new env or
domain/CORS changes are required. Existing optional grading controls, including
`EXERCISE_LLM_GRADING`, remain supported. The kill-switch still leaves submissions recoverable when the
worker is unavailable.

### Interactive student-answer OCR (ADR-0009)

Student handwriting preview uses revisioned answer Sources and immutable
Assets. Per-question photos are read together after a two-second settle window.
A whole-exercise source accepts photos or PDF (defaults: 20 pages, 30 MB, four
rendered pages per vision call), preserves page order, then maps the transcript
to question IDs without sending reference answers or grading notes to OCR.

The student reviews `MarkdownWithMath` output and uncertainty markers. Typed
text is never overwritten. Whole-answer mappings require the explicit
`اعمال پاسخ‌های بازبینی‌شده` action; final submit may explicitly freeze an
unapplied mapping. Attempts freeze Source ID/revision, and grading reuses the
confirmed text without a second vision call. Pending OCR does not block submit;
grading wakes when the frozen Source becomes terminal. Failed image OCR moves
the Attempt to `GRADING_FAILED` for manual review.

Rollout order: migration `0034`, backend, dedicated `interactive` worker,
frontend, then `EXERCISE_ANSWER_OCR_PREVIEW_ENABLED=True`. Keep the flag off if
the interactive worker is absent.

## Risks (accepted, monitored)
1. `pipeline` queue congestion at deadlines (mass grading behind ingest) → monitor; dedicated `grading`
   queue is the named phase-2 escape hatch; kill-switch works today.
2. Grading output truncation on long exercises → per-section/batch chunking from day one (E6).
3. Reference-answer leak (serializer or assistant context) → explicit tests E5/E8 + structural strip;
   pre-reveal grading feedback remains a V2 hardening item (E25) because the grader sees the rubric.
4. Teacher trust in LLM grades → immutable LLM score exists, but append-only audit is still E22.
5. OCR quality on poor scans/handwriting via Avalai → unknown until opt-in benchmark; manual-entry
   fallback in the wizard is the product-level mitigation.
6. Student answer/reference media privacy → E14 made image paths server-owned, but raw serving is not the
   final privacy boundary; E23 is required before broad production claims of private media.
7. God-file growth → all new views in `views_exercises.py`; reviewer rejects additions to `views.py`.

## Resolved decisions (product owner, 2026-07-05)
1. **Reference-answer reveal is gated on the DEADLINE, not on grading (V1 policy).** Reference answers unlock when
   `deadline < now` (no-deadline exercise → on the student's own GRADED submission). Prevents the
   early-submitter leak window. A dedicated **«پاسخ تمرین‌های تمام‌شده»** student area
   (`GET student/exercises/answers/`) browses past exercises' answers. The assistant may teach from the
   reference answer only once that same reveal condition holds. V2 keeps deadline-gated reveal for shared
   homework/assessment, but moves no-deadline homework/assessment to E21's explicit shared release policy.
2. **LLM grade shown immediately** (labeled «نمره‌دهی هوشمند», override later); review-gate = phase 2
   per-exercise option.

## Dissent (recorded)
product-manager proposed deferring the **per-section** assistant toggle to phase 2 (exercise-level covers
~80%). Chair kept it in MVP: it is an explicit owner requirement and costs one bool field + one AND in
the server guard given the section model already exists.
