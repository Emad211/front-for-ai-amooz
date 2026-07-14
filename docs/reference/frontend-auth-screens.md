# Reference — Frontend auth screens ((auth) + start/join/onboarding)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-14
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F5
- **Layer:** frontend-route-group ((auth) + top-level entry routes)

## Purpose
The unauthenticated entry surface: login variants, password reset, teacher/org signup requests, the
role picker, invite-code redemption, and the forced 3-step onboarding wizard. Each screen sits on the
F4 guard/routing flow and F3 services.

## Scope & paths
| Route | Page | Purpose |
|---|---|---|
| `(auth)/login` | `login/page.tsx` | password login (identifier) |
| `(auth)/admin-login` · `org-login` | dedicated login variants |
| `(auth)/join-code` | `join-code/page.tsx` | unified phone-code entry (student/all-roles) |
| `(auth)/forgot-password` | OTP password reset |
| `(auth)/register/complete` | teacher token completion (B3 waitlist) |
| `(auth)/teacher-signup` · `organization-signup` | waitlist request forms |
| `start/` | `start/page.tsx` | role picker (teacher-vs-student) |
| `join/` | org invite-code redemption |
| `onboarding/` | `onboarding/page.tsx` | forced 3-step wizard |

**Out of scope:** the guards/routing → F4; the services → F3; shared UI → F11.

## Public surface / screens
- **`OnboardingPage`** (`onboarding/page.tsx:59`) — react-hook-form + zod (`OnboardingFormValues`),
  `step` state (`:61`), per-step validation via `trigger(ONBOARDING_STEP_FIELDS[step])` (`:85`), and a
  `FIELD_MAP` (`:54`) mapping backend snake_case errors → form fields for `setError`. Calls
  `completeOnboarding` (F3) → routes to the role home (F4).
- **`StartPage`** (`start/page.tsx:10`) — role picker linking to `/teacher-signup` etc.
- Login screens use `login-form` / `unified-code-form` (F4); signup screens post to the waitlist (B3).

## Key flows
1. **Onboarding wizard:** 3 steps (credentials → contact → role profile); `ONBOARDING_STEP_FIELDS`
   (`validations/onboarding.ts`, F2) gates advancing; on submit → `completeOnboarding` → server sets
   credentials + `is_profile_completed=True` (B2) → redirect to role home. Backend field errors surface
   via `FIELD_MAP` → `setError`.
2. **Code entry:** `join-code` (and `/join`) take a phone/code → `inviteLogin`/redeem (F3/B2/B3a) → new
   or returning user → `/onboarding` if not completed, else role home.
3. **Signup requests:** teacher/org signup forms → waitlist intake (B3b), no account until approved.

## Data & invariants
- Onboarding is 3 steps with per-step zod validation; the schema is the canonical multi-step pattern (F2).
- Backend snake_case error keys are mapped to camelCase form fields (`FIELD_MAP`) — a new onboarding
  field needs both the zod schema AND the map entry.
- All screens are Persian + RTL (F2); copy is natural (the «کد سازمان آموزشیِ مدرسه» lesson — grammar in context).
- These screens implement the phone-identity + forced-onboarding model (B1/B2) on the client; the server
  is authoritative (completed accounts blocked from code re-entry → the screen shows the server message).
- Invite-code inputs are capped at 64 characters. Phone input accepts common Iranian forms and Persian
  digits but is normalized to exactly `09XXXXXXXXX` before submission.
- Every new-password screen shares the backend policy: 8–128 printable ASCII characters with at least
  one uppercase English letter, one lowercase English letter, and one digit. Login itself deliberately
  does not enforce this policy so existing users can authenticate with their current password.

## Gotchas
- `register/complete` is the TEACHER token path (B3b); org managers register by redeeming the admin code
  via `/join` (B3a) — two different "completion" flows, don't merge.
- The onboarding `FIELD_MAP` must stay in sync with the backend serializer field names (B1
  `OnboardingSerializer`) or backend validation errors won't attach to the right field.

## Cross-links
[frontend-auth-guards.md](frontend-auth-guards.md) (F4, the gate + routing) ·
[frontend-services-hooks.md](frontend-services-hooks.md) (F3, `completeOnboarding`/`inviteLogin`) ·
[frontend-conventions.md](frontend-conventions.md) (F2, the zod wizard pattern) ·
[backend-authentication.md](backend-authentication.md) (B2) · [backend-waitlist.md](backend-waitlist.md)
(B3b) · [backend-organizations.md](backend-organizations.md) (B3a) · memory:
`onboarding-and-user-uniqueness`, `waitlist-feature`.

## Verified-by
- `Glob (auth)/**/page.tsx` → the 8 auth screens tabulated above.
- Read (2026-07-02): `onboarding/page.tsx:1-85` (react-hook-form+zod, `step` state, `FIELD_MAP`,
  `ONBOARDING_STEP_FIELDS`, per-step `trigger`), `start/page.tsx:10` (role picker).
- Top-level `start/`,`join/`,`onboarding/` confirmed in the F1 route inventory.
- NOT read whole: the screen bodies (grep gives the structure). NOT run this pass: tsc/lint (AUDIT gate).
