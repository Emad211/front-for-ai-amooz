# 2026-09-03, Grade 9 shared Exam Prep MVP

- **Status:** Prepared on implementation branch · production demo runbook added 2026-09-05 · **Date:** 2026-09-03 · **Owner:** engineering

## Changes

- Added `seed_grade9_exam_mvp`, which creates or reuses one published grade 9 Exam Prep session, ten student accounts, invitation access, and permanent invite codes without sending SMS.
- Added `ingest_exam_prep_pdf`, which queues a local PDF into the production Exam Prep OCR pipeline (create-or-reuse `EXAM_PREP` session, dispatch `process_exam_prep_pdf_session` on the `pipeline` queue) without running OCR synchronously.
- Added `publish_exam_prep_session`, which publishes an `exam_structured` Exam Prep session with its parsed question count.
- Added `import_exam_prep_results`, which validates and atomically imports finalized results by invited student phone number without invoking an LLM.
- Added `import_grade9_exam_results`, which reads the real external `exam-result.json` export (array, BOM, `courses/answers`, statuses `correct`/`wrong`/`white`, answer `0` = unanswered), maps `q_no` to session question ids, and imports the ten students via the underlying result service.
- Added the accepted results adapter forms for answer maps, question records, and `correct`/`wrong`/`unanswered` buckets.
- Added `--dry-run` validation and `--force` replacement behavior to the import commands.
- Added the student result page's finalized **all** versus **wrong answers** filter.
- Added the production runbook [`docs/runbooks/grade9-shared-exam-production.md`](../runbooks/grade9-shared-exam-production.md), which makes the demo visible in the production deployment: the merged PDF `allexamdata.pdf` is uploaded through the real Exam Prep intake so the 120-question content, images, solutions, and visuals come from the production OCR pipeline, then the session is published, `seed_grade9_exam_mvp --session-id` attaches the ten demo students, and `import_exam_prep_results` records the finalized results.

## Operations

Run the seed command before importing results. Copy external JSON files into a backend-accessible path first. The exact external JSON must match the documented adapter contract. PDF files are not read directly by these commands.

See [`docs/features/grade9-shared-exam-mvp.md`](../features/grade9-shared-exam-mvp.md) for command syntax, payload examples, and limitations.

Run the production sequence from [`docs/runbooks/grade9-shared-exam-production.md`](../runbooks/grade9-shared-exam-production.md). The runbook also documents that the external `exam-result.json` export is BOM-encoded UTF-8 with no phone field; the branch mapper `import_grade9_exam_results` reads it directly and maps each `q_no` to the published session's question ids.

## Owner decisions

- The ten demo phone numbers `09129090001` to `09129090010` are intentionally used in production for this demo (owner decision). Live OCR content generation is an owner-run deployment action; the merged PDF is ingested through the production Exam Prep UI or its intake endpoint, never through dev/CI or a local exam JSON transfer.

## Migrations and configuration

No migration or environment-variable change is part of this release. Two teacher-scoped endpoints were added for the visual-repair feature: `POST/GET /api/classes/exam-prep-sessions/<session_id>/visuals/teacher/...` (see `docs/features/grade9-shared-exam-mvp.md`, "Teacher visual repair").

## Verification

Documentation is based on the implemented branch symbols and command contracts. No runtime test result is claimed in this release note.
