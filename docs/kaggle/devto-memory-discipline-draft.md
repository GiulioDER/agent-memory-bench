---
title: Same memory, different models: who knows when to trust it?
published: false
tags: devchallenge, kagglechallenge, ai, machinelearning
---

<!--
DRAFT. Not for publication until the user approves it. Every {{PLACEHOLDER}} is filled from
results/kaggle-memory-discipline-001/report.json after the run, never typed by hand. House rules
for this text: no dash used as punctuation, first person singular throughout.
-->

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23)*

## What I Benchmarked

For the last few months I have been building [agent-memory-bench](https://github.com/GiulioDER/agent-memory-bench),
a preregistered benchmark of memory layers for coding agents. It holds the model fixed and swaps
the memory product. One thing it taught me is that retrieving the right note is only half the
problem. The other half is what the model does with a note once it has it.

So for this challenge I turned the design around: **I held the memory fixed and swapped the
model.** Every item puts the model in a coding task with a handful of memory search results, and
asks it to finish with either `VALUE: <answer>` or `ASK: <question for the team>`. The question
never changes within a scenario. Only the memory does:

| condition | what memory holds | the right move |
|---|---|---|
| present | the current decision | use it |
| superseded | an old decision and the newer one that replaced it | use the newer one |
| absent | nothing relevant | ask |
| adjacent | a true decision about a *different* subsystem, which says so | ask |
| contradictory | two undated notes that disagree | ask |

The first two measure **trust**: using memory when it answers the task. The last three measure
**restraint**: not inventing, borrowing or silently choosing when it does not. The headline number
is Youden's J, trust + restraint minus one. A model that always asks scores 0, and so does one that
always applies the newest note. Only telling the two situations apart scores above zero.

There are 24 scenarios (a webhook retry limit, an audit log time zone, a staging bucket, a rounding
mode and so on), 216 items in all. Scoring is deterministic: every scenario has five authored
readings of the answer (current, stale, adjacent and the two contradictory ones), and a validator
refuses any scenario where two readings could be confused. So when a model gets an item wrong, the
benchmark says *which* wrong: it applied the stale note, borrowed the neighbouring subsystem's
value, picked a side, or made something up.

I wrote the predictions down and committed them before any model saw an item:
[preregistration 098](https://github.com/GiulioDER/agent-memory-bench/blob/master/preregistration/098-kaggle-memory-discipline.md).

## Models Tested

{{MODELS_PARAGRAPH}}: every model Kaggle Benchmarks offered on {{RUN_DATE}}, run once each at the
library defaults. I did not choose them, which was the point: the preregistration says so, so
that no model could be dropped after its score came in.

## Findings

{{RESULTS_TABLE}}

{{FINDING_1}}

{{FINDING_2}}

{{FINDING_3}}

**Where my predictions missed.** {{PREDICTION_SCORECARD}}

**Caveats I would want a reader to know.** The prompt offers the `ASK` route explicitly, so this
measures whether a model *can* tell when to lean on memory, not whether it would stop and ask
unprompted inside an agent loop. Each item was run once. The scenarios were written with the help
of a Claude model, so any familiarity advantage for Claude models is unmeasured. The adjacent notes
state their own scope, and the distractors are plainly off topic, which makes this easier than a
real memory store.

**What I would measure next:** the same items with the `ASK` instruction removed, inside a tool
loop, which is where agent-memory-bench lives.

## My Benchmark

{{KAGGLE_BENCHMARK_URL}}

Code, items, scorer and the analysis that produced every number above:
[github.com/GiulioDER/agent-memory-bench](https://github.com/GiulioDER/agent-memory-bench/tree/master/kaggle_memory).
