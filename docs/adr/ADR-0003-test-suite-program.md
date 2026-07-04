# ADR-0003 — Whole-application test-suite program (loop-driven)

- **Status:** Accepted
- **Date:** 2026-07-04 · **Deciders:** tech-lead (council chair) + user (Emad) · **Council (parallel):** qa-engineer, backend-engineer, ai-engineer, frontend-engineer · **Flagged for future per-step consults:** database-engineer, security-auditor, devops-engineer, release-manager

## Context
The suite is real but uneven: 97 backend test files skewed to `classes` (52), no coverage
measurement, no CI, 9 known pre-existing failures, a sqlite-vs-Postgres migration hazard that forces
`--no-migrations`, and a **frontend with zero tests and no runner**. The user wants precise, categorized,
tidy tests for every part of the app, delivered as a step-by-step program executed one step per `/loop`
iteration — exactly the shape of the reference-docs program (ADR-0002). We need a durable home, a taxonomy,
an ordered roadmap, and a per-step definition-of-done, without writing any tests during this planning pass.

## Decision
**Run the test build-out as a numbered, loop-driven program mirroring ADR-0002**, controlled by a
`docs/testing/` subtree: `ROADMAP.md` (per-step specs T0..Tn), `README.md` (progress checklist = the loop's
control file), `TEMPLATE.md` (per-step spec shape). One step per `/loop` iteration; each step ships a
coherent GREEN set of new/organized tests plus the updated checklist, committed `test(<scope>): …` and pushed.
**Foundations first** (runnable-suite fix + coverage + CI + shared fixtures), then per-domain backend
hardening (by layer: services → API-contract → integration/tasks), then the LLM/pipeline slice, then the
**frontend test bootstrap** (Vitest + Testing Library, later Playwright). Coverage is measured with
pytest-cov and **ratcheted** from the measured baseline, never dropped.

Test taxonomy (six layers, mapped to this stack):
1. **unit** — pure functions (`apps/*/services/*` pure logic, `commons/*_utils`, adaptive_quiz math). No DB, no network. Marker `unit`.
2. **service** — a service function against a real (test) DB / mocked LLM client. Marker `service`.
3. **api** — DRF `APIClient` request→response contract incl. **negative** auth/permission tests. Marker `api`.
4. **integration** — Celery tasks (eager) + service + DB wired together (pipeline steps, pregeneration). Marker `integration`.
5. **benchmark** — real LLM keys, accuracy; **skipped by default** (existing marker `benchmark`).
6. **frontend** — Vitest unit (services/lib/hooks with mocked fetch) + component render; Playwright e2e later.

Pyramid target: broad unit/service base, a solid api-contract middle, a thin integration top, e2e minimal.
Organization stays **per-app, tests-next-to-code** (`apps/<app>/test_*.py`) — layer is expressed by **marker**,
not directory — so nothing moves and `git blame`/graph stay intact.

## Alternatives considered
- **Reorganize tests into `tests/unit|api|integration/` trees** — rejected: mass file moves, breaks locality
  and the reference-docs map; markers give the same taxonomy at zero churn.
- **Coverage gate as a hard fail from day one at a high floor (e.g. 80%)** — rejected: current baseline is
  unknown and uneven; a high floor blocks every PR. We ratchet from the measured number instead.
- **Frontend Jest instead of Vitest** — rejected: Vitest is the Vite/TS-native, faster fit for a Next 15 + TS
  strict repo and is already the CLAUDE.md-stated plan.
- **One giant "add all tests" effort** — rejected: not independently shippable; the loop shape (ADR-0002)
  already proved it keeps each increment green and reviewable.

## Consequences
- Positive: every step is small, green, reviewable, and reversible; coverage becomes visible and only rises;
  CI stops regressions; the frontend finally gets a runner.
- Negative / accepted risk: the sqlite hazard means CI must run backend tests on **Postgres** (so migrations
  run) — slightly heavier CI; T0 fixes the local story (`--no-migrations` documented + a `pytest-postgres`
  path) so contributors aren't blocked.
- Follow-ups created: the 9 pre-existing failures are cleared in an early step (T2) before the coverage
  ratchet begins, so the floor reflects a truly-green suite.

## Dissent (recorded)
- **qa-engineer** argued the organizations raw-SQL migrations (`DO $$…$$`) should be made **vendor-safe**
  so local sqlite runs the REAL migration path — rather than institutionalizing `--no-migrations` (which
  means the migration path is never exercised locally). **Chair deferred:** CI-on-Postgres is the
  migration-truth gate, so vendor-guarding is an optional later improvement (database-engineer), not a
  program blocker; T0 documents the `--no-migrations` sqlite fast lane. Adopted otherwise.
- **backend-engineer** ordered the backend phase by **RISK×gap** (commons admin/cost/analytics + orgs
  tenancy-isolation first — the near-zero-coverage money+auth surfaces). The chair's roadmap uses a
  foundations→identity→outward dependency order instead (T5 utils → T6/T7 identity → T8 orgs → T10
  commons-admin). Both are defensible; **T8 (orgs tenancy) and T10 (commons admin/cost) are flagged as the
  highest-RISK×gap steps** and may be pulled earlier if the user prefers risk-first.
Further ordering dissents get recorded inline in `docs/testing/ROADMAP.md` against the affected step.
