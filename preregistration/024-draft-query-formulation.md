# 024 — Does searching with the draft, rather than the goal, close the retrieval miss?

**Date:** 2026-09-01   **Status:** predicted, not yet measured

Written before the variant exists and before any session runs.

## The question

On the `superseded` condition, does instructing the recall arm to search memory with **the code it
is about to write** rather than with a description of its task reduce the share of sessions in
which **neither plant document is retrieved**?

## Why this and not the other things

Five lanes are already measured and closed, and this record exists so none of them is re-opened:

| lane | measured | where |
|---|---|---|
| rewriting memos for discoverability | 0 of 14 rescued, twice, live instrument; one arm LOST a hit | `authored-discoverability-surfaces-cannot-close-the-formulation-gap` |
| fusion weights / ranking | 12 variants, recall solved, **zero** viable gating points | `search-with-the-draft-not-the-goal` |
| recalibration | frontier swept, no knee; a monotone remap cannot reorder hits | same |
| per-write automatic search | 11/11 on sessions needing it, 29/36 on sessions not | same, design killed |
| declaring lineage | **1 cell of 30** once the perturbation is removed | `lineage-tier-result-t0-vs-t2` |

**The reframe that motivates this one.** recall's `superseded` damage rate is 0.179 (5/28). So is
the placebo's. So is `fs_grep`'s. Three arms, one carrying deliberately useless memory, land on the
identical number, so that is the condition's noise floor and **there is probably no recall-specific
damage to fix**. The recoverable term is on the benefit side:

| what recall surfaced | share of sessions | solved |
|---|---:|---:|
| current plant only | 36% | **1.00** (19/19) |
| both plants | 17% | 0.56 |
| **neither plant** | **45%** | 0.46 |

Retrieval that works solves the task nineteen times out of nineteen. The 45% miss is worth roughly
+13 solved; the lineage failure we just spent a night on is worth ~+4 and measured at one cell.

## What I predict

Deliberately low. `i-over-predict-effect-magnitudes` records eleven of twelve registered predictions
too high by two to four times, and its instruction is to predict a quarter to a half of the ceiling
and to predict the mechanism metric beside the outcome. The ceiling here is the 11/11 measured on
recall's own corpus, which would take the miss to ~0.

1. **Neither-plant share falls from 0.45 to 0.32** (range 0.38 to 0.25). About a third of the
   ceiling. Probability it moves at all in the predicted direction: 0.75.
2. **Task success on `superseded` rises by +4 percentage points** (range 0 to +10). Probability the
   CI excludes zero at n=55 admitted cells: **0.20**. This is registered as probably underpowered.
3. **Mechanism metric moves first and moves more.** Mean recall-arm query length rises from 7.1
   words to over 20 tokens, and mean lexical overlap between query and the retrieved plant roughly
   doubles. If the outcome moves while this does not, the instruction was not followed and the
   result means nothing.
4. **Damage rate does NOT fall and may rise slightly**, to between 0.167 and 0.25 from 0.167.

## The prediction I most expect to be wrong, stated now

Prediction 1 assumes sessions move from *neither* to *current only*. **They may move from *neither*
to *both* instead**, and both-plants sessions solve at 0.56 against current-only's 1.00. Better
retrieval surfaces the stale plant just as readily as the current one, because the draft's
identifiers appear in both versions of the document.

If that happens the miss share falls as predicted and task success barely moves. **That outcome is
not a failure of the idea; it is the discovery that the retrieval fix and the lineage fix are
complements**, and it would be the one result that revives supersession declaration, which tonight
measured at one cell.

I am registering that I consider this the single most likely way the run surprises me, at
probability **0.35**.

## What would falsify this

* **Neither-plant share unchanged or worse.** Then the draft-query effect does not transfer from
  recall's own corpus to a 4,911-document adversarial haystack, and the lane closes here rather
  than after a task-success run.
* **Mechanism metric flat.** The instruction was not followed; nothing about draft search is
  learned and the record is about prompt compliance instead.
* **Miss share falls while damage rises enough to cancel it.** Then the intervention trades a
  retrieval failure for a confusion failure and needs the lineage work as a prerequisite rather
  than as an alternative.

## How it will be measured

Corpus: `bench-lineage-t0-superseded`, already built, certified and promoted, 4,911 documents,
scale-25 haystack, generation `gen_623717ea…`. **No rebuild.** This is the same corpus the Tier 0
control ran against, so the baseline arm is a re-run of a measured configuration and not a
remembered number.

