# Reference — `core/` project package (+ `apps/core`)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `28baf8c`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B0
- **Layer:** backend-app (project configuration + shared primitives)

## Purpose
`backend/core/` is the Django project package (the name is **`core`, not `config`** — `core.wsgi`,
`celery -A core`): settings, root routing, Celery bootstrap, middleware, storage backend, and the API
error contract. `backend/apps/core/` is the small shared-primitives app: health view, the
`IsPlatformAdmin` permission, and `SafeScopedRateThrottle`.

## Scope & paths
| File | Role |
|---|---|
| `backend/core/settings.py` (575) | Everything env-driven; sections below |
| `backend/core/urls.py` | Root routing table (see [00-architecture-overview.md](00-architecture-overview.md)) |
| `backend/core/celery.py` | Celery app + full task lifecycle logging (prerun/success/retry/failure/postrun + duration) |
| `backend/core/middleware.py` | `HealthCheckMiddleware`, `RequestLogMiddleware`, `LLMTrackingMiddleware` |
| `backend/core/exception_handlers.py` | `api_exception_handler` — the unified error envelope |
| `backend/core/storage_backends.py` | `ProxiedS3Storage` + `media_proxy_view` |
| `backend/apps/core/views.py` (71) | `HealthCheckView` (`/api/health/`, unauthenticated) |
| `backend/apps/core/permissions.py` | `IsPlatformAdmin` (role==ADMIN **or** is_superuser **or** is_staff) |
| `backend/apps/core/throttling.py` | `SafeScopedRateThrottle` (no-ops when its scope has no rate) |
| `backend/conftest.py` | autouse fixture: clears throttle classes/rates + throttle cache in every test |

## Public surface
- **`GET /api/health/`** — unauthenticated readiness probe; DB failure ⇒ 503, Redis failure ⇒ reported
  but still 200 in the middleware variant (`middleware.py:62-74`) / 503 in the view variant
  (`apps/core/views.py:57-69`). Note: **`HealthCheckMiddleware` is first in MIDDLEWARE and intercepts
  the path before `ALLOWED_HOSTS`** (K8s pod-IP probes; `settings.py:70-72`) — the DRF view is
  effectively shadowed at runtime.
- **`/media/<path>`** — `media_proxy_view` streams from S3/MinIO through Django; rejects `..`/absolute
  paths; `If-Modified-Since` + `Cache-Control: max-age=3600`; storage outage ⇒ JSON 503.
- **Exports:** `IsPlatformAdmin`, `SafeScopedRateThrottle` — the shared building blocks other apps import.

**Env knobs (core):** `DJANGO_SECRET_KEY` (refuses insecure default when `DEBUG=False`,
`settings.py:394-400`) · `DEBUG` (default True!) · `ALLOWED_HOSTS` · `DATABASE_URL` (postgres/sqlite
schemes, `settings.py:106-134`) · `CONN_MAX_AGE` 600 · `REDIS_URL` · `CELERY_TASK_TIME_LIMIT` 7200 /
`CELERY_TASK_SOFT_TIME_LIMIT` 6000 · `CELERY_WORKER_MAX_MEMORY_PER_CHILD` 1.5M KiB ·
`MAX_UPLOAD_MB` 500 · `TRANSCRIPTION_MAX_UPLOAD_MB` 500 · `PDF_*` family (`settings.py:427-445`) ·
`CLASS_PIPELINE_ASYNC` (True in prod, False under DEBUG — request-deterministic for tests,
`settings.py:449-452`) · `CORS_*`, `CSRF_TRUSTED_ORIGINS` · `AUTH_REFRESH_COOKIE*` (HttpOnly refresh
cookie, `settings.py:326-337`) · `ACCESS_TOKEN_LIFETIME_MINUTES` 60 / `REFRESH_TOKEN_LIFETIME_DAYS` 3 ·
`DRF_PAGE_SIZE` 50 · `LOG_LEVEL`/`LOG_HTTP`/`LOG_SQL` · storage: `AWS_STORAGE_BUCKET_NAME` (the S3
on/off switch) + `AWS_S3_ENDPOINT_URL`/`AWS_S3_CUSTOM_DOMAIN`/`AWS_QUERYSTRING_AUTH`.

## Key flows
1. **Request lifecycle:** `HealthCheckMiddleware` (bypass) → Security/WhiteNoise/Session/CORS/Common →
   `RequestLogMiddleware` (method/path/status/latency/ip/user_id; skips health) → CSRF → Auth →
   `LLMTrackingMiddleware` → view. `LLMTrackingMiddleware` (`middleware.py:129-176`) resolves the user
   (falling back to manual JWT decode) into thread-local storage so `token_tracker` can attribute LLM
   calls without explicit plumbing; always cleared in `finally`.
