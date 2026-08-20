# CLAUDE.md

Guidance for AI agents (Claude Code / Cowork) in this repo. Read before editing.

## First step for every task (standing order)

Before any task — read, edit, debug, plan, answer — **first read all three knowledge sources, in order:**

1. **Memory** — the auto-memory index `MEMORY.md` (loaded each session) plus the linked files relevant to the task. Memory holds current `main` state, past decisions, and gotchas **not** derivable from code.
2. **This file** — conventions, architecture, Gotchas.
3. **Knowledge graph — `graphify-out/GRAPH_REPORT.md`** (architecture map: communities, god nodes, cycles). To locate code or trace a relationship, query `graphify-out/graph.json` with `/graphify query "<question>"`. The graph is **not** auto-loaded — open it yourself. If `graphify-out/` is missing or stale, rebuild: `/graphify backend/apps frontend/src` (code-only AST extraction, ~free, 0 host tokens).

Only after all three do you start. Hard rule.

## Project

**AI-Amooz** (`پلتفرم آموزشی هوشمند`) — AI-powered educational platform. Teachers upload lecture media (audio/video) and PDFs; an LLM pipeline transcribes, structures, and enriches them into chapters, prerequisites, recaps, quizzes, and **exam prep** (extracting questions from scanned exam-booklet PDFs); students learn through a personalized RTL Persian UI with a course-aware chatbot.

UI is **Persian / right-to-left** (`lang="fa" dir="rtl"`, Vazirmatn font, KaTeX for math). Product copy is Persian; **code, comments, docstrings are English.**

## Monorepo layout

```
front-for-ai-amooz/
├── frontend/            # Next.js 15 (App Router) + React 19 + TypeScript
├── backend/             # Django 5 + DRF + Celery
├── Dockerfile           # Production backend image (migrate + collectstatic + gunicorn)
├── docker-compose.yml / .prod.yml / .override.yml   # local + prod stacks
├── scripts/             # dev-up.ps1 / dev-down.ps1 — one-shot Windows stack control
├── pytest.ini           # root pytest (pythonpath=backend, testpaths=backend)
├── k8s/ , nginx/        # deploy manifests + reverse proxy
├── docs/                # adr/ features/ releases/ runbooks/ + EXAM_PREP_* findings
├── graphify-out/        # knowledge graph (see above)
├── AvalAI-Developer-Documentation.md   # Avalai LLM gateway docs — read before touching LLM calls
├── Hamravesh-Docs-Summary.md           # hosting (Hamravesh/Darkube)
└── MEDIANA DOCUMENT.json               # Mediana SMS provider API
```

`frontend/` and `backend/` are independent apps with own deps, Dockerfiles, `.env`. No root `package.json` (git-ignored on purpose).

## Tech stack

**Frontend:** Next.js 15.5 (App Router, `output: standalone`), React 19, TypeScript strict, Tailwind 3 (HSL CSS-variable tokens), shadcn/ui + Radix, lucide, react-hook-form + zod, framer-motion, recharts, sonner, next-themes, KaTeX, Vazirmatn. (Genkit deps + `genkit:*` scripts are **dead leftovers** — `src/ai/` no longer exists; all AI work is backend.)

**Backend:** Django 5 + DRF, SimpleJWT, drf-spectacular (OpenAPI), Celery 5 + Redis (broker/result/cache), PostgreSQL (psycopg2), django-storages + boto3 for S3 (MinIO locally), WhiteNoise, Gunicorn. LLM via `google-genai` (Gemini) and the `openai` client pointed at Avalai. PDF: pdfplumber / pypdf / pypdfium2 (ingest), WeasyPrint (export). Media: ffmpeg.

## Commands

### Local stack via Docker (recommended)
```bash
docker-compose up -d    # postgres:5432 redis:6379 minio:9000/9001 backend:8000 celery(default,pipeline)
docker-compose down
```
`minio-init` auto-creates the `ai-amooz-media` bucket. Backend env from `backend/.env`; compose overrides hostnames to service names.

Windows: `scripts/dev-up.ps1` does it end-to-end (build, up postgres/redis/minio, wait for PG health, migrate + `createcachetable`, start backend + celery, launch frontend). Flags: `-NoFrontend`, `-Superuser`. `dev-down.ps1` tears down.
```bash
powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1
```

### Backend (manual)
```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # venv at backend/.venv
pip install -r requirements.txt
python manage.py migrate
python manage.py createcachetable
python manage.py runserver 8000
celery -A core worker -Q default,pipeline --loglevel=info --concurrency=2   # separate terminal
```

