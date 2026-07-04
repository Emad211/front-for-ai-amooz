# Test-suite program — ROADMAP (per-step specs)

Governed by **ADR-0003**. Loop mechanics + DoD live in `README.md`; per-step spec shape in `TEMPLATE.md`.
Execute the **lowest unchecked** step in `README.md` each `/loop`. Steps are ordered by dependency then value:
Phase 0 foundations → Phase 1 backend domains → Phase 2 LLM/pipeline → Phase 3 frontend → Phase 4 steady state.

Baseline (2026-07-04): 97 backend test files (classes 52 · authentication 11 · chatbot 7 · accounts 7 ·
commons 5 · organizations 4 · waitlist 4 · core 3 · notification 1 · material 0=empty app). No coverage, no CI,
9 known failures, frontend 0 tests. `material` is an empty shell — **no tests owed**.

---

## Phase 0 — Foundations

### T0 — Reliable, runnable suite ☑ (2026-07-04)
- **Owner:** qa-engineer · **Layer:** infra
- Settle the run story: Postgres (Docker) = source of truth (migrations run); sqlite path documented as
  `DATABASE_URL=sqlite:///test.sqlite3 --no-migrations` because org migrations use `DO $$…$$` raw SQL
  (`organizations/0002-0006,0010`, `classes/0019`) that sqlite can't parse. Register all markers
  (`unit,service,api,integration,permission,smoke,slow,benchmark`) in `pytest.ini` + `--strict-markers`.
- **DONE:** both `pytest.ini` files carry the 8-marker taxonomy + `--strict-markers`; `docs/runbooks/testing.md`
  documents the two lanes + `--reuse-db`/`--create-db` hygiene. Verified: **892 tests collect clean** under
  `--strict-markers` (only `unit`/`benchmark` were actually in use, both registered).

### T1 — Coverage measurement + baseline ☑ (2026-07-04)
- **Owner:** qa-engineer · **Layer:** infra
- Add `pytest-cov` to `backend/requirements.txt` (dev), a `.coveragerc` (omit migrations, tests, settings,
  `.venv`). Record the measured baseline % in `README.md` as the **starting floor**. No gate yet.
- **DONE:** `pytest-cov` + `coverage[toml]` in requirements; config in `backend/pyproject.toml` (branch=true,
  source=apps, omit migrations/tests/conftest/settings/wsgi/asgi/__init__/.venv). **Baseline = 79%** branch
  (sqlite `--no-migrations`, `-m "not benchmark"`). No hard gate yet; floor pinned in CI at T4. Note: run
  with `--cov-config=backend/pyproject.toml` from repo root so pytest-cov picks up the omit list.

### T2 — Clear the pre-existing failures ☑ (2026-07-04, stale/flaky tranche)
- **Owner:** qa-engineer + backend-engineer · **Layer:** unit/api
- Fix or correctly-mock: stale exam-prep `_get_clients` unit; exam-prep role-403 + idempotency;
  `requires_student_role`/`teacher_rejected` permission tests; `test_health.py` (`.data` on plain
  `HttpResponse`); 3 chatbot `_get_clients` tests. Suite must be **fully green** so the ratchet is honest.
- **DONE (13/15):** `test_health` `.data`→`json.loads(content)`; `test_real_race_condition_same_username`
  `skipif(connection.vendor=='sqlite')`; transcription heartbeat pinned to a past `updated_at` (kills the
  same-microsecond flake); chatbot memory×2 mock lambda now accepts `feature=`; provider-selection test
  rewritten to `preferred_provider()` (the dual-client `_get_clients` seam was removed); exam-prep service
  unit rewritten to patch the module-bound `generate_text`; the **6 role tests** (`test_teacher_rejected`
  + 5 `requires_student_role`) now assert the CURRENT policy — `IsStudentUser` deliberately allows
  teachers, and phone-scoping (not role) yields the no-data-leak guarantee (uninvited → 200-empty / 400 /
  404). **Policy flag for security-auditor:** tighten `IsStudentUser` to student-only iff strict role
  separation is the intended product policy.

### T2b — Genuine exam-prep behavior items (carved from T2) ☑ (2026-07-04)
- **RESOLVED — both were stale/too-strict tests, the CODE is correct:** (a) the idempotency test uploaded
  two DIFFERENT files with one `client_request_id`; `_is_same_uploaded_source` (name+size) correctly makes
  a new session (anti "new-input/stale-output"). Fixed to a same-file retry + added a new test locking the
  different-file→new-session behavior. (b) reset clears `attempt.answers={}` in the DB (verified); the
  `/result/` view returns a per-question blank map for display — aligned the assertion. **Full sqlite lane
  now GREEN** (891 pass / 3 skip / 0 fail); also skipif'd `test_concurrent_registration_same_username`
  (a sibling sqlite concurrency flake). Original spec below.
