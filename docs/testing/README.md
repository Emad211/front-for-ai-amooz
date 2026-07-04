# Test-suite program — progress checklist (loop control file)

The loop's control file. Governed by **ADR-0003**. One step per `/loop` iteration. Do the **lowest
unchecked** step, ship it GREEN, tick it here, commit `test(<scope>): …`, push.

**Taxonomy (markers):** `unit` · `service` · `api` · `integration` · `benchmark` (skipped by default) ·
frontend = Vitest/Playwright. Tests stay next-to-code (`apps/<app>/test_*.py`); layer = marker, not folder.

**Definition of done (every step):**
1. New/organized tests are GREEN locally on Postgres (Docker) — the source of truth.
2. Coverage delta reported in the commit body (`pytest --cov`); floor never drops.
3. **No NEW failures** vs the tracked baseline; any pre-existing failure touched is fixed or re-noted.
4. Auth/permission code has **negative** tests (401/403) — non-negotiable (security-auditor rule).
5. Checklist ticked + `ROADMAP.md` step marked done with the commit sha.

## Phase 0 — Foundations (runnable, measured, gated)
- [ ] **T0** — Reliable-suite fix: document/settle the sqlite `--no-migrations` story + a Postgres test path; markers registered in `pytest.ini`.
- [ ] **T1** — Adopt `pytest-cov` + `.coveragerc`; record the **baseline** coverage number (the starting floor).
- [ ] **T2** — Clear the 9 pre-existing failures (stale `_get_clients` unit, exam-prep 403/idempotency, `requires_student_role`/`teacher_rejected`, `test_health.py`, 3 chatbot `_get_clients`).
- [ ] **T3** — Shared fixtures/factories: consolidate user/role/org/class/session builders into reusable `conftest`/factory fixtures.
- [ ] **T4** — CI: GitHub Actions running the **backend** suite on Postgres (migrations run) + coverage report; frontend `tsc`/`lint` job.

## Phase 1 — Backend per-domain hardening (services → api → integration)
- [ ] **T5** — `commons` unit/service: `json_utils.extract_json_object`, `structured_llm`, `phone_utils`, `structured` schemas.
- [ ] **T6** — `accounts` service+api: `get_or_create_user_by_phone`, uniqueness constraint, role model; negative auth.
- [ ] **T7** — `authentication` api: token/login-by-identifier, refresh; negative (bad creds, blocked re-entry).
- [ ] **T8** — `organizations` service+api: membership, study groups, manager oversight scope; negative (cross-org, role).
- [ ] **T9** — `waitlist` api: approval gate, org auto-create, SMS-only; negative (unapproved access).
- [ ] **T10** — `commons` admin api (`/api/admin/`): analytics, activity feed; negative (non-admin 403).
- [ ] **T11** — `notification` service+api (currently 1 file): dispatch, read-state; negative (other-user notif).
- [ ] **T12** — `chatbot` service+api: chat flow, history; fix/replace `_get_clients` mocking pattern.
- [ ] **T13** — `classes` teacher api + roster/invites/publish: permissions, org-class roster; negative (non-owner, non-teacher).
- [ ] **T14** — `classes` student api: courses, chapter/final content, PDF export, progress/enrollment; negative (non-enrolled).
- [ ] **T15** — `classes` model constraints + serializer annotations + settings/env-only guards.

## Phase 2 — LLM / pipeline slice (ai-engineer)
- [ ] **T16** — Prompt contract + rendering (`prompts_contract`, `prompt_rendering`) audited & extended; keep byte-for-byte keys.
- [ ] **T17** — Structure/prereqs/recap/quizzes services with **mocked** LLM client (structured-output + repair path).
- [ ] **T18** — Adaptive loop: `adaptive_quiz` weak-point math + `regenerate` endpoints (`last_passed` reset guard) + pregeneration task.
- [ ] **T19** — Transcription: chunking, cancellation (`TranscriptionAborted`→CANCELLED), heartbeat, avalai multimodal shape.
- [ ] **T20** — Pipeline orchestration integration (eager Celery): step chaining, cancel checkpoints, idempotent dispatch (`cache.add`), OOM/robustness regressions.
- [ ] **T21** — Exam-prep pipeline: windowing, submit/result/reset api, chat; negative (role, idempotency).

## Phase 3 — Frontend bootstrap
- [ ] **T22** — Install Vitest + Testing Library + jsdom; wire `test`/`test:watch` scripts; one smoke test green.
- [ ] **T23** — `src/services/*` unit tests (mocked fetch): URL building + `NEXT_PUBLIC_API_URL` guard, error mapping, per-service happy/negative paths.
- [ ] **T24** — `src/lib` + hooks: RTL/Persian helpers (`normalize-math-text`, `persian-option-label`, `date-utils`), zod validations, custom hooks.
- [ ] **T25** — Component render tests for a few load-bearing widgets (quiz/exam JSON shapes, auth guards); optional Playwright e2e smoke on the login→onboarding flow.

## Phase 4 — Steady state
- [ ] **T26** — Ratchet coverage floor up one notch; wire CI to fail below floor; add the frontend job to CI.

_Ordering dissents get recorded in `ROADMAP.md` next to the affected step, not erased._