```
RUN_ID=draft-024 NAMESPACE=bench-lineage-t0 CONDITIONS=superseded \
  ARMS=bare,recall SEEDS=5 AMB_HAYSTACK=<scale-25/seed-1> \
  --memory-instruction draft        # the new variant
```

Baseline is the existing `lineage-t0-superseded` run (110 records, `skill` instruction), so the
comparison is `draft` against `skill` on one corpus, 11 tasks, 5 seeds, 2 arms, 110 sessions,
model `deepseek/deepseek-v4-flash`.

Metrics, each named by its denominator:

| metric | denominator |
|---|---|
| **neither-plant share** (primary) | recall-arm sessions in `superseded` that issued ≥1 search |
| plant-retrieval split (current only / both / neither) | same |
| task success | admitted cells |
| damage rate | paired cells against `bare` |
| mean query tokens, query-plant lexical overlap | recall_search calls |

## Apparatus verification, before any session runs

Three checks, because predicting the outcome does not reveal a broken harness and this project has
paid for that lesson twice this week:

1. **The rendered `prompt.md` differs** from the `skill` variant's, and names drafting explicitly.
   Assert on the file, not on the config.
2. **Positive control on a known case.** Take one `superseded` task, issue its goal query and a
   draft-shaped query against the same tenant, and confirm the draft query returns a plant the goal
   query does not. If it does not, the mechanism is absent on this corpus and the run is cancelled
   before it is paid for.
3. **The baseline is reproducible.** The `skill` arm's neither-plant share recomputed from the
   existing `lineage-t0-superseded` records must land at 0.45 ± 0.10 against official-002's figure.
   If it does not, the metric is not measuring what the 45% measured.

## What I already know

* Draft-time search surfaces the governing memo in **11 of 11 sessions that demonstrably needed
  it**, against **1 of 14** for the goal query, on executed-checker ground truth with no judge. The
  same retriever ranks the memo at 1 for the draft and 127 to 142 for the goal.
* That effect was measured on recall's **own** corpus (`probe2_control`, `agent-ab-skill-001`),
  **not** on this benchmark's adversarially generated haystack. Transfer is the open question.
* The per-write automatic form is dead: it fires on 29 of 36 sessions that need nothing, base rate
  23%, and no gate fixes the arithmetic. **What survives, and what this tests, is a deliberate
  search**, which was left unregistered there because "the agent chose to search" cannot be
  measured by replaying recorded sessions. **This benchmark runs live agents against an executed
  checker, so it can measure exactly that.**
* A task-success null already exists for a memory-layer A/B (`agent-ab-task-success-result-2026-08-22`,
  +0.154 with the CI crossing zero). Prediction 2's low confidence is set from it.

## Confounds I can name now

1. **Corpus transfer.** 11/11 came from a corpus built from real sessions; this one has 4,902
   adversarially generated distractors built from corpus vocabulary to be confusable. A draft query
   is a bag of repository identifiers, which is precisely what those distractors share.
2. **Prompt length.** The `draft` instruction is longer than `skill`. Any effect could be the
   instruction's length or specificity rather than its content. **Mitigation: report token counts,
   and treat a null on the mechanism metric as decisive.**
3. **`skill` is not the fair variant, by the harness's own documentation.** `scripts/pilot.py`
   states "pass `--memory-instruction protocol` for the fair variant", and official-002 and every
   tier run used `skill`. This record compares `draft` against `skill` because that is the measured
   baseline, and it therefore inherits whatever `skill` does. A `protocol` arm would separate them
   and is **explicitly out of scope here** to keep this a one-variable change.
4. **Both-plants displacement**, registered above as the most likely surprise.
5. **One model.** `deepseek/deepseek-v4-flash`. Query length spans 2.6x across three models from
   identical instructions, so a draft instruction may land differently elsewhere.

## Out of scope, deliberately

* `contradictory`. Rival plants have no authoritative version and no retrieval fix addresses that.
* Any corpus rebuild. This is a prompt variable measured against an existing certified generation,
  which is the whole reason it costs ~45 minutes and under a dollar rather than a Voyage pass.
* The automatic per-write trigger, which is closed.

<!-- results are appended below this line; everything above is frozen -->