- **Owner:** backend-engineer · **Consult:** security-auditor · **Layer:** api
- (a) `test_idempotency_with_client_request_id`: a 2nd exam-prep step-1 with the same `client_request_id`
  returns a NEW session (id 2) instead of the existing one (id 1) — is idempotency implemented, an
  aspirational test, or a real dedup bug? (b) `test_reset_clears_attempt_and_allows_retake`: reset returns
  `answers={'q1':'','q2':''}` not `{}` — should reset clear to `{}`? Read the views; fix real bugs
  red-first or align the expectation with the documented behavior. These need care (real code, not test
  cleanup) — deliberately NOT rushed into T2.

### T3 — Shared fixtures / factories ☑ (2026-07-04)
- **Owner:** qa-engineer · **Layer:** infra
- Consolidate repeated builders (user-by-role, org+membership, study group, class + creation session,
  enrolled student, quiz/exam JSON) into `conftest` fixtures / model-bakery recipes. Later steps reuse these.
- **DONE:** `backend/testing/recipes.py` (Recipes for `admin/teacher/manager/student_completed/student_shell`
  with `seq`-unique valid phones, `organization`/`org_membership`/`invite_code`/`study_group`,
  `class_session`/`exam_prep_session`/`class_section`/`class_unit`) + fixtures in `backend/conftest.py`
  (`admin_client`…`anon_client`, `other_teacher_client`/`other_student_client`, `mock_llm` patching the
  module-bound `apps.classes.services.<stage>.generate_text` — zero tokens, `freeze_tehran` via freezegun).
  Proof: `testing/test_fixtures_smoke.py` (8) + classes `test_permissions` refactored onto `anon_client`
  + new `organizations/test_permissions_smoke.py` platform-admin matrix (`permission` marker). **26 green.**
  `testing/` omitted from coverage; freezegun in requirements.

### T4 — CI gate ☑ (2026-07-04)
- **Owner:** devops-engineer + qa-engineer · **Consult:** release-manager · **Layer:** infra
- GitHub Actions workflow: backend job on a **Postgres service container** (migrations run), installs reqs,
  runs `pytest --cov`, uploads coverage; frontend job runs `tsc --noEmit` + `next lint`. PR-triggered.
- **DONE:** `.github/workflows/tests.yml` — backend job (postgres:16 + redis:7 services, DATABASE_URL/
  REDIS_URL env, apt: ffmpeg + libpango/cairo/gdk-pixbuf for WeasyPrint, `pytest -m "not benchmark"
  --create-db --cov ... --cov-report=xml`) + frontend job (node 20, `npm ci`/`typecheck`/`lint`). push(main)
  + PR. No `--cov-fail-under` yet (T26). YAML parse-validated. **CANNOT run Actions from here** → activates
  on next GitHub push; the first run may need a system-lib tweak — flagged for the user to watch.

---

## Phase 1 — Backend per-domain hardening (services → api → integration)

### T5 — commons unit/service
- **Owner:** backend-engineer · **Layer:** unit/service
- `json_utils.extract_json_object` (fences, greedy, malformed), `structured_llm.generate_structured` +
  `validate_keep_dict` (repair round-trip, raises-not-`{}`), `phone_utils.normalize_phone`, `schemas.py`.

### T6 — accounts service + api
- **Owner:** backend-engineer · **Consult:** security-auditor · **Layer:** service/api
- `get_or_create_user_by_phone`, partial unique constraint `uniq_student_phone`, role model, forced-onboarding
  funnel. **Negative:** completed account blocked from code re-entry; duplicate phone.

### T7 — authentication api
- **Owner:** backend-engineer · **Consult:** security-auditor · **Layer:** api
- Token issue/refresh, login-by-identifier. **Negative:** bad creds, expired/blocked, deny-by-default.

### T8 — organizations service + api
- **Owner:** backend-engineer · **Consult:** database-engineer, security-auditor · **Layer:** service/api
- Membership, study groups, manager oversight-only scope, per-teacher/class/group AI-cost read.
  **Negative:** cross-org access, manager write-attempt, role escalation.

### T9 — waitlist api
- **Owner:** backend-engineer · **Layer:** api
- Approval gate (no account until approved), org approval auto-creates org+code, SMS-only path.
  **Negative:** unapproved cannot authenticate/act.

