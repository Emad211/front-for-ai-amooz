# CLAUDE.md

Guidance for AI agents (Claude Code / Cowork) working in this repository. Read this before editing code.

## ⛳ First step for EVERY task (standing order — do this before anything else)

Before starting **any** task in this repo — reading, editing, debugging, planning, answering a question — **FIRST read all three knowledge sources, in this order, every single time:**

1. **Memory** — the auto-memory index `MEMORY.md` (loaded each session) **and** open the linked memory files relevant to the task. Memory records the current `main` state, past decisions, gotchas, and operational facts that are **not** derivable from the code.
2. **This file (`CLAUDE.md`)** — project conventions, architecture, and the **Gotchas** list.
3. **The knowledge graph — `graphify-out/GRAPH_REPORT.md`** — the architecture map (communities, god nodes, dependency cycles, knowledge gaps). When you need to locate code or trace a relationship, query `graphify-out/graph.json` with `/graphify query "<question>"`. **The graph is NOT auto-loaded — you must open it yourself.** If `graphify-out/` is missing or stale, rebuild it with `/graphify backend/apps frontend/src` (code-only AST extraction — ~free, 0 host tokens, no Whisper).

Only **after** all three have been read do you begin the actual work. This is a hard rule, not a suggestion. (Built/maintained so every task is grounded in the real architecture + prior decisions instead of starting cold.)

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
├── AvalAI-Developer-Documentation.md  # Avalai LLM gateway API docs (read before touching LLM calls)
├── Hamravesh-Docs-Summary.md   # Hosting platform (Hamravesh/Darkube) docs digest
└── MEDIANA DOCUMENT.json       # Mediana SMS provider API reference
```

`frontend/` and `backend/` are independent apps with their own dependencies, Dockerfiles, and `.env` files. There is no root `package.json` (it is git-ignored on purpose).

## Tech stack

**Frontend:** Next.js 15.5 (App Router, `output: standalone`), React 19, TypeScript (strict), Tailwind CSS 3 (HSL CSS-variable tokens), shadcn/ui + Radix primitives, lucide icons, react-hook-form + zod, framer-motion, recharts, sonner, next-themes, KaTeX, Vazirmatn font. (Genkit deps and the `genkit:*` npm scripts are leftovers — `src/ai/` no longer exists, so those scripts are dead; all real AI work lives in the backend.)

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

- **accounts** — custom user model (`AUTH_USER_MODEL = 'accounts.User'`) with platform roles `ADMIN` / `TEACHER` / `STUDENT` / `MANAGER` (org manager — granted on redeeming an org admin/deputy invite, or assigned from the admin panel); `/api/accounts/`
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

Both pipelines are **cancellable**: owner-only `POST …/<id>/cancel/` endpoints (class + exam-prep) set `cancel_requested` and hard-revoke the persisted `celery_task_id`; the full-pipeline tasks also check cooperative cancellation checkpoints between steps, ending the session in the terminal `CANCELLED` status. Preserve those checkpoints when reordering steps.

Pure logic lives in `apps/classes/services/` (keep it out of views/tasks): `pdf_extraction.py`, `structure.py`, `transcription.py`, `prerequisites.py`, `recap.py`, `quizzes.py`, `adaptive_quiz.py` (weak-point extraction — see below), `pdf_export.py` (WeasyPrint), `media_compressor.py` (ffmpeg), `mediana_sms.py`. `views.py` is very large — search before editing.

**LLM → JSON handling (new convention):** the canonical robust extractor is `apps/commons/json_utils.py` (`extract_json_object`); `apps/classes/services/json_utils.py` just re-exports it. For any NEW pipeline JSON, prefer `apps/commons/structured_llm.py` — `generate_structured(schema=PydanticModel, ...)` (JSON-mode + Pydantic validation + one repair round-trip, **raises** instead of returning `{}`) or `validate_keep_dict(text, schema)` when you must preserve the model's exact dict (e.g. `structure.py`). Pydantic schemas live in `apps/classes/services/schemas.py`. Don't reintroduce raw `extract_json_object` + silent-`{}`.

**Prompt repository (`apps/commons/llm_prompts/prompts.py`):** ONE `PROMPTS` dict is the single source of all LLM prompts (only `PROMPTS` is exported). A key is a "feature"; its value is a string or a `{"strategy": str}` sub-dict; callers look prompts up by these **exact** literal keys. Templates are rendered with safe **`str.replace`**, never `str.format` — so literal JSON braces `{ }` are fine, but the documented placeholder tokens (`{user_message}`, `{count}`, `STRUCTURED_BLOCKS_JSON`, the literal `{{blank}}`, …) and the **output-JSON keys** shown in each prompt are a hard contract with the parsers/Pydantic models/frontend widgets — keep them byte-for-byte. Shared blocks `SAFETY_PREAMBLE` (injection/leak/accuracy guards), `AUDIENCE_ADAPTIVE` (no hardcoded "K-12" — the platform serves any level), `MCQ_QUALITY` (distractor/Bloom rubric), and `MATH_FORMAT_INSTRUCTIONS` are concatenated in; edit them in one place. Dead prompts were audited out 2026-06-07 — **don't re-add unreferenced prompts**. `backend/apps/classes/test_prompts_contract.py` is the zero-token guard over the live-key list + every placeholder/output-key; run it after any prompt edit. The `generate_structured` migration for recap/prereqs/quizzes/exam_prep_structure is a documented, still-pending follow-up (deferred because the live pipeline is VPN-untestable).

### Adaptive weak-point quiz/exam loop (student-facing)

Chapter quizzes **and** the course-wide final exam form an adaptive remediation loop: a student who **fails** is shown the correct answer to *every* question, then can request a **new** assessment regenerated to target exactly the concepts they missed — repeating until they pass. Key pieces:

- **`services/adaptive_quiz.py`** — `compute_weak_points_from(questions_obj, attempts)` (pure, zero-token) joins the missed question ids from an attempt's `result['per_question']` with the question bank to produce a sorted weak-point list. It handles **both** grading shapes: section quizzes (`score_0_100`, threshold 70) and the final exam (`score_points`/`max_points`). `compute_weak_points(quiz)` is the `ClassSectionQuiz` wrapper.
- **Adaptive generation** lives in `quizzes.py`: `generate_adaptive_section_quiz(...)` and `generate_adaptive_final_exam(...)`, driven by the `section_quiz."adaptive"` and `final_exam_pool."adaptive"` prompt strategies. These strategies share the **exact same output contract** as their `"default"` siblings (the contract test enforces `LIVE_KEYS` = `[default, adaptive]` for both) — frontend widgets and parsers are unchanged.
- **Regenerate endpoints** (`views.py` / `urls.py`): `POST …/chapters/<cid>/quiz/regenerate/` and `POST …/final-exam/regenerate/`. Guard: only allowed when `last_passed is False` (else 409; no assessment yet → 400). They overwrite the stored `questions`/`exam` JSON and **reset `last_passed`/`last_score` to `None`** — that reset is the deliberate rate-limiter (you must take and fail the fresh assessment before regenerating again → a natural forever-loop, not a spam button).
- **Answer reveal on submit:** the chapter-quiz and final-exam **POST** responses now include `correct_answer` (final exam also `explanation`) in `per_question`. This is intentional (the failed assessment is about to be replaced) — but **GET before answering still hides them**. Don't "tidy up" by dropping those keys.
- **Pre-generation:** `tasks.pregenerate_student_assessments(session_id, student_id)` builds every section quiz + the final exam up front, dispatched once from `StudentCourseContentView.get` on a student's first entry (guarded by a `cache.add` flag + a no-quiz-exists check), idempotent and best-effort. On-demand generation remains the fallback, so a missing/down worker just means the student waits once.
- **No migration** — the whole loop reuses the existing `ClassSectionQuiz.questions` / `ClassFinalExam.exam` JSON fields. Deploy = image rebuild only.

### LLM providers
`LLM_PROVIDER = gemini | avalai | auto` (env; legacy alias **`MODE`**, which is what prod actually sets — `MODE=avalai`). Gemini via `google-genai`; **Avalai** (`https://api.avalai.ir`, Iranian gateway) via the OpenAI client. `AVALAI_BASE_URL` **must** include `/v1` — `llm_client._normalize_base_url` auto-appends it if missing. Models are env-driven (`MODEL_NAME`, `TRANSCRIPTION_MODEL`, `IMAGE_MODEL`, `EMBEDDING_MODEL_NAME`, …). Never hardcode model names or keys.

