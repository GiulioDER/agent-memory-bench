# abstention-001 task selection: which tasks can carry which endpoint, fixed before any result

Status: DRAFT until committed; a committed record is frozen above the results marker.

Preregistration 005 requires that "task selection for this suite must screen on `bare` having a
non-trivial success rate, and the screen must be fixed before seeing results". This is that screen.
It is a separate record rather than an edit to 005, because a committed prediction is never edited.

## Disclosure, stated first because it is the weakest part of this record

I had already seen per-task outcome data before writing this screen. Specifically: the
`scripts/task_discrimination.py` table across pilot-003, pilot-004, `diagnostic-009` and
`diagnostic-010`, and then the per-task `bare` rates reproduced below. So this screen was written
by someone who knew the answer, and it should be read with that in mind.

Two things bound the damage:

1. **The rule is derived from the estimand, not from the numbers.** It would be the same rule
   whatever the rates turned out to be, and the derivation is given below without reference to any
   task. What the data determined is only how many tasks satisfy it, which is a fact about the
   suite rather than a choice I made.
2. **No abstention-suite data exists yet.** The screen uses prior runs, none of which measured any
   corpus condition. Nothing here was tuned against the result it will be used to report.

What I cannot claim is that this record was written blind. It was not.

## The rule

The primary endpoint of 005 is net harm:

    P(arm fails AND bare succeeds) - P(arm succeeds AND bare fails)

Its two terms need opposite things from a task. The harm term needs `bare` to succeed, so a task
`bare` never solves contributes zero to it no matter what any memory layer does. The benefit term
needs `bare` to fail, so a task `bare` always solves contributes zero to that one. A task can
therefore carry the primary endpoint only if `bare` sometimes succeeds and sometimes fails.

That gives three strata:

| stratum | `bare` rate `b` | carries |
|---|---|---|
| `TWO_SIDED` | `0 < b < 1` | endpoint 1 (net harm), and everything below |
| `DAMAGE_ONLY` | `b = 1` | endpoint 2 (damage rate), endpoint 4 |
| `BENEFIT_ONLY` | `b = 0` | endpoint 4 only |

Endpoint 4, the wrong-fact-applied rate, needs no `bare` reference at all: it asks whether the
deliverable contains the planted convention, which is knowable by construction. So every task with
a plant carries it, including tasks in `BENEFIT_ONLY`.

"Always" and "never" are estimates from prior runs, not guarantees. A task at 1.00 over six
observations can still fail once in a new run, so the bias from pooling strata is asymptotic rather
than absolute. It is nonetheless one-directional, which is why the strata are reported separately:
pooling them would push net harm positive for a reason that has nothing to do with any memory
layer.

## Which evidence the screen uses

Only runs that carried a real `bare` arm, on `deepseek/deepseek-v4-flash`, the model 005 pins to
`diagnostic-009`: **pilot-003-deepseek** and **pilot-004-placebo**, pooled, over admitted cells
only. `pilot-003-gpt53` is a different model and is printed as a cross-check without being used.
`pilot-001` is excluded because it has no `environment.json`, so its model cannot be confirmed.

A `claude_md` proxy would not do. It is handed the fixture README bundle, so its success rate is a
different quantity from the reference point damage is defined against.

Minimum 4 admitted `bare` observations for a task to be screened at all.

## The measurement, taken 2026-08-27

```bash
python -m scripts.select_abstention_tasks
```

| stratum | n | tasks |
|---|---|---|
| `TWO_SIDED` | **5** | ts-atomic-write (0.50), ts-dedup-order (0.83), ts-golden-regen (0.50), ts-manifest-rel (0.50), ts-mig-name (0.83) |
| `DAMAGE_ONLY` | **8** | ts-append-only, ts-bom-merge, ts-glob-hidden, ts-ignore-gen, ts-legacy-hash, ts-schema-additive, ts-semver-pin, ts-tz-utc (all 1.00) |
| `BENEFIT_ONLY` | **11** | ts-base36-id, ts-casefold-sort, ts-config-layer, ts-crlf-export, ts-empty-input, ts-log-mask, ts-nfc-count, ts-quote-shell, ts-retry-cap, ts-round-money, ts-stable-sort (all 0.00) |

The distribution is bimodal: 19 of 24 tasks sit at exactly 0.00 or exactly 1.00.

### Two robustness checks, run before freezing this

Both were run as mutations against the screen, expecting them to change the answer. Neither did,
and that is worth recording because it bounds how much this record depends on my choices above.

* **Pooling the different-model run changes nothing.** Adding `pilot-003-gpt53` to the evidence
  moves **0 of 24** tasks between strata, so excluding it was the conservative choice rather than
  a load-bearing one. Individual rates do differ (ts-atomic-write 0.50 against 0.00, ts-golden-regen
  0.50 against 0.67), but never across a boundary.
* **Admission discards change one rate and no stratum.** Ignoring them alters `n` for 7 tasks and
  the rate for exactly 1 (ts-atomic-write), while leaving all three strata identical. The rates
  printed above are therefore discard-respecting, and `tests/test_abstention_selection.py` pins the
  five `TWO_SIDED` values so this record cannot drift away from the script that produced it.

## The consequence, which is a result about the benchmark rather than about any product

**Preregistration 005's primary endpoint cannot be delivered at adequate power on the current task
suite.** 005 states that "a condition with fewer than 8 admitted tasks is reported as underpowered
rather than as a result", and only 5 tasks can carry net harm at all. That is before any admission
discard, so 5 is the ceiling rather than the expectation.

What the suite CAN deliver at the preregistered power:

* **Endpoint 2, damage rate per condition**, on the 8 `DAMAGE_ONLY` tasks. This meets the 8-task
  threshold exactly, and it is the more quotable number in any case: how often a memory layer
  breaks something that worked without it.