### Frontend (manual)
```bash
cd frontend
npm install
npm run dev        # ⚠️ dev server on http://localhost:9002 (not 3000)
npm run build      # next build (standalone)
npm start          # production server on port 3000
npm run lint       # next lint
npm run typecheck  # tsc --noEmit
```

### Tests
```bash
python -m pytest                          # all backend (root pytest.ini: pythonpath=backend, --reuse-db)
python -m pytest backend/apps/classes/test_exam_prep_pipeline.py    # from root
python -m pytest apps/classes/ -m unit                              # from backend/
cd frontend && npx tsc --noEmit           # frontend type safety
```
pytest-django + DRF `APIClient` + model-bakery. Markers: `unit`; **`benchmark`** = accuracy tests needing real LLM keys, **skipped by default** (opt in explicitly). Throttling auto-disabled in tests via `backend/conftest.py`.

## Key URLs (dev)

- Frontend `http://localhost:9002` · API `http://localhost:8000/api/`
- Admin `/admin/` · Health `/api/health/` · Schema `/api/schema/`, Swagger `/api/docs/`, ReDoc `/api/redoc/`
- Auth `POST /api/token/`, `POST /api/token/refresh/` (refresh also read from HttpOnly cookie)
- MinIO console `http://localhost:9001` (minioadmin / minioadmin)

Frontend calls same-origin `/api/*`; Next rewrites to `${NEXT_PUBLIC_API_URL || BACKEND_URL || http://localhost:8000}/api/*` (`frontend/next.config.ts`).

## Backend architecture

Project package `backend/core/` — `settings.py`, `urls.py`, `celery.py`, `middleware.py`, `storage_backends.py`, `exception_handlers.py`.

Apps under `backend/apps/` (routed in `core/urls.py`):

- **accounts** — custom user (`AUTH_USER_MODEL='accounts.User'`), roles `ADMIN`/`TEACHER`/`STUDENT`/`MANAGER`; `/api/accounts/`
- **authentication** — JWT login by identifier; `/api/auth/`
- **classes** — **core domain**: courses/chapters, the AI pipelines (class + exam-prep), student chat, quizzes, exam prep, PDF export; `/api/classes/`
- **organizations** — multi-tenant orgs; `/api/organizations/`
- **commons** — admin endpoints + shared LLM infra; `/api/admin/`
- **waitlist** — public teacher access-requests + admin review; `/api/waitlist/`
- **notification** — `/api/notifications/`
- **chatbot**, **material**, **core** — supporting

Note: a few high-traffic exam-prep routes (step-1 intake, review detail, visual content) are declared directly in `core/urls.py` **above** the `apps.classes.urls` include — search there first if an exam-prep URL seems missing from `apps/classes/urls.py`.

### The `classes` pipelines

Long LLM work runs as Celery tasks on the **`pipeline`** queue (`apps/classes/tasks.py` + `tasks_exam_prep.py`); SMS + `cleanup_stale_sessions` (beat) run on **`default`**.

**Class pipeline** — 5 steps orchestrated by `process_class_full_pipeline`:
1. `process_class_step1_transcription` — speech-to-text of media
2. `process_class_step2_structure` — chapter/section extraction
3. `process_class_step3_prerequisites`
4. `process_class_step4_prereq_teaching`
5. `process_class_step5_recap`

**Both pipelines are cancellable:** owner-only `POST …/<id>/cancel/` sets `cancel_requested` and hard-revokes the persisted `celery_task_id`; full-pipeline tasks check cooperative checkpoints between steps, ending in terminal `CANCELLED`. **Preserve those checkpoints when reordering steps.**

Pure logic lives in `apps/classes/services/` (keep it out of views/tasks). `views.py` is very large and split into `views_*.py` / `views_v4_*.py` modules — **search before editing.**

### Exam-prep Mistral OCR subsystem (largest + most active area)

Teachers upload scanned exam-booklet PDFs; the pipeline OCRs them and extracts structured questions/options/answers/solutions with source-anchored visuals. This subsystem is **not** in the old docs and is the current focus (`work/mistral-stage5-*` branches, `docs/EXAM_PREP_MISTRAL_*` findings).

