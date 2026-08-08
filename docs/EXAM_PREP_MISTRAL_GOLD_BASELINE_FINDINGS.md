# Mistral OCR4 Gold-48 Baseline

This is a strict publish-safe gate on a deliberately hard-balanced 48-region source set. It is **not** an estimator of average whole-PDF accuracy.

## Result

- Gold regions: 48 (26 question, 22 solution)
- Strict publish-safe pass: 7 / 48 = 14.58%
- Question pass: 7 / 26 = 26.92%
- Solution pass: 0 / 22 = 0%
- Local-only visual repair: Q81 (text acceptable, source visual must be preserved)
- Independent Gemini recovery targets: 40

Strict baseline passes:

- Q33
- Q46
- Q57
- Q65
- Q110
- Q140
- Q150

Q81 is excluded from paid recovery because its readable text is acceptable and the remaining failure is visual preservation only.

## Dominant failure modes

Failure categories overlap by item:

- formula / mathematical-symbol fidelity: 24
- Persian/scientific text fidelity: 16
- critical number fidelity: 8
- source-visual dependency/coverage: 6
- hallucinated/repeated text: 5
- answer/option label corruption: 2

The worked-solution side is the clear bottleneck. Repeated stable corruption, formula symbol substitution (for example 2/3 becoming other glyphs), and source-font tofu make raw full-page OCR unsuitable for direct publication.

## Interpretation

The 14.58% number must not be reported as average document accuracy. The Gold-48 set intentionally over-samples diagrams, formulas, chemistry structures, RTL layouts, hard solutions, and previously observed failure modes. Its purpose is to be a high-sensitivity release gate.

The full-document structural layer remains strong (question numbering/boundaries were previously closed to 155/155 after deterministic targeted recovery). The remaining work is semantic fidelity, especially solutions.

## Test-3 policy

- Keep the 7 strict Mistral passes.
- Repair Q81 locally by preserving its source visual; no LLM call.
- Send only the 40 true semantic failures to `gemini-3-flash-preview`.
- Use one source crop per call.
- Hide the Mistral candidate to avoid anchoring bias.
- Use `thinkingLevel=minimal` via AvalAI provider-specific parameters.
- No automatic retry and no paid repair.
- Capture every AvalAI `x-request-id` and batch lookup exact cost through `/user/v1/transactions/lookup`.
- Test 4 is residual-only: only items still failing after Test 3 may use GPT-5.4-mini or deterministic repair.
