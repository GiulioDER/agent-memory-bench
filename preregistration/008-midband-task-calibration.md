# midband-001: do the six new tasks land where they were designed to land?

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

For each of the six task candidates added for the abstention suite, what is `bare`'s success rate,
and how many of them fall strictly inside (0, 1), the `TWO_SIDED` stratum that preregistration 007
fixed as the only one able to carry preregistration 005's primary endpoint?

## Why this needs a record at all

This is task construction, which would normally not. It needs one because the number decides
membership: a task joins the abstention suite if and only if this measurement puts it in
`TWO_SIDED`, and a rule that admits tasks on a number I have already seen is not a rule. Writing
the prediction down first is also the only way to find out whether I can design toward a stratum
or merely hope.

## Design

`bare` only, six tasks, six seeds, 36 sessions. No other arm, because `bare` ingests no corpus and
its rate is what both preregistration 005 and 007 are defined against. No corpus work is needed for
any of these tasks yet, and none has been done: precursor recordings and memory bundles are
deliberately deferred until after this measurement, so that effort is spent only on tasks that
survive it.

**Six seeds, matching the modal `n` of the screen in 007 rather than exceeding it.** The existing
24 tasks were classified on 4 to 6 admitted `bare` observations. More seeds would make a new task
strictly more likely to show both a success and a failure, so calibrating new tasks at higher
resolution than old ones would let them into `TWO_SIDED` on an easier test. That would be a
selection bias in favour of my own new tasks, and it is avoided by using the same resolution.

Model `deepseek/deepseek-v4-flash`, timeout 600s, permission mode `acceptEdits`, run on VPS2, all
matching `diagnostic-009` and recorded in `environment.json` before the first session. Admission is
unchanged; discarded cells are published with reasons.

## Predictions

House prior: my effect predictions on this benchmark are eleven falsified out of twelve, every one
too optimistic, so these are set low deliberately. The base rate to beat is the 5 of 24 (21%) that
landed mid-band by accident among tasks never designed for it.

1. **Three of the six land in `TWO_SIDED`**, with a range of **2 to 4**. Below 2 the design rule
   from the existing 0.50 tasks is not a rule; above 4 I have understood something I do not think
   I have understood.
2. **`ts-csv-quote` is the most likely to hit the ceiling.** The prompt names CSV explicitly, and
   reaching for the csv module on a task about CSV is close to a default rather than a habit.
   `bare` at or above **0.83**.
3. **`ts-natural-order` is the most likely to hit the floor.** The sandbox stops at five reports,
   so `sorted()` is correct locally and nothing prompts a numeric key. `bare` at or below **0.33**.
4. **No task lands at exactly 0.00 across all six seeds except possibly `ts-natural-order`.** Every
   other candidate encodes something a competent agent does sometimes, which is the design rule.
5. **Cost under $0.60** for the 36 sessions. `diagnostic-010` ran 288 sessions for $0.890, and
   `bare` sessions are cheaper than memory ones, so the arithmetic says roughly $0.11; the house
   prior of five times that gives the bound.

Prediction 1 is the one that matters. Predictions 2 and 3 exist to test whether I can pick which
direction a task will fail in, which is a stronger claim than the count and one I expect to get
wrong at least once.

## What happens to each outcome

Fixed here, before the numbers exist:

* A task in `TWO_SIDED` joins the abstention suite, and a result is appended below
  preregistration 007's marker recording that its `TWO_SIDED` stratum has grown.
* A task in `DAMAGE_ONLY` is **kept**, not discarded. That stratum carries endpoint 2 and currently
  has exactly 8 members, which is preregistration 005's own underpowered threshold, so one
  admission discard drops it under. More is strictly better there.
* A task in `BENEFIT_ONLY` is kept in the repository and used by neither stratum of the abstention
  suite. It remains available to the fact-present suite, where a floor task is ordinary.
* **No task is redesigned and re-measured in order to move it between strata.** That would be
  fitting tasks to a target, and the second measurement would not mean what the first one meant.
  If fewer than 8 `TWO_SIDED` tasks exist after this, the honest options are to build more
  candidates under a rule revised in the open, or to run the abstention suite with its primary
  endpoint labelled underpowered.

## What would falsify this

* Prediction 1 falsified at 0, 1, 5 or 6 mid-band. At 0 or 1 the design rule extracted from
  ts-atomic-write, ts-golden-regen and ts-manifest-rel does not generalise and I should say so
  rather than build a seventh candidate. At 5 or 6 the rule is stronger than I believe, which is
  worth reporting because it means the missing middle was a construction accident rather than
  something hard.
* Predictions 2 or 3 falsified if either named task lands in the opposite stratum from the one
  predicted. That would mean I can build mid-band tasks without being able to predict which way
  one leans, which is a real and reportable limit on the method.
* The whole calibration is void if `bare`'s rate on the existing 24 tasks, re-measured in the same
  run, disagrees with preregistration 007's table. That would mean run-to-run variance rather than
  task structure is what 007 stratified on. **This run does not re-measure the existing tasks**, so
  this check is not performed here and the risk stands unquantified; it is the same exposure 007
  already names in its own falsification section.

## What I already know

