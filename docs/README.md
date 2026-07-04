# AI-Amooz Documentation

- **Status:** Living · **Created:** 2026-07-02 · **Owner:** technical-writer (agent team)

The single home for project documentation. The agent team's law: **code and its docs land together** —
a change is done only when its documentation is in the same commit series.

## Structure

| Directory | What lives here | Rules |
|---|---|---|
| `reference/` | Code-verified module/domain reference (the codebase map) | One doc per module per `reference/TEMPLATE.md`; progress + resume rules in `reference/README.md`; program: ADR-0002. |
| `testing/` | The loop-driven test build-out program | `testing/ROADMAP.md` per-step specs + `testing/README.md` progress checklist (the loop control file); program: ADR-0003. |
| `adr/` | Architecture Decision Records | Numbered (`ADR-NNNN-<slug>.md`), **immutable** — supersede with a new ADR, never rewrite. Status: Proposed → Accepted → Superseded-by-NNNN. |
| `features/` | One living spec per feature | Status: Draft → Approved → Shipped. Updated whenever behavior changes — a stale feature doc is a bug. |
| `releases/` | One note per meaningful push/deploy | Written by release-manager: changes, migrations, env, rebuild targets, verification, rollback. |
| `runbooks/` | Operational lessons | Symptom → Root cause → Fix → Prevention. Written when an ops problem is solved, not later. |

Templates: `adr/TEMPLATE.md`, `features/TEMPLATE.md`.

## Quality bar (every document)
- Header: Title · Status · Date created · Date last-verified · Owner.
- Facts verified against the code/output **at writing time** (exact paths, runnable commands, exact routes).
- English body; user-facing Persian strings quoted as-is; absolute dates (`YYYY-MM-DD`).
- One fact lives in exactly ONE place; everything else links to it.
- Deprecated info is marked (strikethrough + date) or superseded — silently deleted history is forbidden in ADRs.

## Related sources of truth
- `CLAUDE.md` (repo root) — conventions, architecture, gotchas. Overrides the stale root `README.md`.
- `.claude/agents/README.md` — the 16-member agent team manual (roster, consultation loop, this doc policy).
- `graphify-out/GRAPH_REPORT.md` — generated architecture map (rebuild with `/graphify backend/apps frontend/src`).
- `backend/DEPLOY_CHECKLIST.md`, `AvalAI-Developer-Documentation.md`, `Hamravesh-Docs-Summary.md`,
  `MEDIANA DOCUMENT.json` — pre-existing operational references.

## Index
- Reference: `reference/README.md` (index + 35-step program checklist) · `reference/00-architecture-overview.md`
- ADRs: `adr/ADR-0001-agentic-team.md` · `adr/ADR-0002-reference-docs-program.md`
- Features: (none yet — created per feature from the template)
- Releases: (started with the next shipped change)
- Runbooks: `runbooks/local-stack.md`
