# ADR-0001 — Adopt a permanent 16-member agent team with a consultation loop and docs law

- **Status:** Accepted
- **Date:** 2026-07-02 · **Deciders:** user (Emad) + main assistant session · **Consulted:** —

## Context
AI-Amooz has grown into a real multi-tenant product (LLM pipeline, orgs/managers, adaptive assessments,
waitlist, analytics) built by one person + an AI assistant. Upcoming work is "hard new features + raise
overall app quality". Knowledge was accumulating in chat sessions and machine-local memory instead of the
repo; there was no standing structure for specialist review (security, DB migrations, prompts) and no
enforced documentation habit.

## Decision
Create a permanent, repo-committed team of 16 specialist subagents in `.claude/agents/` (the path Claude
Code resolves project agents from), each encoding this repo's hard-won rules for its specialty, bound by:
1. a **consultation loop** — a mandatory-consult matrix + a standard handoff block
   (`Decisions/Files/Docs/Risks/Consult next`) ending every agent report;
2. a **documentation law** — code and its docs land together, in the new `docs/` tree
   (`adr/`, `features/`, `releases/`, `runbooks/`);
3. a **token-cost rule** — agents run only on explicit user request or via the `/council` and
   `/feature-cycle` commands; by default the main session works solo and reads the agent files as
   zero-cost expert checklists;
4. `model: inherit` everywhere; the two auditors (`security-auditor`, `code-reviewer`) are read-only by tool policy.

Roster: product-manager, tech-lead, backend-engineer, frontend-engineer, ai-engineer, database-engineer,
devops-engineer, qa-engineer, security-auditor, code-reviewer, ux-designer, technical-writer,
performance-engineer, debugger, data-analyst, release-manager.

## Alternatives considered
- **A few generic agents (explore/plan/review only)** — rejected: doesn't encode role-specific project
  scars (migration DML/DDL split, prompt contract, RTL rules), which is where real review value is.
- **External tooling (CI bots, SaaS review)** — rejected for now: the constraint is expertise-in-context,
  not automation; also keeps everything local/free.
- **More than 16 (separate prompt-engineer, SRE, scrum roles)** — rejected: overlap without new coverage;
  16 covers every needed discipline for this codebase.

## Consequences
- Positive: durable team knowledge in-repo; every risky dimension (auth, schema, prompts, deploy) has a
  named reviewer; documentation becomes enforced instead of aspirational.
- Negative / accepted risk: agent files must be maintained like code (stale rules would mislead);
  multi-agent runs cost tokens — mitigated by the explicit-invocation rule and cost guards in both commands.
- Follow-ups: team manual at `.claude/agents/README.md`; docs policy at `docs/README.md`; each agent
  updates its own file when it learns a new failure mode.

## Dissent
None recorded.