Preregistration 007, measured 2026-08-27: 19 of 24 tasks sit at exactly 0.00 or 1.00, leaving
`TWO_SIDED` at 5, `DAMAGE_ONLY` at 8 and `BENEFIT_ONLY` at 11. The three existing tasks at exactly
0.50 are ts-atomic-write, ts-golden-regen and ts-manifest-rel, and reading them is where the design
rule for these six came from: a convention that is a recognised best practice applied
inconsistently, with the obvious implementation also plausible.

All six candidates pass the three-way reference gate, so each has a competent factless solution
that fails and an informed solution that passes. That gate says nothing about where a real agent
lands between them, which is the entire question here.

<!-- results are appended below this line; everything above is frozen -->

## Result, measured 2026-08-27

`midband-001`, VPS2, `deepseek/deepseek-v4-flash`, `bare` only, 6 tasks x 6 seeds.
**36 sessions, 36 admitted, 0 discarded, 0 session errors.** Wall 18 minutes, $0.0493,
539,253 tokens. Overall `bare` 19/36 = 0.528.

| task | `bare` | stratum | predicted |
|---|---:|---|---|
| ts-bool-env | 1.00 | `DAMAGE_ONLY` | mid-band |
| ts-cli-exitcode | 0.00 | `BENEFIT_ONLY` | mid-band |
| ts-csv-quote | 1.00 | `DAMAGE_ONLY` | ceiling ✓ |
| ts-idempotent-run | 0.17 | `TWO_SIDED` | mid-band ✓ |
| ts-json-sorted | 0.00 | `BENEFIT_ONLY` | mid-band |
| ts-natural-order | 1.00 | `DAMAGE_ONLY` | floor ✗ (ceilinged) |

Reproduce with `scripts.select_abstention_tasks.stratify` over
`results/midband-001/records.final.jsonl`.

### Scoring the predictions: two confirmed, three falsified

1. **Three of six land mid-band, range 2 to 4.** **FALSIFIED.** One did. Below the stated range,
   so this is not a near miss.
2. **`ts-csv-quote` ceilings at or above 0.83.** **CONFIRMED**, at 1.00.
3. **`ts-natural-order` floors at or below 0.33.** **FALSIFIED**, and in the opposite direction: it
   ceilinged at 1.00. The model sorts by numeric suffix reliably, unprompted, with only five
   single-digit reports visible.
4. **No task at exactly 0.00 except possibly `ts-natural-order`.** **FALSIFIED.** Two tasks landed
   at exactly 0.00, and neither was the predicted one.
5. **Cost under $0.60.** **CONFIRMED**, at $0.0493, an order of magnitude under.

That makes thirteen falsified predictions out of seventeen on this benchmark. Prediction 1 failed
in the same direction as every previous one: too optimistic.

### What the pre-committed rule now binds me to

The frozen text says: "Prediction 1 falsified at 0, 1, 5 or 6 mid-band. At 0 or 1 the design rule
does not generalise and I should say so rather than build a seventh candidate."

**The design rule does not generalise.** Building more candidates to the same rule is exactly what
this record forbids, and the 1-in-6 hit rate says the cost of reaching 8 that way would be roughly
twelve more tasks for two more slots.

### What the pattern actually is, which the rule missed

The rule was "a recognised best practice applied inconsistently". The results say agent
convention-following is close to **deterministic per convention**, not inconsistent, and splits on
something the rule never mentioned:

* **Reliably right** (1.00): use the csv module, parse `off`/`no`/`0` as false, sort by numeric
  suffix. Every one of these is a property of the output of a **single run**, visible by looking at
  what the program just produced.
* **Reliably wrong** (0.00): sort JSON keys for reproducibility, exit non-zero so a pipeline stops.
  Both are properties that only exist **across invocations or across consumers**, and neither is
  visible in the artefact a single run produces.
* **The one mid-band case** (0.17): idempotency on re-run, which is also a cross-invocation
  property, and the only one where the fixture's README said out loud that re-runs happen.

So the blind spot is **cross-invocation properties**, and it is close to all-or-nothing too. That
is a more useful generalisation than the one predicted, and it was not derivable from the three
existing 0.50 tasks, which is why the rule extracted from them failed.

### A resolution limit that this design cannot see, recorded rather than fixed

With `n = 6`, a task whose true rate is 0.90 shows 6/6 about 53% of the time. So `DAMAGE_ONLY`
here means "no failure in six", not "cannot fail", and some of these three may be near-ceiling
rather than at it. The same applies to every task in preregistration 007, which used 4 to 6.

This is **not** grounds for re-measuring these six at higher `n`: doing that now would give the new
tasks an easier path into `TWO_SIDED` than the old ones faced, which is the exact bias the frozen
design avoided by matching `n`. A higher-resolution re-measurement is only legitimate if it covers
**all 30 tasks at the same `n`**, and that is a separate preregistration, not an amendment here.

---

⚠️ **The corpus feed changed on 2026-08-29, after this record's numbers were measured.**
`corpus/manifest.json` went from 125 entries to 195 (thirteen signal sessions that were on disk
and unlisted, plus 57 distractors to hold the 4:1 ratio), so retrieval here ran over a smaller
haystack than any later run will. Do not difference a number measured after that date against one
above. Nothing above this line was edited.
[`docs/audit/2026-08-29-corpus-feed-change-record.md`](../docs/audit/2026-08-29-corpus-feed-change-record.md)
