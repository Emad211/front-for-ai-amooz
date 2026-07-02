# Reference — `apps/classes` data model (the core domain)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `8a0a65c`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B4
- **Layer:** backend-app (data model only; views split across B5/B6/B7, pipeline in L4-L10)

## Purpose
The entity map of the core domain — a course-creation session, its generated structure (sections/units),
prerequisites, quizzes, final exam, student progress/attempts, and course chat. This is the reference
every classes view (B5-B7) and pipeline stage (L4-L10) links to for field semantics.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/models.py` (579) | 17 models below |
| `apps/classes/permissions.py` (28) | `IsTeacherUser`, `IsStudentUser` |
| `apps/classes/migrations/0001–0023` | Lineage below |

**Out of scope:** views → B5/B6/B7; pipeline task bodies → L4-L10; JSON *generation* contracts → L8
(this doc covers field *shape/semantics*, L8 covers how they're produced).

## Public surface — the 17 models
**Session + roster**
- `ClassCreationSession` — the pipeline root; carries `Status` (state machine below), `teacher`,
  nullable `organization` + `study_group`, `source_file`, publish + cancellation fields.
- `ClassInvitation` — per-session phone invite (`uniq_class_invite_session_phone`,
  `uniq_class_invite_session_code`).
- `StudentInviteCode` — global stable invite code per phone (the B2 invite-login lookup).
- `Enrollment` — student↔session (`uniq_enrollment_session_student`; index `[student, session]`).
- `StudentUnitProgress` — per-unit completion (`uniq` on session+student+unit).
- `StudentExamPrepAttempt` — exam-prep attempt (`answers` JSON; `uniq` session+student).

**Generated content**
- `ClassLearningObjective`, `ClassSection`, `ClassUnit` (`image_ideas` JSON), `ClassPrerequisite`,
  `ClassAnnouncement` — the structure the pipeline writes (all uniqueness-scoped to session).

**Assessment**
- `ClassSectionQuiz` — per (session, section, student) quiz; **`questions` JSON**; `last_score_0_100`,
  **`last_passed` (nullable)** — the adaptive rate-limiter field.
- `ClassSectionQuizAttempt` — `answers` + **`result` JSON** (`result['per_question']` drives weak-points).
- `ClassFinalExam` — per (session, student); **`exam` JSON**; `last_*` fields.
- `ClassFinalExamAttempt` — `answers` + `result` JSON.

**Chat**
- `StudentCourseChatThread` (uniq per session+student), `StudentCourseChatMessage`
  (`payload`/`suggestions` JSON; indexes `[thread, created_at]`, `[lesson_id, created_at]`).

## Key flows / state machine
`ClassCreationSession.Status` (`models.py:12-32`) — the pipeline's spine (L4 drives it):
- **Class (5-step):** TRANSCRIBING → TRANSCRIBED → STRUCTURING → STRUCTURED → PREREQ_EXTRACTING →
  PREREQ_EXTRACTED → PREREQ_TEACHING → PREREQ_TAUGHT → RECAPPING → RECAPPED.
- **Exam-prep (2-step):** EXAM_TRANSCRIBING → EXAM_TRANSCRIBED → EXAM_STRUCTURING → EXAM_STRUCTURED.
- **Shared terminal:** FAILED, **CANCELLED** (teacher cancel — the pipeline-cancellation feature).

## Data & invariants
- **JSON field contracts** (shape here; generation in L8): `ClassSectionQuiz.questions`,
  `ClassFinalExam.exam`, `*Attempt.result` (with `per_question` incl. `correct_answer`/`explanation` on
  submit but hidden on GET — B6); `ClassUnit.image_ideas`; chat `payload`/`suggestions`. The adaptive loop
  reuses these JSON fields — **no migration** for content-shape changes.
- **`last_passed` reset = rate-limiter:** regenerate resets `last_passed`/`last_score` to None so a
  student must take+fail a fresh assessment before regenerating again (B6/L8). Don't "tidy" this.
- Cancellation fields on the session (`cancel_requested`, `celery_task_id`) + CANCELLED status — the
  cooperative-cancel contract (L4); migration `0022_pipeline_cancellation`.
- Uniqueness everywhere is session-scoped; org/group FKs are `SET_NULL` (a deleted org doesn't cascade
  away classes).
- **Migration lineage:** 0001–0023 (23 migrations); notable — `0019` org FK, `0021` enrollment+progress,
  **`0022` pipeline cancellation (renumber precedent)**, `0023` study_group FK.

## Gotchas
- `IsStudentUser` deliberately allows TEACHER too (teachers can learn/take exams) — not a bug.
- `models.py` is 579 lines — grep by model; don't read whole in future passes.
- Quiz/exam are per-student rows (not shared), because the adaptive loop regenerates them per student.

## Cross-links
[backend-classes-teacher-views.md] (B5) · [backend-classes-student-views.md] (B6) ·
[backend-classes-exam-prep.md] (B7) · [llm-pipeline-orchestration.md](llm-pipeline-orchestration.md)
(L4, drives Status) · [llm-quizzes-adaptive.md] (L8, generates questions/exam JSON) ·
[backend-organizations.md](backend-organizations.md) (org/group FKs) · memory: `adaptive-quiz-loop`,
`pipeline-cancellation` · `.claude/agents/database-engineer.md`.

## Verified-by
- `rg "^class |class Status|UniqueConstraint|models.Index|JSONField|ForeignKey" models.py` → the 17-model
  inventory + constraints + JSON fields + indexes cited above.
- Read (2026-07-02): `models.py:12-46` (Status enum + session FKs), `:417-456` (ClassSectionQuiz +
  Attempt), `permissions.py` (28).
- `ls migrations/ | grep -cE '^0[0-9]'` → 23 migrations; last five confirm `0022` cancellation, `0023`
  study_group.
- NOT read whole: the 579-line `models.py` field bodies (inventory via grep is the contract; field-level
  JSON shape lives in L8). NOT verified live: DB constraint behavior on Postgres (sqlite in tests).
