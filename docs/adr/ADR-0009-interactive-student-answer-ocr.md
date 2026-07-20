# ADR-0009: Interactive OCR Sources for Student Exercise Answers

- Status: Accepted
- Date: 2026-07-20
- Supersedes: the grading-time-only handwriting OCR path in ADR-0004

## Context

Students can submit one handwritten answer as photos or upload a multi-page
answer bundle. Running OCR only during grading hides transcription mistakes and
can turn an unreadable image into a false zero. A whole-answer bundle also must
be transcribed once, not resent to vision separately for every question.

## Decision

Store answer media in a server-owned, revisioned `StudentExerciseAnswerSource`
with immutable `StudentExerciseAnswerAsset` rows. OCR has four separate layers:
source media, raw AI reading, student-reviewed reading, and grading. OCR never
receives reference answers or grading notes and never judges correctness.

Question sources are projected into the draft after OCR. Whole-exercise sources
require one explicit review/apply action. Typed answers and OCR remain separate
channels and are combined only by grading. Final submit freezes source IDs and
revisions in the Attempt. A valid preview is reused without a second vision
call; terminal OCR failure produces `GRADING_FAILED` for manual review rather
than an automatic zero.

Interactive OCR runs on a dedicated `interactive` Celery queue. The feature is
disabled by default and is enabled only after migration, backend, worker, and
frontend are deployed together.

## Consequences

- Raw OCR and student corrections remain auditable alongside original media.
- Revision checks reject stale edits and stale task results.
- Whole-answer OCR costs one page/chunk transcription pass plus one text-only
  mapping pass, independent of question count.
- Production requires one additional worker deployment and capacity budget.
- Mathematical correctness checking and pre-submit tutoring remain out of scope.
