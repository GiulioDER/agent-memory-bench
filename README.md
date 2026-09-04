# agent-memory-bench

A preregistered, execution-graded benchmark of pluggable memory layers for coding agents. It
evaluates Claude Code on real repository tasks whose solutions depend on information from earlier
sessions. The primary endpoint is artifact execution: tests pass or fail. No LLM judge is used.

## Current status

`official-003` is the current public run. It is a retrieval benchmark over a bulk-ingested corpus,
not a full memory lifecycle benchmark.

| field | value |
|---|---|
| model | `deepseek/deepseek-v4-flash` |
| arms | eight |
| tasks | 26 in the official grid, 34 executable in the suite |
| conditions | `present`, `absent`, `superseded`, `contradictory`, `adjacent` |
| admitted cells | 317 paired cells, one seed per cell |
| baseline | `claude_md`, task success `0.577` |

The headline is a null. `placebo` scored `0.672`, `recall` and `bare` each scored `0.659`, and no
arm's 95% interval excludes zero. The run is weaker than the benchmark's normal protocol because
its preregistration was committed about two hours after the first session and the run was not
announced in advance. Both deviations are disclosed in the record.

The detailed, dated state of the benchmark is in [`docs/STATUS.md`](docs/STATUS.md). Every number
there has a command or artifact that can re-derive it.

## What is measured

The benchmark measures whether a coding agent can use prior-session information while completing
real work:

1. The task is run in an isolated repository with a fixed seed and fixture.
2. Each memory arm receives the same corpus and its own published integration.
3. The agent produces an artifact in the repository.
4. An executable checker evaluates that artifact against oracle inputs absent from the sandbox.

The comparison is paired by task, seed and fixture. A cell is admitted only when every arm proves
that its treatment was available and the sandbox was equivalent. A wiring failure is discarded and
reported. A timeout is an outcome and is not retried.

The primary endpoint does not use an LLM judge, rubric or partial credit. A silent session and a
fluent but incorrect session both score zero.

## Scope and limits

The official run ranks retrieval over a corpus ingested before the grid. No arm writes to its own
store during the run, so extraction, consolidation and persistence are not measured. The result
must not be read as a complete ranking of memory systems.

Other limits are material:

1. The official grid uses one seed per cell.
2. It uses one relatively inexpensive model.
3. The memory arm is not budget matched. In `pilot-004-placebo`, `recall` used 4.5 times the input
   tokens and 2.6 times the wall time of the other arms.
4. Most tasks state one governing fact in one document. The three `xs-*` tasks test cross-session
   synthesis, but they are not in the current headline grid.

These limits are part of the result, not footnotes. See the [method](site/method.html),
[replication guide](docs/REPLICATION.md), and [audit records](docs/audit/) for the full treatment.

## Design

1. **Published integrations.** Each product enters through its shipped Claude Code integration,
   such as a plugin, MCP server or lifecycle hooks. The adapter and frozen configuration are
   reviewable before measurement.
2. **Controlled instruction.** The `claude_md` arm is the designated baseline. Memory arms use the
   shared memory protocol and publish their instruction size, so retrieval is not confused with
   generic agent coaching.
3. **Neutral feed.** Every arm receives the same verbatim session transcripts. What a product keeps
   or discards is part of what is measured.
4. **Executable grading.** The sandbox never contains the checker oracle. Each task includes a naive
   reference that must fail and an informed reference that must pass, both asserted in CI.
5. **Admission and pairing.** MCP startup, lifecycle hooks, tool isolation and sandbox digests are
   checked before a cell contributes to the headline.
6. **End-to-end cost.** Session and ingestion tokens, wall time, discarded cells and negative
   transfer are recorded per arm. Price inputs are explicit for every live run.

## Task suite

The suite contains 34 executable tasks:

| group | purpose |
|---|---|
| 30 `ts-*` tasks | retrieve a governing fact from prior sessions |
| three `xs-*` tasks | combine, revise or scope facts across sessions |
| `fa-dedup-key` | recover a failed approach from prior work |

The harm conditions test whether memory helps without becoming a liability:

| condition | corpus state | correct behavior |
|---|---|---|
| `present` | current governing fact is present | use it |
| `absent` | governing fact is absent | use the repository or report uncertainty |
| `superseded` | old and current facts are both present | apply the current fact |
| `contradictory` | two undated facts disagree | surface the conflict |
| `adjacent` | a confident fact governs another subsystem | do not apply it |

## Arms

| arm | role |
|---|---|
| `bare` | no memory and no `CLAUDE.md`, the floor |
| `claude_md` | curated `CLAUDE.md` bundle, the baseline |
| `placebo` | length-matched prose with no memory content |
| `protocol` | shared memory instruction with no memory behind it |
| `fs_grep` | transcripts on disk plus grep, a retrieval control |
| `recall` | MCP memory server, a product arm |
| `mempalace` | product arm, held for vendor review on the public board |
| `recall_prefetch` | harness-side retrieval with the exact task prompt, a reference track |

Reference tracks diagnose the memory path and are never ranked as products. `protocol` measures the
cost of asking an agent to use memory. `recall_prefetch` removes query formulation from retrieval.

## Check the evidence

Run the test suite and static audits:

```bash
python -m pytest tests/ -q
python -m scripts.audit_corpus
python -m scripts.audit_plants
```

Re-derive every published run without credentials, a database or model calls:

```bash
python -m scripts.verify_run --all
```

This checks the published records against the admission, cost and endpoint artifacts. It checks
arithmetic and provenance, not whether the benchmark is fair. The method, preregistrations and
vendor reviews are the evidence for that question.

## Run it

Dry run:

```bash
python -m scripts.pilot --dry-run --arms bare,claude_md,recall
```

A live run requires the Claude Code CLI, the credentials listed in `.env.example`, and explicit
prices:

```bash
python -m scripts.pilot --run-id my-run \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

See [`docs/REPLICATION.md`](docs/REPLICATION.md) before spending money. The guide distinguishes
checking a published run from reproducing one and records the infrastructure required by each arm.

## Repository layout

| path | purpose |
|---|---|
| `harness/` | Claude Code executor, sandbox, admission gate, statistics and cost ledger |
| `adapters/<name>/` | adapter code, frozen configuration, version pins and vendor review |
| `corpus/` | verbatim session transcripts and the sha256 manifest |
| `tasks/<id>/` | task specification, fixture, checker and reference solutions |
| `oracles/<id>/` | checker inputs absent from the sandbox |
| `preregistration/` | protocol and predictions committed before measurement |
| `results/<run_id>/` | session logs, streams, admission verdicts and costs |
| `site/` | published pages, deployed without a build step |

## Disclosure

This benchmark is built by the authors of `recall`, which competes in it. The harness is open, the
method is preregistered, configurations are vendor-reviewable, and losses are published alongside
wins.

The project is licensed under Apache-2.0.
