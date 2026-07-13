# 2026-07-13 — Student Onboarding Step Guard

Commit: `fix(onboarding): prevent early wizard completion` · Scope: frontend

## Changes

- Prevented the onboarding form from calling the completion API before the final wizard step.
- Pressing Enter on steps one and two now validates the visible step and advances to the next step,
  matching the explicit `بعدی` button.
- Added synchronous guards against rapid Enter/double-submit races, so steps cannot be skipped and the
  completion endpoint receives at most one in-flight request from the wizard.
- Final validation returns the user to the first step containing an error instead of leaving an error
  hidden behind another step.
- Student grade and major remain optional, but the student is always shown their profile step before
  they can finish onboarding and enter the dashboard.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Rebuild and deploy the `front` service only.

## Verification

- `npx tsc --noEmit --pretty false`: existing baseline recorded separately; zero errors in the changed file.
- `git diff --check`.

## Rollback

- Revert the application commit and rebuild the `front` service. No data rollback is required.
