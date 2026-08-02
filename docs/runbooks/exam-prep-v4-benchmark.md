# Runbook — Exam Prep V4 Source-Aware Benchmark

- **Status:** Active design contract; runner not implemented yet
- **Branch:** `feat/exam-prep-v4-source-aware`
- **Owner:** Classes / Exam Prep
- **Created:** 2026-08-03
- **Last updated:** 2026-08-03
- **Related design:** `docs/features/exam-prep-v4-source-aware-split-pipeline.md`

## Purpose

This runbook defines the acceptance benchmark for Exam Prep V4. V4 must split each uploaded PDF into logical page ranges, route every range through the correct specialized extractor, and connect each answer plus its full solution to the correct question inside the same independent exam.

The benchmark is intentionally based on real teacher-style PDFs with irregular ordering, overlapping answer ranges, multi-column pages, formulas, diagrams, and answer continuations. The source files are private local test inputs and must never be committed to Git.

## Data-handling rules

1. Do not commit source PDFs, rendered pages, filenames, extracted text, answer keys, or screenshots.
2. Keep local benchmark files outside the repository or under an ignored directory.
3. Commit only aggregate metrics, structural expectations, anonymized failure codes, and implementation-independent assertions.
4. Do not use one benchmark PDF as evidence that another PDF belongs to the same exam.
5. Treat every uploaded PDF as a separate `ExamProject` unless the user explicitly groups files before processing.
6. Cross-file duplicate pages must not trigger cross-exam deduplication or matching.

## Fixture matrix

The current benchmark contains three **independent exams**. The labels below are anonymized and do not identify the source files.

### Fixture A — Questions first, solutions second

- Total pages: 16
- Expected segments:
  - page 1: `cover`
  - pages 2–8: `questions`
  - pages 9–16: `answer_solutions`
- Expected question inventory: printed numbers 1–50
- The answer-solution range contains records outside the question inventory near the upper boundary.
- Required behavior:
  - extract questions 1–50;
  - attach only in-scope answer-solution records;
  - classify answer-solution records without a matching question as `out_of_scope`;
  - never create questions from those answer records.

### Fixture B — Solutions first, cover in the middle, questions last

- Total pages: 27
- Expected segments:
  - pages 1–11: `answer_solutions`
  - page 12: `cover`
  - pages 13–27: `questions`
- Expected question inventory: printed numbers 51–115
- The answer-solution range starts before and continues after the question range.
- Required behavior:
  - segment correctly even though the cover is not the first page;
  - extract questions 51–115;
  - keep answer-solution records 51–115 in scope;
  - classify lower- and upper-bound records outside 51–115 as `out_of_scope`;
  - process answer-first ordering without waiting for a question transcript to exist.

### Fixture C — Questions first with overlapping solution boundaries

- Total pages: 15
- Expected segments:
  - page 1: `cover`
  - pages 2–8: `questions`
  - pages 9–15: `answer_solutions`
- Expected question inventory: printed numbers 116–145
- The answer-solution range begins below 116 and ends above 145.
- Required behavior:
  - extract questions 116–145;
  - attach only answer-solution records 116–145;
  - classify records below and above the inventory as `out_of_scope`;
  - never expand the exam inventory from the answer section.

## Cross-fixture invariants

- The fixtures are three different exams.
- A visually or byte-identical page appearing in two fixtures is not a reason to merge the exams.
- Deduplication is scoped to one `ExamProject` only.
- Matching is scoped to one `ExamProject` only.
- A question number in Fixture A can never match an answer or solution in Fixture B or C.
- Uploading all three files in one browser action must create three independent exam drafts by default.

## Structural capabilities under test

The benchmark must exercise all of the following:

- cover pages appearing at the beginning or middle of a PDF;
- question-first and answer-first document ordering;
- two-column right-to-left layouts;
- printed Persian, Arabic, and Latin digits;
- mathematical formulas and scientific notation;
- diagrams, charts, tables, and option visuals;
- answer headings that include both the printed number and correct option;
- one answer and its detailed solution represented as a single logical record;
- answers continuing onto the next page before the next numbered heading;
- pages containing multiple answer-solution records;
- question and answer ranges that do not have identical boundaries;
- out-of-scope answer records;
- partial JSON failure without loss of valid sibling records.

## Ground-truth representation

