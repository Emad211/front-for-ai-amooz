# Advisor Growth Loop (تصمیم‌یار) — Living Spec

Status: **shipped (2026-08-31)** · Scope: advisor decision surface + student IA
rework + activity-type sentinel fix. Supersedes nothing; extends
[advisor-mvp.md](advisor-mvp.md) and [advisor-restart-plan.md](advisor-restart-plan.md).

## Why

The 2026-08-31 growth wave gave students a goal, mistake notebook, topic
coverage and analytics — but all of it was student-only. The advisor could
not see any of it, and neither side got a next decision out of the data.
This wave closes that loop **without** auto-replanning: the system derives
deterministic next actions, a human advisor acts on them through the
existing plan/exam/feed surfaces.

## Backend — `GET /api/advisory/students/<engagement_id>/growth/`

- **Auth**: `[IsAuthenticated, IsAdvisorUser]`; engagement resolved ONLY via
  `services/scope.py::advisor_engagement`. Foreign/nonexistent/ENDED → 404
  (never 403 — leak posture). Anonymous 401, student 403, non-GET 405.
- **Read-only**: no writes anywhere in the path (pinned by a test that
  snapshots row counts across `DailyLog`, `MistakeEntry`, `TopicProgress`,
  `StudyPlan`, `StudyPlanItem`).
- **Wire contract** (flat by design — NOT a dump of the notebook):

```json
{
  "active": true,
  "asOf": "2026-08-31",
  "evidence": {
    "streak": 4,
    "loggedToday": true,
    "planExecutionPercent": 55,
    "latestExamPercent": 72,
    "examTrend": "روند صعودی",
    "openMistakes": 2,
    "reviewDue": 3,
    "backlogTotal": 7
  },
  "recommendations": [
    {
      "code": "review-overdue-topics",
      "title": "مرور مباحث عقب‌افتاده",
      "description": "3 مبحث موعد مرورشان گذشته است: …",
      "priority": "HIGH",
      "evidenceKeys": ["reviewDue"],
      "actionArea": "plan"
    }
  ]
}
```

- `services/growth.py` — composite projection + `build_evidence_digest`
  (services stay serializer-free; models map to plain primitives).
- `services/recommendations.py` — PURE rules, explicit `as_of`, no
  queries/LLM/clock. Rule precedence (capped at 3, stable sort):
  1. `review-overdue-topics` — overdue `NEEDS_REVIEW` topics (HIGH, → plan)
  2. `follow-open-mistakes` — unresolved mistakes, prefers stored
     `next_action` (HIGH if any HIGH, → exams)
  3. `compensate-backlog` — largest planned-vs-actual deficit (MEDIUM, → feed)
  4. `record-today-log` — today's log missing (MEDIUM, → feed)
  5. `publish-current-plan` — no published current plan (MEDIUM, → plan)
- `evidenceKeys` must reference the evidence digest; every description is
  reconstructable from returned evidence. No confidence scores.
- Tests: `test_growth.py` (contract shape, access matrix incl. own-ENDED →
  404, read-only snapshot, determinism, evidence digest).

## Frontend

- **Student `/advisory`** — reorganized from six equal tabs to four jobs:
  `امروز | برنامه | پیشرفت | پرونده` (Radix Tabs, keyboard-complete,
  ≥44px targets). Legacy `?tab=` values alias to the new jobs so old deep
  links keep working. Distinct loading/error/inactive states via
  `EngagementBoundary` (an engagement fetch failure is an ERROR now, no
  longer masquerades as «بدون مشاور»). Low-frequency cards live behind
  `<details>` progressive disclosure.
- **Advisor `/advisor/students/[id]`** — four jobs:
  `تصمیم امروز | شواهد مطالعه | برنامه‌ریزی | پرونده`, default «تصمیم».
  The decision tab renders `AdvisorGrowthPanel` (recommendations + flat
  evidence + links into existing plan/exams/feed surfaces — read-only).
  Legacy tab values alias forward (`feed→activity`, `exams/intake/assess/
  month/challenges→record`).
