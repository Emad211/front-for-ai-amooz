# Exam Prep — Mistral OCR 4 Exact-Repeat Findings

Date: 2026-08-08
Branch: `experiment/mistral-ocr-layout-probe`

This note records content-free evidence from two identical AvalAI Mistral OCR 4
requests over physical PDF pages 20, 39, and 40 of the representative 55-page exam.
No production path is changed by this work.

## Exact request identity

Both requests used:

- model `mistral-ocr-4-0`;
- the same selected mini-PDF SHA-256
  `60892097031c514b7bb45f91fbbdbf8f7100747cc2a86cf7bc552a1c85769f14`;
- 437,154 decoded PDF bytes;
- `include_blocks=true`;
- `confidence_scores_granularity=word`;
- header/footer extraction;
- HTML table output;
- no image base64;
- no annotation;
- no retry.

The provider-reported cost was exactly `0.0030000000` unit for each three-page run.
Latency was 16.640 s for the first run and 34.829 s for the repeat.

## Run-to-run text stability

| Physical page | Markdown similarity | High-confidence changed words | Formula instability |
|---|---:|---:|---|
| 20 | 1.000000 | 0 | no |
| 39 | 0.993647 | 5 | no |
| 40 | 0.930687 | 60 | yes |

Across all three pages:

- average markdown similarity: `0.974778`;
- minimum similarity: `0.930687`;
- changed words with confidence >= 0.95: `65`;
- pages with formula instability: `1`.

On page 40, 97 changed words were inside LaTeX/formula regions. Their mean confidence
was `0.905761`, median confidence was `0.976382`, and 59 of those changed formula
words had confidence >= 0.95.

Therefore word confidence is useful as a weak recognition-quality signal, but high
confidence cannot be interpreted as correctness and cannot be the publication gate.

## Geometry stability

The same two runs were compared using position-aligned OCR block/image bounding-box IoU.

| Physical page | Block mean IoU | Block minimum IoU | Image mean IoU |
|---|---:|---:|---:|
| 20 | 0.997306 | 0.933333 | 1.000000 |
| 39 | 0.999907 | 0.992248 | 0.997416 |
| 40 | 1.000000 | 1.000000 | 1.000000 |

No representative page crosses the geometry-instability threshold. Page 20 does have
block-label instability (`list` blocks became `text`) while its markdown and geometry
remain effectively unchanged.

This is strong evidence for treating OCR 4 geometry as substantially more reliable than
its exact formula transcription on this document.

## Full-document HTTP 400

A direct 55-page single-request probe returned HTTP 400 before any bundle could be
created. The current Microsoft Foundry model catalog documents `mistral-ocr-4-0` on the
Azure route as accepting PDF inputs up to 30 pages and 30 MB. AvalAI's published Mistral
OCR rate-limit tables identify its Mistral OCR provider route as Azure.

The 55-page request exceeds that documented page limit. This is the leading root-cause
hypothesis for the observed HTTP 400. The failed response body should still be retained
as provider evidence when available; the new chunked diagnostic also archives any future
HTTP failure automatically.

## Architecture consequence

The former requirement `one OCR request for all pages` is not portable to the current
AvalAI/Azure deployment. Replace it with:

```text
Render once locally
-> physically split only for provider transport (<=30 pages and bounded bytes)
-> minimum number of OCR 4 requests
-> normalize every returned page back to immutable physical page numbers
-> all page-role, RTL order, heading, region, visual, and integrity logic remains local
```

For the representative 55-page PDF this means two requests: pages 1-30 and 31-55,
unless the byte limit forces a smaller chunk.

Chunking must not create semantic boundaries. Question/solution continuation state is
maintained after OCR across physical pages, including across a provider chunk boundary.

## Next benchmark

Run the complete 55-page PDF twice through the bounded chunked diagnostic. Each complete
run should require the minimum two provider calls under the current page limit. Then:

1. analyze both runs locally for RTL order, regions, visuals, tables, and uncovered art;
2. compare both runs for markdown/formula/block-label/bbox stability;
3. localize disagreements to question/solution regions;
4. estimate how many regions require a paid visual verifier;
5. decide whether production needs one OCR pass plus targeted verification, or two OCR
   passes only for a narrow high-risk subset.

Do not make dual OCR a permanent production requirement until this full-document
benchmark quantifies its incremental value.