**Avalai API reference: [`AvalAI-Developer-Documentation.md`](AvalAI-Developer-Documentation.md)** (repo root) — the gateway's full developer docs (endpoints, models, multimodal shapes, limits/errors). Consult it before touching any LLM call. Key rule: multimodal MUST use the **standard** OpenAI shapes — `content:[{type:'image_url',image_url:{url:'data:…'}}]` for images, `{type:'input_audio',input_audio:{data,format}}` for audio (or the dedicated `POST /v1/audio/transcriptions`). The legacy `attachments/input_media/data_base64` shape is **silently ignored** by the gateway (that historical bug caused hallucinated/empty transcripts; large payloads over a flaky link also surfaced as `SSL: UNEXPECTED_EOF_WHILE_READING`). **Fixed:** `transcription.py` now extracts audio (mp3 → `input_audio`) + sampled frames (jpeg → `image_url`, governed by the `FRAME_*` env knobs) via `transcription_media.py` and sends the standard shape. Build any new multimodal call the same way.

**Long media is transcribed chunk-by-chunk** (`transcription.py`): media longer than ~1.5× `TRANSCRIPTION_CHUNK_SECONDS` (default 600 s) is split into sequential mono-mp3 segments (one ffmpeg `-f segment` pass); each segment is ONE small LLM request carrying the frames of its own time window (`TRANSCRIPTION_FRAMES_PER_CHUNK`) and the tail of the transcript so far (prompt `transcribe_media.chunked`). This is what makes 500 MB / multi-hour lectures survive the gateway (the old single request hit body limits and silent output-token truncation). A `progress_cb` heartbeat between chunks bumps `updated_at` (so `cleanup_stale_sessions` never reaps a live run) and aborts on `cancel_requested` (`TranscriptionAborted` → CANCELLED, never retried). Duration cap: `TRANSCRIPTION_MAX_DURATION_SECONDS` (default 4 h). Don't collapse this back into a single request, and keep `transcribe_media_bytes` (chat audio path) single-shot.

