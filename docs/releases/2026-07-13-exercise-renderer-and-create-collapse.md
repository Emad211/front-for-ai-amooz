# 2026-07-13 — Exercise Renderer and Create Collapse

Commits: `fix(exercise): correct math rendering and collapse intake` · Scope: frontend

Teacher exercise rendering corrections and a quieter default creation workspace.

## Changes

- Overrode KaTeX's centered display-math default so pure solution blocks align physically left.
- Fixed the Markdown renderer's code pipeline by protecting code as placeholders until after source
  escaping, preventing generated `<code class=...>` markup from appearing as visible answer text.
- Kept code source escaped and rendered code elements explicitly LTR.
- Made the standalone `ایجاد تمرین جدید` card collapsed initially, matching the class/exam-prep
  creation sections.
- Preserved unfinished intake state while toggling the card and collapsed it after successful submit.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Rebuild and deploy the `front` service only.

## Verification

- `npx tsc --noEmit --pretty false`: 13 known baseline errors; zero errors in changed files.
- `npm run lint`: blocked before file analysis by the known circular `.eslintrc.json` configuration error.
- `git diff --check`: passed (line-ending warnings only).
- Local teacher exercise route smoke-check: HTTP 200.

## Rollback

- Revert the application commit and rebuild the `front` service. No data rollback is required.
