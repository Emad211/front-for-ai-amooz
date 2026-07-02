# Reference — Frontend shared component library (ui / shared / layout / content)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `dcc72c3`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F11
- **Layer:** frontend-layer (the shared component catalog every group reuses)

## Purpose
The reusable UI substrate: shadcn primitives (`ui/`), the app shell (`layout/` headers/sidebars/nav),
shared states (`shared/`), and the math renderers (`content/`). A reference catalog so per-group docs
link a component instead of re-describing it.

## Scope & paths
| Dir | Contents |
|---|---|
| `components/ui/` (39) | shadcn primitives (below) |
| `components/layout/` (13) | header, dashboard/teacher/admin header+sidebar, `sidebar-content`, `mobile-nav`, `user-profile`, `workspace-switcher` |
| `components/shared/` (1) | `error-state` |
| `components/content/` (2) | `markdown-with-math`, `math-text` |

**Out of scope:** the theming tokens + `cn` → F2; the math-render rule → F2; per-group usage → F5-F10.

## Public surface
**`ui/` primitives (39, shadcn/Radix):** accordion, alert(+dialog), avatar, badge, button, calendar,
carousel, card, chart, checkbox, collapsible, dialog, dropdown-menu, form, input, label, logo, menubar,
page-transition, popover, progress, radio-group, scroll-area, select, separator, sheet, sidebar (the
large one), skeleton, slider, switch, table, tabs, tag-badge, textarea, theme-toggle, toast, toaster,
tooltip. Customized-beyond-stock: `logo`, `page-transition`, `tag-badge`, `theme-toggle`, the big
`sidebar`, `chart`.

**`layout/` shell:** per-role header+sidebar (`dashboard-header`, `teacher-header`/`teacher-sidebar`,
`admin-header`/`admin-sidebar`), `header`, `sidebar-content`, `mobile-nav`, `user-profile`,
`workspace-switcher` (F8).

**`shared/`:** `error-state`. **`content/`:** `markdown-with-math` (body), `math-text` (titles) — F2/B6.

## Key flows
1. Every screen composes these primitives via `cn` (F2); forms use `ui/form` + react-hook-form (F2/F4).
2. The layout shell (header + sidebar + mobile-nav) wraps each route group; `user-profile` +
   `workspace-switcher` (F8) sit in the header; nav menus differ per role (F7/F8/F9).
3. Math content anywhere renders through `content/` (never raw LaTeX).

## Data & invariants
- shadcn primitives use the F2 HSL tokens + `cn` — a primitive with hardcoded colors is a finding.
- Primitives should be RTL-audited (logical utilities, F2) — the app is globally `dir="rtl"`.
- Direction-implying icons in `layout` nav must flip per direction (F2).
- `content/` renderers are the ONLY place raw markdown/LaTeX becomes rendered KaTeX (F2 split:
  `markdown-with-math` body / `math-text` titles).
- Toasters (`toast`/`toaster` + the sonner instance in the root layout, F1) are the notification surface.

## Gotchas
- `ui/sidebar.tsx` is the large composable sidebar primitive; the per-role `layout/*-sidebar` compose it
  — don't confuse the primitive with the role shells.
- Most `ui/` files are stock shadcn; the customized ones (logo, theme-toggle, tag-badge, page-transition,
  sidebar, chart) are where project-specific behavior lives — check those before assuming stock behavior.
- `shared/` has only `error-state` — most "shared" state components actually live per-group; this is the
  cross-group one.

## Cross-links
[frontend-conventions.md](frontend-conventions.md) (F2, tokens/`cn`/math rule) · [frontend-app-shell.md](frontend-app-shell.md)
(F1, root layout + toasters) · [frontend-org.md](frontend-org.md) (F8, workspace-switcher) · F5-F10 (the
screens composing these) · `.claude/agents/ux-designer.md`, `frontend-engineer.md`.

## Verified-by
- `Glob components/ui/*.tsx` → the 39 primitives listed above.
- `Glob components/{shared,layout,content}/*.tsx` → layout (13), shared (1 = `error-state`), content (2).
- Math-renderer split cross-checked against F2 + memory `title-math-rendering`.
- NOT read whole: primitive bodies (catalog by glob; behavior contract is shadcn-standard + F2 tokens).
  NOT run this pass: tsc/lint (F-layer AUDIT gate).
