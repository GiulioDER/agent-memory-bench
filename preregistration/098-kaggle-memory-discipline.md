# 098 kaggle-memory-discipline-001: with the memory held fixed, which models use it correctly?

Status: frozen when committed. No task may be pushed to Kaggle, and no model may answer a single
item, before the commit that adds this record.

This is not an agent-memory-bench leaderboard run. It touches no AMB corpus, task, oracle or
held out set. It inverts the AMB design for the DEV x Kaggle Benchmarking Challenge (submissions
close 2026-10-11): AMB holds the model fixed and varies the memory layer; this holds the memory
fixed and varies the model. The item set is new, authored for this run, and public by design.

## Question

For each model Kaggle Benchmarks serves, what is its Youden's J on the memory-discipline item set,
where J = trust + restraint - 1, trust is accuracy where memory answers the task and restraint is
accuracy where it does not?

## What is frozen, by sha256 of the LF bytes

| file | sha256 |
|---|---|
| `kaggle_memory/scenarios.json` | `6b8dcdc5581448aef80fdcbf0d9e57bbe636f5d790d489d6640ed4c6da24b1ba` |
| `kaggle_memory/items.json` | `f3f95b26f2b07f047fcc033007eebd8c2be96f3d31eb83caabfc2d91159de109` |
| `kaggle_memory/scoring.py` | `34a06168e8a66f517c2f2f31767f725bc4f58f9d1c1eb1d1efbd12ccb6f6a53f` |
| `kaggle_memory/items.py` | `b7b6865a57cc25063149ec3f6043d23425f0d94c6bc822ebb77d8a50e19a2342` |
| `kaggle_memory/tasks/memory_discipline_trust.py` | `8c0212f33a78d8ab27692fe11ac52b7dd422dbc76eaf90000d814f440ffea930` |
| `kaggle_memory/tasks/memory_discipline_restraint.py` | `cf1074e4dc102f83ab60441de74c8f60fcbc3385f6b89ed20c030051e77e30d0` |
| `scripts/analyze_kaggle_memory.py` | `efb4b5bf48987a3b24f8a6530d90c7380bcb42d7759b76c74d43aa8a013ec7fd` |

These hashes are of the set AFTER a pre-freeze adversarial review, which found and fixed, before
any model saw an item: a scorer that marked correct spellings wrong (`decimal.ROUND_HALF_EVEN`,
`s3://bucket`, `35MB`, `3.12.x`); a parser that missed `` `VALUE: 6` `` and `Final answer:
VALUE: 6`; "implicit" supersession items whose current memo still said "the old limit"; eight
contradictory pairs where one side cited a harder constraint or sounded newer; naming patterns
that let the adjacent memo spell out the current value; and stale defaults being labelled as
memory failures in `absent`. The review's findings and the fixes are in the commit that adds this
record, and `tests/test_kaggle_memory_discipline.py::REALISTIC_REPLIES` pins the formats.

## Design

24 scenarios, each one coding question about one project decision (a retry count, a time zone, a
bucket name). Every scenario authors five readings of the answer, pairwise distinguishable by the
scorer, which `kaggle_memory.items.validate` enforces: `current`, `stale`, `adjacent` (a true
decision about a different subsystem that states its own scope), and `contra_a` and `contra_b` (two
undated memos that disagree, neither of them current). Three unrelated distractor memos accompany
every item. The question text is identical across a scenario's items; only the memory differs.

| condition | items | memory | correct | family |
|---|---:|---|---|---|
| present | 24 | the current memo | `VALUE: <current>` | trust |
| superseded | 96 | stale and current, both dated; explicit or implicit; both orders | `VALUE: <current>` | trust |
| absent | 24 | distractors only | `ASK: ...` | restraint |
| adjacent | 24 | the adjacent memo | `ASK: ...` | restraint |
| contradictory | 48 | both undated halves, both orders | `ASK: ...` | restraint |

Explicit supersession appends one sentence to the current memo naming the note it replaces;
implicit leaves only the dates to tell them apart, and no current memo contains any language that
implies a change. The two halves of each contradictory pair give reasons of the same kind, with no
wording that implies one is newer or binding.

A VALUE is attributed to a reading by token match, tolerant of a namespace or path prefix, a glued
unit on a number, a patch or wildcard on a version, and listed aliases. A reading named whose memo
is NOT in the item's memory is labelled `value:guess` rather than `value:<reading>`: a stale value
guessed in `absent` is the model's prior, not a memory failure. A VALUE naming two readings is
`value:multiple` and scored incorrect. A family score is the unweighted mean of its
conditions' accuracies. Kaggle shows the two tasks and their average, `score`; J = 2 x score - 1
ranks identically and puts both trivial policies (always ask, always apply the newest memo) at 0,
which is how AMB reports usefulness (`harness.abstention.usefulness`, preregistration 017).

