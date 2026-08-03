# Runbook — Exam Prep V4 AvalAI Mistral OCR Smoke

- **Status:** fake-response gate implemented; live request not authorized or executed
- **Branch:** `feat/exam-prep-v4-source-aware`
- **Owner:** Classes / Exam Prep V4
- **Reviewed:** 2026-08-03
- **Pinned model:** `mistral-ocr-4-0`
- **Endpoint:** `POST https://api.avalai.ir/v1/ocr`
- **Roadmap ledger:** `docs/features/exam-prep-v4-status.md`

## Official documentation reviewed

AvalAI pages reviewed before implementation:

```text
https://docs.avalai.ir/fa/
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

Supplementary upstream Mistral documentation was used only where the current AvalAI page did not expose enough response detail:

```text
https://docs.mistral.ai/studio-api/document-processing/basic_ocr
https://docs.mistral.ai/studio-api/document-processing/annotations
https://docs.mistral.ai/api/endpoint/ocr
```

AvalAI documentation remains authoritative for the AvalAI endpoint, authentication, exposed parameters, and AvalAI pricing. Upstream Mistral documentation is treated as capability context that must still be verified against the AvalAI gateway.

## Documentation findings

### OCR model versions

- `mistral-ocr-2512` is OCR 3 and remains available for existing integrations.
- OCR 4 is the newer model.
- AvalAI's OCR reference pins OCR 4 as `mistral-ocr-4-0`.
- `mistral-ocr-latest` is a mutable alias and is not used for reproducible tests.
- paragraph-level block labels are an OCR 4 capability in current upstream Mistral documentation; AvalAI gateway support is measured in the smoke rather than assumed.

### Input contract

AvalAI documents:

- PDF/document input through `document_url`;
- image input through `image_url`;
- private bytes through a base64 data URL;
- zero-based selective PDF pages through `pages`;
- `include_image_base64` control;
- image extraction limits;
- `document_annotation_format`;
- `bbox_annotation_format`;
- header/footer extraction;
- Markdown or HTML table formatting.

The V4 smoke uses only local bytes encoded to data URLs. It never creates a public or presigned source URL.

### Output distinction

The four smoke modes answer different questions:

1. **markdown** — is Persian/RTL text, formula syntax, and table structure preserved?
2. **blocks** — does the AvalAI OCR 4 gateway return paragraph-level block labels, ordered bboxes, and page confidence?
3. **document_annotation** — can the entire page be classified into a constrained JSON schema?
4. **bbox_annotation** — can extracted images/figures be classified with a constrained schema?

BBox annotation is not treated as a replacement for text-block detection. Current Mistral documentation describes it as annotation of extracted image/figure bboxes. OCR 4 blocks are the candidate acceleration path for Phase 4 text/layout boundaries.

### Pricing stated by AvalAI OCR reference

```text
mistral-ocr-4-0 OCR:        $0.004 per page
mistral-ocr-4-0 annotation: $0.005 per annotated page
```

The documentation available during review does not establish whether annotation pricing replaces or adds to base OCR pricing for every billing case. Exact live cost must be measured from provider request IDs/transaction records and must not be inferred solely from the table.

### Data-handling boundary

The docs establish base64 transport, not a no-retention/no-training guarantee for this endpoint. No such guarantee is inferred. Live execution requires explicit product-owner permission to transmit the selected two private page images.

## Architecture decision before live evidence

The production path remains unchanged:

```text
confirmed Source Map
→ current V4 block detector
→ typed QuestionRecord / AnswerSolutionRecord
→ deterministic matcher
```

The OCR smoke is isolated. It may justify a later candidate path:

```text
confirmed Source Map
→ OCR 4 Markdown + blocks
→ deterministic SourceBlock proposals
→ typed validators and persistence already implemented
→ vision fallback only for unresolved/low-confidence evidence
```

No routing switch is allowed before measured live smoke evidence.

## Implemented smoke command

```bash
python backend/manage.py smoke_exam_prep_v4_avalai_ocr \
  --question-page /private/question-page.png \
  --answer-page /private/answer-page.png \
  --report /private/ocr-smoke-report.json \
  --mode fake_provider
```

Default modes:

```text
markdown
blocks
document_annotation
bbox_annotation
```

Two inputs × four modes = eight requests in live mode.

## Live preflight contract

Live mode requires all of the following:

```bash
export AVALAI_API_KEY='configured-through-local-secret'

python backend/manage.py smoke_exam_prep_v4_avalai_ocr \
  --question-page /private/question-page.png \
  --answer-page /private/answer-page.png \
  --report /private/ocr-smoke-report.json \
  --mode live_provider \
  --model mistral-ocr-4-0 \
  --max-requests 8 \
  --allow-private-transmission
```

The credential must not be committed, pasted into the ledger, or printed by the command.

## Bounds

Defaults:

```text
max input bytes per page:       12 MiB
max response bytes per request: 24 MiB
max selected PDF pages:         8
max Markdown chars per page:    500,000
max annotation chars:           500,000
request timeout:                180 seconds
```

`include_image_base64` is always false. If image base64 is unexpectedly returned, parsing fails with a privacy error.

## Aggregate-only report

Allowed metrics:

- anonymous fixture ID;
- mode and pinned model;
- opaque request ID;
- input byte count;
- returned page count/indexes;
- Markdown character count;
- RTL character count;
- formula/table signal counts;
- block/image/bbox counts;
- block type counts;
- annotation-present booleans/counts;
- content-free issue codes;
- aggregate page confidence;
- provider-reported pages processed/document bytes;
- latency and request counts.

Forbidden:

- local paths and filenames;
- source bytes or data URLs;
- Markdown text;
- block content;
- document/image annotation payloads;
- image base64;
- question, answer, or solution text;
- credentials or raw provider errors.

## Fake-response acceptance

The fake gate must prove:

- all four modes use the same production parser/report builder as live mode;
- private input is base64 encoded without public URLs;
- exact page coverage is enforced;
- duplicate/missing pages fail closed;
- response, Markdown, input, and annotation bounds are enforced;
- malformed annotations become content-free issues without deleting healthy OCR pages;
- unexpected image base64 fails closed;
- fake report contains no source path, filename, text, annotation, or bytes;
- live mode refuses to start without permission, key, and a sufficient request ceiling;
- all focused V4 backend/frontend gates remain green.

## Live evaluation metrics

The first live smoke will compare the two selected pages across all four modes:

- Persian/RTL reading-order plausibility;
- printed-number preservation;
- formula preservation;
- table preservation;
- OCR 4 block type/bbox coverage;
- question/answer page-role annotation;
- diagram/image annotation usefulness;
- content-free issue counts;
- latency;
- request IDs and authoritative cost lookup.

A human inspection of the private OCR result is required for quality evaluation. Only aggregate conclusions are recorded in the ledger.

## Decision after live smoke

Possible outcomes:

1. **OCR-first candidate accepted:** use OCR4 blocks/Markdown to propose Phase 4/5 evidence and keep vision fallback.
2. **Transcription-only candidate:** use Markdown for block text but retain current vision block detector.
3. **Diagram-only utility:** use bbox annotations only for figures/diagrams.
4. **Rejected for V4:** retain the current vision path when RTL/formula/layout evidence is inadequate.

No canonical roadmap credit is granted until a measured result closes a listed deliverable.