2. **Error contract** (`exception_handlers.py:35-65`): validation errors →
   `{"detail": "Validation error.", "errors": {field: [msgs]}}`; others keep `{"detail": ...}`;
   unhandled exceptions → JSON 500 (never HTML). Guard test: `apps/core/test_error_contract.py`.
3. **Storage switch** (`settings.py:174-243`): `AWS_STORAGE_BUCKET_NAME` set ⇒ `ProxiedS3Storage`
   (URLs become `/media/<key>` unless `AWS_S3_CUSTOM_DOMAIN` is public) + boto timeouts
   (connect 5s / read 300s / 2 retries, `settings.py:210-214`); unset ⇒ local FileSystemStorage.
   Startup logs state the active mode explicitly.
4. **Celery bootstrap** (`celery.py`): config from `CELERY_*` settings; autodiscovers `tasks.py`;
   signal handlers log start/success/retry/failure/done+duration for every task.

## Data & invariants
- `AUTH_USER_MODEL = 'accounts.User'` (`settings.py:68`).
- **Queue discipline** (`settings.py:486-525`): `CELERY_TASK_DEFAULT_QUEUE='default'` is load-bearing —
  without it, unrouted tasks go to the built-in `celery` queue **that no worker consumes** (worker runs
  `-Q default,pipeline`). All 9 pipeline tasks route to `pipeline`; SMS + `cleanup_stale_sessions`
  (beat, every 30 min) to `default`. `prefetch=1`; `CELERY_TASK_REJECT_ON_WORKER_LOST=True` (OOM requeue);
  worker child recycles above ~1.43 GiB RSS.
- **Throttling**: default anon 60/min + user 300/min; scoped rates — waitlist 10/h, login 10/min,
  invite_login 10/min, register 10/h, redeem 15/h, password_reset 15/h, onboarding 20/h
  (`settings.py:256-274`), all env-tunable; `SafeScopedRateThrottle` stays inert when a scope has no
  rate (test-safe by design). Tests disable ALL throttling via `backend/conftest.py` (autouse).
- **Global pagination IS enabled**: `PageNumberPagination`, `PAGE_SIZE=50` (`settings.py:276-277`).
- **`TIME_ZONE='UTC'`** (`settings.py:158`) — Django stores UTC; the Asia/Tehran rule applies to
  *analytics bucketing* in code (B9), not to this setting. Don't "fix" either side.
- ⚠️ **No `DEFAULT_PERMISSION_CLASSES` in `REST_FRAMEWORK`** (`settings.py:245-278`) — DRF's implicit
  default is AllowAny, so **deny-by-default is a per-view convention** (every view must set
  `permission_classes` explicitly), enforced by review + negative tests, not by config.
- JWT: rotation + blacklist on; `UPDATE_LAST_LOGIN=True` (obtain only, not refresh;
  `settings.py:309-324`); refresh token also mirrored into an HttpOnly `Lax` cookie scoped to `/api/`.
- Sessions live in the Redis cache (`SESSION_ENGINE=cache`, `settings.py:473-474`); default cache TTL 5 min.

## Gotchas
- `DEBUG` defaults to **True** — prod must explicitly set `DEBUG=False` (which arms HSTS, secure
  cookies, and the SECRET_KEY guard).
- Two health implementations exist (middleware + DRF view) with different Redis semantics — the
  middleware wins at runtime; if you change health behavior, change `core/middleware.py`.
- The known `test_health.py` pre-existing failure comes from asserting `.data` on the middleware's
  plain `HttpResponse` (see `.claude/agents/qa-engineer.md`).
- General repo gotchas: CLAUDE.md §Gotchas; local-stack failures: [runbook](../runbooks/local-stack.md).

## Cross-links
[00-architecture-overview.md](00-architecture-overview.md) (routing table) · B1 accounts (the user
model this config points at) · L1 (LLM env matrix) · B8 (celery ops detail) · I1 (deploy) ·
`.claude/agents/devops-engineer.md`, `backend-engineer.md`.

## Verified-by
- Full read of `core/settings.py` (575 lines), `core/middleware.py` (177), `core/exception_handlers.py`
  (66), `core/storage_backends.py` (119), `core/celery.py` (110), `apps/core/views.py` (71),
  `apps/core/permissions.py` (34), `apps/core/throttling.py` (26), `backend/conftest.py` (24) — 2026-07-02.
- Routing table: `rg "path\(" backend/core/urls.py` (see S1).
- Claims NOT verified live: K8s probe behavior, Redis-down 200-vs-503 in production, worker memory
  recycling — code-path reading only.
