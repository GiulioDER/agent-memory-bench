# 020: Supermemory control only pilot after config directory wiring fix

Status: FROZEN before measurement.

The first full VPS2 pilot was invalid despite finishing in 68 minutes: all 90 Supermemory cells
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

The measurement is valid only if the smoke and full run are executed on VPS2 and the Supermemory
server is restored to its original environment after collection.

<!-- results are appended below this line -->
