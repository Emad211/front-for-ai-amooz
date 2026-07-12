# ADR-0005: Flat exercise questions and one assistant policy

**Status:** Accepted

**Date:** 2026-07-12

**Supersedes:** ADR-0004's per-section assistant-toggle decision

## Context

Exercise extraction produced `sections[].questions[]` even when the source had no meaningful
headings. That leaked an internal grouping into the teacher and student UI as untitled sections.
The same structure also created two independent assistant controls whose effective policy was
`exercise.assistant_enabled AND section.assistant_enabled`.

## Decision

- Exercise questions are a single ordered list in the product, API, and LLM output contract.
- New extraction returns top-level `questions[]` and persists them in one private, untitled
  `ClassExerciseSection` compatibility row.
- Existing multi-section exercises are flattened at serialization time in section/question order.
- `ClassExercise.assistant_enabled`, captured during initial intake, is the only effective assistant
  policy. It cannot be changed after exercise creation.
- The legacy section-shaped response and section table remain temporarily for compatibility. They
  are not consumed by the current frontend.

## Consequences

No database migration is required for this release. Backend and frontend must deploy together.
Removing the section table and legacy response is a separate future migration after the compatibility
window. Reference-answer reveal and assistant context leak guards are unchanged.
