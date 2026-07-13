# 2026-07-13 — Teacher student management

Commits: `3c90ed9`  ·  Scope: backend + frontend

## Changes

- Teacher rosters, class cards, summaries, analytics, and message recipients now count real `Enrollment` records instead of pending invitations.
- Teachers can create idempotent multi-class invitations and manage pending invitations separately.
- Student profile, direct message, teacher-scoped suspension/restoration, and removal from personal classes are functional.
- The student table exports the current filtered result as a real RTL `.xlsx` workbook.

## Migrations

- `classes/0030_teacherstudentaccess.py`: additive DDL-only table for teacher-scoped access state. It does not rewrite or delete existing data and can be reversed by dropping the new table.

## Env / config

- No new environment variables or production configuration.

## Rebuild

- Rebuild the shared backend/Celery image so the migration and API changes are deployed together.
- Rebuild the frontend image for the new student-management UI and `exceljs` dependency.

## Verification

- Focused backend regression: `75 passed`.
- Django system check: `System check identified no issues (0 silenced).`
- Migration check: `No changes detected`.
- `git diff --check`: clean.
- Frontend typecheck: 13 pre-existing errors outside the changed student-management files; no new error in this change.
- Frontend lint is blocked by the repository's existing `next lint` circular ESLint configuration error before file analysis starts.
- Full backend suite was attempted but exceeded the 8-minute local release window while still CPU-bound; the process was terminated and no result is claimed.

## Rollback

- Revert the release commit, rebuild both images, and migrate `classes` back to `0029` if the access table must also be removed.