## Grid

Every model `kaggle b t models` lists on the day of the first push, each run once on each of the
two tasks, at the library defaults (temperature 0 where the model supports it, seed 0, no
reasoning level set). If quota runs out, models are run in alphabetical order of slug and the run
stops there; the unrun models are listed, never selected. Library `kaggle-benchmarks` as installed
in the Kaggle notebook image on the run date, recorded with the result.

The first push is run on one model per task to prove the pipeline. That run is kept as that
model's result: the items and the scorer are frozen above, so seeing it changes nothing below.

## Endpoints, in reporting order

1. Primary: J per complete model, with a 95% interval from a scenario cluster bootstrap (10,000
   resamples, seed 20260925), ranked.
2. Trust and restraint per model.
3. Accuracy per condition per model, with Wilson 95% intervals.
4. Superseded, explicit against implicit, per model and pooled as the mean over complete models.
5. Stale application rate by memo order (`stale_first`, `current_first`), pooled.
6. Over-asking on `present`, per model.
7. Among ASK replies on `contradictory`, the share that names both values, pooled.
8. Outcome distribution per condition, which is where the damage is attributed: `value:stale`,
   `value:adjacent`, `value:contra_a` or `value:contra_b`, `value:guess`, `value:multiple`,
   `value:other`, `format_failure`.

All endpoints come from `scripts/analyze_kaggle_memory.py`, which re-scores every raw reply from
the downloaded run files and reports any disagreement with the in-notebook score.

## Predictions

Median and pooled figures are over complete models only.

1. **Present is easy.** Median present accuracy >= 0.90.
2. **Contradictory is the hardest condition.** The median of contradictory accuracy is lower than
   the median of every other condition. Mechanism: models settle a conflict by choosing the memo
   with the more persuasive reason rather than reporting it.
3. **Implicit supersession is harder than explicit.** Pooled mean of (explicit - implicit)
   accuracy between +0.03 and +0.20, and explicit >= implicit for at least 70% of models.
4. **Position pulls toward the stale memo.** Pooled stale application rate is at least 0.02 higher
   in `current_first` order (stale memo later, nearer the task) than in `stale_first`. Low
   confidence.
5. **Range.** The best complete model's J is in [0.60, 0.95]; the median complete model's J is in
   [0.30, 0.75].
6. **Two failure profiles exist, not one skill.** At least one complete model is credulous (trust
   >= 0.85 and restraint <= 0.60) and at least one is timid (restraint >= 0.85 and trust <= 0.70).
7. **Over-asking is rare.** Median over-ask rate on present <= 0.05.
8. **A conflict, when reported, is reported properly.** Pooled, >= 0.60 of contradictory ASK
   replies name both values.
9. **The lure costs more than the void.** Median adjacent accuracy <= median absent accuracy. Low
   confidence, since every adjacent memo states its own scope.
10. **The format is not the obstacle.** Pooled `format_failure` rate <= 0.02.

## Exclusion and truncation rules

- A model is complete when at most 5% of each family's items errored or are missing after the
  task's own three attempts. An incomplete model is reported separately and enters no ranking,
  median or pooled figure.
- A reply with no `VALUE:` or `ASK:` line is scored incorrect, not excluded.
- No item, scenario, prompt or scoring rule changes after the first push. A pipeline fix that
  touches none of the frozen files is allowed and is appended below with its reason.

## What would falsify this

Each numbered prediction states its own threshold, and each is scored separately; a miss stays in
the record. The design itself is falsified, and the run reported as uninformative, if more than
half of the complete models land within 0.05 of J = 0, since that is where both trivial policies
sit; or if the re-scored results disagree with the in-notebook results on any item and the cause
is the scorer.

## Confounds I can name now

1. **The ASK channel is offered in the prompt.** This measures whether a model can tell when to
   use its memory given an explicit way out, not whether it would stop to ask unprompted inside an
   agent loop. AMB measures the latter; the results must not be read as the same quantity.
2. **Authorship.** The scenarios were written by a Claude model (Claude Opus 5.5, assisting the
   author). If Claude models are in the grid, any familiarity advantage is unmeasured, and the post
   must say so.
3. **The adjacent memos draw their own boundary** (AMB planting rule 3), and the distractors are
   plainly off topic. Both make the item set easier than a real memory store's retrieval noise.
4. **One sample per item.** No seed variance is estimated; the interval is over scenarios only.
5. **Model versions behind a Kaggle slug can change during the run window.** The run dates and
   slugs are recorded with the result.
6. **Stale values are recognisable conventions** (UTC, gzip, main, 3 retries). Where the stale
   memo is absent from memory the label is `value:guess`, but in `superseded` a model that ignored
   both memos and used its prior is indistinguishable from one that followed the stale memo.
