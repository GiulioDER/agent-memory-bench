---
name: recall-decision-instrumentation-completion-smoke
description: "Live smoke test of retrieval telemetry, staged decisions, and calibration artifact output"
valid_from: 2026-09-03
metadata:
  node_type: preregistration
  type: benchmark
  run_kind: smoke
---

# Prediction

Before running the smoke, I predict that the matching superseded tenant on VPS2 will pass the
RE-call preflight and that the live recall session will record at least one successful memory call
in the first-class retrieval fields. I expect the model to emit a `pre_action` decision, but I do
not expect one short session to emit all four stages. The calibration command should produce a
JSON artifact with a frozen label source identity and an inclusion or exclusion ledger, although
the one-cell sample should remain uncertified because it cannot supply both calibration classes.

# Run configuration

The smoke uses the matching superseded corpus manifest, one task, one seed, the `bare` and
`recall` arms, staged decision emission, and the configured VPS2 runtime. It is a wiring smoke,
not a benchmark effect estimate.

# Result

To be appended after the live run. The prediction above is not edited after measurement.