* **Endpoint 4, wrong-fact-applied rate**, on every task carrying a plant.
* **Endpoint 3, abstention rate**, which depends on the response rather than on `bare`.

## What I will and will not claim when this runs

* I will report net harm on the `TWO_SIDED` stratum and label it **underpowered**, per 005's own
  rule, with its 5-task count stated beside every interval.
* I will report damage rate on `DAMAGE_ONLY` as the suite's headline, since that stratum meets the
  threshold.
* I will **not** pool the strata into a single net harm figure. Pooling is biased positive by
  construction here, and a positive net harm produced by task selection would be indistinguishable
  in the write-up from one produced by a memory layer.
* I will not add, drop or re-stratify a task after seeing abstention results. If a task's `bare`
  rate in the new run contradicts its stratum, that discrepancy is reported and the stratum stands.

## The fix, which is task work rather than analysis

Getting `TWO_SIDED` to 8 needs at least 3 new tasks whose `bare` rate lands strictly inside
(0, 1). That is the same gap `scripts/task_discrimination.py` found from the other direction: the
grid is bimodal and the missing middle is where every interval gets its width. Building those tasks
before running the abstention suite would let the primary endpoint be reported as a result rather
than as a caveat.

I am recording this as the known state rather than treating it as a blocker. Running the suite now
yields endpoints 2, 3 and 4 at full strength and endpoint 1 as an underpowered secondary; that is a
legitimate outcome as long as it is labelled, and this record is what makes labelling it
non-negotiable afterwards.

## What would falsify the screen itself

* If `bare` in the abstention run lands strictly inside (0, 1) for tasks this screen called
  `DAMAGE_ONLY` or `BENEFIT_ONLY` at a rate above roughly 1 task in 4, the prior runs were not
  predictive of `bare` under these conditions and the stratification is measuring run-to-run
  variance rather than task structure. The strata are then void and only endpoint 4 survives.
* If `bare` differs systematically between corpus conditions, something is reaching the `bare` arm
  that should not be. `bare` ingests no corpus, so its rate must be flat across all four
  conditions; that flatness is an apparatus check and its failure voids the whole suite.

<!-- results are appended below this line; everything above is frozen -->

## Update, 2026-08-27: six tasks added, the strata re-counted

`midband-001` (preregistration 008) calibrated six new tasks under the screen frozen above, at the
same `n = 6`, with the same `stratify` function. 36 sessions, 36 admitted, 0 discarded.

| stratum | was | now | added |
|---|---:|---:|---|
| `TWO_SIDED` | 5 | **6** | ts-idempotent-run (0.17) |
| `DAMAGE_ONLY` | 8 | **11** | ts-bool-env, ts-csv-quote, ts-natural-order (all 1.00) |
| `BENEFIT_ONLY` | 11 | **13** | ts-cli-exitcode, ts-json-sorted (both 0.00) |

**The consequence stated above is unchanged: preregistration 005's primary endpoint is still
underpowered.** `TWO_SIDED` is 6 against the threshold of 8, and that is before any admission
discard. One of six candidates landed there, so the rule that produced them does not close the
gap; preregistration 008's frozen text forbids simply building more to the same rule.

What did improve, and it is the stratum carrying the suite's most quotable number: `DAMAGE_ONLY`
was sitting at **exactly** the 8-task threshold, where a single discarded task would have dropped
endpoint 2 under it too. At 11 it has three tasks of headroom.

Nothing above this line was edited. `tests/test_abstention_selection.py` pins the original five
`TWO_SIDED` rates and the count of 5; that count is now stale by design, and the tripwire test
documented there is what forced this section to be written rather than letting the change pass
unnoticed.

## Update, 2026-08-28: re-measured at n = 12, and the strata are now final

`resolution-001` (preregistration 009) re-measured all 30 tasks uniformly at 12 seeds, replacing
the 4-to-6 observation rates above rather than pooling with them. 360 sessions, 348 admitted, 12
discarded to provider connection failures.

| stratum | pilots (n 4-6) | +midband (n=6) | **n = 12, final** |
|---|---:|---:|---:|
| `TWO_SIDED` | 5 | 6 | **7** |
| `DAMAGE_ONLY` | 8 | 11 | **11** |
| `BENEFIT_ONLY` | 11 | 13 | **12** |

`TWO_SIDED` reached 7 against the threshold of 8. Preregistration 009's pre-committed stop rule
therefore applies: **preregistration 005's primary endpoint is underpowered permanently**, and no
third attempt will be made to fill that stratum, by task construction or by measurement.

Two cautions attach to the numbers in that column, both established in 009's result section:

* **Membership at the boundary is noise-sensitive.** ts-dedup-order (0.83 → 12/12) and
  ts-manifest-rel (0.50 → 10/10) left `TWO_SIDED` while ts-bom-merge and ts-legacy-hash entered it.
  A hard in-or-out rule at exactly 0 and 1 will keep reshuffling tasks whose true rate sits near an
  extreme, even though a Fisher test finds only 1 of 30 tasks inconsistent between the two
  measurements, which is what chance predicts at 30 tests.
* **The extremes are not noise-sensitive.** 21 of 30 tasks returned the identical value in both
  measurements, 12 at exactly 0.00 and 9 at exactly 1.00. `DAMAGE_ONLY` rests on that stable
  ground: 9 of its 11 members are hard 1.00 in both.

So the stratum this suite actually reports from, `DAMAGE_ONLY` for endpoint 2, is both above
threshold and stable. The one it cannot report from, `TWO_SIDED` for endpoint 1, is both below
threshold and the least stable part of the grid. Those two facts are the same fact seen twice: a
task only lands in the middle when its rate is near an extreme and the sample was small.
