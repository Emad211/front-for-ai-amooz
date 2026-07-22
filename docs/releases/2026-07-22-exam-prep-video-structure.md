# 2026-07-22 — Exam-prep video structure and math rendering

Scope: backend + pipeline worker

## Changes

- Applies the same validated structure contract to audio, video, and PDF sources.
- Treats speech and sampled video-frame text as potentially duplicated source data.
- Uses `generate_structured(ExamPrepOutput)` for validated exam-prep extraction.
- Separates question stems from options and conservatively repairs affected stored exams on read.
- Repairs malformed LaTeX escapes while preserving real Markdown and LaTeX line breaks.
- Sanitizes every transcription chunk before storage and before reuse as the next chunk's context.
- Returns the inferred question `type` through the student API.

## Migrations

None.

## Env / config

No new variables. Existing optional controls remain:

- `EXAM_PREP_WINDOW_CHARS` (default `20000`, range `4000..40000`)
- `EXAM_PREP_WINDOW_OVERLAP` (default `4000`, capped to half the active window)

## Rebuild

Rebuild and deploy the shared backend image to both the web app and the `pipeline` Celery worker. No
frontend rebuild is required.

## Verification

- `pytest apps/classes`: 875 passed, 3 skipped.
- Cross-format exam-prep, PDF, transcription and prompt-contract suite: 139 passed.
- Upload validation, ffmpeg path and pipeline robustness suite: 68 passed.
- Final regression selection: 80 passed.
- `manage.py check`: no issues.
- `makemigrations --check --dry-run`: no changes detected.
- Frontend `npm run typecheck`: 11 pre-existing errors outside changed files; no new frontend errors.

## Rollback

Revert the release commit and redeploy the previous shared backend image. No database rollback is
required.
