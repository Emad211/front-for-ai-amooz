# Exam Prep Source Map readiness incident

## Observed production behavior

Immediately after upload, rendered PDF pages appeared twice and every page was shown with the default `unknown` role.

## Root causes

1. The embedded source workspace was mounted both by `PipelineTracker` and `CreateClassPage`.
2. Rendered page rows were treated as a valid Source Map before a classification fingerprint existed.
3. The page classifier did not include the deployment-wide `MODEL_NAME` in its environment-only fallback chain.

## Required contract

- The source workspace has exactly one mount point in the existing exam-preparation create flow.
- `hasSourceMap` remains false until `classification_fingerprint` exists.
- The editor remains hidden while any document is uploading, rendering, or classifying.
- Page classification model selection is: `EXAM_PREP_V4_CLASSIFICATION_MODEL` → `PDF_VISION_MODEL` → `MODEL_NAME`.
- Missing model configuration fails visibly; default `unknown` page rows are never presented as completed classification.
