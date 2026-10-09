---
title: "Same memory, 39 models: trusting it is solved, knowing when not to is what separates them"
published: false
tags: devchallenge, kagglechallenge, ai, machinelearning
---

<!--
DRAFT, filled 2026-10-09 from results/kaggle-memory-discipline-001 (commits cc8b1c6d, 54bf6267).
Not for publication until the user approves it.

Still open before publishing:
- {{REPO_REF}}: the GitHub ref that holds the final files (branch
  claude/kaggle-memory-use-benchmark until it merges). It is also the chart's URL below; or
  upload docs/kaggle/trust-restraint.png in the DEV editor and use that URL instead.
- Kaggle benchmark: https://www.kaggle.com/benchmarks/giulioder/memory-discipline (public,
  38 models; on 2026-10-09 its leaderboard cells showed "-" to a logged out viewer).
- Tag: settled. The challenge page names `kagglechallenge` as the required tag.
- DEV draft id 4823060 (unpublished) is built from this file with this comment stripped and
  {{REPO_REF}} set to the branch URLs.
- Keep OUT of this post: the RE-call calibration results of preregistrations 099 to 101 (reserved
  for the Gemma 4 paper track).
- House rules: no dash used as punctuation, first person singular throughout.
- Every number here is in report.json, predictions.json or preregistration 098's Result section.
  The results table is generated from report.json by the snippet in the commit that filled it.
-->

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23)*

I gave 39 language models the same project memory and the same coding questions. Almost all of them
use the memory well when it holds the answer. Where they differ, by a lot, is knowing when it does
not.

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

Before any model saw an item I committed ten predictions, the analysis script and the item set,
frozen by hash: [preregistration 098]({{REPO_REF}}/preregistration/098-kaggle-memory-discipline.md).

## Models Tested

I did not choose the models. The preregistration fixed the rule in advance: every model Kaggle
Benchmarks listed on the day of the first push (41 of them, committed as a list before anything
ran), run in alphabetical order until the budget or the deadline ran out, with no model dropped
after its score came in.

**39 were scored, all of them on every item or within the 5% error allowance.** The other two,
`grok-4.5-0708` and `grok-4.6`, are listed by Kaggle but not served: every call to them returned
`404 model not found`.

Four things about how they ran, because each changes how to read the numbers:

- **Every reply was capped at 8,192 tokens.** Kaggle reserves the worst-case cost of a call before
  making it, and at the default length one call to a large model reserved more than $3 against a
  $10 daily budget, so the largest models could never start. The cap is about fifteen times a
  typical reply, so it bounds cost without shaping answers. It was added after one model had
  answered, and is recorded as a deviation in the preregistration, with that model re-run.
- **Each model answered each item once**, at temperature 0 where the model allows it.
- **One model ran twice by accident**, after a Kaggle login outage confused my run driver. The rule
  committed before any analysis says the first complete run counts. The duplicate is still useful:
  same model, same 216 items, and the two runs differ by 0.03 in J, with 201 of 216 items getting
  the same kind of answer. Read any gap between two models smaller than about 0.03 as noise.
- **One model's scored run comes with a caveat.** `gpt-oss-120b` was overloaded on Kaggle for most
  of a day and was launched five times. Kaggle's API lists only a model's latest run, and I could
  not recover two of the earlier ones, so its scored run may not be its first complete one. Its dot
  is hollow in the chart, and nothing below rests on it alone.

## Findings

![Trust and restraint for 39 models, ranked by J]({{REPO_REF}}/docs/kaggle/trust-restraint.png)

{% details The full table: trust, restraint and J with its 95% interval %}

