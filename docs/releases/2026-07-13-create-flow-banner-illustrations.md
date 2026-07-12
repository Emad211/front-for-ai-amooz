# 2026-07-13 — Create Flow Banner Illustrations

## Commits / Scope

- Scope: teacher create-class and exam-prep entry banner.

## Changes

- Added the classroom illustration to the class-creation banner.
- Added the exam-desk illustration to the exam-prep banner.
- Preserved RTL text priority with responsive image placement and a contrast overlay.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Frontend image only.

## Verification

- Changed-file TypeScript errors: `0` (project baseline remains `13`).
- `/teacher/create-class`: HTTP `200` on the local Next dev server.
- Both new public image assets: HTTP `200` with original byte sizes preserved.

## Rollback

- Revert the frontend commit and rebuild the frontend image.
