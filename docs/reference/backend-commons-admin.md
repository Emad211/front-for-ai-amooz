# Reference — `apps/commons` (admin API, analytics, tickets, LLM cost) + `apps/notification`

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `c1abb0f`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B9 [a/b]
- **Layer:** backend-app (admin panel API + notifications)

## Purpose
The platform-admin backend (`/api/admin/*`): LLM usage/cost dashboards, Tehran-tz analytics, ticketing,
model-price + server settings, and user management (incl. org-manager assign/revoke). Plus the
`notification` app (`/api/notifications/*`): admin/teacher broadcasts, read receipts, preferences.

## Scope & paths
| File | Role |
|---|---|
| `apps/commons/views.py` (1829, god file — grep by class) | ~40 admin view classes |
| `apps/commons/models.py:380-460` | `Ticket`, `TicketMessage`, `AdminSetting` (+ `LLMUsageLog`/`ModelPrice`, L10) |
| `apps/commons/urls.py` (107) | the `/api/admin/*` route table |
| `apps/notification/{models,views,urls}.py` | 5 notification models + 8 views |

**Out of scope:** the LLM cost *substrate* (`token_tracker`, `LLMUsageLog` fields) → L10; the analytics
frontend → F9; admin user-management frontend → F9.

## Public surface (`/api/admin/…`, `[IsAdminUser]` = `IsPlatformAdmin`, unless noted)
| Group | Routes | Views |
|---|---|---|
| **LLM usage** | `llm-usage/{summary,by-feature,by-user,by-provider,daily,recent,breakdown,export-csv}/` + `exchange-rate/` | `LLMUsage*View` (`views.py:177-598`) |
| **Model prices** | `model-prices/` (+`/<pk>/`) | `ModelPrice*View` (admin-editable pricing) |
| **Analytics** | `analytics/{stats,chart,distribution,recent-activity}/` | `Analytics*View` (`:639-875`) |
| **Tickets (admin)** | `tickets/` (+`/<pk>/`, `/reply/`) | `Ticket*View` (`:1024`) |
| **Tickets (user)** | `my-tickets/` (+`/create/`, `/<pk>/reply/`) | `UserTicket*View` (`[IsAuthenticated]`, `:1100`) |
| **Ops** | `server/health/`, `maintenance/tasks/`, `backups/` (+`/trigger/`), `server/settings/` | `Server*/Maintenance/Backup*View` |
| **Admin settings** | `settings/{profile,security,notifications}/` | `Admin*SettingsView` |
| **User mgmt** | `users/`, `users/stats/`, `users/<pk>/`, `users/<pk>/org-manager/` (+`/<org_pk>/`) | `AdminUser*View` (`:1617`) |

**Notifications** (`/api/notifications/…`): `AdminNotificationBroadcast`/`Recipients`
(`[IsAdminUser]`), `TeacherNotification*` (`[IsTeacherUser]`), `NotificationPreferences` /
`MarkNotificationRead` / `MarkAllNotificationsRead` (`[IsAuthenticated]`).

## Key flows
1. **LLM cost dashboards:** read `LLMUsageLog` (L10) aggregated per feature/user/provider/day, with a
   `breakdown` + CSV export; `exchange-rate/` + `model-prices/` feed the monetary estimate.
2. **Analytics** (`AnalyticsStatsView:639`): grouped metrics (users/classes/engagement/llm/tickets/orgs),
   multi-series chart, distribution, and a **unified recent-activity feed** (logins, registrations,
   class/exam-prep creation, quiz/final-exam/exam-prep attempts, tickets+replies, broadcasts) with
   `?type=`/`?limit=`. **All date buckets are Asia/Tehran** (the analytics rule).
3. **Tickets:** admin list/detail/reply vs user create/list/reply; `TicketMessage.author` FK (the fixed
   FieldError — `43815ef`).
4. **User management:** list/stats/detail + `org-manager/` POST-assign / DELETE-revoke (the MANAGER
   grant, memory `manager-role-on-main`).
5. **Notifications:** admin/teacher broadcast to recipient sets → `NotificationReadReceipt` /
   `TeacherNotificationRecipient`; per-user `UserNotificationPreference`; SMS dispatch on the `default`
   queue (B8). Teacher-originated student feed items expose `senderName`, and the SMS body includes the
   same resolved teacher name (full name with username fallback).

## Data & invariants
- **Deny-by-default + admin permission:** every admin endpoint is `[IsAdminUser]` (`IsPlatformAdmin` =
  role ADMIN or is_superuser or is_staff, B0); user-facing ticket/notification endpoints are
  `[IsAuthenticated]` and object-scoped. **Negative tests mandatory** on the admin surface.
- **Asia/Tehran bucketing** everywhere in analytics — never UTC day-buckets (the shipped bug; memory
  `admin-analytics`).
- `TicketMessage`'s author FK is `author` (not `user`) — `select_related('author', 'ticket')`
  (the `43815ef` fix; don't regress).
- `commons` migrations: 5; `notification` migrations: 4.
- `AdminSetting` (`models.py:448`) stores server-tunable settings; `ModelPrice` (L10) is admin-editable
  pricing.

## Gotchas
- `commons/views.py` is 1829 lines — grep by class; this doc's slice map is the four groups above.
- `IsPlatformAdmin` counts is_staff/is_superuser as admin — a Django superuser without `role=ADMIN` still
  has full admin API access (intentional, B0).
- The recent-activity feed touches many models — a new activity source must be added there AND its icon
  mapped on the frontend (the ICON_MAP crash precedent, memory `admin-analytics`).

## Cross-links
[llm-pdf-and-cost.md](llm-pdf-and-cost.md) (L10, the cost substrate these views read) ·
[backend-core.md](backend-core.md) (B0, `IsPlatformAdmin`) · [backend-accounts.md](backend-accounts.md)
(B1, MANAGER role) · [backend-celery-ops.md](backend-celery-ops.md) (B8, notification SMS) · F9 (admin
frontend) · memory: `admin-analytics`, `manager-role-on-main` · `.claude/agents/data-analyst.md`,
`security-auditor.md`.

## Verified-by
- `rg "^class \w+View|permission_classes" commons/views.py` → the ~40-view inventory + permissions
  (all `[IsAdminUser]` except the 3 `UserTicket*` = `[IsAuthenticated]`).
- Full read (2026-07-02): `commons/urls.py` (107) — the complete `/api/admin/*` route table.
- `rg "^class \w+\(models" notification/models.py` → 5 models; `rg "^class \w+View|permission_classes"
  notification/views.py` → 8 views + their role permissions.
- `rg "^class (Ticket|TicketMessage|AdminSetting)" commons/models.py` → `:380/426/448`.
- NOT read whole: `commons/views.py` (1829 lines — grep slice). NOT verified live: analytics tz math on
  real data (unit-tested; memory `admin-analytics`).
