# Reference — Frontend org manager area `(org)` + workspace switching

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `1e29b4c`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F8
- **Layer:** frontend-route-group (org manager area)

## Purpose
The org manager's oversight-only panel: members, invite codes, study groups, all-org class oversight,
per-teacher/class/group AI-cost — plus the workspace-switcher context that lets an org teacher toggle
between personal and org workspaces. Consumes the B3 org endpoints via F3 hooks.

## Scope & paths
| Route (`(org)/org/…`) | Purpose |
|---|---|
| `` (index) | manager dashboard |
| `members` | member + invite-code management |
| `classes` | all-org class oversight |
| `costs` | per-teacher/class/group AI-cost breakdown |
| `notifications`, `settings`, `tickets` | supporting |

Components: `frontend/src/components/organization/` (`org-management-panel.tsx`,
`study-groups-manager.tsx`) + `frontend/src/components/layout/workspace-switcher.tsx` +
`hooks/{use-workspace.tsx, use-organizations.ts}`.

**Out of scope:** the B3 endpoint contracts → B3; the MANAGER role model → B1/B3; shared layout shell → F11.

## Public surface
- **`OrgManagementPanel`** (`org-management-panel.tsx`) — the shared members + invite-code UI (reused by
  the teacher `/teacher/org` tab too).
- **`StudyGroupsManager`** (`study-groups-manager.tsx`) — «گروه آموزشی» CRUD + teacher/student assignment.
- **Workspace switcher** (`layout/workspace-switcher.tsx` + `use-workspace.tsx`): a React context
  (`WorkspaceContext`) with `workspaces`, `activeWorkspace` (null = personal), `switchWorkspace`,
  persisted to `localStorage` (`WORKSPACE_STORAGE_KEY = 'ai_amooz_active_workspace'`).
- Hooks: `use-workspace`, `use-organizations` (F3).

## Key flows
1. **Manager oversight:** dashboard → members/codes (`OrgManagementPanel`), study groups
   (`StudyGroupsManager`), classes (all-org), costs (per-entity AI-cost via `LLMUsageLog.session_id`, B9/
   L10). MANAGER creates NO content — oversight only (B1/B3 invariant).
2. **Workspace switching:** an org-teacher (or a user with multiple orgs) picks a workspace via the
   switcher → `switchWorkspace` sets `activeWorkspace` (persisted) → dependent hooks refetch scoped to
   that org; `null` = personal/freelancer workspace (only if the user may have one, `is_freelancer`, B1).
3. **Roster = study group:** org class rosters derive from study-group membership (B3a `org_roster`);
   the manager edits groups, not per-class invites.

## Data & invariants
- MANAGER = oversight-only — no content-creation UI here (matches the B1/B3 backend rule).
- Workspace state is a context + `localStorage` (`WORKSPACE_STORAGE_KEY`); `activeWorkspace=null` means
  personal. Only teachers with `is_freelancer` may have the personal option (B1).
- Cost breakdowns read the B9 org-cost endpoints (attribution via `session_id`, L10) — no new schema.
- Dedicated `/org` route group (the P4/P5 rework moved the manager panel here; memory
  `org-teacher-dashboard-rework`); layout mounts `OnboardingGate` (F4).
- All API via F3 hooks; RTL + Persian (F2).

## Gotchas
- `OrgManagementPanel` is shared with the teacher area (`/teacher/org`) — a change to it affects both;
  don't fork.
- The workspace switcher persists to `localStorage`; a stale key after a membership change must be
  reconciled (the hook reloads workspaces) — clearing auth storage should also clear the workspace key.
- Manager ≠ teacher: the `/org` group must never expose class-creation UI (a security/UX invariant, B1).

## Cross-links
[backend-organizations.md](backend-organizations.md) (B3, the endpoints + StudyGroup) ·
[backend-accounts.md](backend-accounts.md) (B1, MANAGER + is_freelancer) · [backend-commons-admin.md](backend-commons-admin.md)
(B9, org-cost views) · [llm-pdf-and-cost.md](llm-pdf-and-cost.md) (L10, session_id attribution) ·
[frontend-teacher.md](frontend-teacher.md) (F7, shares OrgManagementPanel + workspace) · memory:
`org-teacher-dashboard-rework`, `manager-role-on-main` · `.claude/agents/security-auditor.md`.

## Verified-by
- `Glob (org)/**/page.tsx` → 7 org routes tabulated above.
- `Glob components/organization/**/*.tsx` → `org-management-panel.tsx`, `study-groups-manager.tsx`.
- Read (2026-07-02): `use-workspace.tsx:3-35` (`WorkspaceContext`, `activeWorkspace` null=personal,
  `switchWorkspace`, `WORKSPACE_STORAGE_KEY`, `is_freelancer` gating).
- Cross-checked against B3 (endpoints/roster) + B9 (cost) + memory `org-teacher-dashboard-rework`.
- NOT read whole: panel/manager component bodies. NOT run this pass: tsc/lint (F-layer AUDIT gate).