### T10 — commons admin api
- **Owner:** backend-engineer · **Consult:** security-auditor · **Layer:** api
- `/api/admin/` analytics (Tehran tz), activity feed, user management. **Negative:** non-admin 403.

### T11 — notification service + api
- **Owner:** backend-engineer · **Layer:** service/api (currently only 1 file)
- Dispatch, list, read-state transitions. **Negative:** cannot read/mutate another user's notification.

### T12 — chatbot service + api
- **Owner:** backend-engineer + ai-engineer · **Layer:** service/api
- Chat flow, history, media. Establish the correct `_get_clients` mock pattern (the source of 3 failures).

### T13 — classes teacher api + roster/invites/publish
- **Owner:** backend-engineer · **Consult:** security-auditor · **Layer:** api
- Teacher CRUD, org-class roster, invite code verify/SMS, publish. **Negative:** non-owner, non-teacher,
  cross-org. (Grep the 195 KB `views.py` — never read whole.)

### T14 — classes student api
- **Owner:** backend-engineer · **Consult:** security-auditor · **Layer:** api
- Courses list, chapter/final content, PDF export, progress/enrollment, chat history. **Negative:**
  non-enrolled student blocked; other-student's session hidden.

### T15 — classes model + serializer + settings guards
- **Owner:** backend-engineer + database-engineer · **Layer:** unit/service
- Model constraints, serializer annotations, env-only model-selection (no hardcoded model names — CLAUDE.md law).

---

## Phase 2 — LLM / pipeline (ai-engineer; LLM always mocked outside `benchmark`)

### T16 — Prompt contract + rendering
- **Owner:** ai-engineer · **Layer:** unit
- Extend `test_prompts_contract.py` / `prompt_rendering`: exact `PROMPTS` keys, `str.replace` placeholders,
  output-JSON keys byte-for-byte, shared blocks (`SAFETY_PREAMBLE`, `AUDIENCE_ADAPTIVE`, `MCQ_QUALITY`,
  `MATH_FORMAT_INSTRUCTIONS`). No unreferenced prompts re-added.

### T17 — Structure / prereqs / recap / quizzes services
- **Owner:** ai-engineer · **Layer:** service
- Each service with a mocked LLM client: structured-output happy path + one-repair path; `validate_keep_dict`
  preserves exact dict (structure.py). Frozen quiz/exam JSON shapes asserted.

### T18 — Adaptive loop
- **Owner:** ai-engineer · **Layer:** unit/api/integration
- `compute_weak_points_from` (both grading shapes: section 0-100 thr 70 + exam points), `regenerate`
  endpoints (409 when `last_passed` truthy, 400 when none, reset-to-None guard), `pregenerate_student_assessments`
  idempotency (`cache.add`). **Negative:** non-owner regenerate; answer-reveal only on POST not pre-answer GET.

### T19 — Transcription
- **Owner:** ai-engineer · **Layer:** unit/integration
- Chunk splitting (>~1.5× `TRANSCRIPTION_CHUNK_SECONDS`), heartbeat bumps `updated_at`, cancellation
  (`TranscriptionAborted`→CANCELLED, never retried), avalai standard multimodal shape (`input_audio`,
  `image_url`), single-shot `transcribe_media_bytes` unchanged.

### T20 — Pipeline orchestration integration
- **Owner:** ai-engineer + backend-engineer · **Layer:** integration
- Eager Celery: step1-5 chaining, cooperative cancel checkpoints between steps, hard-revoke path, idempotent
  dispatch, OOM-at-frame-extraction regression, `cleanup_stale_sessions` never reaps a live (heartbeating) run.

### T21 — Exam-prep pipeline + api
- **Owner:** ai-engineer + backend-engineer · **Consult:** security-auditor · **Layer:** integration/api
- 2-step exam-prep, windowing, submit/result/reset endpoints, chat. **Negative:** role 403, idempotency,
  owner-only cancel.

---

## Phase 3 — Frontend bootstrap

### T22 — Vitest + Testing Library install
- **Owner:** frontend-engineer · **Layer:** frontend-infra
- Add Vitest + @testing-library/react + jsdom to `frontend/package.json`; `test` + `test:watch` scripts;
  config that respects `@/* → src/*` alias; one green smoke test. Keep `tsc`/`lint` gate intact.

### T23 — services layer tests
- **Owner:** frontend-engineer · **Layer:** frontend-unit
- `src/services/*.ts` with mocked fetch: URL building, `NEXT_PUBLIC_API_URL تنظیم نشده است` guard (5 services
  throw), trailing-`/api` normalization, error mapping, per-service happy + negative.

