# Exam-Prep Step-1 file-type routing — one intake, PDF→Mistral & media→legacy

- **Status:** Shipped · **Created:** 2026-08-16 · **Last-verified:** 2026-08-16
- **Owner:** product-manager · **Spec by:** tech-lead · **Built by:** backend + frontend

## Problem

TEACHER creating "آمادگی آزمون" could only upload a **PDF** — the deployment form
was locked to PDF and said so. The new production **Mistral OCR** intake
(`ExamPrepPdfStep1View` → `process_exam_prep_pdf_session`) is PDF-only and it
**shadows** the older transcription-based exam-prep intake at the same URL
(`core/urls.py` registers it above the `apps.classes.urls` include). Mistral OCR
(Avalai `/v1/ocr` + `mistral-ocr-4-0`) **cannot read audio/video**, yet the
platform has a strong, long-used transcription pipeline for media. Teachers who
had a lecture recording or answer voice-note had no path.

## Scope

- **In:** route exam-prep step-1 **by file type** at the view; unlock the frontend
  upload to accept audio/video/image/PDF again.
- **Out (explicitly):** deleting the legacy media pipeline (it is **intentionally
  retained**); any change to the Mistral stages, the V4 split pipeline, or the
  legacy step-2/publish views.
- **Later phases:** none planned.

## Design (technical)

Single intake URL `POST /api/classes/exam-prep-sessions/step-1/` →
`views_exam_prep.ExamPrepPdfStep1View.post`, which branches **before** any
Mistral-specific work (idempotency, scope, session create):

- `is_pdf_upload(upload)` is **false** (audio/video/image) → delegate:
  `return ExamPrepStep1TranscribeView().post(request)`. The legacy view sets
  `source_type=MEDIA`, creates the `ExamPrepExtractionArtifact`, and dispatches
  `process_exam_prep_full_pipeline` (the frontend always sends
  `run_full_pipeline=true`). `_ingest_source_to_markdown` there branches on MIME,
  so PDF/image/audio/video are all handled by that path — but PDFs never reach it
  because of the branch below.
- `is_pdf_upload(upload)` is **true** → require `_valid_pdf_upload` (header sniff +
  `seek(0)`); a fake-`.pdf` with non-PDF bytes returns **400** and does **not**
  fall through to media. Valid PDFs continue into the unchanged Mistral path
  (`source_type=PDF`, `process_exam_prep_pdf_session`).

Why the branch lives at the view: `process_exam_prep_pdf_session` **hard-fails**
(marks FAILED + raises) on any non-PDF `source_type`, so a MEDIA session must never
be dispatched to it.

Delegation is safe: the legacy `post` never touches `self.*`, re-runs the serializer
on cached `request.data`, and neither view declares throttles (no double-throttle).
`is_pdf_upload` checks content-type/name only (no byte read), so the upload pointer
is untouched for the delegated media path. Module-level
`from apps.classes.views import ExamPrepStep1TranscribeView` is cycle-free
(`views.py` never imports `views_exam_prep`; verified by import + full test run).

## API

- **Route/method/auth:** unchanged — `POST /api/classes/exam-prep-sessions/step-1/`,
  `IsAuthenticated + IsTeacherUser`, multipart.
- **Request:** unchanged `ExamPrepStep1TranscribeRequestSerializer`
  (`file`, `title`, `description?`, `client_request_id?`, `run_full_pipeline?`).
  `validate_step1_upload` already accepts audio/video/image/PDF.
- **Response:** unchanged `ExamPrepStep1TranscribeResponseSerializer` (202/200).
- **New error:** fake-PDF → `400 {'file': ['برای آمادگی آزمون یک فایل PDF معتبر بارگذاری کنید.']}`.

## Frontend

`create-class-page.tsx` + `file-upload-section.tsx`: removed the PDF-only locks
(`isExamPrepPdf`, the `isExamPreparation` title-sniff override, the PDF-only `accept`
and hint copy). Upload now accepts `audio/*,video/*,image/*,application/pdf,.pdf` for
both pipeline types; the exam-prep hint mentions PDF **and** video/audio.
`classes-service.ts` unchanged — `transcribeExamPrepStep1` forwards any `File`.

## Testing

`backend/apps/classes/test_exam_prep_simple_pipeline.py`:
- `test_step1_media_delegates_to_legacy_pipeline` — `audio/mpeg` → `source_type=MEDIA`,
  one `ExamPrepExtractionArtifact`, legacy `process_exam_prep_full_pipeline` dispatched,
  Mistral `apply_async` **not** called.
- `test_step1_rejects_fake_pdf_without_delegating_to_media` — `.pdf` name + junk bytes
  → 400, no session, no dispatch.
- `test_step1_creates_only_normal_session_and_dispatches_simple_task` (unchanged) —
  real PDF → `source_type=PDF`, artifact count 0, Mistral captured (PDF regression).

`test_exam_prep_mistral_cutover.py` — route/engine assertions still valid.

Run (needs Postgres; live-provider calls are mocked so no keys required):
```
python -m pytest backend/apps/classes/test_exam_prep_simple_pipeline.py backend/apps/classes/test_exam_prep_mistral_cutover.py backend/apps/classes/test_exam_prep_pipeline.py
```
Result on ship: **57 passed**. Frontend `npx tsc --noEmit` clean.

**Deliberately untested here:** real OCR/transcription quality — exam-prep
live-provider calls are forbidden in dev/CI; the owner validates both branches in
deployment (PDF → Mistral review, audio/video → legacy transcription review).

## Rollout

No migration, no new env vars. Rebuild **backend** (view logic) and **frontend**
(upload unlock). No feature flag — the branch is unconditional. Manual owner check in
deployment: exam-prep tab accepts audio/video/image/PDF; a PDF runs Mistral, an
audio/video file runs legacy transcription; both reach review.
