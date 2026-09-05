# Grade 9 shared Exam Prep MVP

- **Status:** Ready for production demo · **Created:** 2026-09-03 · **Last-verified:** 2026-09-05
- **Owner:** product team · **Built by:** engineering

## Scope

This MVP supports one shared, published grade 9 Exam Prep exam. The seed flow creates or reuses one published `ClassCreationSession`, creates ten student accounts, and creates an invitation for each student. Students use their account and invitation access to open the same exam. The result importer then records finalized results for those invited students without invoking an LLM.

The seeded demo teacher is `grade9_demo_teacher`. The default roster contains exactly ten students. A custom roster must also contain exactly ten rows with unique phone numbers.

## Seed order

Run management commands from `backend/`, after the database is available and migrations have been applied.

### Seed from an exam JSON file

```bash
python manage.py seed_grade9_exam_mvp --from-exam-json path/to/exam.json
```

The command interface requires either `--from-exam-json` or `--session-id`. Provide an exam JSON file when creating or reusing the deterministic seeded session.

### Attach the default ten students to an existing published exam

```bash
python manage.py seed_grade9_exam_mvp --session-id <published_exam_prep_session_id>
```

`--session-id` must identify a published `EXAM_PREP` session. Do not pass it together with `--from-exam-json`.

### Provide a custom ten student roster

```bash
python manage.py seed_grade9_exam_mvp \
  --from-exam-json path/to/exam.json \
  --students-file path/to/students.json
```

`--students-file` accepts either a JSON array, a JSON object with a `students` array, or a CSV file with `name`, `phone`, and optional `password` columns. The command rejects a roster unless it has ten rows and ten unique phones. Re-running the seed is idempotent for the seeded session, accounts, invitation rows, and permanent invite codes.

The command prints each student's `username`, `phone`, `password`, and `invite_code`. It does not send SMS.

## Exam JSON contract

The file passed to `--from-exam-json` must match the existing `exam_prep_json` contract. At minimum, the shape is:

```json
{
  "exam_prep": {
    "title": "Grade 9 Exam Prep Demo",
    "questions": [
      {
        "question_id": "grade9-demo-q1",
        "question_text_markdown": "Which number is prime?",
        "options": ["الف) ۹", "ب) ۱۱", "ج) ۱۵", "د) ۲۱"],
        "correct_option_label": "ب",
        "teacher_solution_markdown": "Eleven has no divisors other than 1 and itself."
      }
    ]
  }
}
```

The command validates this file with `ExamPrepOutput` before creating the shared exam. Question IDs and correct option labels are used later to map imported results.

## Importing finalized results

Copy the external results JSON file into a path readable by the backend process, then validate it before writing attempts:

```bash
python manage.py import_exam_prep_results \
  --session-id <published_exam_prep_session_id> \
  --results-json path/to/results.json \
  --dry-run
```

Import after validation succeeds:

```bash
python manage.py import_exam_prep_results \
  --session-id <published_exam_prep_session_id> \
  --results-json path/to/results.json
```

The session must be published and must be an `EXAM_PREP` session. Each result must identify an invited student by normalized phone number. The importer rejects unknown students, students without accounts, duplicate rows for one student, and unknown question IDs. The whole import is atomic.

`--dry-run` validates the payload and rolls back all attempt writes. Without `--force`, an existing attempt for any listed student is a conflict. `--force` replaces existing attempts for the listed students:

```bash
python manage.py import_exam_prep_results \
  --session-id <published_exam_prep_session_id> \
  --results-json path/to/results.json \
  --force
```

## Accepted results adapter shape

The top-level payload must be an object with a `results` list. The primary row shape is:

```json
{
  "results": [
    {
      "student": {"phone": "+98 912 000 0001"},
      "answers": {"grade9-demo-q1": "ب"},
      "unanswered": ["grade9-demo-q2"]
    }
  ]
}
```

Phone identity may also be supplied as `student` string, `phone`, or `student_phone`. Names and row order are ignored. Unanswered question IDs are omitted from `answers`.

The adapter also accepts either of these row forms:

```json
{
  "student_phone": "09120000001",
  "questions": [
    {"question_id": "grade9-demo-q1", "status": "correct", "answer": "ب"},
    {"question_id": "grade9-demo-q2", "status": "wrong", "answer": "الف"},
    {"question_id": "grade9-demo-q3", "status": "unanswered"}
  ]
}
```

```json
{
  "phone": "09120000001",
  "correct": ["grade9-demo-q1"],
  "wrong": ["grade9-demo-q2"],
  "unanswered": ["grade9-demo-q3"]
}
```

The only accepted question statuses are `correct`, `wrong`, and `unanswered`. When an answer is supplied, it is checked against the exam's `correct_option_label`, and a contradictory explicit status is rejected. Status-only `correct` or `wrong` entries are accepted as imported outcomes and are stored as one attempted question with no selected answer; `unanswered` entries are omitted from stored answers. Imported attempts are finalized, and their score is the rounded percentage of correct questions across the complete exam question set.

