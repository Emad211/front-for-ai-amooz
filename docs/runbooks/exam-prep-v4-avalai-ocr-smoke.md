# Exam Prep V4 — Optional AvalAI OCR Diagnostic

## Policy

This smoke is not a development gate and must not run automatically in CI.

- The production OCR evidence adapter is selected only through environment configuration.
- The owner may run an OCR diagnostic intentionally in a controlled deployment or private runner.
- Normal development validation uses fake transport/provider contracts.
- Real PDF behavior is inspected through the correlated production teacher flow documented in `exam-prep-v4-production-validation.md`.

## Production configuration

```env
EXAM_PREP_V4_OCR_EVIDENCE_ENABLED=True
EXAM_PREP_V4_OCR_EVIDENCE_MODEL=mistral-ocr-4-0
EXAM_PREP_V4_OCR_EVIDENCE_MAX_ATTEMPTS=2
EXAM_PREP_V4_OCR_EVIDENCE_RETRY_BACKOFF_SECONDS=0.25
EXAM_PREP_V4_OCR_EVIDENCE_MIN_CONFIDENCE=0.65
EXAM_PREP_V4_OCR_EVIDENCE_BBOX_FOR_DIAGRAMS=True
```

When disabled, the existing structured block detector remains the fallback and authoritative proposal path.

## Adapter contract

```text
confirmed Source Map
→ one document-annotation request per eligible page
→ deterministic Persian/Arabic/Latin numbered-heading grouping
→ optional bbox request for diagram pages
→ bounded SourceBlock proposals
→ existing parser/persistence validation
→ whole-segment structured fallback when evidence is invalid, unavailable or low-confidence
```

The adapter is proposal-only. It cannot override project, document, page, revision, Source Map or persistence ownership.

Only transport failures receive bounded retry. Schema, response, privacy and configuration failures fall back without repeated requests. Accepted unchanged evidence makes zero OCR and detector calls.

## Production log evidence

Use the extraction `runId` and inspect safe counters:

```text
ocrCalls
ocrRetries
ocrFallbackCount
ocrBboxCalls
providerCalls
```

Fallback reason counts and resolved model IDs may be recorded when content-free. OCR Markdown, block content, annotations, source images and raw responses must not be logged.

## Optional direct diagnostic command

Only the owner should run this intentionally:

```bash
python backend/manage.py smoke_exam_prep_v4_avalai_ocr \
  --question-page /private/question-page.png \
  --answer-page /private/answer-page.png \
  --report /private/aggregate-report.json \
  --mode live_provider \
  --model mistral-ocr-4-0 \
  --smoke-modes markdown,blocks,document_annotation,bbox_annotation \
  --max-requests 8 \
  --allow-private-transmission
```

Requirements:

- explicit owner action;
- explicit API secret and model ID;
- exact bounded request count;
- no automatic rerun;
- private input cleanup;
- aggregate/content-free report only.

## Acceptance interpretation

A transport-successful OCR response is not proof of block quality. Validate in production:

- printed heading detection;
- correct block boundaries;
- continuation handling;
- multi-column and RTL order;
- diagram/formula ownership;
- fallback frequency;
- downstream question/answer correctness.

Report failures using the production extraction `runId`, `taskId`, page number, printed question number and expected/observed behavior. Do not make this diagnostic a blocker for unrelated coding.