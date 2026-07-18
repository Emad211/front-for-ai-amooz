# 2026-07-18 — Integer student-count chart axis

Scope: frontend

## Changes
- Restrict the teacher student-growth chart Y axis to whole-number ticks and render those counts with Persian digits.

## Migrations
None.

## Env / config
None.

## Rebuild
Rebuild the frontend image only.

## Verification
- `npm run typecheck`: no new errors in the changed file; existing repository baseline reported separately.
- `git diff --check`: passed.

## Rollback
Revert the release commit; no database rollback is required.
