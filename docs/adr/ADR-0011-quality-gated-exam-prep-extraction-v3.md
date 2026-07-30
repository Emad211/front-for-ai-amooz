# ADR-0011 — Quality-gated exam-prep extraction V3

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** product owner, backend engineer, AI engineer
- **Consulted:** database engineer, AI engineer, security auditor, code reviewer

## Context

ADR-0010 separated question and answer inventories, but a provider could still return HTTP 200 with
truncated, repeated, numerically unstable, or abnormally large OCR. Treating that response as valid
could contaminate the manifest and both inventories, producing internally consistent but false
questions. Whole-session retries also repeated accepted work and made concurrent delivery harder to
reason about.

## Decision

Persist every extraction operation as a versioned unit and accept its output only after a deterministic
quality contract passes.

- Freeze `pipeline_version` when the session is created. Environment changes never reroute an active
  session.
- Give each OCR, manifest, question, answer, and visual unit a fingerprint, revision, lease, attempt
  budget, provider metadata, output snapshot, and quality report.
- Treat Redis slots as a provider-capacity limiter only. Database row locks and leases are the
  concurrency source of truth.
- Retry a suspicious unit at most once. Quarantine it when the retry remains invalid or its number set
  is unstable, and exclude its text from all downstream stages.
- Preserve stable source block IDs through question and answer extraction. Automatic answer matching
  is limited to exact section/number, globally unique number, and same-block adjacency.
- Require a clean audit and teacher confirmation bound to the current artifact revision and projection
  fingerprint before publication.
- Retain the original source in the existing private storage until seven days after publication or
  cancellation. Unpublished sessions retain it until explicitly removed.

## Alternatives considered

- **Trust successful provider responses** — rejected because transport success does not prove semantic
  completeness or non-repetition.
- **Retry the entire session** — rejected because it repeats accepted calls, increases cost, and creates
  more opportunities for divergent output.
- **Use cache locks as correctness locks** — rejected because cache eviction or expiry must not permit
  duplicate commits.
- **Silently fall back to V1/V2** — rejected because it changes the contract of a running session and
  makes audit claims unreliable.

## Consequences

- Positive: suspicious pages cannot create questions or answers.
- Positive: accepted units are reusable by fingerprint, so a retry pays only for invalidated work.
- Positive: visual detection is a persisted V3 unit rather than an untracked provider call.
- Positive: review confirmation cannot survive an edit, retry, or projection change.
- Positive: no new queue, worker, bucket, or runtime dependency is introduced.
- Negative: V3 stores additional metadata and accepted unit payloads.
- Negative: quarantined sources require teacher action and intentionally block publication.
- Accepted risk: quality thresholds require production observation and may quarantine unusual but valid
  pages; one stable retry can accept soft outliers except persistent repetition.
- Accepted risk: the orphan-source sweep cursor is operational state in the shared cache. Losing that
  cursor restarts the bounded scan from the beginning but cannot delete an active session source.
- Follow-up: remove legacy V1/V2 paths only after V3 benchmark and production telemetry meet the
  acceptance threshold.

## Dissent

None recorded.
