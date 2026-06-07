# CLAUDE.md

Guidance for AI agents (Claude Code / Cowork) working in this repository. Read this before editing code.

## Project

**AI-Amooz** (`پلتفرم آموزشی هوشمند`) — an AI-powered educational platform. Teachers upload class material (audio/video lectures and PDFs); an LLM pipeline transcribes, structures, and enriches it into chapters, prerequisites, recaps, quizzes, and exam prep; students learn through a personalized, RTL Persian UI with a course-aware chatbot.

The UI is **Persian / right-to-left** (`lang="fa" dir="rtl"`, Vazirmatn font, KaTeX for math). Product-facing copy is Persian; code, comments, and docstrings are **English**.

## Monorepo layout

```
front-for-ai-amooz/
├── frontend/            # Next.js 15 (App Router) + React 19 + TypeScript
├── backend/             # Django 5 + DRF + Celery
├── Dockerfile                  # Production backend image (copies backend/, runs migrate+collectstatic+gunicorn)
├── docker-compose.yml          # Local full stack (postgres, redis, minio, backend, celery)
├── docker-compose.prod.yml     # Production compose
├── scripts/                    # dev-up.ps1 / dev-down.ps1 — one-shot Windows/PowerShell stack control
├── pytest.ini                  # Root pytest config (pythonpath=backend, testpaths=backend)
├── k8s/ , nginx/               # Deployment manifests + reverse proxy
├── tests/ , test_api_live.ps1  # Cross-service / live API smoke tests
└── MEDIANA DOCUMENT.json       # Mediana SMS provider API reference
```

`frontend/` and `backend/` are independent apps with their own dependencies, Dockerfiles, and `.env` files. There is no root `package.json` (it is git-ignored on purpose).

## Tech stack

**Frontend:** Next.js 15.5 (App Router, `output: standalone`), React 19, TypeScript (strict), Tailwind CSS 3 (HSL CSS-variable tokens), shadcn/ui + Radix primitives, lucide icons, react-hook-form + zod, framer-motion, recharts, sonner, next-themes, KaTeX, Vazirmatn font. (Genkit deps are present but `src/ai/` is currently empty — all real AI work lives in the backend.)

**Backend:** Django 5 + Django REST Framework, SimpleJWT auth, drf-spectacular (OpenAPI), Celery 5 + Redis (broker/result + cache), PostgreSQL (psycopg2), django-storages + boto3 for S3-compatible storage (MinIO locally), WhiteNoise, Gunicorn. LLM via `google-genai` (Gemini) and the `openai` client pointed at Avalai. PDF: pdfplumber / pypdf / pypdfium2 (ingest) and WeasyPrint (export). Media: ffmpeg.

## Commands

### Local stack via Docker (recommended)
```bash
docker-compose up -d            # postgres:5432, redis:6379, minio:9000/9001,
                                # backend:8000, celery-worker (queues: default,pipeline)
docker-compose down
```
The `minio-init` service auto-creates the `ai-amooz-media` bucket. Backend env is read from `backend/.env`; compose overrides hostnames to the service names.

On Windows, `scripts/dev-up.ps1` wraps the above end-to-end: it builds images, brings up postgres/redis/minio, waits for Postgres health, runs migrations (+ `createcachetable`), starts backend + celery, then launches the frontend dev server. Flags: `-NoFrontend` (backend only), `-Superuser` (create a Django superuser). `scripts/dev-down.ps1` tears the stack back down.
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1
```

### Backend (run manually)
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate     # venv lives at backend/.venv
pip install -r requirements.txt
python manage.py migrate
python manage.py createcachetable
python manage.py runserver 8000
# Celery worker (separate terminal):
celery -A core worker -Q default,pipeline --loglevel=info --concurrency=2
```

### Frontend (run manually)
```bash
cd frontend
npm install
npm run dev          # ⚠️ dev server runs on http://localhost:9002 (not 3000)
npm run build        # next build (standalone)
npm start            # production server on port 3000
npm run lint         # next lint (eslint)
npm run typecheck    # tsc --noEmit
```

