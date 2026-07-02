# Reference — Frontend admin area `(admin)`

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `2822016`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F9
- **Layer:** frontend-route-group (platform admin panel)

## Purpose
The platform-admin panel: user management (incl. org-manager assign/revoke), organizations, waitlist
review, analytics + LLM-usage dashboards, tickets, broadcasts, and server ops. Consumes the B9
`/api/admin/*` endpoints via F3 hooks.

## Scope & paths
| Route (`(admin)/admin/…`) | Purpose |
|---|---|
| `` (index) | admin dashboard |
| `users` | user management + manager assign/revoke |
| `organizations` (+`[id]`) | org list/detail |
| `waitlist` | teacher/org signup review (approve/reject) |
| `analytics`, `llm-usage` | Tehran-tz analytics + AI-cost dashboards |
| `tickets`, `broadcast` | support + notifications |
| `backups`, `maintenance`, `server-settings`, `settings`, `my-classes` (+`[classId]`) | ops + settings |

Components: `frontend/src/components/admin/` (~18): `analytics/` (overview-cards, activity-chart,
class-distribution, recent-activity), `tickets/` (list/detail/cards/headers), `messages/`
(message-form, recipient-selector), `settings/` (profile/security/notifications/appearance tabs). Layout:
`components/layout/admin-sidebar.tsx`/`admin-header.tsx`; hooks `use-admin-*`.

**Out of scope:** the B9 endpoint contracts → B9; the LLM cost substrate → L10; admin backend perms → B0/B9.

## Public surface / key screens
- **Users** (`admin/users`): list + stats + edit dialog; the MANAGER chip + org-manager
  assign/revoke (B9 `users/<pk>/org-manager/`, memory `manager-role-on-main`).
- **Analytics** (`admin/analytics` + `components/admin/analytics/`): overview cards, multi-series
  `activity-chart`, `class-distribution`, unified `recent-activity` feed (Tehran-tz, B9). The
  `recent-activity` ICON_MAP must cover every activity type (the crash precedent, memory `admin-analytics`).
- **LLM usage** (`admin/llm-usage`): the cost dashboards reading B9's `llm-usage/*` (attribution via
  `session_id`, L10).
- **Waitlist** (`admin/waitlist`): approve/reject access requests (B3b).
- **Tickets** (`admin/tickets` + `components/admin/tickets/`), **broadcast** (admin notification).
- Hooks: `use-admin-analytics`, `use-admin-courses`, `use-admin-ops`, `use-admin-settings`,
  `use-admin-server-settings`, `use-admin-backups` (F3).

## Key flows
1. **User mgmt:** `use-admin-*` → list/stats → edit dialog assigns/revokes MANAGER (B9) → refetch.
2. **Analytics:** cards + charts + activity feed from B9 (`analytics/*`), all Asia/Tehran bucketed;
   `recent-activity` renders each feed item by type via ICON_MAP.
3. **Waitlist review:** approve → backend provisions org+code / teacher token (B3b) + SMS.

## Data & invariants
- **Admin layout does NOT mount `OnboardingGate`** (F1/F4) — deliberate; admins never onboard.
- Analytics is Asia/Tehran (F/B rule); Persian digits/Jalali on axes+cards (F2).
- `recent-activity` ICON_MAP must map every activity type the B9 feed can emit — a missing icon renders
  `<undefined>` and crashes (the fixed precedent, memory `admin-analytics`).
- All API via F3 hooks (`use-admin-*`); the admin permission is enforced server-side (B0 `IsPlatformAdmin`) —
  the route group is UX gating only.
- Manager assign/revoke is admin-only (B9); the UI posts to `users/<pk>/org-manager/`.

## Gotchas
- Admin layout omitting the onboarding gate is intentional — don't "add it everywhere."
- A new analytics activity source needs BOTH the backend feed entry (B9) AND an ICON_MAP entry here, or
  it crashes the feed.
- `my-classes` under admin lets an admin view classes as a learner (same student surface, F6) — not a
  separate content system.

## Cross-links
[backend-commons-admin.md](backend-commons-admin.md) (B9, all the endpoints) ·
[llm-pdf-and-cost.md](llm-pdf-and-cost.md) (L10, cost substrate) · [backend-accounts.md](backend-accounts.md)
(B1, MANAGER) · [backend-waitlist.md](backend-waitlist.md) (B3b, approve/reject) ·
[frontend-services-hooks.md](frontend-services-hooks.md) (F3) · [frontend-app-shell.md](frontend-app-shell.md)
(F1, no-gate) · memory: `admin-analytics`, `manager-role-on-main` · `.claude/agents/data-analyst.md`.

## Verified-by
- `Glob (admin)/**/page.tsx` → 15 admin routes tabulated above.
- `Glob components/admin/**/*.tsx` → ~18 components (analytics/tickets/messages/settings groupings cited).
- Cross-checked against B9 (endpoints incl. org-manager + llm-usage + recent-activity) + memory
  `admin-analytics` (ICON_MAP + Tehran-tz) + `manager-role-on-main`.
- Admin-layout-no-gate cross-checked against F1/F4.
- NOT read whole: component bodies. NOT run this pass: tsc/lint (F-layer AUDIT gate).
