# Stage 3 visual replay findings — 2026-08-09

Source: `ai-amooz-mistral-visual-stage3-replay.zip`

This is a forensic record of the first zero-provider replay. It supersedes the
assumption that a large teacher-review queue is acceptable. Teacher review is not
the default correction mechanism for extraction quality.

## Measured first-replay output

- provider requests: 0
- PDF pages: 55
- pages scanned: 51
- assets attached: 126
- question visuals: 36
- option visuals: 0
- solution visuals: 90
- review-only assets: 103
- unresolved regions: 55
- local graphic candidates: 142
- OCR visual candidates: 73
- whole-page fallbacks: 1

Source-kind split in the canonical projection:

- 66 `local_graphic` only
- 52 `ocr_image` only
- 5 `ocr_table` only
- 2 mixed `local_graphic + ocr_image`
- 1 whole-page review fallback

Of the 66 local-only assets, 65 were solution-role assets. Their median page area
was roughly 0.15% of the page. Direct montage inspection showed that many are not
educational visuals at all: they are residual Persian words, answer headings,
glyph fragments, formulas, or paragraphs.

## Why 103 review items is not a teacher problem

The first replay produced 95 assets with `visual_crop_clipped` and 19 with
`visual_residual_graphics`. The clipping rule used dark ink on the final raster
edge as a publication blocker. This confuses two very different cases:

1. an educational diagram is actually cut;
2. unrelated prose extends beyond an over-broad provider image bbox and happens
   to touch the crop edge.

The known crops demonstrate the second case repeatedly. Therefore raw raster
edge ink is no longer a publication blocker. Clipping must be established from
source visual geometry/core coverage instead.

Likewise, merely reducing review thresholds would be unsafe: several assets that
were marked `reviewOnly=false` were still plain residual solution text. The
pipeline must remove false assets, not hide their warnings.

## Known-case crop inspection

### Q65

The grouped crop contains all four circuits and printed option labels, so the
source evidence is present. However, it also includes an unrelated line of the
question stem at the top. The old `visual_crop_clipped` flag is mostly reacting
to that extraneous text, not to an incomplete circuit.

Required fix: refine the OCR image bbox to the rendered graphic core after
masking OCR text, then add short labels back with Smart Union.

### Q81

The table is complete, but the crop includes the atomic-mass/prose line above and
option prose below. The table provider bbox is the useful authority; generic
Smart Union was too permissive.

Required fix: table crops use complete table bbox + bounded padding. They do not
union surrounding option/stem prose.

### Q89

Same class as Q81: the table itself is complete, but unrelated option prose is in
the crop.

### Q94

All three chemical structures A/B/C are visible. This is important evidence that
OCR image blocks plus local rendered graphics can recover a structure missed by
OCR. The crop is nevertheless too broad because option prose is included below.

Required fix: text-masked rendered-core refinement while preserving A/B/C via
Smart Union.

### Q150

The grouped source crop is visually good: all four graphs and the printed 1..4
labels are visible. Requiring four independent bound assets is unnecessary and
caused a false `visual_option_binding_unresolved` blocker.

Policy change: a source-faithful grouped option panel is publishable without
fabricating four crops. The UI can show the panel and four selectable labels.

### S50 / S57

Provider image blocks include the actual diagram but also large portions of the
worked solution, prose, and equations. These are valid source regions but not
precise visual assets.

Required fix: mask textual OCR blocks on the rendered page, discover the graphic
core inside the provider image region, and Smart Union only short diagram labels
back into the final crop.

### S133

Question 133 has source pages `[28, 53]` and a worked solution, but the first
Stage-3 replay produced no solution visual for it. This is the opposite failure
mode from the noisy local solution candidates: a real vector geometry diagram
can exist without an OCR image block.

Policy change: local-only solution detection is not globally disabled. It is
replaced by **strong local solution recovery**: after text masking, only large,
structural connected components are accepted. Small words/glyphs/paragraph
residuals are rejected.

### Q79 whole-page fallback

The single whole-page fallback contains multiple questions and is not an
acceptable product visual. The page includes vector option structures that a
correct text-masked local detector should isolate. Whole-page evidence remains a
machine/debug fallback only and is never publish-safe.

## Stage-3 v2/v3 policy resulting from the replay

1. OCR `image` blocks are refined against the rendered page:
   - mask every OCR textual block;
   - detect remaining connected graphic cores;
   - shrink only when the surviving core is substantial;
   - Smart Union short labels/captions back afterward.
2. OCR `table` blocks use table geometry directly with bounded padding.
3. permissive local-only solution detection is removed.
4. strong local-only solution recovery accepts only large structural components
   after text masking, preserving cases such as S133.
5. raw raster edge ink is not a publication blocker.
6. geometry/source completeness still fail closed.
7. grouped visual options are valid source evidence; individual image binding is
   required only when the product actually stores separate option assets.
8. unresolved Stage-3 evidence proceeds to the later machine risk/verifier stage;
   it is not a queue of work assigned to teachers.

## Expected next replay

The next zero-provider replay should materially reduce the asset count because
residual solution typography is removed. Success is not measured only by a lower
`reviewOnly` count. The mandatory acceptance check is direct source fidelity of
Q65/Q79/Q81/Q89/Q94/Q150 and solution diagrams such as S50/S57/S133, plus a
montage confirming that plain words/paragraphs are no longer emitted as visuals.
