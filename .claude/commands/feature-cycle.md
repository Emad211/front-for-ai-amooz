---
description: چرخه کامل ساخت فیچر با تیم ایجنتیک — اسپک → طراحی → ساخت → تست → بازبینی → مستند → انتشار (هزینه توکن دارد)
argument-hint: <شرح فیچر>
---

The user has EXPLICITLY started a team feature cycle for: **$ARGUMENTS**

You (the main session) orchestrate; agents execute. Run the stages in order, report progress to the user
in Persian between stages (one short line each), and enforce every gate. Roster + consult matrix:
`.claude/agents/README.md`.

1. **SPEC** — `product-manager` writes `docs/features/<slug>.md` (problem, personas, stories with
   acceptance criteria, scope in/out, success metrics).
   **GATE:** show the user the scope summary (Persian) and get approval before any design/code.
2. **DESIGN** — `tech-lead` produces the implementation plan; pull in `ux-designer` (any UI),
   `database-engineer` (any schema), `ai-engineer` (any LLM). Architectural/irreversible choices → ADR.
   **GATE:** you (main session) check the plan against CLAUDE.md conventions and flag conflicts.
3. **BUILD** — the relevant engineers (`backend-engineer` / `frontend-engineer` / `ai-engineer`)
   implement in small, independently verifiable slices; each slice lands WITH its tests
   (regression-first; negative tests for any permission).
4. **VERIFY** — `qa-engineer`: backend suite + targeted new tests; frontend `typecheck`+`lint`
   (0 NEW errors); prompts contract test if prompts were touched. Red gate → back to stage 3.
5. **REVIEW** — `code-reviewer` on the full diff; PLUS `security-auditor` if the diff touches
   auth/permissions/tenancy/uploads/data exposure. BLOCKER/MAJOR findings → back to stage 3.
6. **DOCUMENT** — `technical-writer`: finalize the feature doc (Status → Shipped-pending-release),
   link ADRs, add/refresh runbook if ops changed. Verify every stage's `Docs:` handoff line landed.
7. **SHIP** — `release-manager`: pre-push gate (tests, typecheck, `makemigrations --check`), clean
   `git status`, atomic commits (`type(scope): summary`), push, and the release note in
   `docs/releases/YYYY-MM-DD-<slug>.md` (migrations? env? rebuild targets? rollback?).

Cost guards: stages 3–5 may loop at most TWICE without checking in with the user; if the feature is
clearly large (>1 day of work), propose phases at stage 1 instead of one giant cycle.
