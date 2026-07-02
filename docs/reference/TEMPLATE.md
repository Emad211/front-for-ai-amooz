# Reference — <module/domain name>

- **Status:** Stub | Drafting | Verified · **Created:** YYYY-MM-DD · **Last-verified:** YYYY-MM-DD (commit `<sha>`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step <ID>
- **Layer:** backend-app | backend-service | llm | frontend-route-group | frontend-layer | infra | cross-cutting

## Purpose
2–4 sentences: what this module IS and the one job it owns in AI-Amooz. No history, no how — just the role.

## Scope & paths
- **Root:** `backend/apps/<x>/` (or `frontend/src/<x>/`)
- **Key files** (path — one-line role; `file:line` for entry points; do NOT paste code; flag god files "grep, don't read whole"):
- **Out of scope (lives elsewhere → link):** e.g. "LLM JSON handling → [llm-structured-output.md](llm-structured-output.md)".

## Public surface
The contract other code/users depend on. Keep only the rows that apply:
- **Endpoints** — table: route · method · auth/permission · brief req→resp · error codes.
- **Exports** — public functions/classes/hooks/components · signature · one-line contract.
- **Prompt keys** — exact literal key · strategies (if this module calls the LLM).
- **Env knobs** — VAR · default · effect.

## Key flows
The 1–4 sequences that matter, each as a numbered step list naming real functions/files (`file:func()`),
not pseudocode. Mark async/Celery-queue boundaries and cancellation checkpoints.

## Data & invariants
Models/fields touched, constraints (unique/index), migration numbers, and the RULES that must hold.
State what MUST NOT be changed and why. Cite the guard test if one exists.

## Gotchas
Module-specific traps a future editor will hit. Link to CLAUDE.md Gotchas / a runbook rather than
restating — add only what is NOT already there. Deprecated behavior gets ~~strikethrough~~ + date.

## Cross-links
Related reference docs · feature specs (`docs/features/`) · ADRs · the owning agent file (`.claude/agents/`).

## Verified-by
The evidence this doc is true as of **Last-verified**. Every non-obvious claim traces to one line here.
- `<command run>` → what it confirmed (re-runnable verbatim).
- `file:line` reads that confirmed a signature/constraint.
- What could NOT be verified (VPN-blocked live LLM, running-worker behavior) — stated explicitly.
