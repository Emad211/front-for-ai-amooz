# Stage 3 Visual Validation — zero provider calls

This procedure validates the precise visual subsystem without paying for a new
OCR request. It reuses the existing successful full-document OCR bundle and the
original PDF.

## 1. Focused offline tests

From `backend/`:

```powershell
python -m pytest `
  apps/classes/test_exam_prep_mistral_visuals.py `
  apps/classes/test_exam_prep_mistral_visual_runtime_hardening.py `
  apps/classes/test_exam_prep_mistral_visual_review.py `
  apps/classes/test_exam_prep_mistral_visual_only_options.py `
  apps/classes/test_exam_prep_mistral_visual_content.py `
  apps/classes/test_exam_prep_mistral_visual_boundary.py `
  apps/classes/test_exam_prep_mistral_visual_replay.py `
  apps/classes/test_exam_prep_mistral_production_boundary.py `
  apps/classes/test_exam_prep_mistral_production_core.py `
  -q
```

Provider calls: **0**.

The suite covers Smart Union, decorative suppression, grouped options,
independent option binding, graph-axis false positives, residual annotations,
table border risk, raster clipping, source-visual contracts, review/publish
persistence, private streaming and Stage 2/3 architecture boundaries.

## 2. Full local replay from the existing OCR bundle

Use the original 55-page source PDF and the successful
`ai-amooz-mistral-full-a.zip` bundle:

```powershell
$pdf = "C:\Users\Emad Karimi\Downloads\12T-Kanoon-Jame-20Tir1404-[konkur.in].pdf"
$bundle = "C:\Users\Emad Karimi\Downloads\ai-amooz-mistral-full-a.zip"
$out = "$env:TEMP\ai-amooz-mistral-visual-stage3-replay"

Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
Remove-Item -Force "$out.zip" -ErrorAction SilentlyContinue

python manage.py replay_exam_prep_mistral_visual_stage3 `
  --pdf $pdf `
  --bundle $bundle `
  --output-dir $out

Copy-Item `
  "$out.zip" `
  "C:\Users\Emad Karimi\Downloads\ai-amooz-mistral-visual-stage3-replay.zip"
```

The command makes **zero provider requests** and rejects failure/incomplete OCR
bundles. The final terminal line explicitly reports:

```text
providerRequests=0, pages=55, assets=..., reviewOnly=..., unresolved=...
```

## 3. Replay artifacts

The replay ZIP contains:

- `manifest.json`
  - source SHA, page count, providerRequests=0 and aggregate Stage-3 stats;
- `visual.audit.json`
  - unresolved/review-only/critical visual evidence;
- `visual.questions.json`
  - compact question-by-question visual inventory;
- `projection.stage3.json`
  - canonical projection after Stage 3;
- `stored-files.json`
  - mapping from production-style private storage paths to local diagnostic files;
- `stored/exam-prep/source/visuals/v1/...`
  - every generated crop as a real PNG for human inspection.

The diagnostic files mirror the production private storage names but never write
to production object storage.

## 4. Mandatory known-case inspection

Before accepting Stage 3, inspect at minimum:

### Q65 — grouped circuit options

Expected:

- one `grouped_options` visual when OCR/source gives the circuits as one block;
- all four circuits visible;
- no unrelated question prose inside the crop;
- option labels/necessary circuit labels retained;
- not `reviewOnly` only if source option evidence is complete.

### Q81 and Q89 — visual/table content

Expected:

- complete table border;
- required cells/header/embedded visual retained;
- no clipped cell or table edge;
- `visual_table_border_risk` if the source region cannot prove full coverage.

### Q94 — chemical structures

Expected:

- OCR image candidates plus local uncovered-rendered graphics recover the
  structure missed by OCR;
- the final crop set contains all required structures/labels A/B/C;
- a missing structure must appear as residual/unresolved, never silently pass.

### Q150 — independent visual options

Expected:

- four independent option assets only if explicit external source markers 1..4
  bind one-to-one;
- graph/axis tick numbers must not be option labels;
- uncertain binding becomes grouped/review-only instead of guessed option assets.

### Solution visuals (including S57/S133 where present)

Expected:

- `role=solution`;
- independent storage/identity from the question visual;
- labels/equations immediately tied to the diagram included when required;
- no semantic deduplication against the question-side crop.

## 5. Acceptance criteria for Stage 3

Stage 3 can be considered empirically closed when:

- focused offline tests pass;
- replay reports `providerRequests=0`;
- no unexpected whole-page fallback appears for the mandatory known cases;
- Q65/Q81/Q89/Q94/Q150 and relevant solution visuals are source-complete by
  direct image inspection;
- any ambiguous crop is `reviewOnly` and carries a critical visual issue;
- no obvious logo/header/footer is attached to a question;
- no legitimate repeated body diagram is suppressed as decoration;
- visual-only options survive teacher re-audit without `missing_option_text` only
  when the source visual contract proves a complete safe option set;
- deleting/losing a required Stage-3 asset makes review fail closed;
- the live Celery runner remains unchanged until later rollout stages.

If the replay exposes a false positive/negative, fix the deterministic visual
policy and rerun this same zero-cost replay. Do not spend another OCR request for
Stage-3 tuning because the successful OCR bundle already contains the needed
provider evidence.
