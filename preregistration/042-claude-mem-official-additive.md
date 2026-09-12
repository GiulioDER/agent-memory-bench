# 042: Claude-Mem official additive AMB submission

Status: FROZEN before the first full additive session.

## Question

Does the pinned Claude-Mem integration produce an admissible result on the full AMB retrieval
grid, suitable for an additive row joined to the frozen `official-003` leaderboard base?

## Fixed comparison

This is an additive submission. The frozen `official-003` base arms are not rerun. Claude-Mem is
measured as one new arm and joined to the base `claude_md` records on
`(task_id, seed, condition)`. The base model is `deepseek/deepseek-v4-flash` through OpenRouter,
the Claude Code CLI is the installed 2.1.259 release, and the memory instruction is the frozen
`protocol` variant used by the official base.

The measured product is the reviewed adapter at `adapters/claude_mem/`, using the pinned upstream
Claude-Mem `v13.24.0` commit recorded in its frozen configuration. No upstream product files are
modified during the run.

## Grid

The full condition suite is run with five seeds, using the already assembled and hash verified
condition feeds:

* `present`
* `absent`
* `superseded`
* `contradictory`
* `adjacent`

The task selection is the frozen AMB selection for each condition. This is 27 present task
conditions, 11 absent, 10 superseded, 10 contradictory, and 11 adjacent, for 69 task conditions
and 345 Claude-Mem sessions before admission.

The runner uses `AMB_BLOCK_CONCURRENCY=4`, meaning four `(task, seed)` cells may be in flight at
once. Each cell still has one measured Claude-Mem session. A cell is admitted only when the
Claude-Mem MCP surface, lifecycle hooks, task completion, transcript, and isolation checks pass.
Any failed Claude-Mem wiring or incomplete session discards the cell rather than becoming a
product failure score.

## Cache and ingestion policy

The condition corpus is assembled once per condition and reused byte for byte by the run. The
five condition feeds are not merged, and the Claude-Mem store is never reused across conditions,
because doing so would contaminate one condition with evidence from another.

This is a one-arm additive run, so there is no duplicate vendor ingestion across arms. Claude-Mem
is imported exactly once per condition into its condition-scoped namespace. Repeated session
requests use the provider's normal prompt cache when available; cache read and creation token
counts remain in the session records. The cost ledger uses the same frozen input and output price
basis as `official-003`, with no special cache discount, so the additive cost remains comparable
to the published base rather than mixing pricing policies.

The existing assembled corpus manifests and their rendered transcript bytes are reused. No
adapter store is copied between conditions or treated as a shared product store.

## Publication rule

After all five condition runs complete, the following checks must pass before publication:

1. every condition has `records.final.jsonl`, `admission.json`, `costs.json`, and
   `environment.json`;
2. setup validation passes with the official corpus floor and the requested arm and instruction;
3. `verify_run` passes for every condition and the additive join has positive cells;
4. `build_arm_submission.py --check` reproduces the generated summary;
5. the generated leaderboard passes its source and disclosure checks.

The result is published as an additive arm joined to `official-003`, never as a replacement for
the frozen base and never as a claim that the base admitted-cell set was enlarged.

## Primary report

The primary published quantities are Claude-Mem success, delta against the joined `claude_md`
baseline, the cluster-bootstrap interval, joined cells, discarded cells, per-condition counts,
search and hook reachability, imported items, end-to-end tokens, and estimated spend.

<!-- results are appended below this line; the frozen protocol above is never edited -->
