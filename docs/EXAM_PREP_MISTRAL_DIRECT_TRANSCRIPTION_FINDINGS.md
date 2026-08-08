# Exam Prep Mistral Direct-Transcription Findings

Status: diagnostic evidence only. Production pipeline remains unchanged.

## Run contract

The calibration used four difficult regions: question 65, question 94, solution 57,
and solution 133. Each provider request contained exactly one source crop. The Mistral OCR
candidate was hidden from the transcriber. There were eight successful provider responses,
with no provider retry and no paid repair.

## Provider-reported cost and latency

For this run:

- GPT-5.4-mini: 4 calls, about 0.00775125 unit / 1,441.73 IRT, 20.94 s aggregate latency.
- Gemini-3-flash-preview: 4 calls, about 0.087949 unit / 16,358.52 IRT, 124.39 s aggregate latency.
- Total: about 0.09570025 unit / 17,800.25 IRT.

Gemini's cost was dominated by internal reasoning tokens. Across its four calls it used
28,383 completion tokens, while the final JSON transcripts were short. This makes default
Gemini thinking unsuitable as an always-on production repair path.

## Source-grounded observations

### Q65 — circuit options

Both direct transcribers recovered the printed question sentence and correctly required a
source visual. One-image-per-call eliminated the cross-image contamination seen in the older
multi-image verifier batch. The circuit geometry must remain a visual asset; textual labels are
not a substitute for the four option diagrams.

### Q94 — chemistry structures

Gemini produced the cleaner transcription and correctly classified the source visual as a
chemical structure. GPT independently corrected Mistral's `تایپوندی` corruption to `ناپیوندی`,
which shows that hiding the Mistral candidate reduced anchoring bias. However GPT still made
content-word errors (`یکنواده...` and `رایانه` instead of `رازیانه`). Therefore GPT direct
transcription is not sufficient by itself for chemistry terminology.

### S57 — optics worked solution

Both models recovered the important equations and numerical relations much better than the
full-page Mistral transcript. Both also marked the source diagrams as required. The rasterized
source crop itself contains damaged/box-like glyphs in the prose near the top, and both models
reported uncertainty. This region is not safe for automatic full-text replacement from the
raster transcription alone. Formula repair and visual preservation are still useful.

### S133 — geometry worked solution

GPT recovered the mathematical chain very well, including `AB = CD = 3y`, `BM^2 = 2y^2`,
`x = y`, and the final ratio `3`. Gemini also recovered the main mathematics but was less
reliable on surrounding metadata. Both models made author/footer transcription errors. Such
bylines and source-book footers should be removed deterministically rather than treated as
educational solution content.

## Architectural conclusions

1. One source crop per provider request is mandatory for fidelity repair. Multi-image batching
   is rejected for this path because it caused image-to-item contamination.
2. Local visual coverage is an independent authority. A text transcriber cannot remove a visual
   requirement established by deterministic geometry/coverage evidence.
3. Direct transcription must not blindly replace an entire Mistral region. It is best treated as
   independent evidence for risky text/formula spans.
4. GPT-5.4-mini is the current economical first candidate for formula/number repair, but its
   scientific terminology accuracy requires additional evidence.
5. Gemini-3-flash-preview is useful for chemistry/terminology escalation, but default thinking is
   too expensive. Minimal-thinking calibration is required before production routing is chosen.
6. Author bylines and source-book/page footers should be stripped by deterministic local rules.
7. Regions whose source raster contains damaged glyphs must remain explicit uncertainty/review
   candidates until the PDF text/render source is reconciled.

## Next experiments

- Compare Gemini 3 Flash `thinkingLevel=minimal` against the already-paid default-thinking Q94
  and S133 transcripts. This is a two-call cost/quality calibration only.
- Diagnose page 40 / solution 57 at the PDF text/render layer before spending more verifier calls.
- After these are resolved, run a broader GPT-primary / selective-Gemini calibration on new hard
  regions before integrating the repair router into production.
