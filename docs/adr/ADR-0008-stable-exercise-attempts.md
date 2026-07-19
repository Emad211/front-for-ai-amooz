# ADR-0008: Stable, append-only exercise attempts

- Status: Accepted
- Date: 2026-07-19
- Supersedes: the destructive redo behavior in ADR-0004

## Context

`StudentExerciseSubmission` previously stored both the editable draft and the only grading result.
Allowing a redo cleared that result and grading the same answers called OCR/LLM again. Provider
variance could therefore change a score even when the student changed nothing, and the previous
teacher review was lost.

## Decision

- Each final submit creates an immutable `StudentExerciseAttempt` snapshot.
- The snapshot includes the full question/rubric contract. Grading and historical result rendering use
  that snapshot rather than mutable current exercise questions.
- `StudentExerciseSubmission` remains the stable draft/current-projection record for compatibility.
- `current_attempt` prevents a stale Celery task from overwriting a newer projection.
- Per-question SHA-256 fingerprints include the answer, ordered image paths and byte hashes, question/rubric,
  point budget, configured models, algorithm version, and prompt hashes.
- A matching previous fingerprint reuses the prior AI score, feedback, and OCR text without an LLM
  call. Teacher score and feedback never carry into a new attempt.
- Changed questions alone are OCRed/graded. Progress is saved per successful unit so task retries
  resume rather than start over.
- Transient handwriting OCR/provider failures propagate to Celery retry and never persist an empty OCR
  cache entry. New answer uploads use server-generated UUID object keys to prevent overwrite.
- OCR, grading, and structured-output repair usage is attributed to the owning teacher and class
  session through the task-local LLM tracking context.
- Report cards use the latest graded attempt, never the highest score.
- Teacher and owning student can inspect attempt history; cross-owner attempt IDs return 404.
- A redo closes the no-deadline reveal gate until the replacement attempt is graded. Historical
  attempts remain visible, but cannot expose reference answers while an editable draft is open.
- Pre-reveal model feedback is replaced with fixed label-based copy. Full grader feedback and missing
  points are available to the teacher and become student-visible only after the reveal gate opens.
- Final task projection and teacher overrides lock the Submission row and re-check `current_attempt`,
  so concurrent redo cannot be overwritten and historical attempts cannot be edited.

Existing rows are backfilled as attempt 1. Their historical model/prompt inputs cannot be proven, so
the first post-deploy redo is conservatively regraded when no trustworthy fingerprint exists; all
subsequent attempts are stable. Their question snapshot is the best available contract at migration
time because older versions did not retain the original question revision.

## Consequences

The deployment must drain pipeline workers, apply the DDL and DML migrations, then start matching
backend/workers before releasing the frontend. OCR text and fingerprints are private audit data and
must not be serialized to students or logs.