| # | model | trust | restraint | J | 95% interval |
|---:|---|---:|---:|---:|---|
| 1 | `gpt-6-astra` | 0.995 | 1.000 | 0.995 | 0.98 to 1.00 |
| 2 | `claude-sonnet-4-6` | 1.000 | 0.986 | 0.986 | 0.96 to 1.00 |
| 3 | `gemini-2.5-pro` | 1.000 | 0.986 | 0.986 | 0.96 to 1.00 |
| 4 | `gemini-3.7-flash` | 1.000 | 0.986 | 0.986 | 0.96 to 1.00 |
| 5 | `gemini-3.8-flash` | 1.000 | 0.986 | 0.986 | 0.96 to 1.00 |
| 6 | `gemma-4-31b` | 1.000 | 0.986 | 0.986 | 0.96 to 1.00 |
| 7 | `claude-opus-4-7` | 0.995 | 0.986 | 0.981 | 0.95 to 1.00 |
| 8 | `gemini-3.5-flash` | 1.000 | 0.979 | 0.979 | 0.94 to 1.00 |
| 9 | `gemini-3-flash-preview` | 1.000 | 0.972 | 0.972 | 0.94 to 1.00 |
| 10 | `gemini-3.1-pro-preview` | 1.000 | 0.972 | 0.972 | 0.92 to 1.00 |
| 11 | `gemini-3.6-flash` | 1.000 | 0.972 | 0.972 | 0.93 to 1.00 |
| 12 | `claude-opus-4-5` | 1.000 | 0.965 | 0.965 | 0.92 to 1.00 |
| 13 | `gpt-5.6-luna` | 0.974 | 0.986 | 0.960 | 0.91 to 0.99 |
| 14 | `claude-opus-4-8` | 0.969 | 0.986 | 0.955 | 0.92 to 0.98 |
| 15 | `claude-opus-5` | 0.995 | 0.958 | 0.953 | 0.90 to 0.99 |
| 16 | `gemma-4-26b-a4b` | 1.000 | 0.951 | 0.951 | 0.91 to 0.99 |
| 17 | `gpt-5.6-sol` | 1.000 | 0.944 | 0.944 | 0.90 to 0.99 |
| 18 | `claude-sonnet-5` | 0.974 | 0.965 | 0.939 | 0.88 to 0.99 |
| 19 | `gemini-2.5-flash` | 0.990 | 0.944 | 0.934 | 0.88 to 0.98 |
| 20 | `glm-5` | 0.979 | 0.951 | 0.931 | 0.86 to 0.98 |
| 21 | `qwen3-coder-480b-a35b-instruct` | 0.995 | 0.931 | 0.925 | 0.85 to 0.99 |
| 22 | `claude-haiku-4-5` | 0.979 | 0.931 | 0.910 | 0.85 to 0.96 |
| 23 | `claude-sonnet-4-5` | 1.000 | 0.910 | 0.910 | 0.83 to 0.97 |
| 24 | `gemini-3.5-flash-lite` | 0.948 | 0.951 | 0.899 | 0.85 to 0.94 |
| 25 | `deepseek-r1-0528` | 0.938 | 0.958 | 0.896 | 0.83 to 0.95 |
| 26 | `gpt-5.6-terra` | 1.000 | 0.889 | 0.889 | 0.80 to 0.97 |
| 27 | `gemini-3.1-flash-lite-preview` | 0.953 | 0.875 | 0.828 | 0.73 to 0.91 |
| 28 | `gpt-5.4` | 0.995 | 0.826 | 0.821 | 0.76 to 0.88 |
| 29 | `qwen3-235b-a22b-instruct` | 0.948 | 0.865 | 0.813 | 0.73 to 0.88 |
| 30 | `gpt-5.5` | 1.000 | 0.806 | 0.806 | 0.71 to 0.89 |
| 31 | `claude-opus-4-6` | 1.000 | 0.792 | 0.792 | 0.68 to 0.89 |
| 32 | `qwen3-next-80b-a3b-thinking` | 0.906 | 0.833 | 0.740 | 0.59 to 0.86 |
| 33 | `grok-4.20-reasoning` | 1.000 | 0.701 | 0.701 | 0.58 to 0.81 |
| 34 | `gpt-5.4-mini` | 0.990 | 0.653 | 0.642 | 0.55 to 0.73 |
| 35 | `gpt-5.4-nano` | 0.927 | 0.708 | 0.635 | 0.53 to 0.74 |
| 36 | `qwen3-next-80b-a3b-instruct` | 0.979 | 0.653 | 0.632 | 0.54 to 0.72 |
| 37 | `gpt-oss-20b` | 0.958 | 0.521 | 0.479 | 0.33 to 0.61 |
| 38 | `gpt-oss-120b` * | 0.745 | 0.535 | 0.279 | 0.11 to 0.44 |
| 39 | `grok-4.20-non-reasoning` | 0.979 | 0.111 | 0.090 | 0.02 to 0.18 |

The interval is a scenario cluster bootstrap (10,000 resamples). * marks the flagged run.

{% enddetails %}

**1. Trust is nearly solved. Restraint is not.** Trust has a median of 0.995 and only one model
below 0.90 (the flagged gpt-oss-120b, 0.745). Restraint has a median of 0.951 and fourteen models
below 0.90, ranging from 1.000 (`gpt-6-astra`) down to 0.111 (`grok-4.20` non-reasoning). Spread
four times as wide, restraint is what ranks these models. When memory holds the answer, 34 of 39
models use it on every present item, and an outdated note was applied 9 times in 3,740 replies
where a newer one replaced it.

**2. There is no single way to fail at restraint; there are two, and they belong to different
models.** I did not preregister this, so read it as an observation:

- *Picking a side.* GPT-5.4 asks on all 24 items with empty memory, but on two notes that disagree
  it chooses one 17 times in 48. Its mini and nano versions, and Qwen3-Next instruct, do the same,
  with contradictory accuracy between 0.333 and 0.646.
