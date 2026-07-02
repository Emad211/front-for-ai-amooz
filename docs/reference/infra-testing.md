# Reference — Infra: testing (pytest layout, markers, gates)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `6ac0345`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step I2
- **Layer:** infra (test tooling)

## Purpose
How the project is tested: the pytest layout + config, markers, the sqlite/no-migrations escape hatches,
throttle auto-disable, and the frontend gates. The reference qa-engineer and everyone else runs against.

## Scope & paths
| File | Role |
|---|---|
| `pytest.ini` (root) | `pythonpath=backend`, `testpaths=backend`, `--reuse-db`, `-ra`, marker `unit` |
| `backend/pytest.ini` | same settings from within `backend/`; markers `unit` + `benchmark` |
| `backend/conftest.py` | autouse: disable throttling + clear throttle cache (B0) |
| `backend/apps/*/test_*.py` | tests live next to code |
| `.claude/agents/qa-engineer.md` | canonical list of known pre-existing failures |

**Out of scope:** the throttle mechanics → B0; frontend build gates detail → F1; benchmark LLM setup → L-docs.

## Public surface — how to run
```bash
python -m pytest                                   # all backend, from repo ROOT (root pytest.ini)
python -m pytest backend/apps/accounts -q          # targeted
python -m pytest backend/apps/classes/test_prompts_contract.py -q   # after any prompt edit (L3)
DATABASE_URL='sqlite:///test.sqlite3' python -m pytest backend/apps/... -q   # quick, no Docker
python -m pytest --no-migrations …                 # if raw-SQL migrations break a fresh test DB
cd frontend && npm run typecheck && npm run lint    # frontend gates (build hides errors! F1)
```
Stack: pytest + pytest-django + DRF `APIClient` + model-bakery; `--reuse-db` for speed.

## Key flows / invariants
- **Markers:** `unit` (unit-level); `benchmark` = accuracy tests needing real LLM keys, **skipped by
  default — never run in CI/default** (opt-in explicitly, e.g. `RUN_PDF_BENCHMARK=1`).
- **Throttling is auto-disabled** in every test by `backend/conftest.py` (autouse fixture clears
  `DEFAULT_THROTTLE_CLASSES`/`RATES` + the throttle cache) — don't write throttle-dependent asserts.
- **sqlite fallback** when Docker/Postgres is down (`DATABASE_URL='sqlite:///…'`); `--no-migrations` when
  raw-SQL migrations (org 0002-0007) break a fresh test DB. sqlite can't prove Postgres constraint/
  concurrency behavior — reason those for Postgres (database-engineer).
- **Team laws:** every bugfix adds its regression test FIRST; every auth/permission change ships negative
  tests (401/403) — the qa-engineer/security-auditor gate.
- **Prompt edits** must run `test_prompts_contract.py` (L3, zero-token).
- **Frontend:** no unit runner yet — `tsc --noEmit` is the gate with a small pre-existing error baseline
  (**0 NEW errors** is the bar); `next lint` too. `next build` hides type/lint errors (F1).

## Known pre-existing failures (do NOT chase; verify unchanged)
Canonical home: `.claude/agents/qa-engineer.md`. Currently: `test_real_race_condition_same_username`
(sqlite concurrent-INSERT artifact); a few exam-prep role-403 + idempotency tests; `test_health.py`
(`.data` on the middleware's plain HttpResponse, B0); 3 chatbot `_get_clients` tests. Any OTHER failure
is real until proven pre-existing.

## Gotchas
- The user is near their Avalai token limit — **default tests are fully mocked (0 tokens)**; real
  benchmarks are opt-in only. Never run `benchmark` by default.
- Two `pytest.ini` files (root + backend/) — both use `core.settings` + `--reuse-db`; run from either
  location.
- `test_health.py` fails because it asserts `.data` on the middleware health response (which is a plain
  `HttpResponse`, not a DRF Response) — a known artifact, not a regression (B0).

## Cross-links
[backend-core.md](backend-core.md) (B0, throttle auto-disable + health) · [llm-prompts-contract.md](llm-prompts-contract.md)
(L3, the contract test) · [infra-deploy.md](infra-deploy.md) (I1, migrations on deploy) ·
[frontend-app-shell.md](frontend-app-shell.md) (F1, build hides errors) · `.claude/agents/qa-engineer.md`
(pre-existing failures) · memory: `frontend-verification-and-mobile`, `project-overview`.

## Verified-by
- Full read (2026-07-02): `pytest.ini` (root, 9 lines), `backend/pytest.ini` (9 lines) — confirms
  `pythonpath=backend`, `testpaths=backend`, `--reuse-db`, markers `unit`+`benchmark`.
- `backend/conftest.py` throttle-disable cross-referenced (read in B0).
- Pre-existing-failure list sourced from `.claude/agents/qa-engineer.md` (the canonical home) + memory
  `admin-analytics`/`project-overview`.
- NOT run this pass: the actual suite (documentation pass; qa-engineer runs it at review time).
