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

Measured 2026-09-03 on VPS2 with commit `2fffb05e`. The first live invocation was correctly
refused before model execution because the sourced environment did not export `git` or the API
variables. After explicitly exporting the existing variables and the documented location values,
the one cell completed with one admitted cell, both arms successful, recall search rate 1.000, and
estimated spend of $0.0067 over 111214 tokens. The active generation fingerprint matched
`0278cc651f14d9a5b3af319fc26d44184b119969794d751f6091405d864328aa`.

The record contained one successful recall call and one runtime decision. The first-class fields
reported attempted 1, succeeded 1, failed 0, abstained 0, hits 0, no trust states, and no error
codes. The staged trace observed `pre_action` only, so the completeness report correctly leaves
`evidence`, `action`, and `final` missing for this short session. The calibration path was also
exercised with an independent one-record label and produced the expected labelled artifact, but
remained uncertified because one record cannot provide both classes.

The post-run analyzer exposed and fixed one bug during this smoke: it previously recognized only
wrapper directories named `<run-id>-<condition>` and silently skipped direct `pilot.py` output.
Direct run discovery now recovers the condition from `environment.json` or the record metadata.
The prediction above is not edited after measurement.
