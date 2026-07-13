# ADR-0006: Mutable exercise-level settings

**Status:** Accepted

**Date:** 2026-07-13

**Supersedes:** ADR-0005's intake-only assistant immutability

## Context

ADR-0005 correctly removed section-level assistant controls, but also made the remaining exercise-level
assistant policy immutable after creation. Teachers need to adjust both the deadline and assistant
availability while reviewing or operating an exercise.

## Decision

- `ClassExercise.assistant_enabled` remains the only assistant policy.
- The teacher may change it from the exercise editor at any time through the owner-scoped exercise PATCH.
- Section-level assistant controls and enforcement remain deprecated and ignored.
- Deadline and assistant settings share one clearly labeled mutable-settings panel and one save action.

## Consequences

No migration or environment change is required. Existing student assistant requests immediately observe
the saved exercise-level value because the server guard reads it on every request.