### Tests
```bash
# Backend — runnable from the repo ROOT (root pytest.ini sets pythonpath=backend,
# testpaths=backend) or from backend/ (backend/pytest.ini). Both use core.settings + --reuse-db.
python -m pytest                 # all backend tests
python -m pytest backend/apps/classes/test_pdf_pipeline.py -k step2   # from root
python -m pytest apps/classes/ -m unit                               # from backend/
# Frontend type safety:
cd frontend && npx tsc --noEmit
```

## Key URLs (dev)

- Frontend dev: `http://localhost:9002`  · Backend API: `http://localhost:8000/api/`
- Admin: `/admin/`  · Health: `/api/health/`
- API docs: `/api/schema/`, Swagger `/api/docs/`, ReDoc `/api/redoc/`
- Auth: `POST /api/token/`, `POST /api/token/refresh/`
- MinIO console: `http://localhost:9001` (minioadmin / minioadmin)

The frontend calls same-origin `/api/*`, which Next rewrites to `${NEXT_PUBLIC_API_URL || BACKEND_URL || http://localhost:8000}/api/*` (see `frontend/next.config.ts`).

## Backend architecture

Project package: `backend/core/` — `settings.py`, `urls.py`, `celery.py`, `middleware.py`, `storage_backends.py`, `exception_handlers.py`.

Django apps under `backend/apps/` (all routed in `core/urls.py`):

- **accounts** — custom user model (`AUTH_USER_MODEL = 'accounts.User'`); `/api/accounts/`
- **authentication** — JWT login by identifier, OpenAPI serializers; `/api/auth/`
- **classes** — **the core domain**: courses/chapters, the AI processing pipeline, student chat, quizzes, exam prep, PDF export; `/api/classes/`
- **organizations** — multi-tenant orgs; `/api/organizations/`
- **commons** — admin-facing endpoints; `/api/admin/`
- **notification** — `/api/notifications/`
- **chatbot**, **material**, **core** — supporting apps

### The `classes` pipeline (most important subsystem)

Long-running LLM work runs as Celery tasks on the dedicated **`pipeline`** queue (`apps/classes/tasks.py`), orchestrated step by step:

1. `process_class_step1_transcription` — speech-to-text of lecture media
2. `process_class_step2_structure` — extract chapter/section structure
3. `process_class_step3_prerequisites`
4. `process_class_step4_prereq_teaching`
5. `process_class_step5_recap`

`process_class_full_pipeline` chains them; an analogous `process_exam_prep_*` set handles exam prep. SMS notifications and `cleanup_stale_sessions` (a Celery-beat job) run on the **`default`** queue.

Pure logic lives in `apps/classes/services/` (keep it out of views/tasks): `pdf_extraction.py`, `structure.py`, `transcription.py`, `prerequisites.py`, `recap.py`, `quizzes.py`, `pdf_export.py` (WeasyPrint), `media_compressor.py` (ffmpeg), `json_utils.py` (robust LLM-JSON parsing), `mediana_sms.py`. `views.py` is very large — search before editing.

### LLM providers
`LLM_PROVIDER = gemini | avalai | auto` (env). Gemini via `google-genai`; **Avalai** (`https://api.avalai.ir`, Iranian gateway) via the OpenAI client. Models are env-driven (`MODEL_NAME`, `TRANSCRIPTION_MODEL`, `IMAGE_MODEL`, `EMBEDDING_MODEL_NAME`, …). Never hardcode model names or keys.

### Storage
S3-compatible via django-storages. Active only when `AWS_STORAGE_BUCKET_NAME` is set (MinIO locally, object storage in prod). When no public custom domain is configured, media is served through a Django proxy (`/media/<path>`); otherwise from the bucket.

