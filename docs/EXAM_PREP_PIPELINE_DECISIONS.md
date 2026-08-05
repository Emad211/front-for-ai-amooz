# Exam Prep PDF Pipeline — Decisions and Cost/Integrity Contract

_Last updated: 2026-08-05_

This document is the source of truth for the simple page-first Exam Prep PDF pipeline.
It records the decisions made after reviewing the live Celery run for session 191 and
its 50-question output.

## 1. Page content classification

Every physical PDF page is classified locally before any provider call.

- `non_content`: cover, instructions, separator, index, advertisement, or blank page.
- `content`: a page that may contain questions, answers, solutions, tables, or visuals.

A page may be skipped only with strong local evidence. A scanned page with no usable
native PDF text is not silently discarded merely because no text was extracted.

`non_content` pages:

- return an empty extraction (`records=[]`),
- make zero provider requests,
- are not retried,
- are not added to `failedPageNumbers`,
- never block publication.

## 2. Layout routing and request budget

The route is chosen from native PDF text and deterministic image-density signals.

| Local decision | Provider route | Normal request count |
|---|---|---:|
| `non_content` | skip | 0 |
| `single` | full page | 1 |
| `double` | right column + left column | 2 |
| `uncertain` | full page + both close-ups in one multi-image request | 1 |

The previous route `full page -> right column -> left column` is prohibited.
For a double-column page, only a failed column may be retried once; a successful
column must not be repeated.

Structured-output repair is disabled inside the routed extractor (`max_repair=0`).
Single/uncertain pages may receive one outer retry after a schema failure. Double
pages perform their bounded per-column retry internally and are not repeated as a
whole page.

## 3. Record validation

Provider output is accepted through a permissive page envelope and each record is
normalized/validated independently.

- Harmless number variants are normalized.
- Malformed optional bounding boxes fail open.
- A decorative or empty item with no valid question number is dropped.
- A substantive item with no valid question number is quarantined and logged.
- One malformed item must not invalidate all records from the page.
- An empty extraction is valid.

## 4. Deterministic projection integrity

Before targeted verification, the assembled projection receives a free local pass.

### Serialized options

Option text that is itself a JSON object is decoded and normalized. Raw serialized
payloads may never reach teacher/student UI. Unresolved payloads receive the critical
issue `serialized_option_payload`.

### Grading keys

For multiple-choice questions, `correct_option_label` is the grading contract.
The label is inferred locally from Persian variants including:

- `گزینه ۴`
- `گزینهٔ ۴`
- `گزینۀ ۴`
- Persian, Arabic, or Latin digits

A multiple-choice question without a usable label receives
`missing_correct_option_label` and remains publication-blocked.

Audit counters distinguish:

- answer evidence,
- gradable answer keys,
- missing correct-option labels.

### Cross-question duplicate solutions

Long near-identical solutions attached to materially different question stems are
flagged as `duplicate_solution_across_questions`. The system does not guess which
solution is correct; the later suspicious question is sent to targeted source
verification.

## 5. Orphan answers

Answer/solution records with no matching question never fabricate a new question.
They remain warnings and do not block otherwise valid questions.

## 6. Visual and table questions

A visual-dependent question is publishable only when the attached crop contains the
required evidence. Marker-only options such as `1, 2, 3, 4` are acceptable only when
all visual options are visible and source verification succeeds. Otherwise the
concrete visual/option issue remains critical.

Inline Base64 crop storage remains unchanged for now.

## 7. Targeted verification

- Clean questions: zero requests.
- Suspicious questions: at most one request each.
- `max_repair=0` and no outer retry.
- Default cap: 20 questions.
- Only source pages/crops for selected questions are re-rendered.

Concrete issues include extraction defects, missing grading keys, duplicate solutions,
visual/table dependencies, unresolved counts, and broken/serialized option text.
A provider failure by itself is metadata, not a publication blocker. Publication is
blocked only if a concrete content defect remains.

## 8. Cancellation

Cancellation is checked:

- before each page,
- before every page retry,
- before source-page selection,
- before crop construction,
- before each suspicious question,
- immediately before each provider request,
- immediately after each response before proceeding.

Cancellation ends the task as `cancelled`, never `failed`, and prevents the next call.

## 9. Publication gate

Publication is blocked by unresolved content defects, including:

- failed content page,
- missing question text/options/answer,
- missing gradable option label,
- conflicting answer/options,
- missing continuation,
- broken or serialized option text,
- duplicate solution across unrelated questions,
- incomplete visual/table evidence.

Publication is not blocked by:

- a cover/instructions/blank page,
- out-of-scope orphan answers,
- missing bbox on a non-visual question,
- source-verification failure when no concrete defect remains,
- skipped optional verification caused by the cost cap on an otherwise clean question.

## 10. Required observability

Per-page routed logs include:

- `contentClassification`
- `layoutDecision`
- `layoutConfidence`
- `classificationReasons`
- `providerCallCount`
- `retryCalls`
- `columnCalls`
- `quarantinedRecords`
- `skippedNonContent`

Final pipeline audit includes:

- `nonContentPageCount`
- `contentPageCount`
- `pageExtractionCalls`
- `pageRetryCalls`
- `targetedVerificationCalls`
- `totalProviderCalls`
- `gradableAnswerKeyCount`
- `missingCorrectOptionCount`
- `duplicateSolutionCount`