- *Answering from defaults.* Opus 4.6 and GPT-5.5 are the reverse: on a conflict they ask 46 times
  in 48, but with empty or off topic memory they answer anyway, with a plausible value of their
  own (absent 0.750 for both, adjacent 0.667 and 0.708).

When a model does pick a side, it takes the note shown **last** twice as often as the first (178
against 89, pooled). That holds in every model that picks a side ten or more times, except the two
Grok 4.20 modes, which lean the other way.
And the adjacent note is almost never borrowed (19 replies in 935, 13 of them from one model); the
usual failure there is a confident default.

**3. In both families with two modes, the reasoning mode is more restrained.** Grok 4.20 goes from
0.111 restraint without reasoning to 0.701 with it, and Qwen3-Next 80B from 0.653 (instruct) to
0.833 (thinking). Two pairs are an observation, not a law, and I did not preregister it.

**4. When only the dates tell an old note from its replacement, models that slip stop and ask.**
Every superseded item has the old note and the new one. When the new note says outright that it
replaces the old one, models pick it essentially always (1,852 of 1,869 replies). When only the
dates differ, accuracy falls by 0.044 on average, and by 0.25 for DeepSeek R1. But those misses are
mostly an `ASK` (76 replies), not the stale value (9). That is scored as wrong, and arguably it is
the cautious kind of wrong.

**Where my predictions missed.** I committed ten predictions before running anything. Scored
against the result, six were met and four missed:

| # | prediction | measured | result |
|---|---|---|---|
| 1 | median accuracy on present at least 0.90 | 1.000 | met |
| 2 | contradictory is the hardest condition by median | 0.958; adjacent was lower, 0.917 | missed |
| 3 | implicit supersession is harder than explicit: by 0.03 to 0.20 pooled, and for at least 70% of models | +0.044; 97% of models | met |
| 4 | a stale note nearer the question gets applied more | 0.003 against 0.002 | missed |
| 5 | best J between 0.60 and 0.95, median between 0.30 and 0.75 | 0.995 and 0.931 | missed |
| 6 | at least one credulous and one timid model | two credulous, no timid | missed |
| 7 | over-asking on present at most 0.05 (median) | 0.000 | met |
| 8 | at least 60% of ASKs on a conflict name both values | 0.949 | met |
| 9 | the adjacent note costs more than empty memory | 0.917 against 0.958 | met |
| 10 | format failures at most 2% | 0.4% | met |

The misses point the same way: I expected this to be harder than it was. I set the range in
prediction 5 for models that would be confused by memory, and the median model scored 0.931. I
expected some model to be timid, asking even when memory held the answer, and none was: the lowest
trust after the flagged run is 0.906. And I expected the stale note to be the temptation, when it
was applied too rarely for its position to matter. Position does matter, but on conflicts (finding
2), which I had not thought to predict.

**Caveats I would want a reader to know.**
- The prompt offers the `ASK` route explicitly, so this measures whether a model *can* tell when
  to lean on memory, not whether it would stop and ask unprompted inside an agent loop. That may be
  why the scores are high.
- One run per model; differences under about 0.03 in J are noise (see the duplicate run).
- I also expected smaller models to ask less. GPT-5.4's mini and nano do ask less than the full
  model, but nano asks more than mini, and the two gpt-oss sizes are level, so I make no claim
  about size.
- The scenarios were written with the help of a Claude model, and Claude models are in the grid,
  so any familiarity advantage is unmeasured.
- The adjacent notes state their own scope and the distractors are plainly off topic, which makes
  this easier than a real memory store.
- Model versions behind a Kaggle slug can change; runs are dated in the repository.

**What I would measure next:** the same items with the `ASK` instruction removed, inside a tool
loop, which is where agent-memory-bench lives; and whether a memory layer can recognise a near-miss
question before the model sees it.

## My Benchmark

[Memory Discipline on Kaggle Benchmarks](https://www.kaggle.com/benchmarks/giulioder/memory-discipline)

Three differences between Kaggle's leaderboard and this post, so the numbers line up. Kaggle ranks
by the average of the two task scores; I rank by J, which is twice that average minus one, so the
order is the same. Kaggle shows each model's latest run, while I score the earliest complete one,
as committed before the analysis; that changes two models, Claude Haiku 4.5 (Kaggle shows the
accidental repeat) and gpt-oss-120b (Kaggle shows its trust rerun). And Kaggle's leaderboard lists
38 models, because Claude Sonnet 4.5 was retired from Kaggle after it ran; its runs are still on
the task pages and in my analysis.

Everything behind the numbers is public: the items, the scorer, the analysis script, the
preregistration with its predictions, both deviations and the result, and the selection of scored
runs: [agent-memory-bench, kaggle_memory]({{REPO_REF}}/kaggle_memory).
