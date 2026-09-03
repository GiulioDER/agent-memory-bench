# What a memory product may ship to this benchmark

This is the document a competing product's maintainer should read before their arm is run. It
states what an arm is allowed to bring, what is held fixed for every arm, and what is measured.

It exists because the alternative failed a review. An earlier fairness fix equalised the
instruction text across arms, which sounds fair and is not: it measures a common denominator that
none of the products actually ships, and it contradicts the frozen rule in preregistration 006.

## The principle

**Every arm is wired through its own official integration, and nothing else.**

Preregistration 006, frozen before any of this was built:

> Products differ in how memories get written: some capture sessions automatically through a
> lifecycle hook, some require the agent to call a write tool, some do both. Each arm is wired
> through **its own official integration** and nothing else, and the benchmark measures the outcome
> rather than prescribing the route. A design that required an explicit write call would hand the
> win to products built that way, and a design that required silent auto-capture would hand it to
> the others.

So the benchmark does not ask what a product would score stripped to a shared protocol. It asks
what it scores **as its maintainers ship it**, because that is what a user installs.

## What your arm may bring

| surface | how | limit |
|---|---|---|
| **MCP servers** | `ArmSpec.mcp_config`, an `--mcp-config` file | any number of servers and tools |
| **A system-prompt instruction** | `ArmSpec.append_system_prompt_file` | **no length cap.** recall's is 5,428 characters; if yours is longer, ship the longer one |
| **Hooks and plugins** | `ArmSpec.config_dir`, an isolated `CLAUDE_CONFIG_DIR` holding your `settings.json`, hook scripts and plugins | requires `bare=False`; the directory is hashed into the record |
| **A skill** | a file in your `config_dir`, or folded into your instruction | as you ship it |
| **Environment** | `ArmSpec.env` | your service's own configuration |

There is deliberately no instruction length cap. A cap would be an arbitrary line that advantages
whoever happens to sit under it, and the length is recorded per arm (`instruction_bytes`) so a
reader can see the asymmetry rather than having it hidden by a rule.

## What is held fixed, and is not yours to change

* **The corpus.** Every arm ingests byte-identical bytes through its own write path. What your
  extraction pipeline stores from them is part of what is being measured.
* **The tasks, fixtures and checkers.** Deterministic, and identical across arms.
* **The model, its version, the timeout and the permission mode.** Recorded in `environment.json`
  before the first session.
* **The non-memory tool allowlist** (`Read`, `Grep`, `Glob`, `Bash`, `Write`, `Edit`). Your memory
  tools are additional; you may not remove another arm's.
* **The admission gate.** Your arm must PROVE its treatment reached the session, or the cell is
  discarded for every arm. See below.

## What you must prove, or your cells are discarded

A cell is admitted only when every arm demonstrates its treatment was actually applied. This
protects you as much as it constrains you: a run where your server silently failed to start would
otherwise be published as your product scoring zero.

Declare in your `AdmissionSignal` whichever of these your integration uses:

* `mcp_tool_prefixes` — your tools must appear in the session's tool list.
* `required_hooks` — your hooks must appear in the session's `hook_ledger`.
* `sandbox_paths` — files your integration must have created.

**Not calling your memory is a RESULT, not a discard.** An arm whose tools were present and never
used is admitted and counted, because discoverability is part of what is being measured. Only a
treatment that never arrived is discarded.

## The control arms, and why they are not your competition

* `bare` — no memory. The reference point; damage is defined against it.
* `claude_md` — the fixture README as a static system prompt. What a project already has.
* `placebo` — length-matched neutral prose, to separate "more context" from "the right context".
* `protocol` — a shared instruction with no memory store behind it. This one isolates the
  **coaching** from the **retrieval**: if it moves against `claude_md`, part of every memory arm's
  lift is the instruction rather than the store.

`protocol` is a control, not a costume for your product. Running your arm stripped to it would
measure something nobody ships.

## Status, stated plainly

* MCP-server integration: **exercised**. `recall` and `fs_grep` both run this way.
* System-prompt instruction of arbitrary length: **exercised**.
* Hook and plugin integration: **supported; Supermemory adapter pending smoke verification**.
  `ClaudeExecConfig.config_dir`, `ArmSpec.config_dir`, the `hook_ledger` and the gate's
  `required_hooks` check all exist. The Supermemory adapter ships the official Claude Code plugin
  through an isolated config directory, but it is not a runnable competitor until its preregistered
  smoke test proves both hook delivery and the five-hour full-run projection.

## How to add your arm

1. Implement `harness/adapters/base.py::MemoryAdapter`: `ingest(corpus, namespace)` and
   `build(...) -> ArmSpec`, plus `admission_signal()` and `describe()`.
2. Put it in `adapters/<your-product>/`, with a frozen config file recording versions.
3. Register it in `scripts/pilot.py::adapter_for`.
4. Your `describe()` output is published beside your numbers.

Open a pull request. We would rather run your integration than our guess at it.
