# Reference — `apps/organizations` (multi-tenancy, StudyGroup, invite codes)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `28baf8c`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B3 (a-half)
- **Layer:** backend-app

## Purpose
Owns the tenant model: organizations (schools/institutes), member roles inside them, reusable
invitation codes (the org onboarding entry), study groups («گروه آموزشی» — the roster unit), and the
manager's oversight surfaces (all-org classes + AI-cost breakdown).

## Scope & paths
| File | Role |
|---|---|
| `apps/organizations/models.py` (423) | `Organization`, `OrganizationMembership`, `InvitationCode`, `StudyGroup`, `StudyGroupTeacher`, `StudyGroupMembership` |
| `apps/organizations/views.py` (1042 — god file, grep by class) | 15 view classes (`rg "^class " views.py`) |
| `apps/organizations/urls.py` (84) | Route table below |
| `apps/classes/services/org_roster.py` | `sync_org_class_roster(session)` + `sync_group_classes(group_id)` — StudyGroup → ClassInvitation sync |
| `apps/organizations/migrations/0001–0010` | Lineage below |

**Out of scope:** waitlist signup gate → `backend-waitlist.md` (B3 b-half); class-side invite models → B4.

## Public surface (`/api/organizations/…`)
| Route | View (`views.py:line`) | Access |
|---|---|---|
| `GET/POST /` · `/<org_pk>/` | OrganizationListCreate `:77` / Detail `:126` | **IsAdminUser** (platform admin CRUD) |
| `/<org_pk>/members/` (+`/<pk>/`) | OrgMemberList `:189` / Detail `:226` | IsAuthenticated + `IsOrgAdmin.check` |
| `/<org_pk>/invitation-codes/` (+`/<pk>/`) | OrgInviteCode… `:269`,`:322` | IsAuthenticated + `IsOrgAdmin.check` |
| `/<org_pk>/dashboard/` | OrgDashboard `:629` | IsAuthenticated + org-admin |
| `/<org_pk>/study-groups/…` (CRUD + `/teachers/`, `/students/` add/remove) | StudyGroup* `:723-893` | IsAuthenticated + org-admin |
| `/<org_pk>/my-study-groups/` | MyStudyGroups `:895` | org teacher's own groups |
| `/<org_pk>/classes/` · `/<org_pk>/costs/` | OrgClasses `:924` / OrgCosts `:961` | manager oversight (all org classes + AI-cost) |
| `POST /validate-code/` | ValidateInvitation `:547` | anon (pre-form check) |
| `POST /redeem-code/` | RedeemInvitation `:362` | **anon allowed** · throttle scope `redeem` 15/h |
| `GET /my-workspaces/` | MyWorkspaces `:593` | IsAuthenticated (workspace switcher source) |

`IsOrgAdmin` (`views.py:55-70`) = helper (not a DRF permission class): ACTIVE membership with org_role
∈ {admin, deputy} in THAT org — the org-scoped authorization primitive.

