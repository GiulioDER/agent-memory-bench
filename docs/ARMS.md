# Benchmark arms

An arm is one controlled way of giving Claude Code access to the same task and the same recorded
experience. The arms are not all competing products. Controls remove alternative explanations,
and diagnostic tracks locate the point where the memory path succeeds or fails.

## The arm map

| Arm | What Claude Code receives | Why it exists |
| --- | --- | --- |
| `bare` | No memory layer and no memory instruction | The floor. It measures ordinary task performance and supplies the reference used for damage. |
| `claude_md` | The task's static project instructions | The designated baseline. It represents the useful context a team already keeps in a project. |
| `placebo` | Neutral project shaped prose with no task facts and no memory tools | A context control. It tests whether extra text alone changes performance. |
| `protocol` | The shared memory instruction, but no memory surface | An instruction control. It separates the effect of telling an agent to search from the effect of retrieval. |
| `fs_grep` | The transcript corpus as files, searched with ordinary repository tools | A simple retrieval control. It asks whether a product beats a searchable folder of raw sessions. |
| `recall` | The RE call memory layer and its MCP search tools | Natural product use. The agent decides whether to search and how to formulate the query. |
| `supermemory` | The official Supermemory Claude Code plugin, lifecycle hooks, and local memory service | An official hook based product integration. Its corrected pilot qualified the treatment and timing, but did not create a leaderboard row. |
| `recall_prefetch` | RE call retrieval performed by the harness from the exact task prompt | A diagnostic. It removes the agent's search decision and most query formulation from the path. |
| `oracle_memory` | The exact relevant evidence supplied by the harness | A ceiling diagnostic. It asks whether correct evidence would be enough if retrieval were perfect. |

## How to read the comparisons

The useful comparisons are paired and have different meanings:

* `bare` against `claude_md` measures the value of the static baseline over a memoryless agent.
* `placebo` against `claude_md` measures the effect of neutral context rather than task knowledge.
* `protocol` against `bare` measures memory coaching without memory.
* `recall` against `protocol` measures what the memory surface adds after the coaching is present.
* `fs_grep` against `recall` compares a simple searchable feed with a product integration.
* `recall_prefetch` against `recall` measures the gap caused by the agent's search decision and
  query formulation.
* `oracle_memory` against `claude_md` estimates how much headroom the task set offers when the
  evidence is already correct.

No diagnostic track should be read as a product ranking. A result is only meaningful beside its
baseline, its paired confidence interval, its discard count, and its treatment evidence.

## Why the Supermemory arm is separate for now

Supermemory uses the vendor's official Claude Code integration, not a benchmark invented API. The
adapter copies the pinned plugin into an isolated Claude configuration, records the
`SessionStart` and `UserPromptSubmit` hook evidence required by the admission gate, and uses
Supermemory Local on VPS2. The amended pilot writes deterministic static memories through the
vendor's documented memory endpoint because asynchronous local extraction did not finish within
the original smoke window.

The qualifying pilot was measured on 2026-09-03. It used the reduced roster `bare,supermemory`,
produced 180 records, admitted 89 paired cells, and discarded one `bare` record for exceeding the
600 second Claude timeout. Every Supermemory record passed both lifecycle hook checks. The pilot
shows that the treatment was present and bounded; it does not estimate a general Supermemory task
success rate. The frozen record and its limits are in
[`preregistration/020-supermemory-pilot-config-dir.md`](../preregistration/020-supermemory-pilot-config-dir.md).

## How to use the arms

Start with a dry run. It resolves the roster, task set, seeds, instruction sizes, and expected
session count without writing results or starting Claude Code:

```bash
python -m scripts.pilot --dry-run --arms bare,claude_md,recall
```

The same selector accepts any registered arm. For example, the Supermemory qualification roster
is:

```bash
python -m scripts.pilot --dry-run --arms bare,supermemory
```

For a real measurement, use the committed preregistration for that experiment, keep the model,
task set, seed set, corpus condition, prices, permissions, and arm roster fixed, and make sure the
required credentials and services are available. The runner refuses to start while
`preregistration/` is dirty. A typical fair memory comparison uses the shared protocol variant:

```bash
python -m scripts.pilot \
  --run-id <registered-run-id> \
  --arms bare,claude_md,protocol,fs_grep,recall \
  --memory-instruction protocol \
  --seeds 3
```

Supermemory qualification additionally requires the pinned plugin directory and its explicitly
configured local service. The VPS2 pilot details belong in preregistration 020; do not silently
switch to the hosted service or pool its direct static memory treatment with a different ingest
mode.

After a run, inspect `results/<run-id>/` for the session records, streams, admission verdicts,
environment, and cost ledger. A failed hook or missing MCP treatment is an admission failure, not
evidence that the product was harmless. A session that searched and still failed is an outcome,
not a wiring failure.

## What the current benchmark does not measure

The standard grid bulk ingests the corpus before the agent sessions begin. It measures the read
path, not whether a product extracts, consolidates, updates, or forgets memories created by the
agent. The longitudinal design for that write path is registered separately and has not run.
