# Runbook — Local Docker stack (Windows / WSL2)

- **Status:** Living · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 · **Owner:** devops-engineer

## Normal operation
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1     # full stack (flags: -NoFrontend, -Superuser)
docker compose up -d                                            # containers only
scripts\dev-down.ps1                                            # teardown
```
Services: postgres:5432 · redis:6379 · minio:9000 (console :9001, minioadmin/minioadmin) · backend:8000 ·
celery-worker (`-Q default,pipeline`) · front:3000. Frontend **dev** server runs separately: `cd frontend
&& npm run dev` → **http://localhost:9002**. Health: `http://localhost:8000/api/health/`.
Requires `frontend/.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000`.

## Failure catalog (symptom → root cause → fix → prevention)

### 1. All container egress hangs (LLM calls, exchange-rate, `npm install` in builds)
- **Root cause:** Docker Desktop injects the Windows WinINET proxy (`ProxyServer` registry value —
  a stale `127.0.0.1:10808` xray/VPN leftover, even with ProxyEnable=0) into every container as
  `HTTP_PROXY=http://<host-ip>:10808`. The proxy is dead → every outbound call times out.
- **Fix:** `docker-compose.override.yml` (repo root, **untracked, machine-local**) sets empty
  `HTTP_PROXY/HTTPS_PROXY` + `NO_PROXY="*"` for backend/celery-worker/front. For builds:
  `docker build --network=host --build-arg HTTP_PROXY= --build-arg HTTPS_PROXY= …`.
- **Prevention:** true root fixed by clearing the WinINET `ProxyServer` registry value; takes effect after
  a full Docker Desktop restart. Keep the override file as belt-and-suspenders; do not commit it.

### 2. Front container: `connect ECONNREFUSED 127.0.0.1:8000` on `/api/*`
- **Root cause:** the Next server-side `/api` rewrite ran against `localhost` — which inside the front
  container is the container itself.
- **Fix (shipped `fdb38b6`):** `next.config.ts` prefers `BACKEND_URL`; compose sets
  `BACKEND_URL: http://backend:8000` (service-name DNS). `NEXT_PUBLIC_API_URL` stays `http://localhost:8000`
  for the browser.
- **Prevention:** inside containers always address services by compose service name, never localhost.

### 3. Stale frontend behavior after changing an env value
- **Root cause:** `NEXT_PUBLIC_*` and the rewrite target are **baked into the front image at build time**.
- **Fix:** rebuild the front image (`docker compose build front && docker compose up -d front`).

### 4. Build/container killed with exit code 137
- **Root cause:** WSL2 VM out of memory (ffmpeg / npm / pip peaks).
- **Fix:** `%USERPROFILE%\.wslconfig` → `[wsl2] memory=12GB, processors=6, swap=4GB`, then
  `wsl --shutdown` + restart Docker Desktop. (GUI has no slider on WSL2 backend.)

### 5. Docker Desktop won't start: `initializing Inference manager … dockerInference: file cannot be accessed`
- **Root cause:** Docker Desktop was force-killed (`Stop-Process`), leaving stale AF_UNIX socket files in
  `%LOCALAPPDATA%\Docker\run` that Windows can't delete normally.
- **Fix:** rename `%LOCALAPPDATA%\Docker\run` → `run_broken_<ts>`, create a fresh empty `run`, relaunch.
- **Prevention:** NEVER force-kill Docker Desktop — use `docker desktop stop` / `docker desktop start`.

### 6. Migration crash: `cannot CREATE INDEX … because it has pending trigger events`
- **Root cause:** one migration mixed cascade row deletes (DML) with `AddConstraint` (DDL) in a single
  transaction (Postgres limitation).
- **Fix/prevention (shipped `74d05dc`):** split into separate migrations — data migration first
  (`accounts/0006`), constraint alone in its own migration (`accounts/0007`). This is a standing rule.

### 7. Manual API testing hits HTTP 429
- **Root cause:** scoped throttles are active outside pytest (tests auto-disable them via `backend/conftest.py`).
- **Fix:** wait, or raise the specific `THROTTLE_RATE_*` env for the local backend. Don't disable throttles in code.
