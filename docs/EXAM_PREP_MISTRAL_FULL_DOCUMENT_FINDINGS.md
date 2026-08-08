# Exam Prep — Mistral OCR 4 full-document findings

Branch: `experiment/mistral-ocr-layout-probe`

This document records content-free architecture evidence from the private 55-page
Kanoon benchmark. It does not contain source question/solution text.

## Provider transport contract

A direct 55-page OCR request failed with HTTP 400. The provider error explicitly stated
that the maximum OCR input is 30 pages and instructed the caller to split the document.
The failing PDF was only about 1.9 MB, so the page count, not the byte size, was the
binding limit in that run.

A physical 30-page + 25-page split then completed successfully:

- provider requests: 2;
- retries: 0;
- physical pages returned: 55/55;
- OCR blocks: 2,454;
- block bbox coverage: 100%;
- word-confidence rows: 34,221;
- total provider latency: about 129.7 seconds;
- reported OCR unit cost: 0.055 for the 55 pages.

A later run used the exact same first 30-page mini-PDF (same bytes and SHA-256) but
failed after about 172.6 seconds with HTTP 502 and a plain nginx/ArvanCloud response.
Because the identical payload already succeeded, this is transport/upstream evidence,
not a deterministic PDF-validation failure.

Production implication:

- 4xx semantic/input failures are not retried blindly;
- transient gateway/service failures must retry only the failed physical chunk;
- completed chunks must be checkpointed and never repeated after a later chunk failure;
- cancellation is checked before every retry/provider call;
- the canonical document remains page-number continuous across provider chunk boundaries.

## Question-side structural result

On physical question pages, local parsing produced exactly:

- question anchors: 155;
- unique question numbers: 155;
- range: 1..155;
- missing question numbers: 0;
- duplicate question numbers: 0.

This is the strongest result from the benchmark: OCR4 block geometry plus local heading
parsing is sufficient to construct the question-side geometric skeleton for this file.

## Booklet ranges

The prior free-text range regex is invalid for production because ordinary question and
solution prose contains many numeric `x تا y` expressions.

The cover tables themselves are strong structured evidence. Parsing only tables whose
headers contain `مواد امتحانی`, `تعداد سؤال`, `از شماره`, and `تا شماره` yields:

- Biology: 1..45 (45);
- Physics: 46..75 (30);
- Chemistry: 76..110 (35);
- Mathematics: 111..140 (30);
- Geology: 141..155 (15).

The five ranges are contiguous, non-overlapping, and declare exactly 155 questions.

## Solution-side heading state

Worked solutions are physical pages 33..55. They use Persian two-column reading order:
right column top-to-bottom, then left column top-to-bottom.

Raw OCR exposes 149 solution-heading candidates. A conservative deterministic state
machine currently establishes 147 unique solution anchors and leaves eight explicit
boundary gaps:

`4, 5, 6, 10, 15, 26, 30, 74`

Deterministic question-number corrections supported by neighboring anchors are:

- repeated 8 -> 9;
- lost leading digit 6 -> 56;
- lost leading digit 7 -> 57;
- 97 followed by 95 while 94 is expected -> 94.

Two extra candidates are provider duplicates and are discarded. A visually inspected
page proved that a repeated `31` must not be used to fabricate missing question 30; the
30 heading is genuinely absent from OCR while a duplicated 31 solution appears later.

The provider also commonly emits option labels 1/2/3/4 as 10/20/30/40 in solution
headings. That exact pattern is safely normalized only in answer-heading context.
Question 57 has a raw answer option `5`; it remains invalid and requires source-backed
resolution.

A second real heading form also occurs in the response pages:

`option -> "گزینه" -> question number`

The v2 parser supports both question-first and option-first forms.

## OCR stability interpretation

Exact repeated OCR requests on hard pages showed:

- geometry/bboxes are extremely stable;
- markdown/formula transcription can change materially;
- high word confidence does not guarantee formula correctness;
- OCR block labels can change (for example `list` vs `text`) while content/bbox remains
  stable.

Therefore:

- bbox geometry is strong source evidence;
- block type is a feature, not a semantic authority;
- OCR text is a candidate transcription, not unquestionable ground truth;
- formula/text risk needs confidence + deterministic anomalies + source verification,
  not confidence threshold alone.

## Visual evidence findings

The full run reconfirmed multiple provider visual modes:

- Q65: visual answer choices grouped into one OCR image block;
- Q79 and Q120: source text references a visual but OCR exposes no usable visual block;
- Q81 and Q89: important visual information is embedded in table cells;
- Q94: three labeled chemistry structures but only two OCR image blocks; local rendered
  coverage reconciliation finds the missing graphic;
- Q150: four visual choices returned as four separate image blocks.

The residual-graphics detector also produced decorative false positives on booklet
covers. Covers are now excluded from residual-graphics attention accounting.

## Current architecture

```text
Render PDF locally
-> plan minimum bounded physical provider chunks
-> OCR4 blocks + word confidence
-> remap to immutable physical page numbers
-> semantic booklet tables / document ranges locally
-> RTL multi-column geometric reading order locally
-> question heading regions locally
-> conservative solution-heading state machine locally
-> OCR coverage reconciliation against rendered graphics
-> visual/table/option role classification locally
-> Smart Union Crop locally
-> text/formula/visual completeness risk scoring locally
-> source-backed boundary verifier only for unresolved solution gaps
-> targeted transcription/verifier only for unresolved content risk
-> integrity audit
-> teacher review and publication
```

Production integration remains blocked until the eight solution boundary gaps, the one
invalid answer label, and the text/formula fidelity strategy are measured with targeted
source-backed tests. No production Exam Prep route has been changed by this branch.
