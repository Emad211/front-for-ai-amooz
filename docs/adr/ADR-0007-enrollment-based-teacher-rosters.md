# ADR-0007: Enrollment-based teacher rosters

## Status

Accepted — 2026-07-13

## Decision

Teacher-facing student counts and rosters use `Enrollment` as the definition of a real student. `ClassInvitation` represents pending delivery/access metadata and is not counted as enrollment.

A student enrolled in several classes is counted once in teacher-wide totals and once in each relevant class. Teacher suspension is owner-scoped through `TeacherStudentAccess`; it never changes the platform account. Organization class rosters remain controlled by organization study groups.

## Consequences

- Class cards, teacher student lists, analytics, message recipients, and workspace summaries share the same Enrollment-based definition.
- Pending invitations are displayed separately.
- Removing a student from personal classes removes active relationships but preserves progress, attempts, submissions, and the user account.
- Legacy student endpoints still authorize with class invitations. Suspension therefore atomically removes personal-class invitation grants and restoration recreates them from retained enrollments until all student gates migrate to the centralized policy service.
