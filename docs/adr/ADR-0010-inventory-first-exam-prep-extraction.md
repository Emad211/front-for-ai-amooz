# ADR-0010 — Inventory-first exam-prep extraction

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** product owner, backend engineer, AI engineer
- **Consulted:** database engineer, AI engineer

## Context

The legacy exam-prep pipeline asked one model call to infer questions, options, answers, and solutions
at once. Real booklets may start numbering at any value, place answer keys before or after questions,
mix answers with questions, repeat content across extraction chunks, and contain unrelated answers
from an adjacent booklet. That architecture could turn solutions into new questions, attach an answer
by list position, or invent a solution where the source only contained an answer key.

## Decision

Build a durable source inventory before producing the published projection.

- Classify page/source blocks, then extract question and answer records independently.
- Join records deterministically by normalized section and source question number. A unique-number
  fallback and same-page adjacency are permitted; semantic similarity is never an automatic join.
- Keep source numbering and provenance in a teacher-only artifact while the student projection uses
  stable internal IDs and sequential display numbering.
- Preserve failed chunks and unmatched/out-of-scope records for retry and audit. They never become
  questions implicitly.
- Preserve original source crops as the authoritative visual. A generated candidate is optional,
  automatically compared with the crop, and requires explicit teacher selection.
- Gate publication of version-2 sessions on a passing audit with no critical issue.

## Alternatives considered

- **Improve the single extraction prompt** — rejected because matching and deduplication would remain
  probabilistic and unauditable.
- **Match by array position** — rejected because numbering can start at 51, 78, or 116 and answer
  sections can include records outside the booklet.
- **Replace original figures automatically** — rejected because an attractive redraw can still
  change a label, number, topology, or scientific relationship.

## Consequences

- Positive: question counts and answer joins are deterministic, retryable, and reviewable.
- Positive: PDF, image, audio, and video share the same normalized inventory contract.
- Positive: original files remain in the existing private bucket; no storage service is added.
- Negative: version-2 extraction performs more bounded model calls than the legacy one-call path.
- Negative: generated figures add optional latency and remain unusable until verification and teacher
  approval.
- Accepted risk: audio has no visual source; video visuals depend on sampled frames and therefore may
  require teacher review when a relevant frame was not sampled.
- Follow-up: remove the legacy projection path only after version-2 benchmark and production metrics
  demonstrate acceptable accuracy.

## Dissent

None recorded.
