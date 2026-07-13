# 2026-07-13 — Mutable Exercise Settings

Commits: `feat(exercise): add mutable exercise settings` · Scope: both

Teacher Exercise Hub settings editor and owner-scoped exercise PATCH.

## Changes

- Added a single exercise-level assistant switch to the mutable settings panel.
- Reworked the deadline control into the same structured panel without a floating field label.
- Kept section-level assistant controls removed.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Backend/Celery and frontend images.

## Verification

- Teacher API + assistant regression suite: `63 passed`.
- TypeScript changed-file errors: `0`; known total baseline: `13`.
- `makemigrations --check --dry-run`: `No changes detected`.
- `git diff --check`: clean.
- Code-review findings: fixed.
- Local frontend on port `9002`: route returned `HTTP 200`.

## Rollback

- Revert the application commit and rebuild backend/Celery and frontend images.
