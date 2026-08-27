# resolution-001: at twelve seeds, how many tasks are actually two-sided?

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

Measured uniformly at `n = 12` across all 30 tasks, how many fall strictly inside `0 < bare < 1`,
and does that reach the 8 that preregistration 005's primary endpoint requires?

## Why this exists

Preregistrations 007 and 008 both classify on 4 to 6 observations. At `n = 6`, a task whose true
rate is 0.90 shows 6 successes out of 6 about **53%** of the time, and one at 0.95 about **74%**.
So today's `DAMAGE_ONLY` means "no failure in six", not "cannot fail", and `BENEFIT_ONLY` means "no
success in six". The strata may be reporting **measurement resolution as task structure**.

That matters because only 6 tasks currently sit in `TWO_SIDED` against a threshold of 8, and
preregistration 008 has already established that building new mid-band tasks does not work: one of
six candidates landed there, and 008's frozen text forbids building a seventh to the same rule. If
two of the existing 24 are near-ceiling rather than at ceiling, the constraint dissolves with no
new tasks at all.

⛔ **All 30 tasks at the same `n`, or this is not legitimate.** Preregistration 008 deliberately
calibrated six new tasks at `n = 6` to match the old ones, because more seeds make a task strictly
more likely to show both a success and a failure, and calibrating new tasks at higher resolution
would have let them into `TWO_SIDED` on an easier test. That reasoning binds this record too: a
higher-resolution measurement is only fair if every task faces it.

## Design

`bare` only, all 30 `ts-*` tasks, 12 seeds: **360 sessions**. Model `deepseek/deepseek-v4-flash`,
timeout 600s, `acceptEdits`, VPS2, under the same systemd caps, matching `diagnostic-009` and
recorded in `environment.json`.

**This measurement REPLACES the pilot-derived rates rather than pooling with them.** Pooling
6 old observations with 12 new ones would give a task 18 and reintroduce exactly the unequal-`n`
problem this run exists to remove. The pilots stay in the record as the prior measurement.

`bare` ingests no corpus, so no database and no corpus condition is involved, and the result is
independent of every memory arm.

## Predictions

House prior: thirteen of my seventeen predictions on this benchmark are falsified, all
over-optimistic. These are set low on purpose, and the ones below are deliberately not symmetric
about my intuition.

1. **`TWO_SIDED` reaches at least 8**, i.e. at least 2 of the 24 tasks now at an extreme move
   inside. Point estimate **4 tasks move**, range **2 to 8**. Only two are needed for the
   threshold, which is why I expect this to succeed where designing tasks failed.
2. **Movement is asymmetric, ceiling-side first.** More tasks leave `DAMAGE_ONLY` than
   `BENEFIT_ONLY`, by at least 2 to 1. A near-ceiling task fails occasionally through ordinary
   session variance; a near-floor task succeeding requires getting an unguessable project
   convention right, which is a much rarer event than a slip.
3. **All 6 current `TWO_SIDED` tasks stay `TWO_SIDED`.** This is the apparatus check, not a
   finding: a task measured at 0.50 that comes back 12/12 or 0/12 would mean the screen is reading
   session noise rather than task structure, and both 007 and 008 would need re-reading.
4. **Overall `bare` success stays close to the historical rate.** The pilots measured 62/135 =
   **0.459** pooled over 24 tasks; `midband-001` measured 19/36 = 0.528 over its six. Predict the
   30-task pooled rate lands in **0.40 to 0.55**. Outside that, something about the host, the model
   or the harness has moved and the strata are not comparable with anything published.
5. **Cost under $1.50.** `midband-001` cost $0.0493 for 36 sessions, so 360 sessions arithmetically
   costs about **$0.49**; the house prior of overspending gives the bound.

## Exclusion rules

Admission is unchanged; discarded cells are published with reasons. A task with fewer than 8
admitted observations after discards is reported as **unresolved** and keeps its
preregistration-007 stratum rather than being reclassified on thin evidence.

Retries are triggered by wiring only, never by outcome.

## What happens to each outcome, fixed before the numbers exist

* The `n = 12` stratum **replaces** the 007/008 stratum for every task, and the change is appended
  below both records' markers. The frozen tables are not edited.
* If `TWO_SIDED` reaches 8 or more, preregistration 005's primary endpoint becomes deliverable and
  the abstention suite runs on the tasks this measurement names.
* If it does not, the primary endpoint is reported as underpowered permanently, and I stop trying
  to fix it by measurement or by task construction. Two independent attempts will then have failed,
  and a third would be fishing.
* **No task is dropped, redesigned or re-measured a third time on the basis of where it lands.**

## What would falsify this

- Prediction 1 falsified if fewer than 2 tasks move, which would mean the bimodality is real and
  the `n = 6` strata were not a resolution artefact. That is a genuine and publishable finding
  about agent behaviour, not merely a negative result for the suite.
- Prediction 2 falsified if floor-side movement equals or exceeds ceiling-side.
- Prediction 3 falsified by any current `TWO_SIDED` task coming back at exactly 0 or 12 out of 12.
  The screen would then be measuring noise and this record's own conclusions would not stand.
- The whole measurement is void if `bare`'s pooled rate falls outside 0.40 to 0.55, since `bare`
  ingests nothing and has no reason to move between runs.

## What I already know

Preregistration 007 (pilots, `n` 4 to 6): `TWO_SIDED` 5, `DAMAGE_ONLY` 8, `BENEFIT_ONLY` 11.
Preregistration 008 (`midband-001`, `n = 6`): one of six new candidates landed mid-band, taking the
strata to 6 / 11 / 13. 008 also found that the reliably-wrong conventions are the ones whose
correctness is invisible within a single run (sorted keys, exit codes, idempotency), while
single-run output properties are reliably right. If that determinism is genuine rather than
under-sampled, prediction 1 fails.

<!-- results are appended below this line; everything above is frozen -->
