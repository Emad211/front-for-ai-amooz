# Reference — Infra: Docker, compose, k8s, Hamravesh deploy

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `ced7336`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step I1
- **Layer:** infra

## Purpose
The deployment map: the local Docker stack, the two backend Dockerfiles, the prod compose/k8s, and the
Hamravesh/Darkube service topology + rebuild matrix. Points to the runbook for local failures; contains
NO secrets.

## Scope & paths
| File | Role |
|---|---|
| `docker-compose.yml` | local stack (postgres/redis/minio/backend/celery/front) |
| `docker-compose.override.yml` | **untracked, machine-local** proxy neutralizer (runbook) |
| `docker-compose.prod.yml` | production compose |
| `Dockerfile` (root) | prod backend image (migrate + collectstatic + gunicorn) |
| `backend/Dockerfile` | simpler backend image |
| `frontend/Dockerfile` | Next standalone image (bakes NEXT_PUBLIC_* + BACKEND_URL) |
| `k8s/` | ingress, cors/upload-limit middleware, minio + celery-worker deployments, README |
| `nginx/nginx.conf` | reverse proxy |
| `scripts/dev-up.ps1` / `dev-down.ps1` | one-shot Windows stack control |

**Out of scope:** local failure catalog → `runbooks/local-stack.md`; env-var semantics → B0; celery
queue config → B0/B8; secrets → the user's machine-local memory (never in-repo).

## Public surface — services
**Local** (`docker-compose.yml`): `postgres:16` (:5432, healthcheck), `redis:7` (:6379),
`minio` (pinned `RELEASE.2025-04-22` — later releases broke the console; :9000/:9001, minioadmin) +
`minio-init` (creates `ai-amooz-media`), `backend` (:8000), `celery-worker` (`-Q default,pipeline`),
`front` (:3000). Dev server runs separately on **9002**.

**Prod (Hamravesh/Darkube)** — managed k8s; namespace `ai-products-ai-amooz`; internal DNS
`*.ai-products-ai-amooz.svc`; registry `registry.hamdocker.ir`:
`ai-amooz-backend` (gunicorn `core.wsgi`, :8000) · `aiamooz-celery-worker` (same image + env) ·
`aiamooz` (redis) · `minio` · `front` (Next standalone :3000).

## Key flows
1. **Local up:** `powershell -File scripts\dev-up.ps1` (flags `-NoFrontend`, `-Superuser`) — builds
   images, waits Postgres health, runs migrate + createcachetable, starts backend+celery, launches the
   frontend dev server (9002). `dev-down.ps1` tears down.
2. **Backend image:** the root `Dockerfile` copies `backend/`, runs `migrate` + `collectstatic` +
   env-tunable gunicorn on start — **so deploying a backend image also applies migrations** (I2/B8/
   database-engineer). Package is **`core`** (`core.wsgi`, `celery -A core`), never `config`.
3. **Front image:** `NEXT_PUBLIC_*` + the `/api` rewrite target (`BACKEND_URL`) are **baked at build**
   (F1) — an env change ⇒ rebuild `front`.

## Data & invariants (rebuild matrix)
- **Backend + celery share ONE image** (`ai-amooz-backend`) → a backend change rebuilds it (worker gets
  it too). A frontend change OR any `NEXT_PUBLIC_*`/`BACKEND_URL` change ⇒ rebuild `front`.
- Migrations auto-run on backend image start — every migration is a production event (database-engineer).
- **Prod domain split is intentional:** backend `aiamoooz.darkube.ir/.app` (3 o's) vs frontend
  `aiamooz.darkube.ir/.app` (2 o's) — CORS lists the 2-o origin. **Never "fix" a spelling** (CLAUDE.md §Production).
- Containers reach each other by service name (`http://backend:8000` via `BACKEND_URL`), never localhost.
- `docker-compose.override.yml` is machine-local (untracked) — the proxy neutralizer; don't commit it.
- minio pinned to `RELEASE.2025-04-22` (console regression); default creds local only.

## Gotchas
- Two backend Dockerfiles (root prod + `backend/Dockerfile`) — both must target `core.wsgi`; a
  `config.wsgi` reappearance is a bug (CLAUDE.md §Gotchas).
- Deploy secrets/env live ONLY in the user's machine-local memory `production-deployment` — never in any
  tracked file; only `*.env.example` are committed.
- Local Docker failure modes (proxy hang, ECONNREFUSED, OOM, socket crash) → `runbooks/local-stack.md`.

## Cross-links
[backend-core.md](backend-core.md) (B0, env + queue config) · [backend-celery-ops.md](backend-celery-ops.md)
(B8, worker) · [frontend-app-shell.md](frontend-app-shell.md) (F1, baked env) · `infra-testing.md` (I2) ·
[runbooks/local-stack.md](../runbooks/local-stack.md) · CLAUDE.md §Production · `backend/DEPLOY_CHECKLIST.md`,
`Hamravesh-Docs-Summary.md` · `.claude/agents/devops-engineer.md`, `release-manager.md`.

## Verified-by
- Read (2026-07-02): `docker-compose.yml:1-50` (postgres/redis/minio services + the minio pin comment).
- `Glob {Dockerfile,docker-compose*.yml,k8s/**,nginx/**,scripts/*.ps1}` → the full infra file inventory
  tabulated above (root + backend + frontend Dockerfiles, prod compose, override, 6 k8s files, nginx, 2 scripts).
- Prod topology + domain split + rebuild matrix cross-referenced to CLAUDE.md §Production (not
  independently re-derived — no prod access; secrets in machine-local memory).
- NOT verified live: an actual Hamravesh deploy (no cluster access this pass).
