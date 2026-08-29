# Runbook: backend image build stalls for hours at the apt-get layer

**Date:** 2026-08-29 · **Scope:** `backend/Dockerfile` (Darkube production build)

## Symptom

Darkube backend rebuild hangs ~1 hour at the apt-get layer (step 3/9), then either
completes very slowly or the 2h build limit kills it. Log shape:

```
#10 60.37 Ign:1 http://deb.debian.org/debian trixie InRelease
#10 78.07 Get:2 http://deb.debian.org/debian trixie-updates InRelease [47.3 kB]
```

A 47 kB InRelease taking 78 s is the tell: not a Docker problem, a network problem.

## Root cause

1. `deb.debian.org` is served by **Fastly**, which heavily throttles Iranian IPs
   (sanctions). The ffmpeg + weasyprint dependency set (≈ 200 MB) fetched
   serially (`Pipeline-Depth=0`) with 10 retries per file turns into an
   hour-long stall.
2. **Regression history:** the Dockerfile originally pointed apt at the
   in-country mirror (ArvanCloud). Commit `e3827d3` (2026-06-05, "س") dropped
   that block and switched to the official CDN. Ten days later, commit
   `598c6e5` (2026-06-15, "harden image builds on flaky networks") added
   `Acquire::Retries=10` / `Pipeline-Depth=0` — retry flags over a blocked CDN
   make the stall *longer*, not shorter. They paper over the symptom.
3. `ENV BUILD_VERSION` used to sit **above** the apt layer. It is a manual
   cache-busting knob (nothing reads it at runtime), so bumping it on every
   redeploy invalidated the apt/pip layer caches and forced the full
   re-download every time.

## Fix applied (2026-08-29)

- `sed` the deb822 sources file (`/etc/apt/sources.list.d/debian.sources`) so
  the main Debian repo points at `https://mirror.arvancloud.ir/debian`. Only
  main is mirrored; `debian-security` stays on the official host (tiny
  traffic; the mirror's security path was unreliable historically).
- Base image pulled via `hub.hamdocker.ir/library/python:3.12-slim`
  (Hamravesh's Docker Hub proxy; `library/` prefix required for official
  images).
- `ENV BUILD_VERSION` moved **below** the pip layer: bumping it now only
  invalidates source-copy layers, never apt/pip.
- Retry flags kept (retries=5) as belt-and-braces only.

## If it stalls again

- Read the build log: does apt still hit `deb.debian.org`? Then the sed no
  longer matches — most likely the base image moved to a newer Debian release
  (trixie → next) and the sources file path/format changed. Update the sed.
- From a Darkube app Terminal, verify
  `curl -I https://mirror.arvancloud.ir/debian/dists/<suite>/InRelease`.
  If ArvanCloud is down, switch the sed target to `mirror.pardisco.co/debian`.
- Remember: the apt layer re-runs only when the base image digest changes or
  builder cache is evicted. Do not "fix" a slow apt layer by bumping
  `BUILD_VERSION` — it is deliberately below the cache lines now.
- If the pip layer becomes the slow one (`files.pythonhosted.org` is also
  Fastly), the same class of fix applies, but no in-country PyPI mirror is
  currently configured.