## Teacher visual repair (upload to question/option/solution)

An OCR-flawed question can be repaired by hand in the teacher review UI (`/teacher/my-exams/<session_id>/edit`, `ExamEditForm`). Each question card now shows an **افزودن تصویر به سؤال** control where the teacher picks where the image attaches — صورت سؤال (`question`), گزینه (`option`, with the target option label), or پاسخ تشریحی (`solution`) — then uploads a PNG/JPEG/WebP image up to 5 MB.

- Backend: `POST /api/classes/exam-prep-sessions/<session_id>/visuals/teacher/` (teacher-owner only) validates real image bytes (Pillow), stores the file in the same private `answer_sources` storage family used by OCR assets under `exam-prep/teacher-visuals/<session_id>/`, and appends a `teacher-*` entry to the owning question's `visuals` array in `exam_prep_json`. Removal is client-side in the editor (filter + save) and the `remove_teacher_visual` service helper also deletes the stored file.
- Content: `GET /api/classes/exam-prep-sessions/<session_id>/visuals/teacher/<storage_name>/content/` streams the private bytes to the owning teacher or to an invited student of a published session; solution visuals are only revealed to a student after that student's attempt is finalized (same masking rule as other solution assets). No storage path is ever exposed.
- Frontend: `frontend/src/components/teacher/exam-edit/question-visual-tools.tsx` provides `QuestionVisualUploader` and `TeacherVisualCard` (trash overlay only for `teacher-` ids); `exam-edit-form.tsx` wires attach/remove into the session save flow and disables save while an upload is in flight. Uploaded images render through the existing protected `ProtectedExamVisual` path.
- New service/view modules: `backend/apps/classes/services/exam_prep_teacher_visuals.py`, `backend/apps/classes/views_exam_prep_teacher_visuals.py`; routes added in `apps/classes/urls.py`. Tests: `backend/apps/classes/test_exam_prep_teacher_visuals.py`.

## Student result behavior

The result page starts with the **all** view. After a finalized result, students can switch between:

- **All:** every result item.
- **Wrong answers:** only answered items whose `is_correct` value is false. Unanswered items are not included in this filter.

The page shows the score, correct count, total question count, per-question status, selected answer, and finalized solution content when available. If the wrong-answer filter has no matching items, it shows `پاسخ غلطی برای نمایش وجود ندارد.`. Draft results do not show the filter controls.

## Limitations

- This is one shared published exam, not a teacher analytics or multi-exam reporting feature.
- The seed and import commands are management commands. No new API endpoint or pipeline is introduced by this MVP.
- External JSON and PDF files still need to be copied into a path accessible to the backend process before a command can read them. The seed command reads an exam JSON file, and the import command reads a results JSON file. The exact external JSON schema must match the adapter or `exam_prep_json` contract described above. A PDF is not accepted directly by either command.
- Result import is deterministic and does not call an LLM. It relies on phone identity, invitation membership, question IDs, and the published exam's correct option labels.
- The frontend wrong-answer filter is student-facing only. It does not provide aggregate teacher analytics.

## Production visibility

Status of this feature is ready for the production demo. The operator sequence for making the demo visible in the production deployment is the runbook [`docs/runbooks/grade9-shared-exam-production.md`](../runbooks/grade9-shared-exam-production.md).

In production the exam content (120 questions, images, teacher solutions, generated visuals) comes from the live OCR pipeline, never from a hand-carried local exam JSON. The operator ingests the merged PDF `allexamdata.pdf` (via `python manage.py ingest_exam_prep_pdf` or the real Exam Prep intake `POST /api/classes/exam-prep-sessions/step-1/`), waits until the session reaches `exam_structured`, publishes the session (`python manage.py publish_exam_prep_session` or `POST /api/classes/exam-prep-sessions/<session_id>/publish/`), then runs the management commands inside the backend container:

```bash
python manage.py seed_grade9_exam_mvp --session-id <published_exam_prep_session_id> --students-file path/to/roster.json
python manage.py import_grade9_exam_results --session-id <published_exam_prep_session_id> --results-json path/to/exam-result.json --roster-json path/to/roster.json
```

`--from-exam-json` remains a deterministic dev/CI mode only. A JSON-only session carries no OCR visuals or stored assets, so the production demo must not use it for content. The ten demo phones `09129090001` to `09129090010` are intentionally used in production for this demo (owner decision); the roster maps export row order to those phones. Exact commands, expected outputs, prerequisites, rollback, and the verification checklist live in the runbook.

## Related release

See [`docs/releases/2026-09-03-grade9-shared-exam-mvp.md`](../releases/2026-09-03-grade9-shared-exam-mvp.md).

Production operator sequence: [`docs/runbooks/grade9-shared-exam-production.md`](../runbooks/grade9-shared-exam-production.md).
