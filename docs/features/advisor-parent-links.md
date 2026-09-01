# Advisor Parent Links (گزارش هفتگی والدین) — Living Spec

Status: **shipped (2026-08-31)** · Scope: PARENT role + parent OTP login +
read-only weekly digest + advisor manage UI + student transparency card.
Extends [advisor-growth-loop.md](advisor-growth-loop.md); supersedes the
«والدین = P2» lock in [risman-parity-roadmap.md](risman-parity-roadmap.md)
(owner decision 2026-08-31: parents move to NOW).

## Why

The parent pays the advisor but was invisible to the product (persona QA
verdict 4/10). Research (Kraft & Rogers 2015; Stattin & Kerr 2000; Hamshor;
Ellos; Satchel One; Seesaw) points to one shape: **advisor-mediated linking,
phone-OTP login, a deliberately-limited read-only digest, and student
transparency without veto** — a weekly SMS-readable report, not a portal.

## Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Who links the parent | **Advisor** (from student record), max 2 live links | Parent pays the advisor; GoStudent/Satchel/Seesaw precedent; self-signup dies at low tech literacy |
| Student say | **Transparency, no veto** — sees who is linked + what they see | Stattin & Kerr: disclosure survives only without surveillance feel |
| Auth | **Phone + 6-digit OTP** (hashed in cache, TTL 10 min, 5 attempts, 90 s resend cooldown) | Darsbama/Hamshor pattern; parents can't manage passwords |
| Visibility | Weekly aggregates ONLY (see filter table) | Teen privacy line; mood/notes kill honest logging |
| Cadence | Thursday 17:30 Tehran in-app notify + SMS nudge (beat) | Kraft & Rogers weekly one-liner moved outcomes 41% |

## Backend — files & wire

- Role: `User.Role.PARENT` (`accounts/models.py`), migration
  `accounts/0010_alter_user_role_parent.py` (choices-only),
  `_USERNAME_PREFIX['PARENT'] = 'parent'` (`accounts/services.py`),
  `IsParentUser` (`apps/core/permissions.py`, denies `imp` claim),
  org-manager refusal (`commons/views.py`).
- Model: `ParentLink` (`advisory/models.py` + migration
  `advisory/0020_parent_links.py`) — engagement FK CASCADE, parent FK
  PROTECT (null until first login), phone (11-digit `09…` check),
  relation father/mother/guardian, status PENDING/ACTIVE/REVOKED,
  partial unique `uniq_active_parent_link` (engagement, phone) on
  PENDING+ACTIVE, `created_by`, `activated_at`. REVOKED is audit history:
  revocation frees the slot.
- Services: `services/parent_links.py` (lifecycle + OTP issue/verify +
  SMS enqueue; duplicate phone → 400 Persian «این شماره قبلاً برای این
  دانش‌آموز ثبت شده است.» incl. IntegrityError race), `services/parent_digest.py`
  (pure weekly build). Both registered in `test_import_boundaries.py`.
- Views (`views_parents.py`, all `@extend_schema`):
  - `POST/GET /api/advisory/students/<pk>/parents/` (advisor; 202 `{"status":"sent"}` uniform — no account-existence leak; throttle `advisory_parent_invite` 10/h)
  - `DELETE …/parents/<link_id>/` → 204, REVOKED; foreign 404
  - `POST /api/advisory/parent/login/request/` (public, throttle `parent_login` 5/h) — **always** 202; OTP only when a live link or PARENT user matches the phone
  - `POST /api/advisory/parent/login/verify/` → `{access, refresh, user}` + refresh cookie; first login mints/uses the PARENT user and atomically activates every PENDING link for that phone (`activated_at = today`)
  - `GET /api/advisory/parent/me/links/` — ACTIVE links of ACTIVE engagements only
  - `GET …/links/<id>/digest/` — the digest below; writes `AdvisoryAccessLog` action `parent_digest_view`; 404 foreign/revoked/inactive
  - `GET /api/advisory/me/parents/` (student) — transparency mirror
