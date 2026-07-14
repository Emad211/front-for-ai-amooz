# 2026-07-14 — Figma landing rebuild

Branch: `feature/figma-landing-rebuild` · Scope: frontend-only

## Changes

- Reconstructed the marketing header and hero around the four Figma artboards: desktop/mobile and light/dark.
- Added landing-specific semantic tokens and wide layout shells without changing dashboard design-system contracts.
- Rebuilt the six-item why-us grid with desktop and mobile divider behavior from Figma.
- Rebuilt the feature bento grid with the Figma desktop and mobile proportions.
- Rebuilt the teacher showcase as an interactive four-state product panel.
- Refined testimonial, FAQ, final CTA, and footer hierarchy and spacing.
- Uploaded the supplied teacher screenshots to the connected Adobe workspace for non-destructive preparation. Temporary Adobe URLs are not used in production code.

## Product imagery

The current branch keeps stable repository assets in the teacher showcase so no expiring external URL enters the application. The supplied real teacher screenshots are the approved replacement set for class overview, exam-prep creation, exercise creation, and teacher analytics. Their intended local filenames are centralized in `frontend/src/components/landing/teacher-product-assets.ts`.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Rebuild and deploy the `front` image only.

## Verification

- Code is isolated on `feature/figma-landing-rebuild`; PR #1 remains draft during visual and asset verification.
- Required CI gates: `npm run typecheck`, `npm run lint`, and visual checks at 440px and 1920px in both themes.
- Existing repository lint/typecheck baseline must be reported separately; no clean result is claimed before CI completes.

## Rollback

- Revert the branch commits or close PR #1. No backend or data rollback is required.
