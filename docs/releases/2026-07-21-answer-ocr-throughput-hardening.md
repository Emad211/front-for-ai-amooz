# Student answer OCR throughput hardening

## Changes

- Rapid consecutive images for one question can now join the same draft during
  the configured settle window. The previous queued revision becomes stale and
  exits before storage or the vision provider is opened.
- A whole-answer bundle can be replaced during that same settle window. Active
  processing states remain immutable and return `409`.
- Whole-answer PDF/image pages are rendered and sent one configured provider
  chunk at a time instead of retaining all normalized pages in worker memory.
- PDF, bitmap, EXIF-normalized, and resized image handles are closed
  deterministically after each page instead of waiting for garbage collection.
- Multipart validation keeps only upload metadata, byte size, and SHA-256 after
  validation; it no longer keeps a second copy of every payload in a Python list.
- Removed an unused OCR exception type.

No API, migration, prompt, model, queue name, storage bucket, or environment
variable changed.

## Capacity guidance

Keep `CELERY_WORKER_PREFETCH_MULTIPLIER=1` and isolate this worker on the
`interactive` queue. Start with per-process concurrency `1`; scale replicas from
observed queue wait and provider p95 rather than increasing concurrency blindly.
Each job is idempotent per Source revision, and stale settle-window jobs perform
only a revision lookup before exiting.

## Verification

- OCR suite: 52 tests on SQLite and 52 tests on PostgreSQL/Redis, including
  queued-revision races, stale-before-read, provider-chunk streaming, retry
  reuse, ownership, quota, recovery, and cleanup.
- Exercise and prompt regression: 334 passed on PostgreSQL/Redis with every LLM
  provider call mocked.
- `makemigrations --check --dry-run`: no changes detected.
- Django system check and targeted Python compilation completed successfully.
- Redis stress gate: five rounds of 200 concurrent quota claims admitted exactly
  the configured 10 each time; 100 independent Source locks were admitted while
  all 100 duplicate claims were rejected.
- Frontend production build completed. Typecheck still reports the repository's
  11 pre-existing errors in unrelated admin, exam-edit, and mock-message files;
  no frontend file changed in this hardening.
