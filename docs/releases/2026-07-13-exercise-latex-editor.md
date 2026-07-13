# 2026-07-13 — Exercise LaTeX Editor

Commits: `feat(exercise): add live LaTeX editor` · Scope: frontend

Teacher exercise question/reference editing and the shared math renderer.

## Changes

- Added a live KaTeX preview above every teacher question and reference-answer input.
- Added an optional visual math keyboard with common operators, fractions, roots, powers, sets,
  trigonometry, Greek letters, sums, and infinity.
- Keyboard actions insert standard Markdown/LaTeX at the current text cursor; selected text is used by
  structured templates where applicable.
- Kept the stored question and reference-answer fields unchanged, preserving the existing API,
  grading, and student rendering contracts.
- Escaped protected LaTeX content before restoring it into the shared renderer's HTML, preventing
  teacher-authored math delimiters from becoming executable markup.
- Disabled remote image rendering in the unsaved live-editor preview while preserving image rendering
  in the existing student content surfaces.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Rebuild and deploy the `front` service only.

## Verification

- `npx tsc --noEmit --pretty false`: 13 known baseline errors; zero errors in changed files.
- `npm run lint`: blocked before file linting by the known `.eslintrc.json` circular-config failure.
- `git diff --check`: passed (line-ending warnings only).
- `GET http://localhost:9002/teacher/my-classes/1/exercises`: HTTP 200.

## Rollback

- Revert the feature commit and rebuild the `front` service. No data rollback is required.
