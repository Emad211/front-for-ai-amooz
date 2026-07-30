# 2026-07-30 - Quality-gated exam-prep extraction V3

Scope: backend, existing pipeline worker, frontend

## Commits

- `d791137` - `feat(exam-prep): add quality-gated extraction v3`

## Changes

- Adds durable, revisioned extraction units for OCR, manifest, question, answer, and visual-detection
  stages.
- Rejects successful-but-invalid OCR using deterministic quality checks and one bounded retry.
- Quarantines suspicious source units and excludes them from downstream extraction.
- Preserves source block provenance and restricts automatic answer matching to deterministic evidence.
- Adds owner-scoped source preview and single-unit retry.
- Requires teacher confirmation bound to the current revision and projection before publication.
- Retains original V3 sources for controlled post-publication/cancellation cleanup.
- Advances bounded orphan-source and visual cleanup cursors without deleting live references.
- Denies retained source and visual blobs through the generic media route.
- Makes visual-asset deletion fail closed and applies an in-flight-write grace window.

## Migrations

Apply in this order:

- `commons.0008_llmusagelog_context`
- `classes.0039_exam_prep_extraction_v3`

Both are additive DDL-only migrations. No data backfill changes V1/V2 behavior. Index creation and
schema changes can briefly contend for PostgreSQL schema locks, so apply them before scaling the new
web and worker image.

## Env / config

Set these values on both the backend web application and the existing pipeline worker:

```env
EXAM_PREP_EXTRACTION_VERSION=2
EXAM_PREP_REQUIRE_TEACHER_REVIEW=True
EXAM_PREP_SOURCE_RETENTION_DAYS=7
PDF_OCR_MAX_OUTPUT_CHARS_PER_PAGE=24000
PDF_OCR_MAX_OUTPUT_TOKENS=16000
PDF_OCR_NATIVE_RATIO_LIMIT=3
PDF_OCR_ROBUST_Z_LIMIT=8
PDF_OCR_DUPLICATE_LINE_RATIO_LIMIT=0.35
PDF_OCR_MAX_ATTEMPTS=2
PDF_EXTRACTION_CONCURRENCY=2
LLM_PROVIDER_MAX_CONCURRENCY=8
```

`PDF_EXTRACTION_CONCURRENCY` changes from `4` to `2` to bound page-rendering and OCR memory pressure.
Keep `EXAM_PREP_EXTRACTION_VERSION=2` during deployment and benchmark. Change only that value to `3`
on both processes after the benchmark passes, then restart both. The version is frozen when each
session is created.

## Rebuild targets

- backend web application
- existing Celery worker consuming `pipeline`
- frontend

No new queue, worker, bucket, service, or runtime dependency is introduced.

## Rollout

Deploy migrations and all images while `EXAM_PREP_EXTRACTION_VERSION=2`. Run the benchmark in
`docs/runbooks/exam-prep-v3-benchmark.md`, then set version 3 on backend and pipeline worker and restart
both. Existing sessions keep their stored version.

## Verification

Commands completed on the release worktree:

```text
Focused security/lifecycle suite
44 passed

Fresh PostgreSQL migration and V3 integration suite
79 passed

python -m pytest backend/apps/classes -q
960 passed, 3 skipped

python -m pytest backend/apps/classes/test_prompts_contract.py -q
71 passed

python -m pytest -q --no-migrations -p no:cacheprovider
1504 passed, 5 skipped

DATABASE_URL=<local-postgresql> python -m pytest -q --create-db
1507 passed, 2 skipped

python backend/manage.py check
System check identified no issues (0 silenced).

python backend/manage.py makemigrations --check --dry-run
No changes detected

npm run build
Completed successfully
```

`npm run typecheck` still reports 10 known errors in unrelated admin-ticket and mock-message fixtures;
none is in a file changed by this release. `npm run lint` remains blocked by the repository's existing
Next/ESLint circular-config failure.

## Rollback

Set `EXAM_PREP_EXTRACTION_VERSION=2` for new sessions. Do not rewrite `pipeline_version` on existing
artifacts. Existing V3 sessions must finish or be cancelled under V3.

Revert the release commit and redeploy the prior backend/frontend image only after all V3 sessions are
finished or cancelled. Do not reverse `classes.0039` or `commons.0008` after V3 rows exist unless a
separate data-retention decision and export/removal procedure has been approved. Both migrations are
additive and can remain applied while new sessions use version 2.
