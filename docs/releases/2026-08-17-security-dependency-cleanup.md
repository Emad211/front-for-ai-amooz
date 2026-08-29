# 2026-08-17 - Security dependency cleanup

Commits: PR #26 | Scope: frontend + docs

## Changes

- Removed the leaked `MEDIANA_API_KEY` value from `README.md` (replaced with a
  placeholder). The key remains in git history and must be rotated in the
  Mediana dashboard.
- Removed dead frontend dependencies `genkit`, `@genkit-ai/google-genai`,
  `@genkit-ai/next`, `genkit-cli`, and `firebase`, plus the `genkit:*` npm
  scripts. Nothing imported them (`src/ai/` no longer exists) and their trees
  carried 4 critical and dozens of high-severity npm advisories.
- Bumped `next` 15.5.9 → 15.5.23 (patch line) for multiple high-severity
  advisories (cache poisoning, middleware/proxy bypass, SSRF, DoS).
- `npm audit fix` for remaining non-breaking transitive advisories.
  npm audit went from 105 vulnerabilities (4 critical) to 5 (0 critical); the
  remainder need breaking upgrades (`next@16`, `exceljs`) and were left out.

## Migrations

None.

## Env / config

None.

## Rebuild

Rebuild the frontend image (`npm install` picks up the pruned lockfile). The
backend is unchanged.
