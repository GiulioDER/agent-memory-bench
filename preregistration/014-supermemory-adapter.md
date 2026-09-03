# 014: Supermemory adapter smoke and timing gate

Status: DRAFT until committed; the prediction section is frozen after commit.

## Question

Does the official Supermemory Claude Code integration run as an isolated AMB hook arm, ingest the
shared corpus through Supermemory's write API, and remain fast enough for a full 24 task by 3 seed
comparison within five hours?

## Frozen treatment

The arm is `supermemory`, using the official `supermemoryai/claude-supermemory` plugin at the
version recorded in `adapters/supermemory/config.frozen.json`. The default service is
Supermemory Local at `http://localhost:6767`; the adapter may point at another explicitly supplied
Supermemory API URL, but it must never silently fall back to the hosted service. The plugin files
are supplied by `SUPERMEMORY_PLUGIN_DIR` and are copied into the isolated hook configuration.

The adapter uses the vendor's own `/v3/documents` write path for every transcript and the vendor's
own Claude Code lifecycle hooks for session start, prompt recall, and stop capture. The benchmark
model, task, sandbox, permissions, and non memory tools remain controlled by the harness.

## Smoke endpoint

The smoke roster is `bare,claude_md,fs_grep,recall,supermemory`, one task, one seed. A smoke is
successful only if all of the following hold:

1. Every offered transcript is accepted by Supermemory and the adapter reports at least one stored
   item.
2. The Supermemory SessionStart and UserPromptSubmit hooks appear in the recorded hook ledger,
   each with exit code zero and a nonempty output digest.
3. The MCP and hook admission gate discards no cell.
4. The smoke completes in no more than 600 seconds.
5. The conservative projection for the same arm roster over 24 tasks and 3 seeds is no more than
   18,000 seconds. The projection is measured ingestion time once plus the observed agent session
   time multiplied by 72.

The projection is a timing gate, not a performance claim about Supermemory. A failed timing gate
means the adapter is not ready for the full comparison, even if the task itself succeeds.

## Prediction

I predict that the smoke will satisfy all five conditions, with the projected full run below five
hours. I predict that local Supermemory ingestion will be the dominant adapter overhead and that
the hook overhead will remain below the session timeout budget.

## Exclusion rule

No full comparison starts from a smoke that fails any condition above. A failed smoke is recorded as
an adapter or environment failure, not as a product score.

<!-- results are appended below this line; everything above is frozen -->
