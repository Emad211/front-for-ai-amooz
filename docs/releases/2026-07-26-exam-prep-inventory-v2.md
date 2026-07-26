# 2026-07-26 — Exam-prep inventory extraction v2

Scope: backend, existing pipeline worker, frontend

## Changes

- Separates page/source inventory, question extraction, answer extraction, deterministic matching,
  and final audit.
- Supports arbitrary source numbering and excludes answer records outside the question inventory.
- Adds durable extraction artifacts, source crops, optional verified generated candidates, teacher
  visual selection, and owner-scoped private visual streaming.
- Adds version-2 publication gate and idempotent failed-chunk retry.
- Adds image uploads to the existing exam-prep source intake.

## Migration

Apply `classes.0038_exam_prep_inventory_artifacts` before deploying the new application image.

## Configuration

See `docs/features/exam-prep-inventory-extraction.md`. Flags default off. No new bucket, queue, worker,
or runtime dependency is introduced.

## Rebuild targets

- backend web application
- existing Celery worker consuming `pipeline`
- frontend

## Verification

Verification results are recorded in the implementation task before release. Real source PDFs remain
local benchmark inputs and are not committed.

## Rollback

Disable `EXAM_PREP_IMAGE_GENERATION_ENABLED`, then `EXAM_PREP_EXTRACTION_V2`. The legacy extraction
path remains available and existing `exam_prep_json` projections remain readable.
