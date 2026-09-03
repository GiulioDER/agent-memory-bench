# Retry smoke test: Claude executable on the detached shell PATH

Date: 2026-09-03

The matching corpus retry passed the new RE-call preflight, but both model sessions were refused
by the existing harness because the direct SSH shell did not export the official Claude install
directory. The result is retained as a setup failure and is not reclassified.

## Prediction

With the official Claude directory added to `PATH`, the same one task and one seed smoke should
complete both the bare and recall sessions. The recall session should retain the already observed
preflight record and expose `memory_retrieval` telemetry. The terminal decision should carry stage
`final` if the model reaches structured output. Intermediate stages remain conditional on actual
runtime emission.

## Procedure

Use a fresh run id and the matching superseded manifest, with `PATH` set as in the official launcher,
`--emit-decisions`, and `--emit-decision-stages`. Inspect the environment, session records, and
admission artifact.

## Interpretation

This remains an instrumentation smoke test, not evidence about task performance. A successful
cell is required to validate record emission; a preflight pass followed by a model startup failure
is an environment failure and remains separately visible.

## Result, measured 2026-09-03

Command: direct `scripts.pilot` invocation using the official Claude PATH, the matching superseded
manifest, the current superseded tenant, and the run id
`recall-preflight-stage-smoke-20260903-path-retry`.

The preflight passed. One cell was admitted. The recall session made one successful memory call,
recorded 956 milliseconds of latency, and exposed retrieval telemetry with one attempted and one
successful call. The runtime emitted a `pre_action` abstention with confidence 1.0. It did not write
the task file, so no `action` or `final` stage was observed. The terminal structured result echoed
the same `pre_action` payload, which exposed a parser duplication fixed after this run. The smoke
validated preflight and retrieval telemetry, but it did not validate a terminal `final` stage.
