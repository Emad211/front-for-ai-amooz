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

Store answer media in a server-owned, revision-checked `StudentExerciseAnswerSource`
with content-immutable `StudentExerciseAnswerAsset` rows. OCR has four separate layers:
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

The Source is the current mutable draft, not an append-only revision table. Each finalized Attempt
snapshots the OCR projection that grading consumed. Source assets are served through an authenticated
student/owning-teacher endpoint. Superseded inactive blobs may be removed after the configured grace
period only when no current draft or Attempt references them.

The generic media proxy rejects OCR-source storage prefixes. Each Attempt freezes the exact asset IDs
used by that submission, and retention starts from deactivation rather than original upload time.
Originals are written through a dedicated private storage alias backed by the application's existing private
media bucket (or a local directory outside `MEDIA_ROOT`). The authenticated endpoint is the only answer-source
read path. Teachers may read only asset IDs frozen into an Attempt, not mutable draft media.

## Consequences

- Raw OCR and student corrections used by a finalized Attempt remain auditable in that Attempt;
  intermediate draft revisions are not a permanent ledger.
- Revision checks reject stale edits and stale task results.
- Whole-answer OCR costs one page/chunk transcription pass plus one text-only
  mapping pass, independent of question count; successful chunks are reused after mapping retries.
- Production requires one additional worker deployment and capacity budget.
- Private object storage is a release invariant; disabling the UI flag must not make already-applied OCR disappear
  from submission or grading.
- Mathematical correctness checking and pre-submit tutoring remain out of scope.
