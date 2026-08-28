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

## Result, measured 2026-08-28

`resolution-001`, VPS2, `deepseek/deepseek-v4-flash`, `bare` only, 30 tasks x 12 seeds.
**360 sessions, 348 admitted, 12 discarded.** Wall 259 minutes, **$0.5351**, 5,887,166 tokens.
Pooled `bare` **161/348 = 0.463**.

All 12 discards are `the session did not complete`: provider connection failures, correctly
dropped by `harness/gate.py` rather than scored as task failures. No task fell below 8 admitted
observations, so none is reported unresolved. Lowest was `ts-tz-utc` at 9.

### Strata at n = 12

| stratum | was (n 4 to 6) | now (n = 12) |
|---|---:|---:|
| `TWO_SIDED` | 6 | **7** |
| `DAMAGE_ONLY` | 11 | **11** |
| `BENEFIT_ONLY` | 13 | **12** |

Three tasks moved in, two moved out, for a net of one:

| task | old | new | movement |
|---|---:|---:|---|
| ts-bom-merge | 1.00 | 0.83 | `DAMAGE_ONLY` → `TWO_SIDED` |
| ts-legacy-hash | 1.00 | 0.91 | `DAMAGE_ONLY` → `TWO_SIDED` |
| ts-cli-exitcode | 0.00 | 0.08 | `BENEFIT_ONLY` → `TWO_SIDED` |
| ts-dedup-order | 0.83 | 1.00 | `TWO_SIDED` → `DAMAGE_ONLY` |
| ts-manifest-rel | 0.50 | 1.00 | `TWO_SIDED` → `DAMAGE_ONLY` |

### Scoring: three confirmed, two falsified

1. **`TWO_SIDED` reaches at least 8; 4 tasks move, range 2 to 8.** **FALSIFIED.** It reached 7.
   Three tasks moved in, inside the predicted range, but **I predicted movement in one direction
   only** and two tasks moved out. The net was +1 where I predicted +4.
2. **Ceiling-side movement exceeds floor-side by at least 2 to 1.** **CONFIRMED**, at exactly 2 to
   1: ts-bom-merge and ts-legacy-hash left `DAMAGE_ONLY`, ts-cli-exitcode left `BENEFIT_ONLY`.
3. **All 6 current `TWO_SIDED` tasks stay.** **FALSIFIED.** ts-dedup-order returned 12/12 and
   ts-manifest-rel 10/10. This was the apparatus check, and the clause it triggers is below.
4. **Pooled rate in 0.40 to 0.55.** **CONFIRMED**, at 0.463 against the prior 0.474.
5. **Cost under $1.50.** **CONFIRMED**, at $0.5351.

Running total on this benchmark: 22 predictions, 15 falsified.

### The apparatus clause fired, and here is what the evidence says it actually means

The frozen text says a `TWO_SIDED` task returning 0 or 12 out of 12 means "the screen is measuring
noise and this record's own conclusions would not stand". ts-dedup-order returned exactly 12/12,
so the clause fires and is recorded as firing.

Three diagnostics run afterwards locate the problem more precisely than the clause could:

* **The aggregate is stable.** Pooled `bare` was 0.474 before and 0.463 now, across measurements
  weeks apart. A model or provider shift would move this, and it did not.
* **Per-task, old and new agree.** Fisher exact test per task, old counts against new: **1 of 30**
  is inconsistent at p < 0.05 (ts-manifest-rel, p = 0.0357). With 30 tests, about 1.5 false
  positives are expected by chance, so this is what a stable underlying rate looks like.
* **21 of 30 tasks returned the identical extreme**, 12 at exactly 0.00 and 9 at exactly 1.00,
  across both measurements.

So the measurement is sound and the underlying rates are stable. What is unstable is the
**stratum assignment near the boundary**: a task at a true rate around 0.9 will show 12/12 often,
and the screen's rule is a hard in-or-out test at exactly 0 and 1. The noise is in the RULE, not
in the apparatus.

That distinction is not a way of escaping the clause. Conclusions that depend on exact membership
at the boundary are unsafe, and that includes the count of 7. Conclusions about the 21 tasks
sitting hard at an extreme are solid, because nothing about them moved.

### The stop rule, which was pre-committed and now applies

