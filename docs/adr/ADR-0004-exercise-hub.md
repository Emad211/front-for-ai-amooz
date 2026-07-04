# ADR-0004 — Exercise Hub: models in `classes`, async LLM ingest/grading on the pipeline queue, structural answer-leak guard

- **Status:** Accepted
- **Date:** 2026-07-05 · **Deciders:** tech-lead (chair) + product owner · **Consulted:** product-manager, ai-engineer, ux-designer (council 2026-07-05)

## Context
The product needs a per-class exercise feature: teacher uploads PDF/photos, LLM extracts structure,
teacher sets reference answers, students submit (text/handwriting photos), LLM grades against the
teacher's rubric, report cards are produced, and a toggleable AI assistant helps during solving. The
dashboard calendar currently renders mock data (`dashboard-service.ts` → `MOCK_CALENDAR_EVENTS`) and no
model in the platform has a deadline/schedule field. Adjacent machinery already exists and is
battle-tested: `pdf_extraction.py`, `exam_prep_handwriting_vision`, `text_grading`,
`generate_structured` (apps/commons/structured_llm.py), the exam-prep attempt pattern
(unique(session, student)), and the owner-404 / phone-scope-404 permission models. Full spec:
[docs/features/exercise-hub.md](../features/exercise-hub.md).

## Decision
Build the Exercise Hub inside `apps/classes` as five new models FK'd to `ClassCreationSession`, with
async LLM ingest and on-submit async grading on the Celery `pipeline` queue, three new prompt keys
(`exercise_structure`, `exercise_grading`, `exercise_assistant_chat`), and a **structural** answer-leak
guard (reference answers are stripped from the assistant's context before grading, and from all student
serializers before GRADED).

Essential detail:
- New views live only in `apps/classes/views_exercises.py`; services in `services/exercise_*.py`
  (god-file quarantine for the 195 KB `views.py`).
- Migrations: `0024_exercises` (pure DDL) and a separate `0025` adding nullable
  `ClassCreationSession.scheduled_at` (calendar events for timed exam-prep). DML/DDL split law holds.
- Grading: one `generate_structured` call per `EXERCISE_GRADING_BATCH_SIZE` (default 5) questions;
  MCQ/fill-blank graded deterministically without LLM; totals via `sum()`; teacher override writes
  `teacher_score` beside an immutable `llm_score`; kill-switch `EXERCISE_LLM_GRADING`.
- Grading output shape reuses the final-exam score contract (`score_points`/`max_points`/`per_question`)
  so `compute_weak_points_from` and aggregation reuse existing parsers.
- Assistant toggle: effective = exercise-level AND section-level, enforced server-side (403
  `assistant_disabled`); per-section toggle stays in MVP (explicit owner requirement).
- Calendar: one aggregate endpoint `GET /api/classes/student/calendar/` (Gregorian ISO, Tehran tz);
  Jalali conversion is the frontend service layer's job.
- OCR is 100% reuse: `pdf_extraction.default` for PDF pages AND uploaded photos (a photo is a page);
  student handwriting reuses `exam_prep_handwriting_vision` verbatim.
- Models env-only (`EXERCISE_*_MODEL` chains ending in `MODEL_NAME`, raise when absent) — per the
  established no-hardcoded-model law.

## Alternatives considered
- **A separate `exercises` app** — rejected: ownership, phone-scoping and the publish gate all derive
  from `ClassCreationSession`; a new app means cross-app FKs, violating the no-cross-app-coupling rule.
- **Sync (in-request) extraction/grading** — rejected: multi-minute LLM work blocks gunicorn workers and
  times out; the `pipeline` queue + status machines already exist for exactly this.
- **Reusing `text_grading` for exercise grading** — rejected: single-question 0–100 scale, a hard
  never-reveal rule that conflicts with post-submit feedback, and no batching.
- **Prompt-instruction-only leak guard for the assistant** — rejected: "don't reveal" instructions are
  brittle under injection; not giving the model the answer at all is strictly stronger.
- **Adaptive/regenerate loop for exercises** — rejected: exercises are teacher-authored static content;
  regeneration contradicts the product's mental model.

## Consequences
- Positive: maximal reuse (OCR, handwriting vision, structured output, score shape, permission models);
  zero new infrastructure; the platform gets its first real deadline + calendar data; grading cost is
  bounded by deterministic objective-question grading and batch knobs.
- Negative / accepted risk: `pipeline` queue contention at deadlines (named escape hatch: dedicated
  `grading` queue in phase 2; kill-switch today); grading is the platform's dominant recurring token
  cost (~420k/class-round worst case); Avalai OCR quality on poor scans unverifiable locally (wizard's
  manual-entry fallback is the mitigation).
- Follow-ups created: E1–E12 build roadmap in the feature spec; phase-2 backlog (weighted combined
  report card, SMS reminders, per-student extensions, review-gate, answer-key upload strategy, PDF
  export).

## Dissent (if any)
product-manager: defer the per-section assistant toggle to phase 2 (exercise-level covers ~80% of the
need). Overruled by the chair — explicit owner requirement, and marginal cost is one boolean + one AND
given the section model exists. Recorded, not erased.
