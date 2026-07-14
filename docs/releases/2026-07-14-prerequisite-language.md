# 2026-07-14 — Prerequisite language consistency

Commits: `defcf50`  ·  Scope: backend

## Changes

- Prerequisite extraction now detects language from the transcript's dominant natural prose instead of code or isolated technical terms.
- Prerequisite teaching uses a bounded source-language sample, so English topic names inside Persian courses no longer switch the generated notes to English.

## Migrations

- None.

## Env / config

- No new environment variables. Existing model fallback chains are unchanged.

## Rebuild

- Rebuild the shared backend/Celery image. No frontend rebuild is required.

## Verification

- `backend/.venv/Scripts/python.exe -m pytest backend/apps/classes/test_prompts_contract.py backend/apps/classes/test_step3_prerequisites.py backend/apps/classes/test_pipeline_chaining.py --no-migrations -p no:cacheprovider -q`: `71 passed`.
- Explicit prompt contract gate: `61 passed`.
- Full backend suite after repairing the stale Enrollment-roster fixtures: `1296 passed, 4 skipped`.
- Django system check: `System check identified no issues (0 silenced).`
- Migration check: `No changes detected`.
- `git diff --check`: clean.
- Frontend typecheck reports the existing 13 errors outside this backend-only change.
- Frontend lint remains blocked before file analysis by the repository's existing circular ESLint configuration.
- AI-engineer and code-reviewer audits found no correctness blocker; repeated language context was reduced to a documented 600-character cap.

## Rollback

- Revert the release commit and rebuild the shared backend/Celery image. No database rollback is required.
