# Adaptive assessment draft persistence

Chapter quizzes and the course final exam keep unfinished student answers in
browser-local storage so a refresh does not erase work that has not yet been
submitted.

## Contract

- Draft keys are scoped by student, course, assessment type, and chapter where
  applicable.
- A draft also stores an assessment version built from the assessment ID and
  ordered question IDs.
- A draft is restored only when its version matches the currently loaded
  assessment. Regenerated adaptive assessments therefore never inherit answers
  from the assessment they replaced.
- Unknown question IDs and malformed values are discarded.
- Drafts are cleared after a successful submit, adaptive regeneration, or the
  student's explicit reset action.
- Submitted attempts remain server-owned. Local drafts are only a resilience
  layer for answers that have not been submitted.

## Scroll ownership

The learning workspace has exactly one vertical scroll owner for lesson
content. The surrounding flex containers use `min-height: 0` and hide overflow;
the inner lesson card owns scrolling. This prevents focused quiz controls from
scrolling nested ancestors and moving the assessment outside the visible
viewport.

## Verification

- `npx tsx --test src/lib/assessment-draft.test.ts`
- `npm run typecheck`
- `npm run build`