### Storage
S3-compatible via django-storages. Active only when `AWS_STORAGE_BUCKET_NAME` is set (MinIO locally, object storage in prod). When no public custom domain is configured, media is served through a Django proxy (`/media/<path>`); otherwise from the bucket.

### Auth & API conventions
SimpleJWT (short-lived access + refresh). DRF with serializers for validation, permissions for access control (deny-by-default), class-based views/viewsets. drf-spectacular drives the schema. Throttling is enabled in app but auto-disabled in tests via `backend/conftest.py` (clears `DEFAULT_THROTTLE_CLASSES`/`RATES` and the throttle cache).

## Frontend architecture

App Router with route groups under `frontend/src/app/`:
`(marketing)` landing · `(auth)` login/signup/join-code · `(dashboard)` student area (home, classes, learn, exam, exam-prep, calendar, profile, notifications, tickets) · `(teacher)` · `(admin)` — plus top-level `start/` (teacher-vs-student role picker) and `join/` (organization invite-code redemption).

- **`src/services/*.ts`** — the API layer; every backend call goes through a service (`auth-service`, `classes-service`, `admin-service`, etc.). Don't `fetch` ad hoc from components.
- **`src/components/ui/`** — shadcn primitives. Aliases (`components.json`): `@/components`, `@/lib`, `@/lib/utils`, `@/components/ui`, `@/hooks`. Path alias `@/* → src/*`.
- **`src/lib/`** — utilities incl. RTL/Persian helpers (`normalize-math-text`, `persian-option-label`, `date-utils`), `validations/` (zod schemas).
- RTL is global (root `layout.tsx`); keep new UI direction-aware and math rendered with KaTeX.

