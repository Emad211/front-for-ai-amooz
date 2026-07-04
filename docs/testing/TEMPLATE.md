# T<NN> — <step title>

- **Layer(s):** unit | service | api | integration | benchmark | frontend
- **Scope:** <app / module / feature under test>
- **Owner role:** qa-engineer | backend-engineer | ai-engineer | frontend-engineer
- **Depends on:** T<NN> (must be done first) | none

## Goal
One line: what capability/behavior is proven GREEN after this step.

## What to test (cases)
- Happy path(s): …
- **Negative / auth (required for any permission-touching step):** 401 unauth, 403 forbidden, cross-tenant.
- Edge cases: empty/malformed input, idempotency, cancellation, boundary scores.

## Fixtures / mocks needed
- Reuse from T3 shared factories: <which>.
- LLM client mocked (never a real key outside `benchmark`): <how>.

## Files
- Test files touched/created: `backend/apps/<app>/test_<name>.py` (absolute paths in the commit).
- Any conftest/factory additions.

## Definition of done (this step)
- [ ] Tests GREEN on Postgres (Docker).
- [ ] Coverage delta reported in commit body; floor not dropped.
- [ ] No NEW failures vs baseline.
- [ ] Negative auth tests present (if applicable).
- [ ] `README.md` checklist ticked + this file marked done with commit sha.

## Notes / dissent
<record any specialist disagreement on scope or ordering here>
