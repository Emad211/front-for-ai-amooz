# <Feature name> — <one-line value statement>

- **Status:** Draft | Approved | Shipped · **Created:** YYYY-MM-DD · **Last-verified:** YYYY-MM-DD
- **Owner:** product-manager · **Spec by:** … · **Built by:** …

## Problem
Who hurts, how, today. (Persona: STUDENT / TEACHER / MANAGER / ADMIN.)

## Stories & acceptance criteria
- As a <persona>, I want <capability>, so that <outcome>.
  - **Given** … **When** … **Then** …

## Scope
- **In:** …
- **Out (explicitly):** …
- **Later phases (named, deferred):** …

## UX
Flow, states (empty/loading/error/success), breakpoints, and the Persian copy table
(`key → متن فارسی`). Owner: ux-designer.

## Design (technical)
Plan summary + link to ADR(s) if architectural. Owner: tech-lead.

## Data
Models/constraints touched, migration list (+ DML/DDL split), rollback note. Owner: database-engineer.

## API
Endpoints (route, method, auth, request/response shape, error codes). Contract agreed
backend ↔ frontend before build.

## LLM (if applicable)
Prompt keys + strategies, output contract, env knobs (+defaults), expected token cost. Owner: ai-engineer.

## Testing
What's covered (files), how to run, what's deliberately untested and why. Owner: qa-engineer.

## Security notes
Authz matrix for the new surface; findings + resolutions (dated). Owner: security-auditor.

## Metrics
Success metric definitions (formula, window, timezone=Asia/Tehran, exclusions). Owner: data-analyst.

## Rollout
Migrations? Env vars? Rebuild targets (backend/front)? Flags? Link to the release note.
