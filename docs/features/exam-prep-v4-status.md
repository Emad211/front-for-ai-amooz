# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> Update this file with every meaningful V4 implementation change.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — fast page classification and virtual split
- **State:** Phase 1 complete; Phase 2 implementation started
- **Last updated:** 2026-08-03

## Verified baseline

- Phase 0 architecture and benchmark contracts are committed.
- The three private benchmark PDFs are three independent exams.
- No private PDF, page image, OCR text, filename, answer, or solution content is committed.
- Existing V1/V2/V3 API and pipeline code has not been changed.
- V4 remains disabled unless `EXAM_PREP_V4_ENABLED` is enabled through Django settings or environment configuration.

## Phase 1 — complete

### Source-domain schema

Added additive models under the existing `classes` app:

- `ExamProject`
- `ExamSourceDocument`
- `ExamSourcePage`
- `ExamSourceSegment`
- shared `ExamSourceRole`

The schema stores ownership, organization scope, project revision, private source-object references, page metadata, classifier roles, teacher overrides, virtual page ranges, fingerprints, retention metadata, and processing status.

### Isolation rules

- One PDF creates one independent project by default.
- Several PDFs in one request create several projects.
- Equal SHA-256 values do not merge projects.
- Idempotent retries reuse the same project only when both request and document identifiers match.
- A reused request identifier with different source metadata is rejected.
- The base teacher queryset is owner-scoped.
- Duplicate-page references may not cross project boundaries.
- Segment page ranges and classifier confidence values have database constraints.

### Feature isolation

- No V4 endpoint is exposed yet.
- Project creation raises while `EXAM_PREP_V4_ENABLED` is false.
- Legacy exam-prep models and tasks remain untouched.

### Focused CI

`.github/workflows/exam-prep-v4.yml` validates V4 against PostgreSQL 16:

1. production backend dependency installation;
2. Django system check;
3. classes migration drift check;
4. focused V4 tests with real migrations.

## Phase 1 test evidence

Focused workflow run `30773563369`, job `91564811542`, completed successfully:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
13 passed in 5.68s
```

Verified on PostgreSQL 16 with migration `0040` applied through pytest `--create-db`.
The database also demonstrably enforced the invalid segment-range and classifier-confidence constraints used by the negative tests.

Repository-wide frontend CI remains red on pre-existing files only:

- `src/app/(admin)/admin/tickets/page.tsx`
- `src/constants/mock/messages-data.ts`

No V4 frontend file exists yet. The repository-wide backend suite was still running at the last observation and is not claimed as green.

## Phase 2 scope now in progress

The next implementation slice is intentionally independent of an LLM provider:

- tolerant per-page classification records;
- malformed sibling records must not invalidate valid pages;
- missing pages become `unknown` rather than disappearing;
- teacher role overrides remain authoritative;
- deterministic conversion of page roles into contiguous virtual segments;
- persistence bound to document classification revision and fingerprint;
- structural tests for question-first, answer-first, and cover-in-the-middle patterns.

The actual fast multimodal LLM adapter will be added only after this contract and persistence layer pass focused PostgreSQL tests.

## Files added or changed so far

- `.github/workflows/exam-prep-v4.yml`
- `backend/apps/classes/models_v4.py`
- `backend/apps/classes/migrations/0040_exam_prep_v4_source_foundation.py`
- `backend/apps/classes/apps.py`
- `backend/apps/classes/services/exam_prep_v4_projects.py`
- `backend/apps/classes/test_exam_prep_v4_source_foundation.py`

## Current risks

1. Repository-wide CI has unrelated baseline failures; focused V4 CI remains the authoritative signal for V4-only changes.
2. Actual classifier latency and accuracy are unverified until a provider adapter and private benchmark runner exist.
3. Page roles are not yet generated from PDFs; only the data foundation exists.
4. Source-file upload and private page rendering are not yet exposed through V4 APIs.

## Phase 2 completion gate

- page-classification contract accepts partial valid output;
- malformed records are reported without deleting valid records;
- every source page receives an explicit role, including `unknown`;
- segment proposals preserve arbitrary internal ordering;
- answer-first and cover-in-the-middle structures are represented correctly;
- persistence is revision-safe and idempotent;
- focused PostgreSQL tests pass;
- private live classification benchmark remains explicitly unclaimed until executed.

## Next verified step

Implement and test the tolerant classification contract and deterministic segment builder before adding the LLM adapter.
