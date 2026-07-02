# Reference — Frontend marketing landing `(marketing)`

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `4bc587b`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F10 (thin index)
- **Layer:** frontend-route-group (public landing)

## Purpose
The public marketing landing — a thin index. The rebuild narrative + gotchas live in memory
`figma-landing-rebuild`; this doc is the section map + pointers, not a re-derivation.

## Scope & paths
| Path | Role |
|---|---|
| `frontend/src/app/(marketing)/page.tsx` | the landing page |
| `frontend/src/components/landing/` (10) | header, footer, feature-card + `sections/` |
| `frontend/src/services/landing-service.ts` · `hooks/use-landing.ts` | landing data |

**Out of scope:** theming/RTL rules → F2; shared header/footer patterns → F11.

## Public surface — sections (`components/landing/`)
`header.tsx`, `footer.tsx`, `feature-card.tsx`, and `sections/`: `hero-section`, `features-section`,
`why-us-section`, `teacher-cta-section`, `final-cta-section`, `faq-section`, `testimonial-section`.

## Key flows
1. Theme-aware RTL landing built from the Figma dark/light + desktop/mobile redesign (memory
   `figma-landing-rebuild`, commit `e2e975b`).
2. **Dark hero decoration** (`hero-section.tsx`): a faint green halo ring + dot-grid background, both
   **dark-only** via `hidden dark:block` (commit `90ea7cf`) — the canonical dark-only decoration pattern
   (F2).
3. Landing content via `use-landing` → `landing-service` (F3).

## Data & invariants
- Theme-aware via shadcn semantic tokens (F2); dark/light + desktop/mobile parity.
- The dark-only hero halo + dot-grid use `hidden dark:block` (F2 pattern) — don't render them in light mode.
- Phantom-token gotcha applies (the `--primary-rgb` non-token — memory `figma-landing-rebuild`); verify a
  token exists before use.
- Persian + RTL (F2).

## Gotchas
- This is a thin index — the real history (Figma-MCP rate-limit workaround, phantom-token bug, the
  section restructure) is in memory `figma-landing-rebuild`; don't restate it here.
- The hero's dark-only layers must stay `hidden dark:block` — a refactor that drops the guard leaks the
  halo/dot-grid into light mode.

## Cross-links
[frontend-conventions.md](frontend-conventions.md) (F2, tokens + `hidden dark:block`) ·
[frontend-app-shell.md](frontend-app-shell.md) (F1, the shell) · [frontend-services-hooks.md](frontend-services-hooks.md)
(F3, `use-landing`) · [frontend-shared-ui.md] (F11) · memory: `figma-landing-rebuild` ·
`.claude/agents/ux-designer.md`.

## Verified-by
- `Glob components/landing/**/*.tsx` → the 10 landing components (header, footer, feature-card, 7
  sections) tabulated above.
- `(marketing)/page.tsx` confirmed in the F1 route inventory.
- The dark-halo/dot-grid + Figma rebuild facts are cross-referenced to memory `figma-landing-rebuild`
  and CLAUDE.md's recent-commit notes (`e2e975b`, `90ea7cf`) — not independently re-derived (thin index).
- NOT read whole: section component bodies. NOT run this pass: tsc/lint (F-layer AUDIT gate).
