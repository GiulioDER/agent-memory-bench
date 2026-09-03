# Smoke test: RE-call preflight, retrieval telemetry, and staged decisions

Date: 2026-09-03

## Prediction

This smoke test uses one superseded-condition task, one seed, and the `bare` and `recall` arms.
It runs with `--emit-decisions --emit-decision-stages`.

Before any model session starts, the pilot should record a passed RE-call preflight containing:

1. an active generation for the selected tenant;
2. a corpus fingerprint matching the selected manifest;
3. a live MCP server exposing the required tools; and
4. one successful `recall_search` MCP call.

The resulting recall record should contain `memory_retrieval` telemetry with at least one
attempted call, and the attempted call should be classified as succeeded or failed rather than
being invisible behind `memory_call_count`.

The terminal decision should be recorded with stage `final`. I do not predict that this one smoke
session will emit all four intermediate stages, because those depend on whether the model chooses
to call `StructuredOutput` at the requested checkpoints. Missing stages must remain missing rather
than being inferred from prose.

## Procedure

Run one task and one seed from the current superseded corpus tenant, with the new preflight and
staged decision flags enabled. Do not overwrite any existing result directory. Inspect
`environment.json`, `records.final.jsonl`, and `admission.json` after completion.

## Interpretation

This is an instrumentation smoke test, not evidence about recall's task success rate. A failed
preflight is evidence that the run was correctly refused before model spend. A passed preflight
followed by a missing retrieval observation is evidence about model behavior, while a failed MCP
call is an integration failure that remains visible in the record.
