---
title: "I Rebuilt My AI Memory Benchmark. Here Is What It Can Measure Now."
published: false
description: "A control by control explanation of the benchmark, its new measurement surface, and how to interpret the current null result."
tags: ai, agents, programming, productivity
---

# I Rebuilt My AI Memory Benchmark. Here Is What It Can Measure Now.

*A follow up to [I Gave Claude Code a Brain. Then I Measured What It Costs to Ask for One](https://dev.to/gde03/i-gave-claude-code-a-brain-then-i-measured-what-it-costs-to-ask-for-one-5351)*

My last article presented a memory benchmark as a comparison between products. The comments correctly pointed out that the design was still mixing several questions together.

Was the agent benefiting from memory, or from being told to search? Was the reported p value a planned test, or simply the most interesting result among several comparisons? Did the control represent a real empty memory store, or only the absence of memory tools?

I rebuilt the benchmark around those questions.

The result is not just a larger leaderboard. It is a more useful instrument. It can now separate several parts of the memory path, measure both help and harm, check whether the treatment was actually present, and let a reader verify the arithmetic from the published session artifacts.

It can also produce a null. In the first official run with the improved design, the placebo scored highest and no arm had an interval that excluded zero.

That is the result. This article is about how to read it.

## The measurement question

The benchmark no longer asks only:

> Does a memory product improve task success?

That question is too compressed. A memory system can fail because the agent never decides to search, because it asks a poor query, because retrieval returns the wrong passage, because the agent ignores a useful passage, or because the retrieved passage is stale or irrelevant.

The benchmark now asks a sequence of narrower questions:

1. Does the agent complete more real coding tasks?
2. Does memory help when the governing fact is present?
3. Does memory make the agent worse when the corpus is stale, contradictory, unrelated, or empty?
4. Is any change caused by retrieval, or only by extra instructions?
5. Is the system paying for a real benefit in tokens and time?
6. Can another person verify that the reported result follows from the sessions that produced it?

The primary endpoint remains simple. Claude Code edits a repository, and an executable checker decides whether the resulting artifact is correct. There is no LLM judge deciding whether the answer sounds good.

## What each arm is for

The arms are not eight competing products. Several are controls or diagnostic tracks. Treating them all as entries in one ranking would throw away the point of the design.

| Arm | What it receives | What it controls or tests |
| --- | --- | --- |
| `bare` | No memory layer and no memory instruction | The floor. What the agent does without memory or memory coaching |
| `claude_md` | The task's static project instructions | The designated baseline for the current leaderboard |
| `placebo` | Neutral project shaped prose, with no task facts or memory tools | Whether extra context alone changes task success |
| `protocol` | The shared memory instruction, but no memory surface | The cost or benefit of telling the agent to search |
| `fs_grep` | The transcript corpus as files, searched with ordinary repository tools | Whether a memory product beats a simple searchable file feed |
| `recall` | The RE call memory layer and its search tools | Natural use: the agent decides whether to search and how to query |
| `supermemory` | The official Supermemory Claude Code plugin, lifecycle hooks, and local memory service | An official hook based product integration, currently qualified in a control only pilot |
| `mempalace` | The MemPalace integration through its published interface | A product comparison under the same shared protocol |
| `recall_prefetch` | RE call retrieval run by the harness using the exact task prompt | Retrieval with the decision to search and query formulation removed |

There is also an [`oracle_memory` diagnostic](https://github.com/GiulioDER/agent-memory-bench/blob/master/docs/ORACLE_PREFETCH_DIAGNOSTIC.md) in the repository. It injects the exact relevant evidence before a session and acts as a ceiling control. It is not a product and it is not part of the official leaderboard. Its purpose is to answer a different question: can the agent use correct evidence when retrieval has already been solved?

### `bare` is not the same as `protocol`

This distinction is central.

`bare` receives neither memory tools nor instructions about memory. It measures the agent's ordinary performance.

`protocol` receives the shared instruction that tells a memory enabled agent how to use memory, but it has no memory store. It measures what happens when the coaching exists without retrieval.

The difference between `protocol` and `bare` is therefore the effect of the instruction. The difference between `recall` and `protocol` is the value of adding the memory system to that instruction.

That is the comparison the previous article needed to make more explicit.

### `placebo` is not an empty memory store

The placebo contains neutral project shaped prose. It does not expose a memory interface and it does not return an empty search result.

An empty store would hold the interface constant, accept the search, return no evidence, and let the agent continue. That is a different control. The current official run does not include it.

The new design therefore separates coaching from retrieval, but it does not yet isolate interface overhead from coaching. That remains a planned experiment, not a result I can claim today.

### `recall` and `recall_prefetch` measure different paths

The natural `recall` arm asks the agent to decide when memory is worth consulting and to formulate a useful query. Its result includes the product and the agent's use of it.

The `recall_prefetch` arm runs retrieval in the harness using the exact task prompt, then gives the returned evidence to the agent without exposing memory tools. It removes the decision to search and most of the query formulation problem.

The comparison is diagnostic:

* If prefetch is better than natural RE call, the agent's search decision or query is part of the bottleneck.
* If both are better than the baseline by a similar amount, the retrieved evidence is probably doing most of the work.
* If neither is better, better retrieval alone may not solve the task.

Neither arm should be interpreted as a general product ranking without the paired analysis and the other controls.

### Supermemory is now a qualified arm

The newest addition is Supermemory. It enters through the vendor's official Claude Code plugin,
with the plugin copied into an isolated configuration and the `SessionStart` and
`UserPromptSubmit` lifecycle hooks recorded by the admission gate.

The corrected control only pilot ran on VPS2 on 2026-09-03. It produced 180 records, admitted 89
paired cells, discarded one `bare` timeout, and admitted every Supermemory record. Those numbers
qualify the integration and its timing. They are not a Supermemory leaderboard score, because the
pilot compared only `bare` with `supermemory` and was not the preregistered multi product run.

The VPS2 environment uses the amended direct static memory treatment. That choice keeps the pinned
plugin and hooks, but writes deterministic static memories through Supermemory Local because the
original asynchronous local extraction path did not finish inside the smoke window. The limitation
is part of the result: this pilot tests the published integration and this explicit local treatment,
not Supermemory's hosted extraction behaviour.

## The improvements to the benchmark

### The instruction is now controlled

In the earlier run, the memory arms carried different amounts of generic coaching. That made it possible for an apparent retrieval advantage to be an instruction advantage.

The official run uses one shared protocol document for the memory arms. Its measured size was 3,472 bytes, identical across the arms. Each integration can add a capped result schema for its own tools, and those additions are published in the run metadata.

In the official run, the additional material was 549 bytes for `fs_grep`, 735 bytes for RE call, and 853 bytes for MemPalace. The earlier imbalance, where RE call carried the largest coaching surplus, was removed. The remaining differences are visible and measurable.

### The corpus can now expose harm

The original task suite put the governing fact in the corpus every time. It could measure help, but it was structurally weak at measuring damage.

The current corpus has five conditions:

* `present`: the governing fact is available and current
* `absent`: the fact has been removed
* `superseded`: an old version sits beside a newer version
* `contradictory`: rival versions exist without an authority marker
* `adjacent`: related information exists but does not apply to the task

The same executable checker is used in every condition. A memory system is not rewarded merely for finding text. It is evaluated on whether the completed code is correct.

This changes the interpretation of a positive result. A system that helps on `present` but damages work on `superseded` has a different risk profile from one that helps on `present` and stays neutral elsewhere.

### The admission gate is part of the measurement

A cell is admitted only when every arm can demonstrate that its treatment was present and that the session was comparable. The gate checks the available tools, startup signals, sandbox identity, and treatment metadata.

If one arm fails to start, the cell is discarded rather than scored as a task failure. The discard count is published because this rule protects the comparison but can also favour an arm that fails in a way the gate detects.

The official run had eight arms, so it had more ways to lose a cell than the previous four arm run. It produced 2,920 sessions, 317 admitted cells, and 48 discarded cells. The admitted set is not automatically comparable with the earlier run's admitted set.

### The artifacts are now independently checkable

The full official run publishes session records, compressed streams, admission decisions, costs, and endpoint results. The verifier recomputes the published values from those artifacts without credentials, a database, or model calls.

That work found defects in the benchmark itself. One older run stored its records beside the run directory under a sibling filename, so the verifier reported missing evidence even though the records existed. Another guard could not inspect compressed streams. A partition invariant assumed that every run used the same set of corpus conditions.

Those cases are now tested explicitly. The repository documents known missing streams as failures with explanations rather than silently turning them into passes. The [replication guide](https://github.com/GiulioDER/agent-memory-bench/blob/master/docs/REPLICATION.md) explains what an outside runner must report and why a replication gets standing to contradict the official run rather than entering the leaderboard as another incomparable score.

The promotion and verification work is documented in [pull request 70](https://github.com/GiulioDER/agent-memory-bench/pull/70).

## The official result

The first official run used 26 coding tasks, five corpus conditions, five seeds, eight arms, and the `deepseek-v4-flash` model. The leaderboard uses `claude_md` as its designated baseline.

| Arm | Success rate | Difference from `claude_md` |
| --- | ---: | ---: |
| placebo | 67.2% | +9.5 points |
| recall | 65.9% | +8.2 points |
| bare | 65.9% | +8.2 points |
| `fs_grep` | 63.1% | +5.4 points |
| MemPalace | 60.6% | +2.8 points |
| `claude_md` | 57.7% | baseline |

The `protocol` and `recall_prefetch` tracks both scored 61.2%. They are reference tracks and are not product rows.

The raw numbers are in [official 003](https://github.com/GiulioDER/agent-memory-bench/tree/master/results/official-003) and its [published summary](https://github.com/GiulioDER/agent-memory-bench/blob/master/results/official-003/leaderboard_summary.json).

## How to interpret those numbers

The placebo being first does not prove that neutral prose is better than memory. It tells me that this run contains enough variance, task sensitivity, or uncontrolled influence that the ordering of the rates cannot be treated as a ranking.

RE call's 65.9% is above the `claude_md` baseline's 57.7%, but its interval crosses zero. The correct statement is that this configuration performed better descriptively in this run, while the run did not establish a statistically reliable product benefit.

RE call matching the `bare` rate is not evidence that memory and no memory are equivalent. It only says that this run did not separate them. The paired contrast and its interval are the evidence to inspect, not the order of the headline rates.

The protocol arm gives the coaching comparison. If `protocol` had substantially exceeded `bare`, I would have evidence that the instruction itself changes performance. If `recall` had then exceeded `protocol`, I could attribute the additional difference more plausibly to the memory surface. In this run, neither diagnostic track produces a clean positive claim.

The prefetch arm gives the retrieval comparison. A gap between prefetch and natural RE call would show that agent behaviour is limiting the benefit. A gap between prefetch and the baseline would show that the retrieval payload can help when the harness supplies it at the right time. Because the official result is a null at the product level, these tracks should be used to design the next experiment, not to rescue the leaderboard.

The previous article's +20 cell result at p = 0.015 was exploratory. The new official comparison against the protocol arm was +15 cells at p = 0.058. The direction was similar, but the threshold did not clear. That is exactly the kind of change a better control should reveal.

## What it can measure now, and what it cannot

The benchmark can now measure task success under useful and hostile memory conditions, negative transfer relative to a bare agent, the contribution of shared memory coaching, the effect of giving an agent a simple searchable feed, natural retrieval behaviour versus prompt driven retrieval, treatment wiring, discard rates, token cost, wall time, and whether the published arithmetic follows from the published sessions.

The Supermemory addition extends treatment wiring to official lifecycle hooks. The gate can now
distinguish a hook based memory integration that was present from a session in which the product
simply failed to start.

It still cannot measure the write path. The corpus is bulk ingested before the grid and is not updated by the agent. Nothing here says whether a product extracts a good memory from a session, consolidates repeated information, forgets a correction, or preserves a decision over time.

The task suite also favours discrete retrieval. Most tasks place one governing fact in one transcript. Cross session synthesis tasks now exist, but they have not produced a scored result.

The run uses one model and one realization per task condition and seed. The memory arms are not budget matched, and RE call uses substantially more input tokens than the other arms. The official preregistration was committed after data collection began, so it is weaker evidence than a genuinely prospective test. Those limits are part of the result.

The latest registered addition is the Supermemory arm. It is kept separate from the official
multi product leaderboard until a run with its own frozen roster and published comparison is
complete. The next useful experiment is to compare it with the same baseline and controls that
qualify every other product, while keeping its local ingest mode and hook evidence visible.

The earlier reranking proposal below predates this addition. It remains a future diagnostic, not a
result or a current description of the benchmark roster.

## The benchmark is now answering better questions

The useful improvement is not a more impressive leaderboard. It is the ability to tell apart:

* no memory
* memory coaching without memory
* extra neutral context
* simple file search
* natural product use
* retrieval supplied by the harness
* exact evidence supplied as a ceiling

That makes a null more informative. When no arm wins cleanly, I know the benchmark did not merely lack a memory feature. I know which controls were present, which parts of the causal path were removed, which conditions could expose harm, and which artifacts a reader can inspect.

The current result is therefore not “memory does not work.” It is narrower and more useful:

> This run did not establish that any tested memory configuration improves completed coding tasks under this protocol.

That is what the benchmark can measure now.