- Tasks (`tasks.py`, default queue): `send_parent_invite_sms_task`,
  `send_parent_login_otp_sms_task`,
  `send_parent_weekly_digest` (beat `advisory-parent-weekly-digest`,
  `crontab(day_of_week=4, hour=17, minute=30)` in settings; per-link errors
  don't kill the batch; skips links without a parent user).

### Digest contract (parent me/links/<id>/digest/)

```json
{
  "asOf": "2026-08-31",
  "weekMinutes": 75,
  "weekPlanMinutes": 100,
  "adherencePercent": 75,
  "testsTaken": 0,
  "examTrend": [{"date": "…", "scorePercent": 72, "tara": 5123}],
  "openMistakesCount": 2,
  "reviewDueCount": 3,
  "activeChallengeTitle": "…",
  "streak": 1
}
```

**Privacy filter (test-pinned ABSENCE):** mood, note, motivationNote,
dayGoal, mistake texts/topics, call logs, assessment scores never appear —
not as keys, not as serialized values.

## Frontend

- `services/parent-service.ts` — own requestJson; the two login calls go
  through the same-origin `/api` proxy with `credentials: 'include'`
  (refresh cookie must be first-party); authenticated GETs direct like
  advisory-service; persists via auth-service `persistTokens`/`persistUser`
  (same storage keys → gates/layout guards just work).
- `/parent-login` (public, top-level) — one screen, two steps: phone
  (h-14, Persian-digit tolerant, `09xxxxxxxxx`) → 6-digit OTP with 90 s
  resend countdown; server Persian errors verbatim; success → `/parent`.
- `(parent)/parent/` — layout role-guard (`landingFor('PARENT') → '/parent'`)
  + dashboard: per-child card with «این هفته: X ساعت و Y دقیقه مطالعه»,
  اجرا chip (adherenceColorClass), tests count, exam-trend line chart
  (recharts, Persian digits), «اشتباه‌های رفع‌نشده», «مباحث رسیده به مرور»,
  challenge chip, streak, Jalali «به‌روزرسانی» footer. Empty state:
  «هنوز گزارشی برای شما فعال نیست — مشاور فرزند شما شمارهٔ شما را ثبت می‌کند.»
- Advisor manage: `components/advisory/parent-links-card.tsx` in the
  student-detail **پرونده** tab — list (masked phone, relation, PENDING/
  ACTIVE badges), add form (phone + relation + «ارسال دعوت», hidden at the
  2-live cap with a Persian note), revoke behind AlertDialog. Service
  methods in `advisory-service.ts` (defensively normalized).
- Student transparency: `components/dashboard/advisory/my-parents-card.tsx`
  in the پرونده tab's «هدف و شناخت» disclosure — quiet (renders nothing
  when empty) — «این افراد گزارش هفتگی شما را می‌بینند.»
- Wiring: `landingFor` case + test, login-form panel map, `types/index.ts`
  role union, admin users page «والد».
- Ops: `docker-compose.yml` gained the **`celery-beat`** service (the
  Thursday digest — and the pre-existing beat schedule — never had a
  runner before this); `scripts/dev-up.ps1` starts it too.

## Deliberately NOT built

Parent chat, per-day minute feeds, mood/notes to parents, parent-side
mutations of anything, self-signup, monthly PDF (digest covers weekly;
PDF is a later increment), parent impersonation by org managers.

## Verification (2026-08-31)

- `pytest backend/apps/advisory backend/apps/accounts` — **825 passed**
  (20 in `test_parent_links.py`: access matrix incl. advisor↛parent and
  parent↛advisor, OTP issue/verify/auto-activate + wrong/expired/cooldown,
  duplicate-phone 400 regression, quota incl. revoked-frees-slot, digest
  privacy absence + math, revoke→digest 404, student mirror, access-log row).
- `tsc --noEmit` + `next build` clean.
- Live browser QA: advisor add/list/quota/revoke (202/204 + UI states),
  student transparency card, parent phone→OTP→dashboard end-to-end
  (OTP injected into cache for QA; SMS path verified via worker logs),
  mobile 375 px — no overflow, ≥44 px targets, 0 console errors.