The frozen text: "If it does not [reach 8], the primary endpoint is reported as underpowered
permanently, and I stop trying to fix it by measurement or by task construction. Two independent
attempts will then have failed, and a third would be fishing."

`TWO_SIDED` reached 7. **Preregistration 005's primary endpoint is underpowered, permanently, and
I am not making a third attempt.** Task construction failed (008: one of six landed) and
higher-resolution measurement failed (this record: net +1). The boundary instability found above
is a further reason not to try again: a third attempt would be chasing a number whose
task-by-task membership moves under resampling even when the rates do not.

### What this leaves standing, which is more than it sounds

* **`DAMAGE_ONLY` at 11** against a threshold of 8, and **9 of those 11 returned exactly 1.00 in
  both measurements**. Endpoint 2, the damage rate, is deliverable on stable ground. It is also the
  more quotable number: how often a memory layer breaks something that worked without it.
* **Endpoints 3 and 4** never depended on `bare` at all.
* **The suite is bimodal, and that is now measured rather than suspected.** 21 of 30 tasks are
  effectively deterministic under this model. Preregistration 008 found the same shape in six new
  tasks designed against it. That is a finding about how coding agents follow conventions, and it
  is worth reporting in its own right rather than as a failed attempt to fill a stratum.

## Correction, 2026-08-28: the Fisher defence above is underpowered and is withdrawn

Raised by the adversarial audit running on `claude/audit-fixes`, verified here before accepting.

The result section above defends the apparatus by reporting that "1 of 30 is inconsistent at
p < 0.05 ... this is what a stable underlying rate looks like". **That test has almost no power
against the alternative it was invoked to rule out**, so its passing says far less than I implied.

Fisher exact, two-sided, for a task measured 6/6 in the pilots against `k`/12 here:

| new | rate | p | rejects at 0.05 |
|---|---:|---:|---|
| 12/12 | 1.00 | 1.0000 | no |
| 10/12 | 0.83 | 0.5294 | no |
| 8/12 | 0.67 | 0.2451 | no |
| 7/12 | 0.58 | 0.1141 | no |
| 6/12 | 0.50 | 0.0537 | no |
| 5/12 | 0.42 | 0.0377 | **yes** |

A task whose true rate is anywhere from about 0.45 to 1.00 cannot be distinguished from a hard
ceiling by this test. That range is precisely where a "near-ceiling rather than at ceiling" task
lives, which is the entire hypothesis this run existed to test. Finding only one inconsistency was
therefore close to guaranteed whether or not the rates are stable, and it is not evidence that
they are.

Reproduce with `comb`-based Fisher over `(6, 0, k, 12 - k)`; no library needed.

### What survives, and what does not

* **Withdrawn**: "So the measurement is sound and the underlying rates are stable." The data are
  *consistent with* stable rates. They do not establish it, because the test used could not have
  detected instability of the size that matters.
* **Stands**: the pooled rate held at 0.474 against 0.463 across measurements weeks apart. That is
  a real check on model or provider drift, though it is an aggregate and says nothing about any
  individual task.
* **Stands**: 21 of 30 tasks returned the identical extreme, 12 at exactly 0.00 and 9 at exactly
  1.00. This is a direct observation rather than a hypothesis test, so the power argument does not
  touch it, and it is what the bimodality claim actually rests on.

### The internal tension the audit also named, and how it resolves

This record calls the count of 7 unsafe for resting on boundary membership, and then fires a
permanent stop rule whose trigger is that same count. Both cannot be fully load-bearing.

They resolve by separating two different claims, and only one was ever pre-committed:

* **The stop rule stands.** It is a commitment about my own behaviour, written before the number
  existed, and its purpose is to prevent a third attempt chosen because the first two failed. That
  reasoning does not depend on 7 being exactly right. Two independent routes were tried and a
  third would be fishing.
* **The inference does NOT stand.** This record must not be read as showing the task suite is
  demonstrably incapable of reaching 8 two-sided tasks. It shows that two attempts did not reach
  it and that I stopped. Anything published from this suite must say it that way.

Endpoint 2 is unaffected: `DAMAGE_ONLY` has 11 members, 9 of them hard 1.00 in both measurements,
so it clears the threshold on direct observation rather than on any test whose power is in
question.
