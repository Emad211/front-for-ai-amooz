# ADR-0002 — Establish `docs/reference/` and a 35-step looped codebase-documentation program

- **Status:** Accepted
- **Date:** 2026-07-02 · **Deciders:** tech-lead (council chair) + user (Emad)
- **Consulted:** technical-writer, backend-engineer, frontend-engineer, ai-engineer (5-member council, parallel)

## Context
The user ordered: read the ENTIRE codebase and document everything, step by step, in a loop, with the
team deciding the steps. The repo had no structural reference documentation — knowledge lived in
CLAUDE.md (conventions), machine-local memory files (history), and heads. A councilor also corrected the
intake map: `authentication`, `chatbot`, `material` ARE real installed apps (`core/settings.py:57,62,63`);
`chatbot` is service-only (hosts the `llm_client.py` god node), `material` is empty.

## Decision
Create **`docs/reference/`** — one reusable module-reference doc shape (`TEMPLATE.md`, with a mandatory
`Verified-by` evidence section), a **35-step dependency-ordered roadmap** (`ROADMAP.md`: S1 overview ·
B0–B9 backend · L1–L10 LLM · F1–F11 frontend · I1–I2 infra · final AUDIT), and a **`README.md` progress
checklist as the loop's control file** — executed **one step per loop iteration** (hard cost guard), each
step committed as `docs(reference): <ID> <module>` with the checklist flipped in the same commit.
L3 (PROMPTS contract) and L4 (pipeline orchestration) are hub docs all stage docs link into.

## Alternatives considered
- **Fold into `docs/features/`** (proposed by backend/frontend engineers) — rejected: features are
  behavior specs with a ship lifecycle; reference is a structural map re-verified on code change.
  Mixing the axes rots both. (Dissent recorded below.)
- **One giant ARCHITECTURE.md** — rejected: unmaintainable, not resumable, blows any token budget.
- **Chair's original 16 coarse steps** — refined to 35 verified slices: the specialists measured the
  real file sizes (`classes/views.py` 5199 lines forced a 3-way split; 48-file component dirs forced
  [a/b] splits) and the finer grain keeps every loop iteration small — which is the cost guard.

## Consequences
- Positive: deterministic resume (first ☐ in the checklist); every doc auditable via `Verified-by`
  re-runnable commands; durable contracts (env knobs, output keys, guards) finally live in-repo instead
  of machine-local memory.
- Negative / accepted risk: 35 iterations of real token cost (user explicitly commissioned it); doc rot
  risk mitigated by `Last-verified` + the docs-land-together law; the knowledge graph (2026-06-19) is
  ~2 weeks stale, so every step verifies with grep, never the graph alone.
- Follow-ups: the pending `generate_structured` migration (recap/prereqs/quizzes/exam_prep_structure)
  gets documented as pending in L2/L7; live-LLM claims are marked unverifiable-locally (VPN).

## Dissent
backend-engineer and frontend-engineer proposed housing these docs under `docs/features/` (frontend as
`docs/features/frontend/`). Chair overruled per the lifecycle-axis argument; both slices were adopted
otherwise unchanged. backend-engineer's "chatbot is code-empty" claim was corrected by ai-engineer's
verification of `chatbot/services/llm_client.py` (service-only app, no HTTP surface) — resolved, covered
in L1.
