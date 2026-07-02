# Reference — Architecture overview (system map)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `28baf8c`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step S1
- **Layer:** cross-cutting

## Purpose
AI-Amooz (پلتفرم آموزشی هوشمند) turns teacher-uploaded lecture media/PDFs into structured Persian
course content via an LLM pipeline; students learn through a personalized RTL UI with quizzes, an
adaptive remediation loop, exam prep, and a course-aware tutor. This doc is the system map every other
reference doc hangs off.

## Scope & paths (monorepo)
| Path | Role |
|---|---|
| `backend/core/` | Django project package (settings, urls, celery, middleware, storage, exception handlers) — NOT `config` |
| `backend/apps/` | 10 Django apps (below) |
| `frontend/src/` | Next.js 15 App Router + React 19 + TS strict, RTL Persian |
| `Dockerfile` (root) | Prod backend image — runs `migrate` + `collectstatic` + gunicorn on start |
| `docker-compose*.yml`, `scripts/dev-*.ps1`, `k8s/`, `nginx/` | Local stack + deploy (→ [runbook](../runbooks/local-stack.md), I1) |
| `docs/` | ADRs, feature specs, releases, runbooks, this reference tree |

**Backend app inventory** (all in `INSTALLED_APPS` — `core/settings.py`; `authentication`/`chatbot`/
`material` verified present at `settings.py:57,62,63`):
| App | Substance | Reference doc |
|---|---|---|
| `accounts` | Custom `User` (4 roles) + profiles; phone = student identity | B1 |
| `authentication` | JWT/OTP/login layer (0 migrations — uses accounts models) | B2 |
| `classes` | **Core domain**: courses, pipeline, chat, quizzes, exam prep. God file `views.py` = 5199 lines | B4–B7, L4–L9 |
| `organizations` | Multi-tenant orgs, StudyGroup, invite codes | B3 |
| `waitlist` | Teacher/org signup approval gate | B3 |
| `commons` | Admin API, analytics, tickets, LLM plumbing (prompts, structured_llm, token tracking) | B9, L2, L3, L10 |
| `notification` | Notifications + read receipts | B9 |
| `chatbot` | **Service-only** (no models/views/urls): hosts `services/llm_client.py`, the LLM god node | L1 |
| `core` (app) | Health view, shared permissions/throttling | B0 |
| `material` | Empty (`__init__.py` only) — registered placeholder | — |

## Public surface (top-level routing — verified `core/urls.py:94-128`)
| Route | Target |
|---|---|
| `/api/health/` · `/api/schema/` · `/api/docs/` · `/api/redoc/` | Health + OpenAPI (drf-spectacular) |
| `/api/token/`, `/api/token/refresh/` | SimpleJWT obtain/refresh |
| `/api/accounts/` → accounts · `/api/auth/` → authentication | Identity + login flows |
| `/api/classes/` → classes | The core domain |
| `/api/organizations/` · `/api/waitlist/` | Tenancy + signup gate |
| `/api/admin/` → **commons** · `/api/notifications/` → notification | Admin panel API + notifications |
| `/media/<path>` | Django media proxy (when no public storage domain) |
| `/admin/` | Django admin |

**Frontend route groups** (`frontend/src/app/`, 61 page/layout files): `(marketing)` landing ·
`(auth)` + `start/` + `join/` + `onboarding/` · `(dashboard)` student · `(teacher)` · `(org)` manager ·
`(admin)`. Browser calls same-origin `/api/*`; Next rewrites to `BACKEND_URL || NEXT_PUBLIC_API_URL`
(F1). Layers: 9 `services/*.ts` → 34 `hooks/use-*.ts` → pages (F3).

## Key flows
1. **Class pipeline** (Celery `pipeline` queue, cancellable): upload → `process_class_step1_transcription`
   (chunked for long media, L5) → `step2_structure` (L6) → `step3_prerequisites` → `step4_prereq_teaching`
   → `step5_recap` (L7); chained by `process_class_full_pipeline` — a status-guarded state machine
   (TRANSCRIBING → … → RECAPPED, terminal CANCELLED) with cooperative cancel checkpoints + heartbeats (L4).