### T24 — lib + hooks
- **Owner:** frontend-engineer · **Layer:** frontend-unit
- RTL/Persian helpers (`normalize-math-text`, `persian-option-label`, `date-utils`), `validations/` zod schemas,
  custom hooks. Pure, deterministic.

### T25 — component render + optional e2e smoke
- **Owner:** frontend-engineer · **Layer:** frontend-component/e2e
- Render tests for load-bearing widgets that consume the frozen quiz/exam JSON shapes + auth guards
  (redirect-when-unauth). Optional Playwright smoke on login→forced-onboarding.

---

## Phase 4 — Steady state

### T26 — Ratchet + wire the gate
- **Owner:** qa-engineer + devops-engineer · **Consult:** release-manager · **Layer:** infra
- Raise coverage floor one notch above baseline; CI fails below floor; add the frontend Vitest job to CI.
- Thereafter: every new feature PR carries its tests (docs law) and the floor only rises.

---

## Load-bearing specifics (from the council — reuse these, don't re-derive)

**Markers (T0):** register `unit, service, api, integration, permission, smoke, slow, benchmark` in
`pytest.ini` + `--strict-markers`. `permission` is a cross-cut applied alongside `api` so `-m permission`
greps the whole negative auth matrix in one run (the matrix-completeness audit).

**Coverage (T1):** `pytest-cov` + `coverage[toml]`; config in `backend/pyproject.toml` — `branch = true`,
`source = ["apps"]`, omit `*/migrations/* */tests/* */test_*.py */conftest.py */settings*.py wsgi/asgi
__init__ .venv manage.py`. Run: `pytest -m "not benchmark" --cov --cov-branch --cov-report=term-missing`.
Floor = measured baseline, **up-only ratchet**; gating in the Postgres CI job, advisory in the sqlite lane.

**Shared fixtures (T3) — `backend/testing/{recipes,fixtures}.py`, imported by `backend/conftest.py`:**
model-bakery `Recipe`s for `admin_user/teacher_user/student_completed/student_shell/manager_user`,
`organization`+`org_membership`+`invite_code`, `study_group`, `class_session`(+section/unit),
`section_quiz`/`final_exam`/attempts; role-authed `APIClient` fixtures (`admin_client`…`anon_client` +
`other_teacher/other_student` for the wrong-owner leg); `freeze_tehran` (tz tests); and **`mock_llm`** —
the single LLM mock (see Phase 2).

**LLM mock boundary (T3/Phase 2) — uniform:** every stage service does
`from apps.chatbot.services.llm_client import generate_text`, so patch the **module-bound name**
`apps.classes.services.<stage>.generate_text` (NOT the client) — mirrors the proven
`test_transcription_chunked.py` pattern. Also stub ffmpeg (`probe_media_duration`,
`extract_audio_mp3_from_path`, `extract_frames_jpeg_from_path`, `_run_ffmpeg`) and set model-env vars so
`_select_model` doesn't raise. Flavors: `queue_llm(list)` (sequential), `scripted_llm(by_feature)`,
`failing_llm(exc)`. Zero tokens, always. Real-model QUALITY stays `benchmark`-only (VPN-blocked).

**Top RISK×gap (backend, per backend-engineer):** T10 `commons` admin/cost/analytics (~40 endpoints, near-zero
coverage — money+oversight surface; incl. the **Tehran-tz day-boundary** regression test and the
`TicketMessage.author` FK guard) and T8 `organizations` tenancy isolation (the `IsOrgAdmin` in-handler
helper means a forgotten call silently degrades to `IsAuthenticated` → cross-tenant leak; the negatives are
the only thing that catches it). `material` is empty → T15 confirms dead + documents/deletes, no tests.

**Frontend (T22–T25, per frontend-engineer):** Vitest + `@testing-library/react` + jsdom + **msw** (stub
`/api`; the refresh token is an HttpOnly cookie now → stub the refresh endpoint by URL, not a body token).
`vitest.config.ts` sets the `@/*` alias manually (no extra plugin); `vitest.setup.ts` stubs
`matchMedia`+`ResizeObserver` (Radix/jsdom) and sets `dir="rtl"`. Order: pure libs+zod → `baseRequest`
core (401→refresh→retry-once) → services/one-hook → auth forms → onboarding wizard + adaptive widgets.
Playwright (e2e) deferred, off the fast gate, needs the live backend + a token-free pipeline stub.
