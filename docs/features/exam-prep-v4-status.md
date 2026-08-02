# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> Update this file with every meaningful V4 implementation change.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 1 — source-domain foundation
- **State:** Implementation in progress; CI validation pending
- **Last updated:** 2026-08-03

## Verified baseline

- Phase 0 architecture and benchmark contracts are committed.
- The three private benchmark PDFs are three independent exams.
- No private PDF, page image, OCR text, filename, answer, or solution content is committed.
- Existing V1/V2/V3 API and pipeline code has not been changed.
- V4 remains disabled unless `EXAM_PREP_V4_ENABLED=True` is supplied in Django settings.

## Implemented in Phase 1

### Source-domain schema

Added additive models under the existing `classes` app:

- `ExamProject`
- `ExamSourceDocument`
- `ExamSourcePage`
- `ExamSourceSegment`
- shared `ExamSourceRole`

The initial schema stores ownership, organization scope, project revision, private source-object references, page metadata, classifier roles, teacher overrides, virtual page ranges, fingerprints, retention metadata, and processing status.

### Isolation rules implemented

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

## Files added or changed

- `backend/apps/classes/models_v4.py`
- `backend/apps/classes/migrations/0040_exam_prep_v4_source_foundation.py`
- `backend/apps/classes/apps.py`
- `backend/apps/classes/services/exam_prep_v4_projects.py`
- `backend/apps/classes/test_exam_prep_v4_source_foundation.py`

## Test evidence

| Date | Commit | Command / environment | Result |
|---|---|---|---|
| 2026-08-03 | `888abdde` | GitHub Actions run `30773375531` | In progress; do not mark Phase 1 complete yet. |

Targeted assertions added:

- models are registered under the `classes` app;
- feature flag defaults to disabled behavior;
- three PDFs create three projects;
- identical file hashes never merge projects;
- network retry does not duplicate projects;
- conflicting retry metadata is rejected;
- owner scope excludes another teacher's project;
- cross-project page deduplication is rejected;
- teacher role overrides classifier role;
- invalid segment ranges and confidence values are rejected.

## Current risks under verification

1. Registration of the isolated model module through `ClassesConfig.ready()` must pass Django system checks and migration autodetection.
2. Migration `0040` must apply cleanly on PostgreSQL after the existing organization and V3 migrations.
3. Constraint SQL must behave consistently on PostgreSQL.
4. Repository-wide CI has known unrelated frontend and model-ENV failures; V4 failures must be separated from baseline failures.

## Phase 1 completion gate

Phase 1 is not complete until all of the following are evidenced:

- migration applies on PostgreSQL;
- `makemigrations --check --dry-run` reports no V4 drift;
- targeted V4 tests pass;
- Django system check passes;
- owner/project isolation negative tests pass;
- any CI failure is classified as V4-caused or pre-existing;
- this ledger is updated with exact results.

## Next verified step

Read GitHub Actions run `30773375531`. Fix any V4-caused migration, registry, or test failure before adding upload APIs or page classification.
