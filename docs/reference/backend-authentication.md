# Reference — `apps/authentication` (JWT / OTP / login layer)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `28baf8c`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B2
- **Layer:** backend-app (0 migrations — operates on `accounts` models)

## Purpose
Owns HOW users get in and stay in: password login by identifier, student invite-code login, logout,
password change/reset (SMS OTP), and the HttpOnly refresh-cookie mechanics. Account *shape* lives in
B1 (`apps/accounts`); this app only authenticates it.

## Scope & paths
| File | Role |
|---|---|
| `apps/authentication/views.py` (371) | Register, InviteCodeLogin, Logout, PasswordChange, PasswordReset request/confirm |
| `apps/authentication/serializers.py` (275) | Validators for all of the above + `TokenObtainPairByIdentifierSerializer` |
| `apps/authentication/otp_service.py` (117) | Cache-backed SMS OTP (no DB model) |
| `apps/authentication/cookies.py` (54) | `set_refresh_cookie` / `clear_refresh_cookie` / `get_refresh_from_request` |
| `apps/authentication/openapi.py` | Response serializers for the OpenAPI schema |
| `backend/core/urls.py:47-91` | `TokenObtainPairViewDocs` + `TokenRefreshViewDocs` (the actual `/api/token/*` views live here) |

## Public surface
| Route | View | Auth/Throttle | Contract |
|---|---|---|---|
| `POST /api/token/` | `TokenObtainPairViewDocs` (`core/urls.py:47-56`) | anon · scope `login` 10/min | Login by **identifier** (username, or email; `serializers.py:203-…`) → access+refresh; sets HttpOnly refresh cookie |
| `POST /api/token/refresh/` | `TokenRefreshViewDocs` (`core/urls.py:71-91`) | anon | Reads refresh from **cookie first**, body fallback; rotation re-sets the cookie |
| `POST /api/auth/register/` | `RegisterView` | anon · scope `register` 10/h | Creates user (`is_profile_completed=True` — self-chosen credentials), returns user+tokens, logs last_login |
| `POST /api/auth/invite-login/` | `InviteCodeLoginView` | anon · scope `invite_login` 10/min | Student code+phone login (flow below) |
| `POST /api/auth/logout/` | `LogoutView` | IsAuthenticated | Idempotent: clears cookie + 205; blacklists the refresh **only if it belongs to the caller** (`views.py:148-150`) |
| `POST /api/auth/password-change/` | `PasswordChangeView` | IsAuthenticated | Old-password check → set new → **blacklist ALL outstanding refresh tokens** → fresh pair (`views.py:198-215`) |
| `POST /api/auth/password-reset/request/` | `PasswordResetRequestView` | anon · scope `password_reset` 15/h | Always generic 200 (**no account enumeration**, `views.py:234-243`); OTP only for password-using accounts |
| `POST /api/auth/password-reset/confirm/` | `PasswordResetConfirmView` | anon · scope `password_reset` | OTP + new password → revoke all sessions → fresh pair (auto-login) |

## Key flows
1. **Invite-code login** (`views.py:310-371`) — students' PRIMARY login:
   code+phone → prefer global `StudentInviteCode(phone, code)` (must also have a *published*
   `ClassInvitation`); legacy per-class codes accepted and back-filled into the global table
   (`views.py:318-337`) → `get_or_create_student_by_phone` (the SAME factory org-redemption uses —
   single identity per phone) → **completed accounts are rejected 400** «این حساب قبلاً فعال شده است…»
   (`views.py:349-353`) — the code is a one-time bootstrap, never a password bypass → tokens + cookie +
   `_safe_update_last_login`.
2. **Session revocation on credential change:** password change AND reset-confirm blacklist every
   `OutstandingToken` for the user before issuing a fresh pair — a stolen refresh token dies with the
   old password (SimpleJWT is stateless; without this it would survive up to 3 days).
3. **OTP reset** (`otp_service.py`): 6-digit code, cache-only (Redis, no migration), stored **hashed**;
   TTL `PASSWORD_RESET_OTP_TTL_SECONDS` 600s; max 5 attempts then invalidated; single-use; 90s resend
   cooldown (anti SMS-bombing); delivery via Mediana; students (unusable password) can never reset —
   they onboard via code.
4. **Refresh cookie** (`cookies.py`): HttpOnly, `Lax`, path `/api/`, lifetime = refresh lifetime;
   body still carries the refresh for backward compat; master switch `AUTH_REFRESH_COOKIE`.
5. **last_login:** custom paths call `_safe_update_last_login` (`views.py:41-50`, never fails the
   flow); `/api/token/` gets it via `SIMPLE_JWT.UPDATE_LAST_LOGIN` (obtain only, not refresh).

## Data & invariants
- No models/migrations here. State touched: `accounts.User`, SimpleJWT outstanding/blacklist tables,
  `classes.StudentInviteCode` + `classes.ClassInvitation` (read/backfill), Redis (OTP).
- **Invariants:** completed accounts blocked from code re-entry (the account-takeover guard) ·
  register sets `is_profile_completed=True` (user chose credentials) while code-created shells get
  `False` · reset endpoints never reveal whether an account exists · logout can't blacklist another
  user's token · every anonymous mutation endpoint has a dedicated throttle scope (B0 table).

## Gotchas
- `/api/token/` views live in `core/urls.py`, NOT in this app's `views.py` — schema decorators and the
  cookie logic are there; don't duplicate them here.
- OTP lives only in cache: flushing Redis invalidates in-flight resets (harmless, but explains
  "invalid code" after a cache clear).
- Email delivery is disabled platform-wide — SMS is the only OTP channel; without `MEDIANA_API_KEY`
  the request still returns generic 200 but nothing is sent (logged).

## Cross-links
[backend-accounts.md](backend-accounts.md) (the factory + onboarding these flows feed) ·
[backend-core.md](backend-core.md) (JWT lifetimes, cookie settings, throttle rates) ·
[backend-organizations.md](backend-organizations.md) (the other code-redemption path) · guard tests:
`apps/authentication/test_invite_login.py`, `test_token_rotation.py`, `test_security.py`,
`test_password_reset.py` · `.claude/agents/security-auditor.md`.

## Verified-by
- Full read (2026-07-02): `views.py` (371), `otp_service.py` (117), `cookies.py` (54), `urls.py` (15).
- `rg "class \w+Serializer|def validate|def create" serializers.py` → serializer inventory incl.
  `TokenObtainPairByIdentifierSerializer:203` (identifier login).
- `rg "TokenObtainPairViewDocs|serializer_class|set_refresh_cookie" core/urls.py` → `/api/token/*`
  wiring, login throttle scope, cookie set/rotate (`core/urls.py:47-91`).
- NOT verified live: Mediana SMS delivery, Redis-backed OTP expiry timing (unit-tested; no live SMS).
