# 2026-07-14 — Figma landing rebuild

Branch: `feature/figma-landing-rebuild` · Pull request: `#1` · Scope: frontend-only

## Changes

- Reconstructed the marketing header and hero against the four source artboards: desktop/mobile and light/dark.
- Added landing-specific semantic tokens and 1920px-wide layout shells without changing dashboard design-system contracts.
- Rebuilt the six-item why-us area with the distinct desktop/mobile ordering and divider rules from Figma.
- Rebuilt the feature bento grid with the exact desktop and mobile card proportions.
- Rebuilt the teacher showcase as an accessible four-state product panel with hover, focus, click, and mobile icon-tab controls.
- Replaced placeholder teacher visuals with real class-overview, exam-prep, exercise, and analytics captures supplied by the product owner.
- Refined the usage-scenario carousel, FAQ, final CTA, and footer hierarchy and spacing.
- Disabled unconfigured social/legal links rather than shipping placeholder `#` navigation.
- Removed unverified personal identities, exam ranks, and outcome claims from the public usage-scenario copy.

## Product imagery

- Teacher captures were cropped non-generatively in Adobe and committed as local PNG assets under `frontend/public/landing/`; no expiring Adobe URL is used at runtime.
- Personal header details, browser scrollbars, and the teacher navigation sidebar are outside the final visible crops.
- The asset contract is centralized in `frontend/src/components/landing/teacher-product-assets.ts`.
- Decorative frame, laptop badge, glow, border, and responsive cropping are CSS concerns so the original Persian product UI remains unchanged.
- Local screenshots and bento assets use Next Image optimization with responsive `sizes` and quality `90`.

## Visual verification

A production build was started locally in GitHub Actions and rendered with headless Chromium after scrolling through the full page so every in-view section reached its rendered state.

Verified full-page captures:

- Desktop dark: `1920px` viewport · document height `6668px`.
- Desktop light: `1920px` viewport · document height `6668px`.
- Mobile dark: `440px` viewport · document height `7499px`.
- Mobile light: `440px` viewport · document height `7499px`.

The measured section boundaries match the Figma coordinates exactly:

| Section | Desktop y / height | Mobile y / flow height |
|---|---:|---:|
| Hero | `0 / 1200` | `0 / 1004` |
| Why us | `1200 / 633` | `1004 / 1411` |
| Features | `1833 / 1149` | `2415 / 1443` |
| Usage scenarios | `2982 / 768` | `3858 / 772` |
| Teacher tools | `3750 / 848` | `4630 / 827` |
| FAQ | `4598 / 805` | `5457 / 743` |
| Final CTA | `5403 / 768` | `6200 / 512` |
| Footer | `6171 / 497` | `6712 / 787` |

The four rendered images were visually reviewed for ordering, RTL direction, image clipping, card overflow, theme contrast, and footer completion. Hero devices and teacher imagery are on the left in desktop layouts, while Persian copy remains right-aligned, matching the source artboards.

## Fonts

- Vazirmatn remains the licensed/project-available font used by the application.
- Figma uses Peyda for display headings. Pixel-identical display-font metrics require a licensed Peyda webfont supplied to the repository; no font file was copied or fabricated in this change.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Rebuild and deploy the `front` image only.

## Automated verification and known baselines

- The visual-QA production build, local server start, Chromium capture, and artifact upload completed successfully.
- Vercel preview builds for the final application changes completed successfully.
- `npm run typecheck`: the repository compiler reports the same 13 pre-existing errors in admin tickets, notification service typing, exam edit, and mock message recipients; no changed Landing file appeared in the captured error output.
- `npm run lint`: blocked before file analysis by the existing circular ESLint configuration in `frontend/.eslintrc.json` (`next lint` / React plugin serialization); therefore no clean lint result is claimed.
- The repository-wide PostgreSQL backend job is outside this frontend-only scope and is not claimed as passing by this release note.

## Rollback

- Revert the branch commits or close PR #1. No backend or data rollback is required.