## Key flows
1. **Redemption** (`views.py:362-540`) — the org onboarding entry, uniform for ALL roles:
   `select_for_update` on the code row → **re-validate under the lock** (`:396-408`; a max_uses=1 code
   can't mint two accounts — second request sees the incremented `use_count`, 409) → role map
   admin/deputy→**MANAGER**, teacher→TEACHER, student→STUDENT (`:422-427`; membership keeps the original
   org_role) → anonymous redemption REQUIRES phone (`:437-442`) → returning member bypasses the capacity
   guard; new student seat re-checks `is_at_capacity` under the lock BEFORE any account exists
   (`:458-465`) → `get_or_create_user_by_phone` (same factory as class login; org-created staff get
   `is_freelancer=False`) → **completed accounts blocked 400** (`:484-488`) → membership created +
   atomic `F('use_count')+1`; first admin becomes `org.owner` → anonymous flows get tokens + refresh
   cookie (the code doubles as a returning-member re-entry login until onboarding completes).
2. **StudyGroup → class roster:** org class rosters are DERIVED from study groups —
   `sync_org_class_roster(session)` / `sync_group_classes(group_id)` (`org_roster.py:27,82`) regenerate
   `ClassInvitation` rows from group membership; org teachers cannot free-invite (403 on the classes
   side). Editing a group re-syncs every class linked to it.
3. **Manager oversight:** MANAGER (platform role) sees members/codes/groups/dashboard/classes/costs —
   but creates NO content; AI-cost breakdown comes from `LLMUsageLog.session_id` attribution (L10/B9).

## Data & invariants
- `Organization`: unique `slug`; `student_capacity` (default 100) + `subscription_status`
  (active/expired/suspended, indexed); `is_at_capacity` counts ACTIVE student memberships only.
- `OrganizationMembership`: **`uniq_membership_user_org`** (one membership per user+org); org_role ∈
  admin/deputy/teacher/student; status active/suspended.
- `InvitationCode`: unique `code` (readable 6-char, no 0/O/1/I — `models.py:164-167`); `is_valid` =
  active ∧ under max_uses ∧ not expired ∧ **org subscription ACTIVE** (`models.py:234-245`).
- `StudyGroup`: **`uniq_studygroup_org_name`**; M2M teachers through `StudyGroupTeacher`
  (`uniq_studygroup_teacher`); students via `StudyGroupMembership` (`uniq_studygroup_student`).
- **Invariants:** redemption re-validates + re-checks capacity under the row lock; use_count increments
  atomically; anonymous redemption always phone-keyed; MANAGER ≠ platform admin (no `/admin` access);
  a new org-code account is org-only (`is_freelancer=False`).
- **Migration lineage:** 0001 initial · 0002–0007 legacy-column repair series (add-missing /
  fix-defaults / drop-legacy ×2 / owner nullability / ensure-InvitationCode-table — raw-SQL heavy; the
  reason tests sometimes need `--no-migrations` on a fresh DB) · **0008 data: promote existing org
  admins/deputies → MANAGER** · 0009 StudyGroup trio · 0010 drop legacy InvitationCode columns.

## Gotchas
- The 0002–0007 repair migrations contain raw SQL that can fail on a fresh sqlite test DB — that is the
  documented reason for the `--no-migrations` escape hatch (see I2).
- `IsOrgAdmin` is a static helper called inside handlers, not in `permission_classes` — a new org view
  that forgets to call it passes DRF with only `IsAuthenticated`. Review checklist item.
- Capacity guard: pre-lock serializer 400 + under-lock 409 are BOTH needed; removing the second
  re-introduces the double-redemption race.

## Cross-links
[backend-accounts.md](backend-accounts.md) (the phone factory + MANAGER role) ·
[backend-authentication.md](backend-authentication.md) (the sibling class-code login) ·
`backend-waitlist.md` (how orgs get created via approval) · B4/B5 (ClassInvitation, roster consumers) ·
guard tests: `apps/organizations/test_redeem_student_phone.py`, `test_redeem_race_guard.py`,
`test_manager_onboarding.py` · memory history: `org-teacher-dashboard-rework`, `manager-role-on-main`.

## Verified-by
- Full read (2026-07-02): `models.py` (423), `urls.py` (84), `views.py:55-77` (IsOrgAdmin),
  `views.py:362-546` (RedeemInvitationView — the critical flow).
- `rg "^class |permission_classes|throttle_scope" views.py` → the 15-view inventory + access table.
- `rg "^def " apps/classes/services/org_roster.py` → `sync_org_class_roster:27`, `sync_group_classes:82`.
- `Glob migrations/0*.py` → 10-migration lineage (purposes from filenames; 0008's data promotion known
  from repo history `a9b583e`).
- NOT verified here: the org-side classes/costs response shapes (documented at B5/B9 depth), Postgres
  lock behavior under real concurrency (guarded by `test_redeem_race_guard.py`).