The benchmark runner must read a local, non-committed manifest using a content-free structure such as:

```json
{
  "fixtureId": "fixture-a",
  "expectedSegments": [
    {"startPage": 1, "endPage": 1, "role": "cover"},
    {"startPage": 2, "endPage": 8, "role": "questions"},
    {"startPage": 9, "endPage": 16, "role": "answer_solutions"}
  ],
  "expectedQuestionNumbers": {"from": 1, "to": 50},
  "expectedOutOfScopeNumbers": [51, 52, 53, 54]
}
```

The exact local manifest may additionally contain hashes and per-record source coordinates, but it must remain outside Git when it can reveal source content.

## Metrics

Record the following for every cold run and warm rerun:

### Segmentation

- page-role accuracy;
- boundary accuracy;
- number of manual corrections required;
- classification latency;
- classification model call count and cost.

### Question extraction

- expected question count;
- extracted question count;
- question precision;
- question recall;
- option completeness;
- printed-number accuracy;
- visual attachment accuracy.

### Answer and solution extraction

- expected in-scope answer-solution count;
- extracted in-scope count;
- correct-option accuracy;
- full-solution boundary accuracy;
- continuation merge accuracy;
- out-of-scope classification accuracy.

### Matching

- automatic match precision;
- automatic match recall;
- wrong-match count;
- unresolved count;
- duplicate-number ambiguity count;
- cross-exam match count.

### Reliability and cost

- provider calls by stage;
- retry count by record and stage;
- partial-record recovery count;
- cache hit rate;
- total latency;
- estimated LLM cost;
- worker peak RSS and restart count;
- orphaned private object count.

## Required acceptance thresholds

The production gate for the current fixture matrix is:

- cross-exam match count: **0**;
- automatic answer-to-question match precision: **100%**;
- automatic solution-to-question match precision: **100%**;
- question recall: **at least 99%**;
- answer-solution recall for in-scope records: **at least 99%**;
- out-of-scope answer records converted into questions: **0**;
- accepted records lost because a sibling JSON record is invalid: **0**;
- unchanged warm rerun provider calls for accepted units: **0**;
- unresolved ambiguous records may remain unresolved; a wrong automatic match is never acceptable.

Precision takes priority over recall for automatic matching. When evidence is insufficient, V4 must create a review issue instead of guessing.

## Planned execution modes

### Fast segmentation benchmark

Planned command:

```bash
python backend/manage.py benchmark_exam_prep_v4 \
  --manifest "$EXAM_PREP_V4_BENCHMARK_MANIFEST" \
  --stage classify-and-segment
```

### Full cold benchmark

Planned command:

```bash
python backend/manage.py benchmark_exam_prep_v4 \
  --manifest "$EXAM_PREP_V4_BENCHMARK_MANIFEST" \
  --cold
```

### Warm-cache benchmark

Planned command:

```bash
python backend/manage.py benchmark_exam_prep_v4 \
  --manifest "$EXAM_PREP_V4_BENCHMARK_MANIFEST" \
  --warm
```

These commands are contracts for later implementation and must not be documented as available until the management command exists and is tested.

## Test layers

1. **Pure unit tests:** digit normalization, segment boundaries, continuation rules, tolerant JSON parsing, deterministic matching.
2. **Database integration tests:** revision isolation, per-record retries, project scoping, source provenance, private storage lifecycle.
3. **Pipeline integration tests:** question-first, answer-first, cover-in-the-middle, out-of-scope boundaries.
4. **End-to-end tests:** upload three PDFs in one action and verify three independent drafts.
5. **Live-model benchmark:** run the private fixtures against the configured provider and record aggregate metrics only.

## Benchmark result log

Add one row after every meaningful benchmark run.

| Date | Commit | Mode | Fixtures | Result | Key notes |
|---|---|---|---|---|---|
| 2026-08-03 | Initial V4 branch | Contract only | A/B/C | Not run | Runner and V4 implementation do not exist yet. |

## Completion criteria for this runbook

This runbook becomes operational when:

- the local manifest schema is implemented and documented;
- `benchmark_exam_prep_v4` exists;
- unit and integration fixtures exist without copyrighted source content;
- private live fixtures can be supplied through environment-configured paths;
- benchmark output excludes raw source content;
- the result table is updated from an actual run.