## Conventions

Follow `.github/instructions/develop.instructions.md` (the team's standing rules). In short: explore and search before changing; small, tested increments; `camelCase` for variables/functions/hooks and `PascalCase` for types/components; avoid `any`; modular apps with clear boundaries, no cross-app coupling; secrets only via `.env`. Every bugfix adds a regression test first; auth/permission code needs negative (unauthorized/forbidden) tests.

## Agent team (`.claude/agents/`) & documentation law

The repo ships a permanent **16-member agentic product team** (project subagents) — roster, consultation
loop, and usage rules in **`.claude/agents/README.md`** (the team manual). Operating rules for any AI
session working here:

- **Explicit invocation only:** launch team agents only when the user asks (directly, or via the
  `/council <topic>` and `/feature-cycle <feature>` commands in `.claude/commands/`). Default mode: work
  solo and read the agent files as zero-cost expert checklists — each encodes that specialty's hard-won
  rules for THIS repo (migration DML/DDL split, prompt contract, RTL rules, deploy map, …).
- **Mandatory consult matrix** (in the README): auth/permission changes → `security-auditor`; schema →
  `database-engineer`; anything LLM → `ai-engineer` + contract test; non-trivial diffs → `code-reviewer`;
  pushes → `release-manager` gate.
- **Standard handoff:** every agent report ends with `Decisions / Files / Docs / Risks / Consult next`.
- **Documentation law: code and its docs land together.** Docs home is **`docs/`** — `adr/` (numbered,
  immutable decisions), `features/` (one living spec per feature), `releases/` (note per deploy),
  `runbooks/` (ops lessons, e.g. `runbooks/local-stack.md`). Policy: `docs/README.md`. A change without
  its doc update is not done. When an agent learns a new failure mode, it is added to that agent's file.

## Testing notes

- pytest + pytest-django + DRF `APIClient` + model-bakery; `--reuse-db` for speed.
- Markers: `unit`; `benchmark` = accuracy tests that need real LLM keys and are **skipped by default** (opt in explicitly).
- Tests live next to code as `test_*.py` inside each app (e.g. `apps/classes/test_*`).
- Frontend has no unit runner wired up yet — Vitest/Playwright are planned per the instructions file; for now `tsc --noEmit` is the gate.

## Production deployment (Hamravesh / Darkube)

Prod runs on **Hamravesh** — its managed-Kubernetes PaaS is branded **Darkube**, so the `*.darkube.ir` / `*.darkube.app` domains and the `registry.hamdocker.ir` image registry are all Hamravesh. Cluster namespace `ai-products-ai-amooz`; services talk over internal DNS `*.ai-products-ai-amooz.svc`; each has a random `*.hsvc.ir` external ingress.

- **Services:** `ai-amooz-backend` (gunicorn `core.wsgi`, port 8000) · `aiamooz-celery-worker` (`celery -A core worker -Q default,pipeline`) · `aiamooz` (redis) · `minio` · `front` (Next standalone, port 3000). Backend + worker share **one image** (`registry.hamdocker.ir/ai-products/ai-amooz-backend`) and one env set.
- **Frontend → backend:** the `front` service sets `NEXT_PUBLIC_API_URL` = `BACKEND_URL` = `https://aiamoooz.darkube.ir`. (Note: that single var is BOTH the browser fetch-base for several services AND the `next.config.ts` rewrite target — keep it pointed at the real backend.)
- **Secrets + the full env-var dump live ONLY in the local memory file `production-deployment.md`** (outside this repo). Never paste prod secrets into any tracked file — `.env` is git-ignored; only `*.env.example` are committed.
- **Prod domains = SPLIT setup (resolved 2026-06-16, NOT a typo):** the **backend/API is `aiamoooz.darkube.ir` (3 o's)** (`NEXT_PUBLIC_API_URL`/`BACKEND_URL`/`ALLOWED_HOSTS` + user-confirmed), while the **user-facing frontend is `aiamooz.darkube.ir`/`.app` (2 o's)** (which is why `CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS` correctly list the 2-o origin). The two o-counts are intentional — **do NOT "fix" CORS to 3 o's; it would break the real frontend.** Only genuine items: ensure `CORS_ALLOWED_ORIGINS` lists every real frontend origin actually used (else cross-origin browser-direct DATA calls are blocked under `DEBUG=False`; auth uses the same-origin /api proxy so login is unaffected); MinIO uses default `minioadmin/minioadmin`. Never auto-change a domain spelling — confirm with the user.

## Gotchas

- **Frontend dev port is 9002**, not 3000 (the README's "3000" is the production `npm start` port). The README is stale in general (old env-var examples, old ports) — when it disagrees with this file, trust this file.
- **Local dev requires `frontend/.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000`.** Five services (`teacher`/`admin`/`classes`/`dashboard`/`organization`) build absolute URLs from this var and **throw `NEXT_PUBLIC_API_URL تنظیم نشده است`** if it's unset (only `auth`/`user` fall back to the relative `/api` proxy). Don't set it to the frontend's own origin (`:9002`) — `next.config.ts` uses the same var as its rewrite target, so that makes the `/api` proxy loop into itself and 500. Use the bare backend origin: services tolerate a trailing `/api` (they normalize), but the rewrite target does not.
- **Don't "simplify" the `/api` rewrite or remove `skipTrailingSlashRedirect` in `next.config.ts`.** Django URLs end in `/` and `APPEND_SLASH` cannot redirect a POST body (it 500s). Next's default trailing-slash 308 and the `:path*` rewrite token both strip the trailing slash, so the config deliberately uses `skipTrailingSlashRedirect: true` + a `:path(.*)` capture so `/api/foo/` reaches Django verbatim. Reverting either breaks every proxied POST/PUT/PATCH/DELETE.
- `next.config.ts` sets `typescript.ignoreBuildErrors: true` and `eslint.ignoreDuringBuilds: true`, so **`next build` will not catch type/lint errors** — always run `npm run typecheck` and `npm run lint` yourself.
- The Django project package is **`core`**, not `config` — `WSGI_APPLICATION = 'core.wsgi.application'`, so use `core.wsgi` / `celery -A core`. There are two backend Dockerfiles, both now correctly targeting `core.wsgi`: the **root `Dockerfile`** (production — copies `backend/`, runs `migrate` + `collectstatic` + env-tunable gunicorn) and the simpler **`backend/Dockerfile`**. (Historically `backend/Dockerfile` pointed at the nonexistent `config.wsgi:application` — that bug is now fixed; flag any reappearance.)
- Celery long-task limits are large (hard 2h / soft 100min) and `prefetch=1` — the pipeline is meant for slow LLM/media work; don't put quick tasks on the `pipeline` queue.
- `.env` files are git-ignored; only `*.env.example` are committed. Never commit real keys (Gemini, Avalai, Mediana, AWS/MinIO).
- **Mediana** = the SMS provider (`apps/classes/services/mediana_sms.py`, `MEDIANA_API_KEY`); `MEDIANA DOCUMENT.json` is its API reference.
- Production host is **Hamravesh/Darkube** (`aiamoooz.darkube.ir` / `.app`) — see the **Production deployment** section above and `backend/DEPLOY_CHECKLIST.md`, `docker-compose.prod.yml`, `k8s/`, `Hamravesh-Docs-Summary.md`.

## Reducing token usage

This codebase is large (`backend/apps/classes/views.py` alone is ~195 KB). Prefer targeted `grep`/symbol search over reading whole files, lean on `src/services/*` and `apps/classes/services/*` as entry points, and consider a code-context connector (Sourcegraph) or a knowledge-graph memory server (Graphiti) rather than loading broad context.
