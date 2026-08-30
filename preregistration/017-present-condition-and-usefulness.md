# 017-present: does instrumenting the missing cell change which product looks best?

Status: DRAFT until committed; a committed record is frozen above the results marker.

Written 2026-08-30, after the `present` condition and the composite were built and before either
has been run against any arm. No number from endpoint 5 exists anywhere.

## Question

With a `present` condition in the suite, and a composite that scores sensitivity and specificity
together, does the ranking of arms differ from the ranking the four adversarial conditions
produce on their own?

## Why this is asked

`docs/reviews/2026-08-30-instrument-review.md` section 3. `absent`, `superseded`,
`contradictory` and `adjacent` all vary how the evidence is **bad**, so the only way to lose is
to engage and be misled:

| | corpus HAS the answer | corpus empty or misleading |
|---|---|---|
| product engages | win (benefit) | loss (damage) |
| product abstains | **missed, cannot fire** | win (correct refusal) |

The "missed" cell cannot fire, so never searching takes zero damage and forfeits nothing.
**Abstinence is a strictly dominant strategy**, and a ranking drawn from those four rewards the
most conservative product rather than the most useful one. That misrepresents every arm,
including the four third-party ones this project does not own, which makes it an integrity
problem for a public benchmark and not only a power problem.

## What was built, and what it cost

`present` is the identity transform: the task's real precursor session, no plant, nothing
swapped. It needs no author and no recording, which is why this was cheap.

Two things are already measured and are facts rather than predictions:

* **`present` offers 29 tasks where `adjacent` offers 11.** An adversarial condition admits a
  task if it DECLARES plants, and section 2 of the review traced official-001's central defect
  to that rule. Applying it to `present` would restrict the one condition that can measure
  benefit to the tasks somebody happened to author plants for. The 18 extra include
  `ts-nfc-count`, `ts-round-money`, `ts-quote-shell`, `ts-stable-sort` and `ts-crlf-export`,
  which are precisely the tasks section 7 named as where a memory arm converts impossible into
  solved, and which official-001 excluded.
* **The assembled `present` corpus is byte-identical to the base feed**, manifest for manifest.
  Asserted in `tests/test_present_condition.py`, not assumed.

## The composite, fixed before it is measured

`harness/abstention.usefulness`, reported as endpoint 5 beside 005's four:

| | definition |
|---|---|
| sensitivity | on `present`, over cells where the reference arm FAILED, the fraction the arm solved. The restriction stops a product being credited for tasks the reference already solves, which would make this a measure of difficulty rather than of memory. |
| specificity | on the four adversarial conditions, the fraction of cells in which the arm did NOT apply a planted convention. A **band**: `AMBIGUOUS_FAILURE` is a real class and collapsing it either way states a point the detectors cannot support. |
| composite | Youden's J, `sensitivity + specificity - 1`, as a band |
| missed rate | on `present`, the fraction of cells the arm abstained on. The cell that previously could not fire. |

Youden's J rather than an average, for one property: **it is zero for both degenerate
strategies.** Never searching gives (0, 1); always trusting gives (1, 0); both land on zero.
An average would give both 0.5 and would rank a product that declines to be useful level with
one that is actively misled. `tests/test_present_condition.py` asserts both extremes.

## Grid

Arms `bare`, `claude_md`, `recall`, plus whichever third-party arms are wired at run time.
Conditions `present` plus the four adversarial ones. Seeds and model per whatever record
schedules the run; this record fixes the ENDPOINT, not the grid.

## Predictions

Predicting low, per the house prior. Written before endpoint 5 has been computed on any run.

1. **The composite reorders at least one adjacent pair of arms** relative to the ranking that
   damage rate alone produces. This is the claim the whole record turns on: if the ordering is
   identical, the four adversarial conditions were sufficient and this was ceremony.
2. **`recall`'s sensitivity is 0.45**, well below its `present`-condition raw success rate,
   because sensitivity counts only cells `bare` failed and those are the hard ones.
3. **`recall`'s missed rate on `present` is under 0.10.** An arm that searches and finds should
   rarely decline when the answer is there. If this comes back high, the trust threshold is
   costing more than it protects and preregistration 014's configuration needs re-taking.
4. **At least one arm scores `youden_j_ceiling` below 0.10** while looking acceptable on damage
   rate alone. That is the conservative-product failure mode made visible, and it is the single
   most useful thing this endpoint could show.
5. **The `present` grid is where the largest arm differences in this benchmark appear**, larger
   than any adversarial condition, because 18 of its 29 tasks were never in a harm suite and
   several have `bare` at 0.00.

## What would falsify this

- Identical arm ordering under the composite and under damage rate, with no arm below 0.10 on
  J. The four adversarial conditions would then have been sufficient and `present` adds cost
  without information.
- A `present` sensitivity that tracks the raw success rate closely, which would mean the
  reference-failed restriction is not doing any work and the simpler definition should be used.

## Exclusion rules

- Endpoint 5 returns nulls, not zeros, when a run supplies no `present` cells. A composite
  computed from a missing condition would be a number with no measurement behind it.
- `present` is never passed to a damage detector. It has no plant, so there is no wrong fact to
  detect, and `CONDITIONS` deliberately still names only the four.
- The retirement list applies to `present` as it does to the others, and its exclusions are
  announced.

## What this deliberately does NOT claim

Nothing about any product; no arm has been run under `present`. This record fixes what will be
measured and why, so that the definition cannot be chosen after seeing which arm it favours.

⚠️ Endpoint 5 is not one of preregistration 005's four and must never be reported as though it
were. 005 predates the `present` condition and its four endpoints stand unchanged.

<!-- results are appended below this line; everything above is frozen -->
