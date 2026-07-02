# Reference — `apps/accounts` (identity & user model)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `28baf8c`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B1
- **Layer:** backend-app

## Purpose
Owns WHO a user is: the custom `User` model (`AUTH_USER_MODEL='accounts.User'`), the four platform
roles, the **phone-as-unique-student-identity** rule, role profiles, and the one-time forced-onboarding
endpoint that turns passwordless code-login shells into real credentialed accounts.

## Scope & paths
| File | Role |
|---|---|
| `apps/accounts/models.py` (85) | `User`, abstract `BaseProfile`, `StudentProfile`, `TeacherProfile`, `AdminProfile` |
| `apps/accounts/services.py` (113) | `get_or_create_user_by_phone` — THE phone→user factory (all roles) |
| `apps/commons/phone_utils.py` (47) | `normalize_phone` / `is_valid_iran_mobile` — single source of canonicalization |
| `apps/accounts/serializers.py` (330) | `MeSerializer`, `MeUpdateSerializer`, `OnboardingSerializer` |
| `apps/accounts/views.py` (78) | `MeView`, `CompleteOnboardingView` |
| `apps/accounts/signals.py` | `post_save` auto-creates the role profile (MANAGER gets none by design) |
| `apps/accounts/migrations/0001–0007` | Lineage below |

**Out of scope:** login/JWT/OTP flows → B2 (`apps/authentication`); org membership/roles → B3.

## Public surface
| Route | Method | Auth | Contract |
|---|---|---|---|
| `/api/accounts/me/` | GET | IsAuthenticated | Current user + role profile (`MeSerializer`) |
| `/api/accounts/me/` | PATCH | IsAuthenticated | Partial profile update (`MeUpdateSerializer`; students can't switch phone freely — normalized compare, `serializers.py:150`) |
| `/api/accounts/complete-onboarding/` | POST | IsAuthenticated + throttle scope `onboarding` (20/h) | One-time: sets username/password/email/phone + light profile, flips `is_profile_completed`. **400 with «حساب شما قبلاً تکمیل شده است.» if already completed** (`views.py:70-74`) — deliberately NOT an old-password-free reset |

**Exports used by other apps:**
- `get_or_create_user_by_phone(phone, role, *, first_name, last_name, is_freelancer=None) -> (user, created)`
  (`services.py:43`) — phone MUST already be canonical; called by class-invite login AND org redemption
  for ALL roles so one human can never fork into two users.
- `normalize_phone(raw) -> '09XXXXXXXXX'` + `is_valid_iran_mobile(norm)` (`phone_utils.py:25,44`) —
  handles Persian/Arabic digits (`_DIGIT_MAP`), `+98…`(12)→`0…`, `9…`(10)→`09…`. Normalize ≠ validate:
  pair them at input boundaries.

## Key flows
1. **Phone → user (all code entries):** normalize → `get_or_create_user_by_phone`: role-scoped lookup →
   else create inside `transaction.atomic` a passwordless shell (`set_unusable_password`,
   `services.py:88`) with auto-username `<roleprefix>_<phone>` (+`_hex6` on collision) → on
   `IntegrityError` (lost race on username or `uniq_student_phone`) fetch and return the winner
   (`services.py:90-97`). `is_freelancer` applied only on creation (org-created teachers/managers → False).
2. **Forced onboarding:** frontend gate redirects incomplete users to `/onboarding` → POST
   `complete-onboarding/` → `OnboardingSerializer.save()` sets credentials + profile, catches duplicate
   `IntegrityError` → 400 (`serializers.py:304-324`) → `is_profile_completed=True` ends the gate.
3. **Profile auto-creation:** `post_save` on `User` (`signals.py:5-6`) creates the matching role
   profile; `_ensure_profile` (`services.py:31`) is the defensive re-check for older rows.

## Data & invariants
- **`uniq_student_phone`** (`models.py:34-38`): partial `UniqueConstraint(fields=['phone'],
  condition=Q(role='STUDENT', phone__isnull=False))` — ONE student per phone, while the same phone may
  own a different-role account, and NULL phones are unconstrained. Don't "simplify" to a full unique.
- `phone` = `CharField(max_length=15, null=True)`, stored ONLY in canonical `09XXXXXXXXX` form.
- `is_freelancer` (`models.py:24`): TEACHER-only semantics (personal workspace); ignored for other
  roles; a MANAGER never gets a personal space.
- MANAGER = org oversight role, is NOT staff/superuser and gets NO profile row.
- **Migration lineage:** 0001 initial · 0002 profile `location` fields · 0003 data: promote superusers
  to ADMIN · 0004 role choices + MANAGER · 0005 `is_freelancer` · **0006 DATA-ONLY: wipe all non-admin
  users (explicit user decision, 2026-06-20) + canonicalize remaining phones · 0007 DDL-ONLY: add
  `uniq_student_phone`** — the canonical DML/DDL-split precedent (Postgres pending-trigger-events);
  never merge such a pair.

## Gotchas
- Legacy copies of the phone normalizer used `str.isdigit()` (True for Persian glyphs but left them
  unconverted) — that's exactly how one human became two users. Any NEW phone input site must go
  through `phone_utils`; a re-implemented normalizer is a review-blocking finding.
- Onboarding is the ONLY old-password-free credential setter, guarded by the one-time
  `is_profile_completed` check — weakening that check creates an account-takeover path.
- Repo-wide gotchas: CLAUDE.md §Gotchas.

## Cross-links
[backend-authentication.md](backend-authentication.md) (who calls the factory at login) ·
[backend-organizations.md](backend-organizations.md) (redemption path) · [backend-core.md](backend-core.md)
(throttle scope, JWT config) · guard tests: `apps/accounts/test_onboarding.py`,
`test_student_phone_unique.py`, `apps/commons/test_phone_utils.py` · `.claude/agents/security-auditor.md`.

## Verified-by
- Full read (2026-07-02): `models.py` (85), `services.py` (113), `phone_utils.py` (47), `views.py` (78),
  `urls.py` (8).
- `rg "class \w+Serializer|def validate_|def save|IntegrityError" apps/accounts/serializers.py` →
  serializer inventory + validator lines cited above (spot-verified, not full-read: the 330-line body).
- `Glob apps/accounts/migrations/*.py` → the 7-migration lineage listed above (0003/0006 purposes from
  their filenames + this repo's documented history; 0006/0007 split verified in the 2026-06-20 work).
- `rg "post_save" apps/accounts/` → `signals.py:5,24` receivers.
- NOT verified live: concurrent-race behavior on Postgres (unit-tested on sqlite; constraint semantics
  reasoned for Postgres).
