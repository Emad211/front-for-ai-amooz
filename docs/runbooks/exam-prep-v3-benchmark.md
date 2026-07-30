# Runbook — Exam-prep extraction V3 benchmark

- **Status:** Living
- **Created:** 2026-07-30
- **Owner:** classes / exam-prep

## Purpose

Prove extraction accuracy and bounded resource use before enabling V3 for new production sessions.
Real source files are local test inputs only. Do not copy their content, filenames, paths, OCR output,
or answer keys into Git.

## Preconditions

1. Apply `classes.0039_exam_prep_extraction_v3` and `commons.0008_llmusagelog_context`.
2. Deploy the same backend image to the web app and existing `pipeline` worker.
3. Set all V3 quality thresholds, but keep `EXAM_PREP_EXTRACTION_VERSION=2`.
4. Confirm the worker consumes `pipeline` with prefetch 1.
5. Confirm Redis, PostgreSQL, and the existing private object storage are available.

## Local benchmark matrix

Run three independent source structures, each three times from a cold artifact:

| Case | Expected inventory | Required behavior |
|---|---:|---|
| A | source numbers 1–50 | questions before answer key; exactly 50 questions |
| B | source numbers 51–115 | answer key before questions; exactly 65 questions; unrelated 40–50 remain out of scope |
| C | source numbers 116–145 | questions before answer key; exactly 30 questions; unrelated prior-booklet answers remain out of scope |

These ranges are acceptance fixtures, not production assumptions. Numbering may start at any value,
contain gaps, and repeat across distinct section keys.

## Accuracy checks

For every cold run record only aggregate, non-content metrics:

- expected and extracted question counts
- question precision and recall
- answer-match precision
- quarantined and retried unit counts
- unmatched and out-of-scope answer counts
- provider call count, latency, and estimated cost
- worker RSS and restart count

Required result for all three runs of all three cases:

- question precision = 100%
- question recall = 100%
- answer-match precision = 100%
- no source solution is invented
- no out-of-scope answer becomes a question
- no accepted source block remains unprocessed

## Cache and concurrency checks

1. Rerun an unchanged accepted artifact. It must make zero new LLM calls.
2. Run four sessions concurrently.
3. Confirm provider concurrency never exceeds `LLM_PROVIDER_MAX_CONCURRENCY`.
4. Confirm no duplicate unit, stale commit, session resurrection, starvation, or worker OOM occurs.
5. Retry one quarantined page and verify unaffected accepted units are cloned without provider calls.

## Enablement

After all checks pass:

1. Set `EXAM_PREP_EXTRACTION_VERSION=3` on backend and pipeline worker.
2. Restart both so new sessions freeze version 3.
3. Keep image generation disabled.
4. Monitor anomaly, retry, quarantine, match rate, cost, latency, RSS/restarts, and publish rejection.

## Rollback

Set `EXAM_PREP_EXTRACTION_VERSION=2` and restart backend and worker. This affects only sessions created
after rollback. Existing V3 sessions keep their frozen version and review requirements.
