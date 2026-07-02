# Reference — Frontend teacher area `(teacher)`

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `467df64`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F7 [a/b — kept single: ~44 components]
- **Layer:** frontend-route-group (teacher studio)

## Purpose
The teacher's studio: create a class (upload → pipeline tracker + cancel), manage classes/exams,
students, messages, analytics, and settings — plus the org-teacher variant (workspace-aware). Consumes
the B5 teacher endpoints via F3 hooks.

## Scope & paths
| Route (`(teacher)/teacher/…`) | Purpose |
|---|---|
| `` (index) | teacher dashboard (freelancer or org-teacher variant) |
| `create-class` | upload → pipeline tracker → invites |
| `my-classes` (+`[classId]`, `/edit`, `/students`) | class list/detail/editor/roster |
| `my-exams` (+`[examId]`, `/edit`, `/students`) | exam-prep sessions |
| `students`, `messages`, `analytics`, `notifications`, `settings`, `tickets` | supporting |

Components: `frontend/src/components/teacher/**` (~44): `create-class/` (create-class-page,
class-info-form, file-upload-section, **pipeline-tracker**, student-invite-section), `class-detail/`
(structured-content-view, chapters/announcements/students cards), `class-edit/` (chapters-editor,
edit-form), `students/` (student-table + `table/` badges), `messages/` (message-form,
recipient-selector), `analytics/` (activity-chart, overview-cards, class-distribution, recent-activity),
`settings/` (profile/security/notifications/appearance tabs), `org-dashboard.tsx`,
`org-teacher-dashboard.tsx`.

**Out of scope:** the B5 endpoint contracts → B5; the pipeline backend → L4; org workspace context → F8;
shared primitives → F11.

## Public surface / key screens
- **Create class** (`create-class/create-class-page.tsx`): `file-upload-section` → dispatch step-1 (B5) →
  **`pipeline-tracker`** polls session status (the 5-step state machine, B4/L4) → **cancel button beside
  start** (the cancellation feature) → `student-invite-section`.
- **Class detail/edit** (`class-detail/`, `class-edit/`): `structured-content-view` renders the generated
  chapters (`MarkdownWithMath`/`MathText`, F2); `class-chapters-editor` edits them.
- **Students** (`students/student-table` + `table/` badges), **messages** (`recipient-selector` +
  `message-form` → SMS notify, B8/B9), **analytics** (Tehran-tz charts, B5).
- **Org-teacher variant** (`org-dashboard.tsx`, `org-teacher-dashboard.tsx`): a teacher who belongs to an
  org sees a group-centric dashboard; the workspace switcher (F8) toggles context.
- Hooks: `use-teacher-courses`, `use-teacher-class-detail`, `use-teacher-class-actions`,
  `use-teacher-students`, `use-teacher-analytics`, `use-teacher-dashboard`, `use-teacher-recipients`,
  `use-teacher-exam-preps`, `use-teacher-settings` (F3).

## Key flows
1. **Pipeline UI:** upload → `pipeline-tracker` polls `use-teacher-class-detail`/status until RECAPPED or
   CANCELLED (B4 statuses); the destructive «لغو پردازش» sits beside «شروع پردازش» with an AlertDialog
   confirm (memory `pipeline-cancellation`).
2. **Nav menus:** freelancer vs org-teacher nav variants (`getTeacherNavMenu`/`TEACHER_NAV_MENU`) — the
   org-teacher gets group/workspace items.
3. **Messages:** `recipient-selector` picks students → `message-form` → teacher notification broadcast
   (B9) → SMS (B8).

## Data & invariants
- All API via F3 hooks (no ad-hoc fetch); layout mounts `OnboardingGate` (F4).
- The pipeline-tracker polls the B4 status enum — a status rename breaks the tracker; keep them in sync.
- Cancel button is owner-scoped on the server (B5 404/409) — the UI just posts.
- Math content via `MarkdownWithMath`/`MathText` (F2); RTL + Persian digits/Jalali throughout.
- Freelancer vs org-teacher (`is_freelancer`, B1/B3) drives which dashboard + nav renders.

## Gotchas
- The `pipeline-tracker` is coupled to the B4 `Status` values (incl. CANCELLED/FAILED) — a backend
  status change must update the tracker's state mapping.
- Org-teacher dashboards depend on the workspace context (F8) — an org teacher outside a workspace is a
  routing edge (memory `org-teacher-dashboard-rework` P1 bounce fix).
- Component count (~44) under the split threshold — kept as one doc.

## Cross-links
[backend-classes-teacher-views.md](backend-classes-teacher-views.md) (B5, endpoints) ·
[llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, the pipeline the tracker watches) ·
[frontend-org.md] (F8, workspace switcher) · [frontend-services-hooks.md](frontend-services-hooks.md)
(F3) · [frontend-conventions.md](frontend-conventions.md) (F2) · memory: `pipeline-cancellation`,
`teacher-dashboard-and-prompts-audit`, `org-teacher-dashboard-rework` · `.claude/agents/frontend-engineer.md`.

## Verified-by
- `Glob (teacher)/**/page.tsx` → 16 teacher routes tabulated above.
- `Glob components/teacher/**/*.tsx` → ~44 components; the create-class/class-detail/class-edit/students/
  messages/analytics/settings + org-dashboard groupings cited are the real paths (incl.
  `create-class/pipeline-tracker.tsx`, `org-teacher-dashboard.tsx`).
- Cross-checked against B5 (endpoints) + L4 (pipeline statuses) + memory `pipeline-cancellation`.
- NOT read whole: component bodies. NOT run this pass: tsc/lint (F-layer AUDIT gate).
