# Release 2026-08-26 — Advisor Restart (waves 1–6, restart steps 1–13)

- **Status:** Shipped to `main` · **Date:** 2026-08-26 · **Owner:** Sisyphus (orchestrator) + owner verification pending in deployment
- Scope: full expansion of the advisor feature per [`docs/features/advisor-restart-plan.md`](../features/advisor-restart-plan.md), building on the MVP spec [`docs/features/advisor-mvp.md`](../features/advisor-mvp.md) §۱۶.

## Changes

Backend (`backend/apps/advisory/`):
- DailyLog enrichment: `day_goal`, `motivation_note`, `tests_taken`, `test_percent`.
- `StudentSubject.source` (TEXTBOOK | TEACHER_BOOKLET | VIDEO | KONKUR_BOOKLET | OTHER).
- WeeklyPlanItem: `topic`, `unit_label`, `test_minutes`, `mastery_color`; WeeklyPlan `day_notes`; advisor feed flags uncompensated plan slots.
- Student intake: `AdvisoryIntakeProfile` + `AdvisoryIntakeClass` (advisor + student-mirror routes).
- Weekly 15-criteria assessment (`services/assessments.py` owns the canonical criteria list) — advisor-internal only.
- Weekly call log with rotating default topics — advisor-internal only.
- Exam scores (cap 40/engagement; six kinds; PATCH-partial detail route).
- Exam analyses / report cards (rows + question notes, wholesale PUT set-replace).
- Monthly outlook + strategies keyed by a Gregorian `month_start` path param (ISO date converter registered).
- 7-day challenge (server-computed end date = start+6, max 3 ACTIVE, one-way status transitions, student day-fill limited to goal/summary).

New service modules: `calendar, intake, assessments, calls, exam_records, monthly, challenges`
(all added to the import-boundary exempt doors + pinned assertion). New view modules:
`views_intake.py`, `views_monthly.py`, `views_exams.py`.

Frontend (`frontend/src/`):
- `/advisor/students/[id]` restructured into 7 query-param tabs (`feed|plan|exams|intake|assess|month|challenges`, Suspense-wrapped `useSearchParams`).
- New cards: intake form (+ class table), weekly assessment (dynamic 15-criteria editor), call log (4-week checklist), exam scores (inline PATCH editing), exam analysis (report-card metrics + rows + question notes), monthly outlook (Jalali month selector converted client-side), challenge (create/edit/close + 7-day editor).
- Student home mirrors (hidden without an active advisor): my-intake, my-exam-scores, my-exam-analyses, my-monthly-outlook, my-challenge (day-fill restricted to past/today days).
- Hydration fixes en route: nested `<a>` in the landing header logo, nested `<button>` in the subject-picker row.

## Migrations

`advisory.0008_dailylog_enrichment` → `0009_studentsubject_source` →
`0010_planitem_enrichment` → `0011_intake` → `0012_weekly_assessment` →
`0013_call_log` → `0014_exam_score` → `0015_exam_analysis` →
`0016_monthly_outlook` → `0017_challenge`. Applied automatically by the deploy entrypoint.

## Env

No new environment variables, packages, or provider calls (locked principle ق۱: zero LLM/Celery in advisory). Nothing to configure.

## Rebuild targets

Darkube builds from `main` (backend image runs migrate + gunicorn; frontend standalone build).
Local: `docker compose build && docker compose up -d` (see `docker-compose.override.yml` for the
build-time proxy neutralization added this release).

## Verification

- Full advisory suite: **553 passed** (was 326 before the phase; +227 across six waves), zero-token pytest-django.
- `npx tsc --noEmit` clean at every wave boundary.
- Production-like live smoke on local after each wave: full round-trips per module plus pinned Persian error contracts (cap limits, duplicate strategy positions, challenge status revert 409, duplicate question notes 400, student day-fill key restriction).

## Rollback

Standard image rollback redeploys the previous backend/frontend images; all ten migrations are additive (new tables/columns only, no data rewrites), so a pre-0008 image keeps running against a migrated DB without code changes needed on rollback.
