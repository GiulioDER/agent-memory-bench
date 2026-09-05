# 040: Supermemory corrected official replacement run

Status: FROZEN before the replacement measurement.

## Question

Does the pinned Supermemory Claude Code integration improve execution graded task success over
the same `bare` control on the frozen AMB official grid when both of the vendor's lifecycle
injection paths are enabled?

## Relationship to the previous run

This is a replacement measurement for `supermemory-003`. The previous artifacts remain unchanged
and are not silently relabelled. The replacement corrects the isolated home setup, records the
structured hook result, rejects fail-open integration errors at admission, and restores the
vendor documented `maxProfileItems` default of 5.

## Frozen treatment

Supermemory Local remains pinned at version 0.0.8, and the official Claude plugin remains pinned at
commit `e6227edc4f33b83317cfde2e7cd9790c794d22d1`. The run uses the same `protocol` instruction,
task roster, five session seeds, five condition feeds, model, prices, and direct static memory
corpus as `supermemory-003`, so the measured treatment change is the profile setting plus the
validated hook instrumentation.

The isolated home contains `~/.claude/` so the vendor's optional statusline setup cannot fail due
to a missing parent directory. `maxProfileItems` is set to 5. SessionStart profile context and
UserPromptSubmit recall context are recorded as byte counts and hashes without storing raw hook
payloads in the ledger. A hook that exits successfully but reports a Supermemory integration
error is not admissible.

## Prediction

The replacement should produce SessionStart profile context in a substantial fraction of
reachable sessions and should score materially above `supermemory-003` if the profile path was the
main cause of the previous result. Prompt time recall should remain selective, because the pinned
vendor hook injects only fresh matches above its own threshold. If the result remains very low
after these corrections, the evidence will support a genuine contamination or retrieval quality
problem rather than a missing profile injection.

## Eligibility and reporting

The replacement is eligible for review only if all ordinary records, streams, costs, admission
artifacts, and condition artifacts are present; every admitted Supermemory session has both
required lifecycle hooks; no admitted hook reports an integration error; the run is reproducible
against `official-003`; and `scripts/verify_run.py` plus `scripts/build_arm_submission.py --check`
pass. The result will be published separately as `supermemory-004` only after review of the
structured hook evidence.