7. **The task is phrased as "Set X"**, which invites a sensible default, while the ASK line says
   "checking with the team". The pull is the same in every condition, so it moves levels, not the
   contrasts between conditions.

## What I already know

AMB's harm suite (preregistration 005) found superseded and contradictory to be where agent memory
arms failed most often, in runs small enough that no rate from them is quoted here. AMB's own
composite moved to J after abstention was found to be a dominant strategy without `present`
(preregistration 017). No model-varying measurement of this kind exists in the repository.

<!-- results are appended below this line; everything above is frozen -->

## Amendment 1 (2026-09-25), before any measurement

**Status:** predicted, not yet measured. No task had been pushed to Kaggle and no model had seen
an item when this was written. Nothing above this marker was edited: the hash table in "What is
frozen" is left as committed, and it is now superseded by the table below. The predictions,
endpoints, exclusion rules and falsifiers are unchanged.

**Why.** A code review of the committed scorer and analysis, run immediately after the commit,
found defects that would have cost real models points for reasons unrelated to memory use, and
one that could have merged every model into one:

1. An afterthought below the answer overrode it ("VALUE: 6" then "Value: 3 was the stale one").
   Directives now have three strengths (line-initial upper case, line-initial any case, inline
   upper case) and the last of the strongest present wins.
2. An identifier such as `DEFAULT_VALUE:` was read as a directive. The inline lookbehind now
   excludes digits and underscores.
3. `VALUE:` with the answer on the next line, a fullwidth colon, `python3.12`, `v3.12` and `35MiB`
   were misread; each is now accepted.
4. "VALUE: 6 (replaces 3)" and "UTF-8 with BOM (utf-8-sig)" scored `value:multiple`. Two
   tie-breaks now apply: a reading matched only inside a longer match of another is dropped, and
   a parenthetical aside is ignored when that leaves exactly one reading. "UTF-8 with BOM" is an
   alias of `utf-8-sig`. The validator now judges attribution with the same function.
5. The analysis scored only the last assistant content of a reply; it now scores all of them.
   A run file without a model slug is refused instead of being merged. Retries are ordered by
   parsed time, not by string. `report.json` is strict JSON. Any re-scoring disagreement is
   printed in the report and makes the analysis exit 1.

The review also found that `enable_cache` might reuse one model's answers for another. It does
not: run files are keyed by row and model slug, and every Kaggle run is a fresh notebook.

Each fix has a regression test that was shown to fail against a named mutation before being
trusted; they are listed in `tests/test_kaggle_memory_discipline.py`.

**The frozen set is now these bytes:**

| file | sha256 |
|---|---|
| `kaggle_memory/scenarios.json` | `a72d464898de03344541de0d348eb15e3b12add7a721adc89ce53a0d6ca7d248` |
| `kaggle_memory/items.json` | `e8010a1d904668527c8389aaca06ac22be11776aac338ffb5f2290ef64835a7a` |
| `kaggle_memory/scoring.py` | `284bb96980bd48496c2e88c82e302ea6be492af32ffd75e636fc6c5b67c74ec6` |
| `kaggle_memory/items.py` | `07534d4cf06428ca6488e66f081f5bb152974662eb81dc7716f44111173aa438` |
| `kaggle_memory/tasks/memory_discipline_trust.py` | `3db340a6e208f82eedd67a40b233c1f4cfd61eedbb95392eedfaf1c4aed6a888` |
| `kaggle_memory/tasks/memory_discipline_restraint.py` | `1a8e7d0a0a382408dd8536a6ff8522be488d20157827b3de6a645b91d3b14097` |
| `scripts/analyze_kaggle_memory.py` | `1541c34c98b83c8051727042ab0622dd9873dddea6ccf8bbb778782832e56795` |

Nothing may change after the first push; a second amendment of this kind is not available once
any model has answered.

## Deviation 1 (2026-10-05), AFTER one model had answered

**This is a deviation, not an amendment.** Amendment 1 said no further change was available once
any model had answered, and one had: `gemini-3.7-flash` ran on both tasks under the Amendment 1
files (trust 120/120, restraint 95/96, J 0.986, zero re-scoring disagreements). The change was
decided by the user after the quota facts below were measured, and it is recorded here so that
anyone can weigh it.

**What forced it.** The account's Kaggle model quota, read from `GetModelProxyQuotas` on
2026-10-05: **$10 per day and $100 per month**. Kaggle reserves the worst-case cost of every call
before making it, from the maximum output length; at the provider default one Opus call reserved
$3.20 (Sonnet $0.96, Haiku $0.32), and the task sends four calls at a time. The first batch of the
grid (the eight Claude models) was refused on 15 of its 16 runs with `exceeds your available quota
(based on max_output_tokens)`, and no refused run produced an item result. As frozen, the five
Opus models could never start under a $10 daily cap.

