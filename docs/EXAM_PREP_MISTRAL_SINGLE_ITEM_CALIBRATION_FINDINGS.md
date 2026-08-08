# Mistral OCR single-item verifier calibration findings

Date: 2026-08-08

Branch only: `experiment/mistral-ocr-layout-probe`. Production is unchanged.

## Run contract

- 4 source regions: Q65, Q94, S57, S133.
- 2 economical multimodal verifier models: `gpt-5.4-mini`, `gemini-3-flash-preview`.
- Exactly one source crop per provider call.
- 8/8 provider calls returned HTTP 200.
- 8/8 reviews were accepted.
- No automatic retry and no paid repair.
- Total provider-estimated cost: 0.03354375 unit / 6239.14 IRT.

Per-model totals:

- `gpt-5.4-mini`: 4 calls, 0.01167375 unit, 2171.32 IRT, 7430 total tokens, 15.454 s aggregate latency.
- `gemini-3-flash-preview`: 4 calls, 0.02187 unit, 4067.82 IRT, 12540 total tokens, 34.188 s aggregate latency.

## Cross-image contamination result

The multi-image pilot failure mode disappeared when each request contained exactly one image. GPT no longer associated Q65 with Q120 content, and Gemini returned valid accepted structured reviews for all four single-item calls.

Conclusion: verifier and transcriber calls must remain one-source-region-per-call. Batching unrelated source images is rejected for the accuracy-first pipeline even when it is cheaper.

## Source-grounded findings

### Q65 — circuits

The Mistral candidate preserves the question stem but omits the four answer-option circuit diagrams. The printed diagrams are essential source visuals.

- Gemini correctly sets `sourceVisualRequired=true` and identifies the omitted diagrams.
- GPT identifies the omission but sets `sourceVisualRequired=false`.

The text itself is usable if paired with the source visual. This exposes a contract problem: textual fidelity and visual completeness must be separate signals.

### Q94 — chemistry structures

The source contains three chemical structures A/B/C. Mistral omits the structures and mistranscribes `ناپیوندی` as `تایپوندی`.

- Gemini identifies both the missing chemical structures and the terminology error; it treats H₂ formatting as minor.
- GPT recognizes that the structures are missing but fails to flag the `ناپیوندی` transcription error and sets the visual-required flag false.

Gemini is materially stronger on this chemistry/visual example.

### S57 — physics optics solution

The Mistral solution is severely corrupted. Confirmed source values include:

- heading Q57, option 3;
- `2α + 2γ + θ = 180°`;
- `θ = 2β - 180°`;
- `β = (50 + 180) / 2 = 115°`;
- `x = (180 - 30) / 2 = 75°`;
- `β' = 180 - (30 + 75) = 75°`;
- final difference 40°;
- two source diagrams are required.

Both verifiers catch the major formula corruption and require the visual. GPT additionally raises a false positive around the visible `θ=50°` line; Gemini is cleaner on this item.

### S133 — geometry solution

The source contains distinct coefficients that must not be conflated:

- `AB = CD = 3y`;
- `DM = 2y` within the similarity relation;
- `BM² = 2y²`;
- final ratio `AB/BC = 3`.

- GPT distinguishes the `3y` and `2y` roles correctly and catches the gamma/digit corruption in Mistral.
- Gemini correctly recognizes many gamma-vs-digit errors but overgeneralizes the coefficient as 2 in places where the source is 3 and also reports an incorrect source page reference.

GPT is materially stronger on this formula-heavy geometry example.

## Architecture consequences

1. One source crop per verifier/transcriber call is mandatory.
2. Deterministic local visual evidence is authoritative for known visual requirements. A verifier may escalate visual risk but must never de-escalate a local visual requirement.
3. `candidate text usable` and `source visual required` must be modeled independently. Missing a diagram must not by itself invalidate otherwise correct linear text.
4. No verifier output is truth by itself. Model-produced corrections still require source-grounded validation on critical digits, operators, exponents, chemical terminology, and answer labels.
5. Current evidence does not support one universal verifier model:
   - Gemini Flash is stronger on Q65/Q94 visual/chemistry and cleaner on S57.
   - GPT mini is cheaper/faster and stronger on S133 formula distinctions.
6. The next calibration must test independent direct transcription from the source crop without exposing the Mistral candidate. This measures whether either economical model can reliably produce the repaired production text rather than merely detect errors.
