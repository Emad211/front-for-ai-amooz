# Reference — Frontend auth & onboarding routing/guards

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `4447169`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F4
- **Layer:** frontend-layer (client-side auth flow)

## Purpose
The client-side auth flow: token storage, role→home routing, the forced-onboarding gate, and the
zod-validated forms. The frontend view of the phone-identity + forced-onboarding backend model (B1/B2).

## Scope & paths
| File | Role |
|---|---|
| `frontend/src/components/auth/onboarding-gate.tsx` | `OnboardingGate` — redirects incomplete profiles |
| `frontend/src/components/auth/auth-auto-redirect.tsx` | `AuthAutoRedirect` — role→home after login |
| `frontend/src/components/auth/login-form.tsx`, `unified-code-form.tsx`, `password-input.tsx` | login + code forms |
| `frontend/src/lib/auth-routing.ts` | `landingFor(role)` role→route |
| `frontend/src/lib/validations/{auth,onboarding}.ts` | zod schemas |

**Out of scope:** token storage internals + services → F3; the screens themselves → F5; backend auth → B2.

## Public surface
- **`OnboardingGate()`** (`onboarding-gate.tsx:17`) — mounted in dashboard/teacher/org layouts; redirects
  to `/onboarding` when the cached profile is **positively** incomplete.
- **`AuthAutoRedirect`** — sends a logged-in user to their role home.
- **`landingFor(role)`** (`auth-routing.ts:11`): ADMIN → `/admin`, MANAGER → `/org`, TEACHER →
  `/teacher`, STUDENT → `/home`.
- zod schemas in `validations/auth.ts` + `validations/onboarding.ts` (the multi-step wizard schema, F5).

## Key flows
1. **Onboarding gate** (`onboarding-gate.tsx:22-29`): skip if already on `/onboarding`; redirect to
   `/onboarding` ONLY when `user.is_profile_completed === false && !is_staff && !is_superuser`
   (`:28`). A missing/old cached profile flag does NOT redirect (avoids false bounces). Primary routing
   to `/onboarding` also happens at login. **Mounted in dashboard/teacher/org layouts — NOT admin**
   (deliberate: admins never onboard).
2. **Role routing:** after login, `AuthAutoRedirect` + `landingFor(role)` send the user to the correct
   panel; this mirrors the backend role model (B1).
3. **Login/code:** `login-form` (password) and `unified-code-form` (phone code, the one-step
   student/all-roles code entry) → on `!is_profile_completed` route to `/onboarding` (B2 completed-
   account block on the server).

## Data & invariants
- The gate keys on **`is_profile_completed === false`** (positively incomplete) — not falsy — so a stale
  cache never wrongly bounces a user.
- **is_staff / is_superuser are exempt** from the onboarding gate (and admin layout doesn't mount it) —
  keep both exemptions.
- `landingFor` role map must match the backend roles + the route-group homes (F1) — ADMIN/MANAGER/
  TEACHER/STUDENT → admin/org/teacher/home.
- Forms use react-hook-form + zod (`validations/`); the onboarding schema is the canonical multi-step
  pattern (F2/F5).
- Frontend guards are UX only — the BACKEND enforces auth (B2); a route guard is never the security boundary.

## Gotchas
- Admin layout intentionally omits `OnboardingGate` — a future refactor that "adds it everywhere" would
  wrongly force admins through onboarding.
- The gate redirects on `=== false`, not `!user.is_profile_completed` — the difference matters for the
  missing-flag case; don't "simplify" it.
- The completed-account-blocked-from-code message comes from the server (B2); the form just routes.

## Cross-links
[frontend-app-shell.md](frontend-app-shell.md) (F1, which layouts mount the gate) ·
[frontend-services-hooks.md](frontend-services-hooks.md) (F3, token storage + `completeOnboarding`) ·
[frontend-auth-screens.md] (F5, the screens) · [backend-authentication.md](backend-authentication.md)
(B2) · [backend-accounts.md](backend-accounts.md) (B1, roles + onboarding) · memory:
`onboarding-and-user-uniqueness`, `org-teacher-dashboard-rework` · `.claude/agents/security-auditor.md`.

## Verified-by
- Read (2026-07-02): `onboarding-gate.tsx:17-29` (the `=== false && !is_staff && !is_superuser` guard,
  skip-on-`/onboarding`, the "mounted in dashboard/teacher/org not admin" comment),
  `auth-routing.ts:6-20` (`landingFor` role→route map).
- `Glob components/auth/*.tsx` → the 5 auth components.
- Mount points cross-checked against F1 layout inventory (admin layout excluded).
- NOT read whole: the form component bodies (F5 covers the screens). NOT run this pass: tsc/lint (AUDIT gate).
