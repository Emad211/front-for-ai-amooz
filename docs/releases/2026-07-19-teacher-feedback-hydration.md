# Teacher feedback hydration

The exercise gradebook now restores previously saved teacher feedback when a submission is reopened.
The API already persisted and returned `teacher_feedback`; the defect was limited to the editor textarea,
which was initialized as empty instead of using the stored per-question value.

The field remains intentionally uncontrolled: untouched feedback is not resubmitted, while editing or
clearing it sends an explicit update. A backend round-trip regression assertion protects persistence and
the submission-detail response contract.

No migration or environment change is required.
