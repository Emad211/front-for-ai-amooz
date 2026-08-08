# Exam Prep — Mistral OCR word-confidence findings

Branch: `experiment/mistral-ocr-layout-probe`

This note records private-diagnostic conclusions only. It does not change the production
Exam Prep pipeline.

## Observed three-page word-confidence run

Pages: `20,39,40` from the 55-page representative PDF.

The request used exactly one `mistral-ocr-4-0` call with:

- `include_blocks=true`;
- `confidence_scores_granularity=word`;
- HTML tables;
- extracted headers and footers;
- no image base64;
- no annotation;
- no retry.

Observed aggregate metrics:

| Physical page | Average confidence | Minimum confidence | Words | < 0.60 | < 0.80 | < 0.95 |
|---|---:|---:|---:|---:|---:|---:|
| 20 | 0.980433 | 0.587866 | 340 | 3 | 10 | 25 |
| 39 | 0.949592 | 0.165116 | 874 | 31 | 73 | 172 |
| 40 | 0.947335 | 0.122097 | 695 | 25 | 54 | 156 |

The provider completed all three pages in one request in about 16.64 seconds.

## Main conclusion

Word confidence is useful evidence, but it is not a correctness oracle.

Comparing the previous layout diagnostic with this word-confidence diagnostic showed:

- page 39 changed-word confidence was materially lower than stable-word confidence;
- page 40 contained substantial formula/text changes while many changed words still had
  confidence >= 0.95;
- page 20 kept nearly identical markdown apart from image identifiers, yet its block
  labels changed for several regions (`text` versus `list`).

Because the two compared requests were not byte-identical — the later request enabled
word confidence — this is not yet proof of pure stochastic run-to-run instability. The
next required diagnostic is an exact repeat of the same word-confidence payload.

## Architecture consequence

Do not route verification only from a fixed confidence threshold.

The local ambiguity gate must combine independent signals:

1. low word confidence;
2. formula density and malformed-LaTeX/anomaly checks;
3. missing rendered-page graphic coverage;
4. incomplete visual/table evidence;
5. sequence/heading recovery uncertainty;
6. controlled OCR instability evidence where available.

A high-confidence region may still require the targeted visual verifier when another
independent signal says the OCR transcription is ambiguous.

## Controlled repeat test

Run the exact same three-page word-confidence command a second time, changing only the
output directory. Then compare the two private ZIPs with:

```powershell
python manage.py compare_exam_prep_mistral_ocr_runs `
  --first "C:\path\ai-amooz-mistral-word-confidence.zip" `
  --second "C:\path\ai-amooz-mistral-word-confidence-repeat.zip" `
  --output "$env:TEMP\ai-amooz-mistral-word-confidence-comparison.json"
```

The comparison report is content-free. It measures markdown similarity, block-type
stability, changed-word confidence, formula instability, and high-confidence changed
words without writing OCR source text.

## Full-document test

The branch also includes a one-request full-document diagnostic:

```powershell
python manage.py probe_exam_prep_mistral_full_document `
  --pdf "C:\absolute\path\exam.pdf" `
  --output-dir "$env:TEMP\ai-amooz-mistral-full-document" `
  --allow-private-transmission
```

It sends the original PDF once, requests blocks plus word confidence, and locally writes
per-page renders/overlays/records for all pages. It performs no annotation and no retry.
The full ZIP is private and must not be committed.

## Production gate remains closed

Do not replace the production page-first extractor yet. We still need:

1. exact-repeat stability evidence;
2. the full 55-page one-request artifact;
3. all-page page-role, heading, RTL-column, visual-coverage and confidence analysis;
4. a measured ambiguity rate showing how many regions/questions would require the paid
   targeted verifier;
5. an end-to-end extracted exam comparison against the source PDF before publication
   integration.