2. **Exam-prep pipeline**: separate 2-step set (`process_exam_prep_step1/2`, EXAM_TRANSCRIBING →
   EXAM_STRUCTURED) sharing the transcription/windowing infra (L9).
3. **Student learn/assessment loop**: code entry (`/join-code`) → forced 3-step `/onboarding` (B2/F4) →
   course content → chapter quiz / final exam → **fail ⇒ all answers revealed ⇒ regenerate targeting
   missed concepts ⇒ retake until pass** (`last_passed` reset = the rate-limiter; B6/L8).
4. **LLM call path** (every call): caller → `PROMPTS[key]` (`str.replace` templating, L3) →
   `generate_structured`/`validate_keep_dict` (L2) → provider client (`chatbot/services/llm_client.py`,
   Avalai/Gemini via env, L1) → `LLMUsageLog` with `session_id` attribution → per-teacher/class/feature
   cost views (L10/B9).
5. **Tenancy**: org invite redemption maps admin/deputy → MANAGER (oversight-only); org class rosters
   sync from StudyGroup; freelancer vs org teacher split via `is_freelancer` (B3).

## Data & invariants (frozen contracts — breaking any is a production incident)
- **Prompt contract**: 26 live `PROMPTS` keys; placeholders + output-JSON keys are byte-for-byte;
  guarded by `apps/classes/test_prompts_contract.py` (L3).
- **Phone identity**: one STUDENT per canonical phone (`uniq_student_phone` partial constraint);
  all entry points normalize via `commons/phone_utils` (B1).
- **Migration discipline**: DML and DDL always in separate migrations (Postgres pending-trigger-events);
  migrations auto-run on backend container start (B0/B1 precedent `accounts/0006`+`0007`).
- **`/api` rewrite + `skipTrailingSlashRedirect`** in `next.config.ts` — Django's trailing slashes (F1).
- **Deny-by-default permissions** + object-level ownership everywhere; MANAGER never creates content.
- **Queues**: slow LLM/media work on `pipeline` only (hard 2h/soft 100min, prefetch=1); quick tasks on
  `default`; cancellation checkpoints + heartbeats must survive refactors (L4).
- **Env-driven config**: no hardcoded models/keys/domains. Prod domain split is intentional:
  backend `aiamoooz` (3 o's) / frontend `aiamooz` (2 o's) — never "fix" (CLAUDE.md §Production).

## Gotchas
Canonical list lives in **CLAUDE.md §Gotchas** (dev port 9002, `NEXT_PUBLIC_API_URL` rules, build hides
type errors, `core` not `config`, …) and [runbooks/local-stack.md](../runbooks/local-stack.md) — not
restated here.

## Cross-links
[ROADMAP.md](ROADMAP.md) (all step specs) · [ADR-0001](../adr/ADR-0001-agentic-team.md) (agent team) ·
[ADR-0002](../adr/ADR-0002-reference-docs-program.md) (this program) · CLAUDE.md (conventions) ·
`.claude/agents/README.md` (team manual) · `graphify-out/GRAPH_REPORT.md` (generated map, 2026-06-19 —
verify with grep before trusting).

## Verified-by
- `rg "path\(" backend/core/urls.py` → the routing table above (14 entries, 2026-07-02).
- Council verification (5 parallel agents, 2026-07-02): `INSTALLED_APPS` membership incl.
  `authentication`/`chatbot`/`material` (`core/settings.py:57,62,63`); 26 `LIVE_KEYS`
  (`test_prompts_contract.py:39`); pipeline task set + statuses + `acks_late`/`max_retries`
  (`classes/tasks.py`); chatbot = service-only (no models/views/urls, has `services/llm_client.py`);
  frontend inventory (61 page/layout files, 9 services, 34 hooks, component dir counts).
- `wc -l` (2026-07-02): `classes/views.py` 5199 · `commons/views.py` 1829 · `organizations/views.py` 1042.
- NOT verified here: runtime behavior of live LLM calls (Avalai VPN-blocked locally) — code-path claims
  only; per-module details deferred to their own steps (B0–I2).
