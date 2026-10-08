---
title: "Same memory, {{N_SCORED}} models: they all trust it. Few know when not to."
published: false
tags: devchallenge, kagglechallenge, ai, machinelearning
---

<!--
DRAFT, restructured 2026-10-08. Not for publication until the user approves it.

Rules for filling it:
- Every {{PLACEHOLDER}} is filled from results/kaggle-memory-discipline-001/report.json (after
  scripts/select_scored_runs.py and scripts/analyze_kaggle_memory.py), never typed by hand.
- A paragraph marked VERIFY rests so far only on per-run summaries in the grid log. Keep it only
  if the analysis confirms it; otherwise cut it, do not soften it.
- House rules: no dash used as punctuation, first person singular throughout.
- Keep OUT of this post: the RE-call calibration results of preregistrations 099 to 101. They are
  reserved for the Gemma 4 paper track, which requires unpublished research.
- Links: the branch is claude/kaggle-memory-use-benchmark until it merges; set {{REPO_REF}} to the
  ref that holds the final files when publishing.
- Tag check before publishing: the template pre-fills `kagglechallenge`; the announcement named
  `#kagglebenchallenge`. Use what the rules page asks for.
-->

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23)*

Give {{N_SCORED}} language models the same project memory and the same coding question, and they
almost all use the memory well when it holds the answer. Where they differ, by a lot, is knowing
when it does not.

## What I Benchmarked