### Auth & API conventions
SimpleJWT (short-lived access + refresh). DRF with serializers for validation, permissions for access control (deny-by-default), class-based views/viewsets. drf-spectacular drives the schema. Throttling is enabled in app but auto-disabled in tests via `backend/conftest.py` (clears `DEFAULT_THROTTLE_CLASSES`/`RATES` and the throttle cache).

## Frontend architecture

App Router with route groups under `frontend/src/app/`:
`(marketing)` landing · `(auth)` login/signup/join-code · `(dashboard)` student area (home, classes, learn, exam, exam-prep, calendar, profile, notifications, tickets) · `(teacher)` · `(admin)`.

- **`src/services/*.ts`** — the API layer; every backend call goes through a service (`auth-service`, `classes-service`, `admin-service`, etc.). Don't `fetch` ad hoc from components.
- **`src/components/ui/`** — shadcn primitives. Aliases (`components.json`): `@/components`, `@/lib`, `@/lib/utils`, `@/components/ui`, `@/hooks`. Path alias `@/* → src/*`.
- **`src/lib/`** — utilities incl. RTL/Persian helpers (`normalize-math-text`, `persian-option-label`, `date-utils`), `validations/` (zod schemas).
- RTL is global (root `layout.tsx`); keep new UI direction-aware and math rendered with KaTeX.

## Conventions

Follow `.github/instructions/develop.instructions.md` (the team's standing rules). In short: explore and search before changing; small, tested increments; `camelCase` for variables/functions/hooks and `PascalCase` for types/components; avoid `any`; modular apps with clear boundaries, no cross-app coupling; secrets only via `.env`. Every bugfix adds a regression test first; auth/permission code needs negative (unauthorized/forbidden) tests.

## Testing notes

- pytest + pytest-django + DRF `APIClient` + model-bakery; `--reuse-db` for speed.
- Markers: `unit`; `benchmark` = accuracy tests that need real LLM keys and are **skipped by default** (opt in explicitly).
- Tests live next to code as `test_*.py` inside each app (e.g. `apps/classes/test_*`).
- Frontend has no unit runner wired up yet — Vitest/Playwright are planned per the instructions file; for now `tsc --noEmit` is the gate.

## Gotchas

- **Frontend dev port is 9002**, not 3000 (the README's "3000" is the production `npm start` port).
- `next.config.ts` sets `typescript.ignoreBuildErrors: true` and `eslint.ignoreDuringBuilds: true`, so **`next build` will not catch type/lint errors** — always run `npm run typecheck` and `npm run lint` yourself.
- The Django project package is **`core`**, not `config` — `WSGI_APPLICATION = 'core.wsgi.application'`, so use `core.wsgi` / `celery -A core`. There are two backend Dockerfiles, both now correctly targeting `core.wsgi`: the **root `Dockerfile`** (production — copies `backend/`, runs `migrate` + `collectstatic` + env-tunable gunicorn) and the simpler **`backend/Dockerfile`**. (Historically `backend/Dockerfile` pointed at the nonexistent `config.wsgi:application` — that bug is now fixed; flag any reappearance.)
- Celery long-task limits are large (hard 2h / soft 100min) and `prefetch=1` — the pipeline is meant for slow LLM/media work; don't put quick tasks on the `pipeline` queue.
- `.env` files are git-ignored; only `*.env.example` are committed. Never commit real keys (Gemini, Avalai, Mediana, AWS/MinIO).
- **Mediana** = the SMS provider (`apps/classes/services/mediana_sms.py`, `MEDIANA_API_KEY`); `MEDIANA DOCUMENT.json` is its API reference.
- Production host is Darkube (`aiamoooz.darkube.ir` / `.app`); see `backend/DEPLOY_CHECKLIST.md`, `docker-compose.prod.yml`, and `k8s/`.

## Reducing token usage

This codebase is large (`backend/apps/classes/views.py` alone is ~195 KB). Prefer targeted `grep`/symbol search over reading whole files, lean on `src/services/*` and `apps/classes/services/*` as entry points, and consider a code-context connector (Sourcegraph) or a knowledge-graph memory server (Graphiti) rather than loading broad context.
