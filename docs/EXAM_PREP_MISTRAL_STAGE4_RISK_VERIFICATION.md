# Exam Prep Mistral OCR4 — Stage 4 Risk-Gated Verification

Branch of record: `experiment/mistral-ocr-layout-probe`

Production entrypoint remains:

`apps.classes.services.exam_prep_mistral_production.run_exam_prep_mistral_pipeline`

The product contract remains:

`ClassCreationSession -> ExamPrepPipelineResult -> exam_prep_json`

Stage 4 is targeted verification, not a second extraction pipeline and not a
whole-exam LLM audit.

## Pipeline

```text
OCR4 + deterministic Stage 2
        ↓
Precise Stage 3 source visuals
        ↓
Free deterministic region Risk Engine
        ↓
clean --------------------------> no LLM
        ↓ suspicious
one exact source crop
        ↓
Gemini 3 Flash, thinking=minimal
candidate Mistral text hidden
one image / one region / one call
        ↓
source agrees -----------> verify candidate
source safely disagrees --> repair from source
hard math disagreement --> one GPT-5.4-mini second opinion
        ↓
no defensible resolution --> machine blocker
```

Teacher review is not the normal repair mechanism. An unresolved Stage-4 region
is a publication blocker; later UI may expose it, but the pipeline must not turn
large extraction uncertainty into a teacher work queue.

## Risk signals

Every numbered question and solution region receives a local score. The current
signals are:

- formula/math density;
- digits with scientific units;
- scientific terminology;
- Stage-3 visual anomaly;
- missing/invalid answer or option structure;
- recovered/conflicting heading;
- deterministic OCR disagreement;
- broken/source-corrupted text evidence.

OCR/model confidence is not part of the authority model.

The default suspicious threshold is 40, configurable through
`EXAM_PREP_STAGE4_RISK_THRESHOLD`.

Simple scientific prose, one simple formula, or ordinary digits/units alone are
intentionally below the default threshold. Complex math or a strong structural /
source defect crosses it.

## Primary verifier

Default model:

`gemini-3-flash-preview`

Environment override:

`EXAM_PREP_STAGE4_PRIMARY_MODEL`

The exact AvalAI minimal-thinking body is:

```json
{
  "generationConfig": {
    "thinkingConfig": {
      "thinkingLevel": "minimal"
    }
  }
}
```

The provider receives only:

1. target kind (`question` or `solution`);
2. printed question number;
3. physical page number;
4. exactly one PNG source-region crop.

The Mistral candidate text is deliberately absent from provider messages.

Provider SDK retries are forced to zero for Stage 4. There is no automatic JSON
repair round-trip. A malformed/failed response fails closed.

Default primary-call cap:

`EXAM_PREP_STAGE4_MAX_PRIMARY_CALLS=24`

## Source-only transcription contract

The model returns only:

- faithful visible transcription;
- whether a source visual is required;
- visual type;
- source uncertainty flag;
- short uncertain fragments.

There is no model-provided confidence field.

The model is instructed not to solve, infer, normalize from subject knowledge, or
reconstruct unreadable glyphs.

## Repair policy

### Strong agreement

If the independent source transcript strongly agrees with the current candidate
(text similarity >= 0.93 and the numeric signature is identical), the current
candidate is preserved.

### Non-hard disagreement

For a suspicious region that is not hard math, a valid, certain, independently
parsed Gemini source transcription is authoritative enough to repair the text.
No GPT call is added merely because a digit changed.

### Hard math/formula disagreement

Only hard math/formula regions may receive a second opinion.

Default model:

`gpt-5.4-mini`

Environment override:

`EXAM_PREP_STAGE4_SECONDARY_MODEL`

Default cap:

`EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS=6`

GPT sees the same one source crop independently. It does not see Mistral or the
Gemini transcription.

If Gemini and GPT agree sufficiently (text similarity >= 0.88 plus identical
numeric signature), the source repair is accepted. If GPT strongly confirms the
existing candidate instead, the candidate is retained. Otherwise the region
fails closed.

## Visual authority

Stage 4 may change text/answer fields only.

It must preserve:

- `visuals`;
- `visualSourceContract`;
- Stage-3 private storage/provenance metadata.

A source-only model can escalate a visual concern but cannot delete or replace a
deterministic Stage-3 visual.

The `exam_prep_mistral_stage4_runtime` facade also removes stale visual issue
codes that the legacy canonical text-quality helper may reintroduce after a text
repair, but only when the immutable Stage-3 visual contract is healthy.

## Unresolved policy

The issue code:

`stage4_verification_unresolved`

is statically production-critical. It remains critical independently of worker /
web import order and blocks publication.

A clean region never gets this code.

## Audit

Final extraction audit records content-free Stage-4 metadata:

- total regions;
- clean/suspicious region counts;
- primary calls;
- second-opinion calls;
- verified/repaired/unresolved/deferred counts;
- risk signals and scores by region;
- provider model / response IDs / token counts;
- source-visual requirement / uncertainty flags.

Raw model transcription is not copied into Stage-4 audit metadata. The accepted
repair, when any, becomes the normal canonical question/solution field.

## Zero-provider risk plan

Before spending on Gemini, replay the final risk policy against the existing
successful OCR bundle:

```powershell
$pdf = "C:\Users\Emad Karimi\Downloads\12T-Kanoon-Jame-20Tir1404-[konkur.in].pdf"
$bundle = "C:\Users\Emad Karimi\Downloads\ai-amooz-mistral-full-a.zip"
$out = "$env:TEMP\ai-amooz-stage4-risk-plan"

Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
Remove-Item -Force "$out.zip" -ErrorAction SilentlyContinue

python manage.py plan_exam_prep_mistral_stage4 `
  --pdf $pdf `
  --bundle $bundle `
  --output-dir $out `
  --recovered-solution-targets "4,5,6,10,15,26,30,57,74"
```

This command makes **zero provider requests**. It writes:

- `manifest.json` with projected call counts;
- `risk-plan.safe.json` with every content-free risk decision;
- `suspicious-crops/*.png` with the exact images that would be sent to a model;
- local Stage-3 diagnostic visual assets.

The recovered-target list above mirrors the already source-checked targeted
heading recoveries for the known 55-page source. It is only an input to this
research replay; production obtains these targets dynamically from Stage 2.

Do not run a paid Stage-4 batch until this plan shows a small, understandable
suspicious set.

## Focused offline tests

From `backend/`:

```powershell
python -m pytest `
  apps/classes/test_exam_prep_mistral_risk_engine.py `
  apps/classes/test_exam_prep_mistral_region_transcriber.py `
  apps/classes/test_exam_prep_mistral_stage4.py `
  apps/classes/test_exam_prep_mistral_stage4_runtime.py `
  apps/classes/test_exam_prep_mistral_stage4_boundary.py `
  apps/classes/test_exam_prep_mistral_production_core.py `
  apps/classes/test_exam_prep_mistral_production_boundary.py `
  -q
```

These tests make zero provider requests.

## Stage boundary

Stage 4 does not wire Celery to the OCR4 production runner. Live task cutover
remains a later release step after final integrity/UI/release-gate work.