- **Entry:** `POST /api/classes/exam-prep-sessions/step-1/` (`views_exam_prep.ExamPrepPdfStep1View`) **branches by file type**: a **PDF** creates a `ClassCreationSession` (`pipeline_type=EXAM_PREP`, `source_type=PDF`), caps at **5 concurrent** sessions/teacher (429), and dispatches `tasks_exam_prep.process_exam_prep_pdf_session` → `services/exam_prep_mistral_production.run_exam_prep_mistral_pipeline` (`PRODUCTION_ENGINE = "mistral_ocr4_document_visuals_stage5"`). **Audio/video/image** uploads are delegated to the **legacy** transcription intake (`views.ExamPrepStep1TranscribeView`) → `source_type=MEDIA` + `process_exam_prep_full_pipeline` (the strong long-standing media pipeline is intentionally retained — Mistral OCR can't read audio/video). A fake-`.pdf` (non-PDF bytes) is rejected 400 and never falls through to media. The frontend upload accepts all four kinds; routing is server-side by type.
- **"Mistral OCR" is Avalai-hosted, not a separate SDK.** There is **no `mistralai` dependency.** Transport (`exam_prep_mistral_ocr_transport.py`) POSTs to `AVALAI_OCR_ENDPOINT` (default `https://api.avalai.ir/v1/ocr`) with `Authorization: Bearer $AVALAI_API_KEY`, model `mistral-ocr-4-0` (`EXAM_PREP_MISTRAL_OCR_MODEL`). All `EXAM_PREP_MISTRAL_OCR_*` env knobs (max pages/chunk bytes/response bytes/timeout/attempts/backoff) tune it; OCR runs are checkpointed to private storage so they resume.
- **Stages** (facade `exam_prep_mistral_production.py`): **Stage 2** deterministic OCR/numbering/solution recovery (**frozen** in `exam_prep_mistral_stage2_core`), **Stage 3** source-precise visual reconciliation, **Stage 4** free deterministic risk scoring (metadata, *not* an accuracy gate), **Stage 5** — one cheap source-only LLM re-read per numbered question + solution region (single crop per request), budget-bounded (`EXAM_PREP_STAGE5_MINIMUM_RESERVE_USD` etc.). Many `_v2/_v3/_v4` suffixed modules are **superseded iterations kept for reference** — the production facade's imports are the source of truth for what's live; don't wire into a `_v*` module assuming it's current. Stage-5 fans out one request/region at `EXAM_PREP_STAGE5_MAX_CONCURRENCY` (default 4) with bounded SDK backoff `EXAM_PREP_STAGE4_MAX_RETRIES` (default 3) — a large booklet used to 429-flood at `max_retries=0`; **backoff, not a lower cap, is the fix.** A 429-blocked region is **not** an accuracy loss: it falls back to the full deterministic Stage-2 content (`exam_prep_mistral_stage5.py:1219`) and Stage-5 only *appends* the advisory non-gating `stage5_finalization_blocked` — so the log's 429 noise is expected fan-out shape, not lost questions (analysis: `docs/EXAM_PREP_MISTRAL_STAGE5_429_FINDINGS.md`). The sliding-window executor holds a worker slot through backoff sleeps, so it self-throttles — **don't add artificial pacing/jitter.**
- **Publish/review policy — two owner-locked decisions (`docs/EXAM_PREP_MISTRAL_PUBLISH_REVIEW_OVERHAUL.md`, memory `exam-prep-publish-gate-chain`):** (a) a question is forced into the teacher-**review** lane *only* when it has **no stem** or **no options** (`REVIEW_BLOCKING_ISSUE_CODES = {no_questions, missing_question_text, missing_options}` in `exam_prep_page_output.py`) — everything else (Stage-5 blocks, image-options, LaTeX doubts, answer-label authority) is an **advisory** warning; (b) publishing is **always allowed** (`همیشه مجاز`), gated only by teacher-ownership + engine-scoped anti-forgery. The broad `CRITICAL_ISSUE_CODES` set still drives `criticalIssueCount`/display but **gates nothing** — every audit-status calc derives `status` from `review_blocking_question_keys(issues)` + unrecoverable `failedPageNumbers`. **Don't re-widen the gate to the critical set.** The publish view's `pipeline_version>=2/3` artifact block (Gate C/E) is **inert for Mistral** (it creates no `ExamPrepExtractionArtifact`) but is **load-bearing anti-forgery for the separate v2/v3 inventory pipeline** — leave it intact. Per-session token/cost is surfaced via `usageSummary` (aggregates `LLMUsageLog` by `session_id`) in the مرحله ۱ report. Frontend mirror: `REVIEW_BLOCKING_EXAM_CODES` in `exam-review-utils.ts` (keep byte-for-byte synced).
- **Exam-prep V4** (`services/exam_prep_v4_*`, `views_v4_*`, `urls_v4.py`) is a separate source-aware split pipeline, **not** the default production path — status/plan in `docs/features/exam-prep-v4-*.md`. Don't confuse it with the Mistral production engine above.
- **Live-provider calls are forbidden in dev/CI** for exam prep; quality is validated by the **owner in deployment**. `benchmark`-marked tests need real keys and stay skipped.

### Adaptive weak-point quiz/exam loop (student-facing)

Chapter quizzes **and** the course-wide final exam form an adaptive remediation loop: a student who **fails** sees the correct answer to every question, then can request a **new** assessment regenerated to target the concepts they missed — repeating until they pass.

- `services/adaptive_quiz.py` — `compute_weak_points_from(questions_obj, attempts)` (pure, zero-token) joins missed question ids (from `result['per_question']`) with the bank. Handles both grading shapes: section quizzes (`score_0_100`, threshold 70) and final exam (`score_points`/`max_points`).
- Adaptive generation in `quizzes.py`: `generate_adaptive_section_quiz` / `generate_adaptive_final_exam`, driven by the `section_quiz."adaptive"` and `final_exam_pool."adaptive"` prompt strategies — **same output contract** as their `"default"` siblings (contract test enforces `LIVE_KEYS = [default, adaptive]`).
- Regenerate endpoints (`POST …/chapters/<cid>/quiz/regenerate/`, `POST …/final-exam/regenerate/`): allowed **only when `last_passed is False`** (else 409; no assessment yet → 400). They overwrite stored JSON and **reset `last_passed`/`last_score` to `None`** — deliberate rate-limiter (must take and fail the fresh assessment before regenerating again).
- Submit responses include `correct_answer` (+ `explanation` for final exam) in `per_question` — intentional (failed assessment about to be replaced). **GET before answering still hides them — don't "tidy up" by dropping those keys.**
- `tasks.pregenerate_student_assessments` builds all section quizzes + final exam up front (dispatched once from `StudentCourseContentView.get`, `cache.add`-guarded, idempotent, best-effort). On-demand generation is the fallback.
- **No migration** — reuses existing `ClassSectionQuiz.questions` / `ClassFinalExam.exam` JSON.

### LLM providers & JSON handling

`LLM_PROVIDER = gemini | avalai | auto` (env; **legacy alias `MODE`, which is what prod sets** — `MODE=avalai`). See `apps/commons/llm_provider.py`. Gemini via `google-genai`; **Avalai** (`https://api.avalai.ir`, Iranian gateway) via the OpenAI client. `AVALAI_BASE_URL` **must** include `/v1` (`llm_client._normalize_base_url` auto-appends). Models are **env-driven** (`MODEL_NAME`, `TRANSCRIPTION_MODEL`, `IMAGE_MODEL`, `EMBEDDING_MODEL_NAME`, …). **Never hardcode model names or keys.**

**Avalai reference: [`AvalAI-Developer-Documentation.md`](AvalAI-Developer-Documentation.md)** — consult before any LLM call. Multimodal MUST use **standard OpenAI shapes**: `content:[{type:'image_url',image_url:{url:'data:…'}}]` for images, `{type:'input_audio',input_audio:{data,format}}` for audio (or `POST /v1/audio/transcriptions`). The legacy `attachments/input_media/data_base64` shape is **silently ignored** by the gateway (caused hallucinated/empty transcripts historically). `transcription.py` sends the standard shape via `transcription_media.py` (mp3 → `input_audio`, sampled jpeg frames → `image_url`, governed by `FRAME_*` env).

**Long media is transcribed chunk-by-chunk** (`transcription.py`): media > ~1.5× `TRANSCRIPTION_CHUNK_SECONDS` (default 600s) is split into sequential mono-mp3 segments (one ffmpeg `-f segment` pass); each segment is ONE small LLM request carrying its window's frames + the transcript tail (prompt `transcribe_media.chunked`). This is what lets multi-hour lectures survive the gateway. A `progress_cb` heartbeat bumps `updated_at` (so cleanup never reaps a live run) and aborts on `cancel_requested`. Cap: `TRANSCRIPTION_MAX_DURATION_SECONDS` (default 4h). **Don't collapse back into a single request**; keep `transcribe_media_bytes` (chat audio path) single-shot.

**LLM → JSON:** canonical extractor is `apps/commons/json_utils.py` (`extract_json_object`); `apps/classes/services/json_utils.py` re-exports it. For **new** pipeline JSON prefer `apps/commons/structured_llm.py` — `generate_structured(schema=PydanticModel, …)` (JSON-mode + Pydantic + one repair round-trip, **raises** instead of returning `{}`) or `validate_keep_dict(text, schema)` when the model's exact dict must survive (e.g. `structure.py`). Schemas in `apps/classes/services/schemas.py`. **Don't reintroduce raw `extract_json_object` + silent-`{}`.**

**Prompt repository (`apps/commons/llm_prompts/prompts.py`):** ONE `PROMPTS` dict is the single source of every LLM prompt (only `PROMPTS` exported). A key is a "feature"; value is a string or `{"strategy": str}` sub-dict; callers look up by these **exact literal keys**. Templates render with safe **`str.replace`** (never `str.format`) — literal JSON braces are fine, but documented placeholder tokens (`{user_message}`, `{count}`, `STRUCTURED_BLOCKS_JSON`, literal `{{blank}}`, …) and the **output-JSON keys** shown in each prompt are a hard contract with parsers/Pydantic/frontend widgets — keep them byte-for-byte. Shared blocks `SAFETY_PREAMBLE`, `AUDIENCE_ADAPTIVE` (no hardcoded "K-12" — platform serves any level), `MCQ_QUALITY`, `MATH_FORMAT_INSTRUCTIONS` are concatenated in; edit once. **Don't re-add unreferenced/dead prompts.** `apps/classes/test_prompts_contract.py` is the zero-token guard over live keys + placeholders/output-keys — **run it after any prompt edit.**

### Storage
S3-compatible via django-storages, active when `AWS_STORAGE_BUCKET_NAME` is set (MinIO locally, object storage in prod). With no public custom domain, media is served through a Django proxy (`/media/<path>`); private exam/answer sources stream through dedicated authenticated `media/exam-prep/...` routes in `core/urls.py`.

### Auth & API conventions
SimpleJWT (short access + rotating refresh, refresh in HttpOnly cookie). DRF serializers for validation, permissions for access (**deny-by-default**), class-based views/viewsets. drf-spectacular drives the schema.

## Frontend architecture

App Router route groups under `frontend/src/app/`: `(marketing)` · `(auth)` login/signup/join-code · `(dashboard)` student area (home, classes, learn, exam, exam-prep, calendar, profile, notifications, tickets) · `(teacher)` · `(admin)` — plus top-level `start/` (role picker) and `join/` (org invite redemption).

- **`src/services/*.ts`** — the API layer; **every** backend call goes through a service (`auth-service`, `classes-service`, `admin-service`, …). Don't `fetch` ad hoc from components.
- **`src/components/ui/`** — shadcn primitives. Aliases (`components.json`): `@/components`, `@/lib`, `@/lib/utils`, `@/components/ui`, `@/hooks`. Path alias `@/* → src/*`.
- **`src/lib/`** — utilities incl. RTL/Persian helpers (`normalize-math-text`, `persian-option-label`, `date-utils`), `validations/` (zod).
- RTL is global (root `layout.tsx`); keep new UI direction-aware and math rendered with KaTeX.

## Conventions

Follow `.github/instructions/develop.instructions.md`. In short: explore/search before changing; small, tested increments; `camelCase` variables/functions/hooks, `PascalCase` types/components; avoid `any`; modular apps, no cross-app coupling; secrets only via `.env`. **Every bugfix adds a regression test first; auth/permission code needs negative (unauthorized/forbidden) tests.**

**Documentation law: code and its docs land together.** Docs home is `docs/` — `adr/` (numbered, immutable decisions), `features/` (one living spec per feature), `releases/` (note per deploy), `runbooks/` (ops lessons). Exam-prep research/findings live in `docs/EXAM_PREP_*.md`. A change without its doc update is not done.

## Gotchas (fast reference)

- **Frontend dev port is 9002**, not 3000. Prod is 3000.
- **`MODE=avalai`** is the live provider setting (legacy alias for `LLM_PROVIDER`).
- **"Mistral OCR" = Avalai `/v1/ocr` + `mistral-ocr-4-0`**, keyed by `AVALAI_API_KEY`. No `mistralai` SDK.
- **Never hardcode models/keys** — everything env-driven.
- **Prompt keys + output-JSON keys are a byte-for-byte contract**; run `test_prompts_contract.py` after edits.
- **`views.py` and exam-prep are split across many `views_*.py` / `_v*` modules** — grep before editing; trust `exam_prep_mistral_production.py` imports for what's live, not the newest-looking `_v4` file.
- **Genkit / `src/ai/` is dead** — ignore those npm scripts.
- **Cancellation checkpoints** in full-pipeline tasks are load-bearing — preserve on reorder.
- **Adaptive regenerate resets `last_passed`/`last_score` to `None`** on purpose; submit responses reveal answers on purpose.
- **Exam-prep live-provider calls are forbidden in dev/CI**; owner validates in deployment.
