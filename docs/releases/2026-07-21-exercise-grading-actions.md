# Exercise grading action states

Teacher grading actions now follow the finalized Attempt state instead of
appearing as disabled or ineffective controls:

- `SUBMITTED` and `GRADING` show a live processing message and poll every four
  seconds. Manual override and redo controls are not rendered.
- `GRADED` exposes both manual override and redo.
- `GRADING_FAILED` exposes redo but not an invalid manual override form.
- Historical Attempts remain read-only and display saved teacher feedback.
- Gradebook row actions use status-specific labels instead of always promising
  grading capability.

The API already enforced the same policy with fail-closed `409` responses.
Regression tests now cover override and redo attempts in both pending states.

No schema, migration, endpoint, queue, environment variable, or deployment
topology changed.
