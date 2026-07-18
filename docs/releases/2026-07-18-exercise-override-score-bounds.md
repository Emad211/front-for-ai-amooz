# Exercise override score bounds

Teacher grade overrides can no longer exceed a question's configured maximum or fall below zero.
The gradebook validates the range before submission, while the API remains the authoritative guard
and rejects the entire override batch when any score is malformed, non-finite, or out of range.
Clearing the manual-score input now sends an explicit `null`, removes the override, recomputes the
submission from the preserved AI score, and clears the current teacher-edit badge when no other manual
score or feedback remains.

The effective-score calculation also bounds legacy values defensively. Data migration `0031` clamps
historical finite overrides to `0..max_points`, clears malformed overrides, and recomputes affected
per-question and submission totals. Its reverse is intentionally a no-op because invalid historical
scores cannot be reconstructed safely.

Deployment requires the usual backend migration and coordinated frontend release. No environment
variable or service topology change is required.
