# 2026-07-23 — Class and exam student actions

Scope: frontend

## Changes

- Connects `افزودن دانش‌آموز` on class and exam-prep roster pages to the existing owner-scoped
  invitation endpoints.
- Adds a shared multi-phone invitation dialog with normalization, deduplication, complete batch
  validation, and explicit pending-invitation feedback.
- Connects `خروجی اکسل` to a real `.xlsx` export of the currently displayed roster.
- Generates a right-to-left workbook with phone, email and invite-code identity columns, Persian
  dates, a frozen header, auto-filter, typed percentage column, and Persian labels.
- Loads the existing ExcelJS dependency only when an export is requested.
- Keeps organization-managed rosters read-only.

## Migrations

None.

## Env / config

No new or changed environment variables.

## Rebuild

Rebuild and deploy the frontend image only. The backend and Celery workers do not need rebuilding.

## Verification

- Backend invitation regression suite: 10 passed.
- Frontend production build: passed.
- `git diff --check`: passed.
- Frontend `npm run typecheck`: 11 pre-existing errors outside changed files; no new errors in the
  changed files.
- Frontend lint remains unavailable because the repository's existing `next lint` configuration is
  incompatible with the installed ESLint version.

## Rollback

Revert the release commit and redeploy the previous frontend image. No database rollback is required.
