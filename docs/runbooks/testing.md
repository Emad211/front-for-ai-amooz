# Runbook — Running the test suite

- **Status:** Living · **Created:** 2026-07-04 · **Last-verified:** 2026-07-04 · **Owner:** qa-engineer
- Program: [ADR-0003](../adr/ADR-0003-test-suite-program.md) · Roadmap: [../testing/README.md](../testing/README.md)

## The two lanes
| Lane | Command | When | Proves |
|---|---|---|---|
| **sqlite fast (local)** | `DATABASE_URL='sqlite:///test.sqlite3' python -m pytest --no-migrations -q` | quick local runs, no Docker | logic/contract/permission behavior |
| **Postgres truth (CI + pre-push)** | `docker compose up -d postgres` then `python -m pytest -q` | before push, in CI | the REAL migration path + constraint/concurrency behavior |

**Why `--no-migrations` on sqlite:** the `organizations` migrations (`0002–0006,0010`) and `classes/0019`
use raw Postgres SQL (`DO $$…$$`, column drops) that sqlite can't parse (`near "DO": syntax error`), so a
fresh sqlite test DB fails at migrate. `--no-migrations` builds tables straight from the models and
sidesteps it. **Trade-off:** the sqlite lane therefore does NOT exercise the migration path or Postgres-only
constraint semantics (partial `uniq_student_phone`, real concurrency) — **only the Postgres lane proves
those.** CI runs on Postgres for exactly this reason.

## Markers (taxonomy)
Registered in `pytest.ini` (root + `backend/`), enforced with `--strict-markers`:
`unit` · `service` · `api` · `integration` · `permission` (cross-cuts `api`) · `smoke` · `slow` ·
`benchmark` (real LLM keys — **skipped by default, never in CI**).
- Run one layer: `pytest -m unit` · `pytest -m "api and not slow"`.
- Audit the negative-auth matrix across the app: `pytest -m permission`.
- Default lane excludes benchmarks: `pytest -m "not benchmark"`.

## `--reuse-db` hygiene
`--reuse-db` caches the test DB for speed. **After any model/migration change, reset once:** add
`--create-db` (e.g. `pytest --create-db`). CI always uses a fresh DB so it can't be fooled by a stale cache.

## Which config wins
Run from the repo **root** → root `pytest.ini` (`pythonpath=backend`, `testpaths=backend`). Run from
`backend/` → `backend/pytest.ini`. Both register the same markers + `--strict-markers`.

## venv
The backend venv is at `backend/.venv`. On Windows:
`backend/.venv/Scripts/python.exe -m pytest …` (a bare `python` may lack pytest-django → `unrecognized
arguments: --reuse-db`).

## Known pre-existing failures
Canonical list lives in `.claude/agents/qa-engineer.md` (cleared to green in roadmap step **T2**). Until
then, a red suite is expected; verify a failure is on that list before treating it as a regression.

## Coverage (from T1)
`python -m pytest -m "not benchmark" --cov --cov-branch --cov-report=term-missing` (config in
`backend/pyproject.toml`; floor is the measured baseline, ratcheted up-only).
