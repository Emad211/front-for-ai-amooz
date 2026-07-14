# 2026-07-14 — Figma landing rebuild

Branch: `feature/figma-landing-rebuild` · Scope: frontend-only

## Changes

- Reconstructed the marketing header and hero around the four Figma artboards: desktop/mobile and light/dark.
- Added landing-specific semantic tokens and wide layout shells without changing the dashboard design system.
- Rebuilt the six-item why-us grid with the desktop and mobile divider behavior from Figma.
- Rebuilt the feature bento grid with the Figma desktop and mobile proportions.
- Rebuilt the teacher showcase as an interactive four-state product panel.
- Refined testimonial, final CTA, and footer to the Figma hierarchy and spacing.
- Uploaded the supplied teacher screenshots to the connected Adobe workspace for non-destructive preparation. Temporary Adobe URLs are not used in production code.

## Product imagery

The first code pass keeps stable repository assets in the teacher showcase so no expiring external URL enters the app. The supplied real teacher screenshots are the approved replacement set for class overview, exam-prep creation, exercise creation, and teacher analytics. They must be committed as local web assets before merge.

## Migrations

- None.

## Env / config

- None.

## Rebuild

- Rebuild and deploy the `front` image only.

## Verification

- Code was isolated on a feature branch for pull-request CI.
- Required CI gates: `npm run typecheck`, `npm run lint`, and visual checks at 440px and 1920px in both themes.
- Existing repository lint/typecheck baseline must be reported separately; no clean result is claimed before CI completes.

## Rollback

- Revert the commits on `feature/figma-landing-rebuild` or close the pull request. No backend or data rollback is required.