**What changed, and only this.** Every model call now carries a reply-length cap of 8,192 tokens
(`kaggle_memory/generation.py`, copied verbatim into both task files): `max_output_tokens` for
Google's client, `max_completion_tokens` for the OpenAI-compatible one. Items, prompts, the
scorer, the analysis, the endpoints and the predictions are unchanged, byte for byte. 8,192 is
about fifteen times `gemini-3.7-flash`'s mean of 532 output tokens per item (114,854 over 216,
thinking included). A reply cut off by the cap has no directive line and scores `format_failure`;
the analysis reports that rate, and prediction 10 stands as written.

**How the change was checked before use.** Probes through the proxy with the cap accepted it on
Gemini, GPT, Claude, DeepSeek and Qwen models; a fake-model run of both generated files under
`kaggle_benchmarks` confirmed all 216 calls carry the cap under the right name for either client;
two new tests, each shown red against a named mutation, pin both facts.

**Consequences for the record.**

1. `gemini-3.7-flash` is re-run under the capped files in its alphabetical place, so every model
   in the reported grid ran under identical settings. Its pre-deviation result is reported only
   here, as the one observation made before the change.
2. Runs are made one model at a time, both tasks together, in alphabetical order of slug, so the
   reservations of one model never block another. When the daily quota is spent, the run waits for
   the refill and continues in the same order. Whatever is unrun at the deadline is listed, never
   selected.
3. The analysis reads only the capped task version's downloads.

**The files now in force:**

| file | sha256 |
|---|---|
| `kaggle_memory/generation.py` | `b8d6e75eb6d239fb59ed4914117f94c845a5dbf9ef034269ca02a65841f83fd7` |
| `kaggle_memory/tasks/memory_discipline_trust.py` | `2f8a25c6d6a3c8f8790121daaca5811018b6f5be6979b06e1aee3ba722f8966a` |
| `kaggle_memory/tasks/memory_discipline_restraint.py` | `6d315a9eae2e76b3c087bdc5501a4af85576b158c304fe06ae3aff94bf69c59f` |
| `kaggle_memory/items.json` | `e8010a1d904668527c8389aaca06ac22be11776aac338ffb5f2290ef64835a7a` (unchanged) |
| `kaggle_memory/scoring.py` | `284bb96980bd48496c2e88c82e302ea6be492af32ffd75e636fc6c5b67c74ec6` (unchanged) |
| `scripts/analyze_kaggle_memory.py` | `1541c34c98b83c8051727042ab0622dd9873dddea6ccf8bbb778782832e56795` (unchanged) |

## Deviation 2 (2026-10-08): one model was run twice; the first complete run is the scored one

**What happened.** From 2026-10-07 21:48 to 22:16 UTC every Kaggle API call made by the grid
driver returned `401 Unauthorized`, and the driver crashed and was restarted 27 times. On the
restart that got through, the status check for `claude-haiku-4-5-20251001` still failed, the
driver (v2) read the failure as "not complete", and it ran that model again at 22:17 UTC, two days
after its complete run of 2026-10-05 (about 19:00 UTC). Both runs are on task version 2, under
identical files. The second run's in-notebook scores were trust 0.953 and restraint 0.924,
against 0.979 and 0.931 for the first.

**The rule, stated now, before the analysis is run.** For each model, the scored run is the
**earliest** run on task version 2 in which both tasks completed with at most 5% of items errored.
Any later run of the same model is excluded from every endpoint and every prediction. This is the
reading of "each run once" in the Grid section; for every model except this one it selects the
only complete run. It selects, for example, `gpt-5.5`'s retry, because its first run was refused
for quota on 142 of 216 items. The excluded duplicate is reported separately and only as what it
is: one accidental repeat of one model on the same items, which says something about run-to-run
variation and nothing about any other model.

**Why this is a deviation and not a rule from the start.** `scripts/analyze_kaggle_memory.py`
(frozen) keeps the LATEST completed reply per item. Applied to downloads containing both Haiku
runs, it would score the duplicate. So the downloads are filtered to the scored runs before the
frozen script reads them, and the filter is committed with its own test before the analysis runs.

**Also recorded.** `gpt-oss-120b`'s runs have shown "Running" on Kaggle with no start time since
2026-10-07 20:38 UTC; three launches never started. If none completes before the deadline it is
listed as not run, for that reason, like any model the budget does not reach. The driver (v3,
deployed 2026-10-08 07:56 UTC) no longer re-runs a model it has recorded as done, treats a failed
check as unknown rather than incomplete, and defers a model stuck in flight to a second pass.
