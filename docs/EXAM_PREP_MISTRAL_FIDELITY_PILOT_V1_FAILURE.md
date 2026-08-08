# Mistral OCR Fidelity Pilot V1 Failure Findings

## Scope

This note records the content-free failure mode of the first six-region fidelity pilot. It is diagnostic evidence only; production remained unchanged.

## What succeeded

- Both verifier model preflight checks returned HTTP 200 and were accessible.
- The six intended source crops were generated successfully.
- Visual inspection confirmed the crops preserve the intended target content for Q65, Q94, Q120, S50, S57, and S133.
- The selected models were `gpt-5.4-mini` and `gemini-3-flash-preview`.

## What failed

The first verifier batch (`q-065`, `q-094`, `q-120`) failed before a schema-valid review was produced.

The first request used `response_format={"type":"json_object"}` but the prompt did not explicitly contain the word `json`. AvalAI rejected it with HTTP 400 and an `invalid_request` message requiring the word `json` in the messages.

The generic structured-output layer then fell back to a request without JSON mode. That request returned HTTP 200, but the resulting content was not parseable as a JSON object. The generic repair path issued another HTTP 200 request, but that repair call did not include the source images, which is unsuitable for a source-image fidelity benchmark.

No verifier review was accepted and no verifier model completed.

## Local database noise

The local PostgreSQL server was not running. Usage/error logging attempted to write `LLMUsageLog` rows and emitted connection errors. Those database failures were noisy but were not the root cause of the verifier benchmark failure.

Because the generic runner did not archive the two successful provider responses and the local usage logger could not persist their usage metadata, the exact billed cost cannot be reconstructed from the pilot bundle alone.

## Architecture correction

The economical pilot now uses a dedicated direct verifier runner:

1. explicit JSON wording in the prompt;
2. one `json_object` request per batch;
3. no automatic retry;
4. no automatic structured repair;
5. no dependency on local database logging;
6. raw private provider response saved after every call;
7. content-free safe request metadata saved after every call;
8. partial accepted verifier reviews persisted after every successful batch;
9. failure bundles retain the exact failed model and batch IDs;
10. the six source crops remain unchanged because their source coverage was verified.

With batch size 3, the v2 pilot has exactly four intended paid verifier calls: two batches per model across two models.

## Interpretation

This V1 run provides no evidence about verifier accuracy. It only identifies a runner/protocol failure. The next valid pilot must complete the direct v2 path before any conclusion is drawn about `gpt-5.4-mini`, `gemini-3-flash-preview`, or Mistral OCR transcription fidelity.
