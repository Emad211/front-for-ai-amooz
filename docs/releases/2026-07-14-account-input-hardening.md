# 2026-07-14 — Account and Input Hardening

Commits: this commit (`fix(auth): harden account and notification inputs`) · Scope: backend + frontend

## Changes

- Unified new-password validation across registration, onboarding, reset, and password change.
- Bounded and normalized invite-code/mobile input in frontend and backend.
- Anonymous login no longer refreshes stale credentials, preserving the correct wrong-password error.
- Clearing a profile image removes the stored avatar and immediately refreshes cached user data.
- New standalone, embedded, and edited exercise deadlines must be in the future.
- Teacher messages identify the sender in both the student notification feed and SMS; feed/read state
  are limited to active Enrollment relationships and respect personal-teacher suspension.
- Enrollment-based student-count regression fixtures now match the production roster contract.

## Migrations

- None. `manage.py makemigrations --check --dry-run` reports `No changes detected`.

## Env / config

- No new environment variables or secrets.
- Django password validation behavior changes through the existing settings module.

## Rebuild

- Rebuild and deploy the shared backend/Celery image.
- Rebuild and deploy the frontend image from the same revision.

## Verification

- Full backend suite: `1296 passed, 4 skipped` (no live-LLM benchmark).
- Post-review notification authorization suite: `26 passed`.
- Focused exercise/notification regression suite: `92 passed`.
- Prompt and exercise contract suite: `149 passed`.
- Authentication suite: `118 passed, 2 skipped`.
- Organization and notification suite: `148 passed`.
- Final password/avatar/invite validation check: `15 passed`.
- Django system check: `System check identified no issues (0 silenced)`.
- Migration drift check: `No changes detected`.
- `git diff --check`: clean apart from platform line-ending notices.
- Frontend typecheck has 11 known errors in untouched admin-ticket, exam-edit, and mock-message files;
  no error is reported in a changed file (baseline before this work was 13).
- Security-auditor and code-reviewer final verdicts: PASS.

## Rollback

- Revert this commit and rebuild both backend/Celery and frontend images.
- No database rollback or environment change is required.
