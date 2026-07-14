# 2026-07-14 — Figma landing rebuild

Branch: `feature/figma-landing-rebuild` · Scope: frontend-only

## Changes

- Reconstructed the marketing header and hero around the four Figma artboards: desktop/mobile and light/dark.
- Added landing-specific semantic tokens and wide layout shells without changing dashboard design-system contracts.
- Rebuilt the six-item why-us grid with desktop and mobile divider behavior from Figma.
- Rebuilt the feature bento grid with the Figma desktop and mobile proportions.
- Rebuilt the teacher showcase as an interactive four-state product panel.
- Replaced placeholder teacher visuals with real class-overview, exam-prep, exercise, and analytics captures supplied by the product owner.
- Refined testimonial, FAQ, final CTA, and footer hierarchy and spacing.

## Product imagery

- The teacher captures were cropped non-generatively in Adobe and committed as local PNG assets under `frontend/public/landing/`; no expiring Adobe URL is used at runtime.
- Personal header details, browser scrollbars, and the teacher navigation sidebar are outside the final visible crops.
- The asset contract is centralized in `frontend/src/components/landing/teacher-product-assets.ts`.
- Decorative frame, glow, border, and responsive cropping remain CSS concerns so the original Persian UI text stays unchanged.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Rebuild and deploy the `front` image only.

## Verification

- Code is isolated on `feature/figma-landing-rebuild`; PR #1 remains draft during CI and visual verification.
- `npm run typecheck`: the compiler reports only the 13 pre-existing errors in admin tickets, notification service typing, exam edit, and mock message recipients; no changed Landing file appears in the error output.
- `npm run lint`: blocked before file analysis by the existing circular ESLint configuration in `frontend/.eslintrc.json` (`next lint` / React plugin serialization); no Landing lint finding was produced.
- Remaining release gate: visual checks at 440px and 1920px in both themes.

## Rollback

- Revert the branch commits or close PR #1. No backend or data rollback is required.
