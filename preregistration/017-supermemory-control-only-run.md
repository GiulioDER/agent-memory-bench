# 017: Supermemory control-only qualification run

Status: FROZEN before the reduced-roster smoke measurement.

## Run roster

The qualification and full benchmark run only the amended Supermemory treatment and the `bare`
control arm. Recall, `claude_md`, and `fs_grep` are not part of this run. The control arm is the
same task and seed workload without a memory product, so the Supermemory delta remains attributable
to the adapter and service treatment being tested.

## Prediction and gates

Before measurement, I predict that both offered arms will complete the smoke, the Supermemory
ingest will accept every deterministic static memory part with no discard, both required
Supermemory lifecycle hooks will pass admission, the smoke will remain under 600 seconds, and the
24-task by 3-seed full run will project below 18,000 seconds.

The full run must use the same reduced arm roster, task roster, seed roster, pinned plugin, pinned
server, amended Supermemory ingestion mode, and admission rules. Results are reported as a
Supermemory versus bare-control comparison, not as a multi-competitor ranking.

<!-- results are appended below this line -->
