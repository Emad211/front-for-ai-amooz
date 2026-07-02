# Reference — `apps/waitlist` (teacher/org signup approval gate)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `6110dec`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B3 (b-half)
- **Layer:** backend-app

## Purpose
Teachers and organizations do NOT self-register instantly. They submit an `AccessRequest` (a lead); a
platform admin reviews and approves; approval issues a one-time registration token (and, for orgs,
provisions the Organization + admin code). **No account exists until approval** — this app is the sole
record of a pending teacher/org.

## Scope & paths
| File | Role |
|---|---|
| `apps/waitlist/models.py` (104) | `AccessRequest` (the lead + review state + outcome links + token) |
| `apps/waitlist/views.py` (202) | Public intake, teacher completion, admin list/approve/reject |
| `apps/waitlist/services.py` | `approve_access_request`, `complete_teacher_registration`, `reject_access_request`, SMS notify |
| `apps/waitlist/serializers.py` | Intake + completion validators (`normalize_iran_phone = normalize_phone` alias) |
| `apps/waitlist/migrations/0001_initial.py` | Single migration |

**Out of scope:** the org that approval provisions → [backend-organizations.md](backend-organizations.md);
the User it eventually creates → [backend-accounts.md](backend-accounts.md).

## Public surface (`/api/waitlist/…`)
| Route | View (`views.py:line`) | Access |
|---|---|---|
| `POST /requests/` | AccessRequestCreate `:47` | **AllowAny** · throttle scope `waitlist` 10/h |
| `POST /complete/` | TeacherRegistrationComplete `:86` | AllowAny · scope `waitlist` — consumes a TEACHER token → real account |
| `GET /admin/requests/` | AccessRequestList `:134` | **IsPlatformAdmin** (filter by kind/status) |
| `POST /admin/requests/<pk>/approve/` | AccessRequestApprove `:155` | IsPlatformAdmin |
| `POST /admin/requests/<pk>/reject/` | AccessRequestReject `:181` | IsPlatformAdmin |

## Key flows
1. **Intake:** public form → `AccessRequest` (kind teacher|organization, contact + kind-specific fields),
   status PENDING. No user/org created.
2. **Approve** (`services.py:41-73`): stamp APPROVED + reviewer + `token_expires_at`
   (`REGISTRATION_TOKEN_TTL_DAYS`). **Org branch:** `provision_organization` creates the Organization +
   admin `InvitationCode`; **the admin code IS the registration token** — the manager registers by
   redeeming it (→ B3a redemption → MANAGER). **Teacher branch:** `generate_registration_token()` (a
   standalone one-time token). Approval SMS carries the code/link (`build_approval_sms_text:183`).
3. **Teacher completion** (`services.py:88-142`): `select_for_update` the row by
   (token, kind=TEACHER, status=APPROVED, not-yet-consumed) → reject unknown/expired
   (`InvalidRegistrationToken`) → `User.objects.create_user(..., is_profile_completed=True)` +
   `TeacherProfile` → stamp `created_user` + `token_consumed_at` (single-use, race-safe under the lock).
4. **Reject** (`services.py:146`): status REJECTED + reason; no account.

## Data & invariants
- `AccessRequest`: `kind` (teacher|organization, indexed), Status
  pending→contacted→approved/rejected (indexed), composite index `(kind, status)`; outcome FKs
  `created_user`/`created_organization` (SET_NULL); token trio
  `registration_token`(indexed)/`token_expires_at`/`token_consumed_at`.
- **Invariants:** no account/org before approval; the registration token is **one-time**
  (`token_consumed_at` gate + `select_for_update`); teacher completion sets
  `is_profile_completed=True` (credentials chosen at completion, so no forced onboarding after); org
  approval reuses the invite-code redemption path rather than a separate token; SMS-only delivery
  (email disabled platform-wide).
- Single migration `0001_initial` — deploy = image rebuild + migrate.

## Gotchas
- Two different "token" meanings: a TEACHER gets a synthetic `registration_token`; an ORG's token IS its
  admin invite code (redeemed via B3a). Don't unify them.
- `complete/` is public (AllowAny) but safe because it requires a valid, approved, unconsumed,
  unexpired token under a row lock — the token is the credential.

## Cross-links
[backend-organizations.md](backend-organizations.md) (org provisioning + admin-code redemption) ·
[backend-accounts.md](backend-accounts.md) (the teacher account created) · [backend-core.md](backend-core.md)
(the `waitlist` throttle scope) · admin review UI → F9 · memory history: `waitlist-feature`.

## Verified-by
- Full read (2026-07-02): `models.py` (104), `urls.py` (21), `services.py:41-115` (approve + complete).
- `rg "^class |permission_classes|throttle_scope" views.py` → 5-view access table above.
- `rg "^def |registration_token|is_profile_completed" services.py` → service inventory + the
  `is_profile_completed=True` at completion (`services.py:125`) + single-use token gate.
- `Glob migrations/0*.py` → single `0001_initial`.
- NOT verified live: Mediana approval SMS delivery; `provision_organization` internals (documented at B3a).
