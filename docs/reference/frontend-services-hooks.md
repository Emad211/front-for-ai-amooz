# Reference — Frontend services layer + hooks

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `9fe1a62`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F3
- **Layer:** frontend-service (the API layer every page/component reads through)

## Purpose
The data seam: 9 service modules (the ONLY place that talks to the backend) + 34 `use-*` hooks that wrap
them for pages. Every per-group screen doc (F5-F10) links here for its service+hook rather than
re-describing the fetch.

## Scope & paths
| Path | Role |
|---|---|
| `frontend/src/services/*.ts` (9) | auth, user, classes, teacher, admin, organization, dashboard, waitlist, landing |
| `frontend/src/hooks/use-*.ts(x)` (34) | one hook per service-slice — the page↔service data seam |

**Out of scope:** the `/api` proxy config → F1; error → RHF field-error mapping details → F4; per-screen
usage → F5-F10.

## Public surface
**Shared request core** (in `auth-service.ts`, imported by the others):
- `baseRequest<T>(path, options, retry=true)` (`:241`) — the single fetch wrapper; `API_URL = "/api"`
  (`:81`, same-origin proxy), attaches tokens, 401→refresh→retry-once (`:273`), throws
  `ApiRequestError(extractError(payload), status, payload)` (`:286`).
- `normalizeApiError(err)` (`:192`) + `extractError(payload)` (`:232`) — turn the backend's
  `{detail, errors}` envelope (B0) into a usable message (avoids the literal "Validation error." leak).
- `translateBackendMessage` (`:108`) — Persian message mapping.
- Token/user storage: `getStoredTokens`/`persistTokens`/`persistUser`/`getStoredUser`/`clearAuthStorage`.

**Service → endpoint mapping (representative, `auth-service.ts`):**
| Service fn | → endpoint |
|---|---|
| `login` | `POST /token/` |
| `register` | `POST /auth/register/` |
| `inviteLogin` | `POST /auth/invite-login/` |
| `requestPasswordReset`/`confirmPasswordReset` | `POST /auth/password-reset/{request,confirm}/` |
| `fetchMe` | `GET /accounts/me/` |
| `completeOnboarding` | `POST /accounts/complete-onboarding/` |

The other 8 services follow the same pattern (each `export async function` → one `baseRequest` call to a
`/api/...` path). The hooks (`use-teacher-*`, `use-course-content`, `use-exam`, `use-admin-*`,
`use-workspace`, `use-organizations`, `use-notifications`, `use-calendar`, …) wrap these with
loading/error state + `use-mounted-ref` (`:hooks/use-mounted-ref.ts`) to avoid setState-after-unmount.

## Key flows
1. **A page fetch:** page → `use-<x>` hook → service fn → `baseRequest` → `/api/...` (proxied to Django,
   F1/B0) → on 401, refresh + retry once → data or `ApiRequestError`.
2. **Error → UI:** `ApiRequestError` carries the raw payload; `normalizeApiError`/`extractError` produce
   the Persian message; field-level errors feed react-hook-form (F4).

## Data & invariants
- **No ad-hoc `fetch` in components** — everything routes through `src/services/*` (and usually a hook).
- `API_URL = "/api"` (same-origin) so auth uses the proxy; several services also build absolute URLs
  from `NEXT_PUBLIC_API_URL` and **throw «NEXT_PUBLIC_API_URL تنظیم نشده است» if unset** (teacher/admin/
  classes/dashboard/organization) — only auth/user fall back to the relative `/api` (CLAUDE.md §Gotchas).
- Hooks are the data seam: page never calls a service directly; state + mounted-ref live in the hook.
- 401 → single refresh-and-retry (no infinite loop — `retry=false` on the retry).

## Gotchas
- Don't point `NEXT_PUBLIC_API_URL` at the frontend's own origin (:9002) — the `/api` rewrite (F1) would
  loop into itself and 500.
- `baseRequest` lives in `auth-service.ts` and is imported by the others — a new service reuses it, doesn't
  reimplement fetch.
- `extractError` exists specifically so the UI never shows the raw "Validation error." envelope — keep it.

## Cross-links
[frontend-app-shell.md](frontend-app-shell.md) (F1, the `/api` proxy) · [frontend-auth-guards.md] (F4,
token storage + field errors) · [backend-core.md](backend-core.md) (B0, the error envelope) · the
backend view docs B2/B5/B6/B7/B9 (the endpoints these services call) · `.claude/agents/frontend-engineer.md`.

## Verified-by
- `rg "baseRequest|normalizeApiError|extractError|API_URL|export async function" auth-service.ts` →
  the request core (`:241`), error helpers (`:192`,`:232`), `API_URL="/api"` (`:81`), 401-retry
  (`:273`), and the service→endpoint map cited above.
- `Glob src/hooks/use-*.ts*` → the 34-hook inventory.
- `Glob src/services/*.ts` (F1/roadmap) → the 9 services.
- NOT read whole: the 9 service bodies (auth-service is the pattern; the rest mirror it). NOT run this
  pass: tsc/lint (F-layer AUDIT gate).
