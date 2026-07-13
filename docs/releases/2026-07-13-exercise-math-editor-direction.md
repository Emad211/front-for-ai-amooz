# 2026-07-13 — Exercise Math Editor Direction

Commits: `fix(exercise): improve math editor direction and keyboard` · Scope: frontend

Direction-aware preview rendering and a more approachable visual math keyboard.

## Changes

- Made Persian and mixed-language paragraphs RTL/right-aligned while rendering Latin-only, numeric,
  and math-only paragraphs LTR/left-aligned.
- Fixed standalone negative-number placement such as `-5` inside RTL exercise pages.
- Replaced the dense symbol list with Persian-labeled category tabs and larger stable keys.
- Added negative numbers, grouping, percentages, factorials, implications, limits, integrals,
  derivatives, vectors, geometry symbols, matrices, and equation systems.
- Added delimiter awareness: keyboard input inside an existing math expression inserts raw LaTeX and
  does not create nested math delimiters.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Rebuild and deploy the `front` service only.

## Verification

- `npx tsc --noEmit --pretty false`: 13 known baseline errors; zero errors in changed files.
- `npm run lint`: blocked by the documented pre-existing `.eslintrc.json` circular-config failure.
- `git diff --check`: passed (line-ending warnings only).
- Local teacher exercise route smoke-check: HTTP 200.

## Rollback

- Revert the application commit and rebuild the `front` service. No data rollback is required.
