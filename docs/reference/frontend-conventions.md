# Reference — Frontend conventions (theming, RTL, Persian) + lib catalog

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `79d86f5`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F2
- **Layer:** frontend-layer (conventions + `src/lib/` A-Z index)

## Purpose
The cross-cutting frontend rules — shadcn HSL tokens, dark/light parity, RTL logical utilities, Persian
digit/date formatting, KaTeX math rendering — plus the flat catalog of `src/lib/` utilities. The style
contract every component doc (F5-F11) links back to instead of restating.

## Scope & paths
| File | Role |
|---|---|
| `frontend/src/app/globals.css` | HSL semantic tokens (`:root` + `.dark`) |
| `frontend/src/components/theme-provider.tsx` | next-themes wrapper |
| `frontend/src/lib/*` | utils, persian-digits, persian-option-label, date-utils, normalize-math-text, calendar, auth-routing, classes/course-structure, validations/{auth,onboarding} |
| `frontend/src/components/content/{markdown-with-math,math-text}.tsx` | KaTeX renderers |

**Out of scope:** the app shell/providers → F1; the guards + validation *flow* → F4; component inventory → F11.

## Public surface — `src/lib/` catalog
| Module | Exports (one-line contract) |
|---|---|
| `utils.ts` | `cn(...)` — Tailwind class merge (shadcn standard) |
| `persian-digits.ts` | `toPersianDigits`, `toEnglishDigits`, `formatPersianNumber`, `formatPersianPercent`, `formatPersianDelta` |
| `persian-option-label.ts` | Persian MCQ option labels (الف/ب/…) |
| `date-utils.ts` | `formatPersianDateTime`, `formatPersianDate`, `formatPersianMonthDay` (Jalali) |
| `calendar.ts` | Jalali calendar helpers |
| `normalize-math-text.ts` | `normalizeMathText(input)` — clean LaTeX-ish text before KaTeX |
| `auth-routing.ts` | role→home routing + token helpers (F4) |
| `classes/course-structure.ts` | course-structure shaping for the learn UI |
| `validations/auth.ts`, `validations/onboarding.ts` | zod schemas (F4/F5) |

**Theming tokens** (`globals.css`): HSL semantic vars in `:root` (light) + `.dark` — e.g.
`--background`, `--foreground`, `--primary` (mint green: `160 60% 40%` light / `160 60% 50%` dark),
`--accent`, `--primary-foreground`. Used as `hsl(var(--token))`.

**Math renderers** (`components/content/`): `MarkdownWithMath` (body text), `MathText` (titles/headings).

## Key flows / conventions
1. **Tokens only:** colors via `hsl(var(--…))` — never hardcoded hex, never a token that doesn't exist
   (the phantom `--primary-rgb` gotcha, memory `figma-landing-rebuild`). Verify a token is in `globals.css`
   (both `:root` and `.dark`) before using it.
2. **Dark/light parity is mandatory** — spec both; dark-only decoration uses `hidden dark:block` (the hero
   halo/dot-grid pattern, memory `figma-landing-rebuild`).
3. **RTL-first:** logical utilities (`ps-/pe-`, `ms-/me-`, `start/end`) not `pl-/pr-`; direction-implying
   icons flip per direction.
4. **Persian formatting:** digits via `persian-digits`, Jalali dates via `date-utils`/`calendar` — never
   `toLocaleString('en')` or raw Gregorian in UI.
5. **Math:** body → `MarkdownWithMath`, titles → `MathText` (memory `title-math-rendering`); never render
   raw LaTeX strings; pre-clean with `normalizeMathText`.

## Data & invariants
- shadcn HSL semantic tokens only; a hardcoded color or a nonexistent token is a review finding.
- Dark/light parity + `hidden dark:block` for dark-only decoration.
- RTL logical utilities everywhere; the app is globally `dir="rtl"` (F1).
- Persian digits + Jalali dates via the lib utils — the single source; don't reimplement.
- `MathText` for titles / `MarkdownWithMath` for body — the fixed split.
- Forms use react-hook-form + zod schemas in `validations/` (canonical multi-step example:
  `onboarding.ts`, F4).

## Gotchas
- `--primary-rgb` and similar `*-rgb` tokens do NOT exist — check `globals.css` before referencing a token.
- Persian numerals must stay Persian even inside mixed Persian text — use the util, not the browser locale.
- `normalize-math-text` overlaps `math-text.tsx`'s rendering — normalize is the pre-clean, MathText is the
  render; don't duplicate logic across them.

## Cross-links
[frontend-app-shell.md](frontend-app-shell.md) (F1, the RTL shell) · [frontend-auth-guards.md] (F4,
`auth-routing` + validations) · [frontend-shared-ui.md] (F11, components using `cn`) · [backend-classes-student-views.md](backend-classes-student-views.md)
(B6, the math-bearing content) · memory: `title-math-rendering`, `figma-landing-rebuild` ·
`.claude/agents/ux-designer.md`, `frontend-engineer.md`.

## Verified-by
- `Glob src/lib/**/*.ts` → the 10-module catalog above.
- `rg "export (function|const)"` on `persian-digits.ts` (5 fns), `date-utils.ts` (3 Jalali fns),
  `normalize-math-text.ts` (`normalizeMathText`) → the export contracts.
- `rg "--primary|--background|hsl\(var"` `globals.css` → HSL tokens in `:root` + `.dark` (mint
  `--primary` values cited).
- `Glob components/content/*.tsx` → `markdown-with-math.tsx` + `math-text.tsx`.
- NOT read whole: lib bodies (grep gives the export contract). NOT run this pass: tsc/lint (F-layer AUDIT gate).