- **`study-log-form.tsx`** — the `ثبت ساده` Select sentinel fix: UI value
  `plain` maps to `''` before entering state, and the save payload
  conditionally spreads `activityType` — `"plain"` never crosses the wire
  (previously a guaranteed 400). New sticky save bar states the save scope
  («ثبت کل گزارش روز») and shows last-saved state (`aria-live`).
- Design contract: [`frontend/DESIGN.md`](../../frontend/DESIGN.md) (tokens,
  card roles, 44px targets, async-state anatomy, motion/a11y rules,
  accepted debt).

## Wave 6 (2026-08-31) — hidden metrics + AI planner evidence

### 6b — five hidden metrics now computed and visible

`compute_analytics` grew five evidence-backed numbers (all bounded windows,
null-safe, existing keys untouched):

| Key | Definition | Surface |
|---|---|---|
| `testDensity` | tests per logged day, last 14 days (1-decimal) | student chips + advisor growth digest |
| `mistakeResolutionDays` | median days created→resolved for mistakes resolved in last 30 days; needs `MistakeEntry.resolved_at` (migration `0021`, backfilled from `updated_at`, set/cleared by `update_mistake` on resolve/unresolve) | student chips + digest |
| `planCalibration` | Σplanned/Σactual over the last 14 days, days with BOTH a published-plan item and a logged item (>1 under-planning, <1 over-planning) | student chips + digest |
| `reportRate7d` | % of the last 7 days with a log (streak-shame-free survival metric) | student chips + digest |
| `advisorDosageDays` | days since the most recent done call (`WeeklyCallLog`) — the advisor's own value number | **advisor growth digest ONLY — never rendered in the student tab** |

Wire: student `/me/analytics/` + advisor growth evidence digest (the five
keys are flat scalars in `EVIDENCE_KEYS`); student analytics tab renders
four calm stat chips (quiet-null: hidden when null), the growth panel
labels all five in Persian.

### 6a — the AI plan-drafter stopped planning blind

`services/ai_planner.py` grew `_student_evidence(engagement)` — the stated
goal, up to 5 open mistakes (HIGH first), up to 5 due reviews, top-3
backlog rows (reused from `compute_analytics`, the sanctioned read door —
ai_planner still imports no tenancy models, `test_import_boundaries` green)
and the 3 most recent exams — serialized camelCase by `_evidence_json`
under a ~1200-char budget (trim order: backlog rows → exam rows → reviews
→ mistakes; goal stays). The `ai_plan_draft` prompt gained the
`{evidence_json}` placeholder + a Persian section instructing the model to
prioritize due reviews and open-mistake follow-ups unless the advisor's
request says otherwise. Output JSON schema, DRAFT-only guards, caps and
`LLMUsageLog` unchanged; `test_prompts_contract` PLACEHOLDERS updated (the
contract change is pinned by that test).

## Deliberately NOT in this wave

Automatic carry-forward/replanning, advisor writes to goal/mistakes/topics,
recommendation persistence/notifications, LLM coaching, parent portal,
public exam-calendar ingestion, gamification. `actionArea` is a link hint,
never a mutation.

## Verification (updated 2026-08-31, wave 6)

- Backend (Postgres truth lane): `pytest backend/apps/advisory
  backend/apps/accounts -m "not benchmark"` — **842 passed** (wave 6 adds
  12 metric tests + 7 planner-evidence tests; migration `0021` exercised
  on a fresh `--create-db` run including the resolved_at backfill).
- Frontend: `npm run typecheck` ✓, `npm run build` ✓.
- Live API smoke: all five metrics return real values from seeded data
  (testDensity 0, mistakeResolutionDays 3, planCalibration 0.73,
  reportRate7d 14, advisorDosageDays 2); advisor growth digest carries
  all five; student analytics carries all five (the tab renders four).
