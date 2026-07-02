# Reference — Frontend app shell, routing map & next.config

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `18889ae`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F1
- **Layer:** frontend-route-group (the shell every other frontend doc links back to)

## Purpose
The Next.js App Router shell: the root RTL/Persian layout + providers, the full route-group inventory,
and the `/api` proxy config (the load-bearing rewrite + trailing-slash rules). The map every per-group
frontend doc (F5-F10) hangs off.

## Scope & paths
| File | Role |
|---|---|
| `frontend/src/app/layout.tsx` | root `<html lang="fa" dir="rtl">` + Vazirmatn + `ThemeProvider` + Toasters |
| `frontend/next.config.ts` | `/api` rewrite, `skipTrailingSlashRedirect`, `output: standalone`, image domains |
| `frontend/src/app/**` | route groups (below) — 61 page/layout files |

**Out of scope:** theming/RTL/lib conventions → F2; the services layer → F3; per-group screens → F4-F10.

## Public surface — route inventory
| Group / route | Layout | Purpose |
|---|---|---|
| `(marketing)/` | — | landing (F10) |
| `(auth)/` — login, admin-login, org-login, forgot-password, register/complete, teacher-signup, organization-signup, join-code | `(auth)/layout.tsx` | auth screens (F5) |
| `start/`, `join/`, `onboarding/` | own layouts | role picker · invite redemption · forced onboarding (F4/F5) |
| `(dashboard)/` — home, classes, learn/[courseId], exam/[examId](+result), exam-prep, calendar, profile, notifications, tickets | `(dashboard)/layout.tsx` | student area (F6) |
| `(teacher)/teacher/` — dashboard, create-class, my-classes(+[classId] edit/students), my-exams(+[examId] edit/students), students, messages, analytics, notifications, settings, tickets | `(teacher)/teacher/layout.tsx` | teacher studio (F7) |
| `(org)/org/` — dashboard, classes, costs, members, notifications, settings, tickets | `(org)/layout.tsx` | org manager (F8) |
| `(admin)/admin/` — dashboard, users, organizations(+[id]), waitlist, tickets, broadcast, analytics, llm-usage, backups, maintenance, server-settings, settings, my-classes(+[classId]) | `(admin)/admin/layout.tsx` | admin panel (F9) |

**Root providers** (`layout.tsx`): `<html lang="fa" dir="rtl" suppressHydrationWarning>`; Vazirmatn
(all weights) + KaTeX CSS; `ThemeProvider` (next-themes, `attribute="class"`, `defaultTheme="system"`);
shadcn `Toaster` + `sonner` (RTL, top-center).

## Key flows
1. **`/api` proxy** (`next.config.ts:30-40`): `source: "/api/:path(.*)"` → `${backendUrl}/api/:path`.
   `backendUrl = BACKEND_URL || NEXT_PUBLIC_API_URL || "http://localhost:8000"` — server-side, so in
   Docker it must be the backend SERVICE (`http://backend:8000`), not localhost (the ECONNREFUSED fix).
   In `npm run dev` only `NEXT_PUBLIC_API_URL` is set (fallback).
2. **Trailing slash** (`:20`, `:36`): `skipTrailingSlashRedirect: true` + `:path(.*)` capture preserve
   `/api/foo/` verbatim so Django's `APPEND_SLASH` doesn't 500 a POST body. Reverting either breaks every
   proxied mutation.
3. **Build gates** (`:22-28`): `typescript.ignoreBuildErrors` + `eslint.ignoreDuringBuilds` are ON — so
   `next build` catches nothing; `npm run typecheck` + `npm run lint` are the real gates.

## Data & invariants
- **NEVER** simplify the `/api` rewrite, remove `skipTrailingSlashRedirect`, or switch `:path(.*)` to
  `:path*` — all three break proxied POST/PUT/PATCH/DELETE (Django trailing slashes).
- `output: "standalone"` for the prod image.
- RTL is global (root layout `dir="rtl"`) — new UI must be direction-aware (F2).
- `next.config` image `remotePatterns` allow localhost:8000 + the prod backend `aiamoooz` (3-o) domains +
  a few CDNs — a new media host must be added here.
- `NEXT_PUBLIC_*` + the rewrite target are baked at BUILD time — an env change ⇒ front image rebuild
  (I1, memory `local-stack`).

## Gotchas
- Dev server is port **9002** (not 3000); local dev needs `frontend/.env.local` with
  `NEXT_PUBLIC_API_URL=http://localhost:8000` (CLAUDE.md §Gotchas) — don't point it at :9002 (proxy loop).
- The image `remotePatterns` use the backend `aiamoooz` (3-o) domain — matches the intentional
  domain split (CLAUDE.md §Production); don't "fix" to 2-o.
- `(admin)` layout deliberately does NOT mount the onboarding gate (F4) — a consistency rule, not an omission.

## Cross-links
[frontend-conventions.md](frontend-conventions.md) (F2, RTL/theme/lib) · [frontend-services-hooks.md]
(F3, the API layer this proxy serves) · [frontend-auth-guards.md] (F4, layouts + guards) · F5-F10
(per-group screens) · [backend-core.md](backend-core.md) (B0, the Django side of the proxy) ·
[infra-deploy.md] (I1) · CLAUDE.md §Gotchas · `.claude/agents/frontend-engineer.md`.

## Verified-by
- Full read (2026-07-02): `next.config.ts` (79), `layout.tsx` (51).
- `Glob src/app/**/page.tsx` → the 61-file route inventory (all groups + dynamic segments) tabulated above.
- Confirmed: `dir="rtl"` + providers (`layout.tsx:28-47`); the rewrite + skipTrailingSlashRedirect +
  backendUrl fallback + build-error-ignore (`next.config.ts:8-40`); image domains incl. `aiamoooz` 3-o.
- NOT verified live this pass: runtime proxy behavior (covered by the memory `local-stack` runbook +
  the shipped `fdb38b6` fix); tsc/lint (F-layer gate, run at AUDIT).
