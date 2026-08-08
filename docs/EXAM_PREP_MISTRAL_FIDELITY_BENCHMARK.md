# Exam Prep — Mistral OCR transcription fidelity benchmark

Branch: `experiment/mistral-ocr-layout-probe`

This benchmark is diagnostic only. It does not update production Exam Prep records.

## Structural prerequisite

The full-document + targeted-recovery evidence for the representative 55-page PDF now
supports the structural contract required before transcription work:

- 155/155 question anchors;
- 155/155 projected solution anchors after target-only recovery;
- zero remaining solution-heading gaps;
- zero remaining invalid answer labels after the Q57 targeted recovery;
- non-target disagreements are never allowed to overwrite the base run.

The transcription benchmark therefore treats question/solution boundary discovery as a
separate, already-audited layer. It does not use verifier output to change boundaries.

## Crop storage policy

There are two different kinds of crops and they must not be conflated.

### Diagnostic benchmark crops

Temporary benchmark crops are written only to the command `--output-dir` and the
private diagnostic ZIP. They are disposable and can always be regenerated from the
original PDF/full-run bundle. They must not be committed or persisted as product media.

### Product visual/source crops

Only source crops that are actually needed by a question, option, or worked solution
should become persistent product assets. The existing `ExamPrepVisualAsset.source_file`
field already uses the private `answer_sources` storage alias and the logical key prefix:

`exam-prep/visuals/source/`

Generated alternatives use:

`exam-prep/visuals/generated/`

When S3 is active, `answer_sources` is private S3-compatible object storage. When S3 is
inactive, the same alias resolves to local `BASE_DIR/private_answer_media`, so a local
source visual is stored under approximately:

`backend/private_answer_media/exam-prep/visuals/source/`

The generic public media proxy explicitly rejects `exam-prep/visuals/` paths. Product
source crops therefore remain private and should be served only through owner/session
scoped application endpoints.

## Why two independent verifiers

Mistral OCR 4 has shown several different failure modes on the representative PDF:

- high-confidence formula transcription can change across otherwise identical OCR runs;
- word confidence can be high for a wrong answer-label digit;
- OCR visual blocks can omit meaningful line art;
- targeted column OCR can recover missing boundaries while introducing new errors in
  already-correct neighboring answer labels.

A single second model must therefore not be treated as ground truth. The benchmark sends
the same source crop and Mistral candidate to two independently selected multimodal
models. Only consensus is considered strong evidence. Verifier disagreement remains an
explicit review/risk signal.

No verifier output auto-repairs the OCR candidate in this diagnostic.

## Default challenge set

The default set deliberately covers biology visuals, physics diagrams/formulas,
chemistry structures/tables, math formulas/graphs, geology visual options, and
formula-heavy worked solutions. It is capped and configurable using `--targets`.

Boundary-recovered solution 74/94 are intentionally not default solution targets in this
benchmark because their old base-run regions are not unique. Their question-side source
regions are still benchmarked. This keeps transcription fidelity separate from boundary
recovery.

## Run

Before running, explicitly route the shared OpenAI-compatible client to AvalAI in the
current PowerShell session:

```powershell
$env:AVALAI_BASE_URL = "https://api.avalai.ir/v1"
```

The API key must also exist in the same shell:

```powershell
$env:AVALAI_API_KEY = "..."
```

Then run from `backend/`:

```powershell
$out = "$env:TEMP\ai-amooz-mistral-fidelity"
Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
Remove-Item -Force "$out.zip" -ErrorAction SilentlyContinue

python manage.py probe_exam_prep_mistral_fidelity_benchmark `
  --bundle "C:\Users\Emad Karimi\Downloads\ai-amooz-mistral-full-a.zip" `
  --output-dir $out `
  --models "gpt-5.5,gemini-3.1-pro-preview" `
  --batch-size 3 `
  --allow-private-transmission

Copy-Item "$out.zip" `
  "C:\Users\Emad Karimi\Downloads\ai-amooz-mistral-fidelity.zip"
```

## Bundle contents

The ZIP contains:

- `q-*.png` / `s-*.png`: private source crops;
- `candidates.private.json`: Mistral candidate text and source mapping;
- `verifier.<model>.private.json`: detailed discrepancy reports;
- `targets.json`: content-free crop/source metadata;
- `consensus.json`: content-free cross-model architecture report;
- `manifest.json`: benchmark parameters and completion state;
- `failure.json`: written before archiving if a verifier fails.

## Interpretation rules

1. The source image is authoritative; models must not solve or infer intended content.
2. A changed digit, operator, exponent, variable, chemical symbol, or answer label is at
   least a major semantic problem.
3. Harmless whitespace/Markdown differences do not count as OCR errors.
4. `consensusCritical=true` is strong evidence that the Mistral candidate needs a repair
   path before publication.
5. `verifierDisagreement=true` is not a pass or fail; it is an ambiguity signal.
6. `sourceVisualRequiredByAll=true` supports preserving a source crop instead of trying
   to force a diagram/table into text.
7. This benchmark does not auto-correct any question or solution.

## Final full-document test

After the fidelity policy, visual union-crop policy, and bounded provider retry/resume
policy are implemented, run one final end-to-end test on the complete representative PDF.
That final test must start from the original PDF and exercise the production-shaped path,
not reuse diagnostic OCR text. It should emit a complete audit proving question/solution
coverage, visual coverage, transcription-risk handling, provider calls/retries, persisted
private visual assets, and publication readiness.
