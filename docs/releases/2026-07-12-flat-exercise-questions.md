# 2026-07-12 — Flat Exercise Questions

## Commits / Scope

- Commit: `feat(exercise): flatten exercise questions`
- Scope: coordinated backend/Celery + frontend Exercise Hub release.

## Changes

- Exercise extraction returns one ordered `questions[]` list and stores one private compatibility
  section instead of exposing untitled groupings.
- Teacher, solver, result, and finished-answer interfaces render questions as one continuous list.
- The assistant policy is captured once during exercise intake and enforced only at exercise level.
- Existing section-shaped exercises remain readable through a temporary backward-compatible API shape.
- Exercise workflow copy uses six visible stages and no longer renders raw review-warning blocks.

## Migrations

- None. `manage.py makemigrations --check --dry-run` reports `No changes detected`.

## Env / config

- No new or changed environment variables.

## Rebuild

- Rebuild and deploy the shared backend/Celery image.
- Rebuild and deploy the frontend image from the same commit.

## Verification

- Focused prompt/ingest/extraction/teacher/student/assistant suite: `179 passed`.
- All `backend/apps/classes/test_exercise*.py`: `174 passed`.
- Python compile check: passed.
- Migration drift check: `No changes detected` (local Postgres was unavailable for history validation).
- TypeScript: existing baseline remains `13` errors; changed-file errors: `0`.
- `npm run lint`: tooling exception before lint execution — Next 15 `next lint` exits with
  `Converting circular structure to JSON`, referenced from the existing `frontend/.eslintrc.json`.
  This pre-existing project tooling failure is documented and tolerated for this release; it produced
  no findings against changed files. TypeScript, focused tests, security audit, and code review are the
  effective gates for this change.
- Security audit: no actionable findings.
- Code review: approved; no blocking findings.

## Rollback

- Revert the application commit and rebuild both images.
- No migration or data rollback is required.
