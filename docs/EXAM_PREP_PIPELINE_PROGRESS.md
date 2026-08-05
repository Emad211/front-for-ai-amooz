# Exam Prep PDF Pipeline — Progress Log

## 2026-08-05 — Layout, content integrity, and cancellation hardening

Baseline evidence from live session 191:

- 16 physical PDF pages.
- Page 1 was a cover but consumed four requests and became a failed chunk.
- Pages 9–16 used a full-page request plus two column requests.
- 40 AvalAI requests total.
- 50 questions assembled; one visible review question, but additional deterministic
  output defects existed (serialized options, missing gradable labels, copied solution).

Implemented on branch `fix/exam-prep-layout-content-integrity`:

1. Local cover/non-content classifier with zero-call skip.
2. Local single/double/uncertain layout router.
3. One multi-image request for uncertain layout.
4. Two-call double-column path with retry limited to the failed column.
5. Loose page envelope and independent record quarantine.
6. Deterministic serialized-option decoding.
7. Persian combining-hamza correct-option inference.
8. Missing gradable option-label gate.
9. Cross-question duplicate-solution detection.
10. Cancellation-aware targeted verifier.
11. Per-page and final provider-call accounting.
12. Focused regression tests for the new contracts.

Remaining verification before merge:

- Run the full backend suite once at the end.
- Run frontend/type checks once at the end.
- Re-run the same 16-page PDF in the deployed environment.
- Compare output and Celery logs against the session-191 baseline.
- Confirm the actual request count and inspect any new edge cases.
