# Teacher student management

## Product contract

- A real student has an `Enrollment` in at least one teacher class.
- An invitation without an enrollment appears only under `دعوت‌های در انتظار`.
- The teacher can invite several phones to several personal classes in one operation.
- Organization classes are excluded from manual roster changes.
- Profile, direct message, suspend/restore, and remove actions are functional and owner-scoped.
- Excel export is a real filtered `.xlsx` workbook with an RTL worksheet.

## Access and deletion

Suspension affects only the teacher's personal classes and does not disable `User.is_active`. Removal deletes personal enrollments and invitation grants while retaining learning records for audit and potential re-enrollment. Cross-teacher reads and mutations return 404.

## API

- `GET /api/classes/teacher/classes/summary/`
- `GET|POST /api/classes/teacher/student-invitations/`
- `DELETE /api/classes/teacher/student-invitations/<id>/`
- `GET /api/classes/teacher/students/<student_id>/`
- `PATCH /api/classes/teacher/students/<student_id>/access/`
- `DELETE /api/classes/teacher/students/<student_id>/relationship/`

Class list/detail responses expose `students_count`; `invites_count` remains a temporary alias carrying the same real enrollment count.
