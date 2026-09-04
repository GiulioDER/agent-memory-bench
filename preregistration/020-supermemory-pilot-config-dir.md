# 020: Supermemory control only pilot after config directory wiring fix

Status: FROZEN before measurement.

The first full remote-host pilot was invalid despite finishing in 68 minutes: all 90 Supermemory cells
were discarded because the pilot did not pass each arm's isolated `config_dir` into
`ClaudeExecConfig`. The reduced smoke path did pass it and recorded the required lifecycle hooks.
This record freezes the prediction for the corrected run. The roster remains exactly `bare,
supermemory`, the model, task set, seeds, permissions, no `claude_md`, no `fs_grep`, amended direct
static Supermemory treatment, and five hour ceiling remain unchanged.

Prediction: the corrected reduced smoke will pass both executable checkers, record nonempty zero
exit `SessionStart` and `UserPromptSubmit` entries for Supermemory, accept the static memory corpus
without discarding a cell, and project the full run below 18,000 seconds. The corrected full pilot
will produce 180 records, admit all 90 paired cells, discard none for missing lifecycle hooks, and
finish below 18,000 seconds total wall time. I will not use the invalid pilot's outcome rates as a
benchmark result.

The measurement is valid only if the smoke and full run are executed on the remote benchmark host and the Supermemory
server is restored to its original environment after collection.

<!-- results are appended below this line -->

## Smoke result

The first corrected invocation, `smoke-supermemory-control-20260903-r7`, was invalid before
measurement because the noninteractive SSH PATH omitted the installed Claude executable. Both
cells were discarded before session start. It is not a product result.

The qualifying corrected smoke, `smoke-supermemory-control-20260903-r8`, ran on the remote benchmark host on
2026-09-03 with exactly `bare,supermemory`. Both cells passed `RESULT.txt == '4731'`, one paired
cell was admitted, and no cell was discarded. Supermemory accepted 135 explicit static memories
from 131 offered transcript files and verification returned five hits. `SessionStart` and
`UserPromptSubmit` both exited zero with nonempty output digests. Smoke elapsed time was 540.6
seconds, and the projected full run was 2,631.7 seconds, or 43.9 minutes. The timing gate passed.

Artifacts: `<supermemory-run-root>/results/smoke-supermemory-control-20260903-r8`
on the remote benchmark host. This qualifies the corrected full pilot prediction for the amended direct static
Supermemory treatment.

## Full pilot result

The corrected full pilot, `pilot-supermemory-control-20260903-r2`, ran on the remote benchmark host on 2026-09-03
with 180 records: 90 `bare` and 90 `supermemory`. Wall time was 82 minutes, below the 18,000
second five hour ceiling. The run admitted 89 paired cells and discarded one cell, the `bare`
control for `ts-legacy-hash`, seed 2, which exceeded the configured 600 second Claude timeout.

All 90 Supermemory records have both required lifecycle hooks, `SessionStart` and
`UserPromptSubmit`, with exit code zero and nonempty output digests. No Supermemory cell was
discarded. Among the 89 admitted pairs, `bare` passed 42 of 89 cells and `supermemory` passed 15
of 89 cells. These are the valid control only pilot outcomes; the earlier invalid 68 minute pilot,
which discarded every Supermemory cell for missing hook ledgers, is excluded.

Artifacts: `<supermemory-run-root>/results/pilot-supermemory-control-20260903-r2`
on the remote benchmark host. The temporary Supermemory server was stopped, its original environment file was restored,
and port 6767 is closed.
