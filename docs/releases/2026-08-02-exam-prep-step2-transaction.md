# 2026-08-02 - Exam-prep step 2 transaction fix

Commits: pending | Scope: backend

## Changes

- Restore the missing Django transaction import in exam-prep structure step 2.
- Add a regression test that executes the V3 projection commit boundary and
  proves extraction is not repeated after a successful result.

## Root cause

The V3 atomic commit path called `transaction.atomic()` from
`process_exam_prep_step2_structure`, but `transaction` was imported only inside
the unrelated source-ingestion function. The resulting `NameError` happened
after extraction, so the retry wrapper repeated expensive LLM work before the
session was marked failed.

## Migrations

None.

## Env / config

None.

## Rebuild

Rebuild and restart the backend image and pipeline worker. The frontend is
unchanged.

## Verification

- Regression reproduced before the patch with
  `NameError: name 'transaction' is not defined`.
- Relevant exam-prep and pipeline suite: `117 passed`.

## Known limitation

The full-pipeline coordinator currently reports a failed result payload while
Celery records the coordinator task as `SUCCESS`. The database session is still
marked `FAILED`; aligning Celery task state is separate observability work and
is intentionally outside this limited root-cause patch.

## Rollback

Revert the fix commit. No schema or data rollback is required.
