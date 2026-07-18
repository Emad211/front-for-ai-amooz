# 2026-07-18 — Durable student exercise drafts

Scope: frontend

## Changes
- Preserve the latest typed exercise answer across rapid navigation, tab closure, refresh, and transient autosave failures.
- Flush pending answers on blur and page lifecycle events, restore interrupted drafts, and expose save/retry status to the student.
- Abort superseded autosave requests and prevent autosave from racing final submission.

## Migrations
None.

## Env / config
None.

## Rebuild
Rebuild the frontend image only.

## Verification
- `npm run typecheck`: no new errors in changed files; 11 pre-existing errors remain in admin/mock files.
- Targeted ESLint: unavailable because the existing ESLint 9 install is incompatible with the repository's legacy `.eslintrc.json` configuration.
- `pytest backend/apps/classes/test_exercise_student_api.py --no-migrations -p no:cacheprovider -q`: 27 passed.
- `python backend/manage.py makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: passed.

## Rollback
Revert the release commit; no database rollback is required.
