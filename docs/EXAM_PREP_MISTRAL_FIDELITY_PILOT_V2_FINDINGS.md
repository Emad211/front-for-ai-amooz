# Mistral OCR fidelity pilot v2 findings

Diagnostic only. No production pipeline change is justified by verifier output alone.

## Run contract

- Models: `gpt-5.4-mini`, `gemini-3-flash-preview`
- Six source regions in two three-item batches per model
- Four provider responses were HTTP 200
- No provider retry and no paid repair in v2
- Exact reported total provider cost across the four responses:
  - 0.02303 unit
  - 4,283.57 IRT
- GPT total: 0.0121395 unit / 2,257.94 IRT
- Gemini total: 0.0108905 unit / 2,025.63 IRT

## Artifact/runner result

The run is a failure bundle because Gemini batch 2 did not satisfy the local response contract. Its provider content contained a complete JSON object followed by extra structural junk, so strict `json.loads` rejected it. The first review in that batch also echoed the schema example id `q-001` instead of the requested S50 id.

All six source crops were visually inspected and were usable. The failure was not crop construction.

## Model-level evidence

### GPT-5.4-mini

Strengths:

- Both batch responses were valid structured JSON.
- Strong numeric/formula error detection on S50, S57, S133.
- Correctly read the critical S133 relation as `BM^2 = 2y^2`.
- Strong Q120 transcription-error detection.

Weaknesses:

- Severe cross-item image binding failure on Q65: the review used Q120 sine-function content as the Q65 source reading even though the Q65 image contains circuit options.
- Missed or underweighted source-visual requirements on S50 and S57.
- Q94 review was less precise than Gemini and mislabeled real A/B/C captions as hallucinated text.

Conclusion: multi-image batching is unsafe for high-accuracy source adjudication even when the JSON contract succeeds.

### Gemini 3 Flash Preview

Strengths:

- Correctly identified the missing four circuit option diagrams on Q65.
- Strong Q94 visual dependency detection and detected the `تایپوندی` vs `ناپیوندی` text error.
- Strong and detailed Q120 error detection.
- Correctly recognized omitted/necessary diagrams in S50 and S57.
- Strongly detected the repeated OCR `7` vs printed `2` corruption in S57.

Weaknesses:

- Batch 2 response contract was malformed after the first complete JSON object.
- Echoed an irrelevant schema-example id for S50.
- On S133, incorrectly reported the printed source relation as `BM^2 = 3y^2`; visual inspection confirms it is `BM^2 = 2y^2`.

Conclusion: visually useful, but not an unquestioned source-of-truth transcriber and not sufficiently contract-stable in the multi-item batch shape.

## Architecture consequence

Do not use multiple source images in one high-stakes OCR-verifier request.

Next calibration should mirror the likely production shape:

1. exactly one target region;
2. exactly one source image;
3. exactly one provider response;
4. no model-echoed item id;
5. no paid repair/retry;
6. deterministic local extraction of the first complete JSON object;
7. raw response and exact cost retained per call.

The discriminating re-test needs only Q65, Q94, S57, and S133. These four directly test the observed cross-image, visual-dependency, and source-formula failure modes while avoiding unnecessary repeat spend on already-concordant Q120/S50.