For the last few months I have been building
[agent-memory-bench](https://github.com/GiulioDER/agent-memory-bench), a preregistered benchmark of
memory layers for coding agents. It holds the model fixed and swaps the memory product. One thing
it taught me is that retrieving the right note is only half the problem. The other half is what
the model does with the note once it has it.

So for this challenge I turned the design around: **I held the memory fixed and swapped the
model.** Every item puts the model in a coding task with a handful of memory search results, and
asks it to end with either `VALUE: <answer>` or `ASK: <question for the team>`. Within a scenario
the question never changes. Only the memory does:

| condition | what memory holds | the right move |
|---|---|---|
| present | the current decision | use it |
| superseded | an old decision and the newer one that replaced it | use the newer one |
| absent | nothing relevant | ask |
| adjacent | a true decision about a *different* subsystem, which says so | ask |
| contradictory | two undated notes that disagree | ask |

The first two conditions measure **trust**: using memory when it answers the task. The last three
measure **restraint**: not inventing, borrowing or silently choosing when it does not. The
headline is Youden's J, trust plus restraint minus one. A model that always asks scores 0, and so
does one that always applies the newest note; only telling the two situations apart scores above
zero.

There are 24 scenarios (a webhook retry limit, an audit log time zone, a staging bucket, a rounding
mode and so on) and 216 items. Scoring is deterministic. Every scenario has five authored readings
of the answer (current, stale, adjacent and the two contradictory ones), and a validator refuses
any scenario where two readings could be confused. So a wrong answer says *which* wrong: the stale
note applied, the neighbouring subsystem's value borrowed, a side picked, or something made up.

Before any model saw an item I committed the predictions, the analysis script and the item set,
frozen by hash: [preregistration 098]({{REPO_REF}}/preregistration/098-kaggle-memory-discipline.md).

## Models Tested

I did not choose the models. The preregistration fixed the rule in advance: every model Kaggle
Benchmarks listed on the day of the first push ({{N_LISTED}} of them, committed as a list before
anything ran), run in alphabetical order until the budget or the deadline ran out, with no model
dropped after its score came in.

**{{N_SCORED}} were scored.** The rest, and why:
{{NOT_SCORED_LIST}}
<!-- Expected: grok-4.5-0708 and grok-4.6 are listed by Kaggle but not served (every call
returns 404 "model not found"); gpt-oss-120b, if its trust task never completes, was blocked by
Kaggle's own capacity ("The model is currently experiencing heavy load"). -->

Three things about how they ran, because each changes how to read the numbers:

- **Every reply was capped at 8,192 tokens.** Kaggle reserves the worst-case cost of a call before
  making it, and at the default length one call to a large model reserved more than $3 against a
  $10 daily budget, so the largest models could never start. The cap is about fifteen times a
  typical reply, so it bounds cost without shaping answers. It was added after one model had
  answered, and is recorded as a deviation in the preregistration, with that model re-run.
- **Each model answered each item once**, at temperature 0 where the model allows it.
- **One model ran twice by accident**, after a Kaggle login outage confused my run driver. The rule
  committed before any analysis says the first complete run counts. The duplicate is still useful:
  same model, same 216 items, and the two runs differ by {{RETEST_GAP}} points. Read any gap
  smaller than that between two models as noise.

## Findings

{{RESULTS_TABLE}}
<!-- One row per scored model, ranked by J, with trust, restraint, J and its 95% interval. A
two-panel chart (trust and restraint side by side, one dot per model) shows finding 1 at a
glance; build it from report.json with the dataviz skill. -->

**1. Trust is nearly solved. Restraint is not.** Trust ranges from {{TRUST_MIN}} to
{{TRUST_MAX}}; restraint ranges from {{RESTRAINT_MIN}} to {{RESTRAINT_MAX}}. Almost every model
uses memory when it holds the answer, including when an older note says otherwise. They differ in
what they do when memory does not hold the answer: some ask, some answer anyway.
<!-- VERIFY: per-run summaries show trust about 0.90 to 1.00 for nearly all models and
restraint from 0.111 (grok-4.20 non-reasoning) to 1.000 (gpt-6-astra). -->

**2. The hardest situation is {{HARDEST_CONDITION}}.** {{HARDEST_CONDITION_DETAIL}}
<!-- From the per-condition accuracies (endpoint 3) and the outcome labels (endpoint 8): which
of absent, adjacent and contradictory catches the most models, and what they do instead
(invent a value, borrow the neighbour's, or pick a side). This is preregistered prediction 2. -->

**3. Reasoning modes are more restrained.** {{REASONING_PAIRS}}
<!-- VERIFY, and keep the hedge: two families have both modes in the grid. Grok 4.20 restraint
0.111 non-reasoning against 0.701 reasoning; Qwen3-Next 80B 0.653 instruct against 0.833
thinking. Two pairs are an observation, not a law. -->

**4. Within a family, smaller models ask less.** {{SIZE_PATTERN}}
<!-- VERIFY: GPT-5.4 restraint 0.826, mini 0.653, nano 0.708. Preregistered as no claim, so
present it as an observation. -->

**5. Superseded notes: {{SUPERSESSION_FINDING}}.**
<!-- From endpoints 4 and 5: explicit against implicit supersession (predictions 3) and whether
the stale note does more damage when it sits nearer the question (prediction 4). Cut if both
are null and say so in the scorecard instead. -->

**Where my predictions missed.** I committed ten predictions before running anything. Scored
against the result:

{{PREDICTION_SCORECARD}}
<!-- A table: prediction, threshold, measured, met or missed. Expected miss: prediction 6
asked for both a credulous and a timid model; the grid shows a credulous one (grok-4.20
non-reasoning) and, so far, no timid one. Say what I believed and why it was wrong. -->

**Caveats I would want a reader to know.**
- The prompt offers the `ASK` route explicitly, so this measures whether a model *can* tell when
  to lean on memory, not whether it would stop and ask unprompted inside an agent loop.
- One run per model; differences under {{RETEST_GAP}} points are noise (see the duplicate run).
- The scenarios were written with the help of a Claude model, and Claude models are in the grid,
  so any familiarity advantage is unmeasured.
- The adjacent notes state their own scope and the distractors are plainly off topic, which makes
  this easier than a real memory store.
- Model versions behind a Kaggle slug can change; runs are dated in the repository.

**What I would measure next:** the same items with the `ASK` instruction removed, inside a tool
loop, which is where agent-memory-bench lives; and whether a memory layer can recognise a near-miss
question before the model sees it.

## My Benchmark

{{KAGGLE_BENCHMARK_URL}}

Everything behind the numbers is public: the items, the scorer, the analysis script, the
preregistration with its predictions and both deviations, and the raw per-run files:
[agent-memory-bench, kaggle_memory]({{REPO_REF}}/kaggle_memory).
