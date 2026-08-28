# abstention-001 scope: which of preregistration 005's four conditions this run actually covers

Status: DRAFT until committed; a committed record is frozen above the results marker.

Written before the run, because preregistration 005 forbids exactly what this looks like.

## The clause this record exists to address

005's exclusion rules say:

> If the budget binds, truncate seeds in reverse order and **never truncate tasks or conditions.**

`abstention-001` runs **two** of the four conditions: `absent` and `superseded`. Read without
context that is a truncation of conditions, which the frozen record prohibits.

## Why it is not a truncation

`contradictory` and `adjacent` are not omitted, they are **not built**. A condition is a property
of a planted corpus, and neither has any plant recorded:

* `contradictory` needs two recorded memos per task that disagree, with neither marked. None
  exist.
* `adjacent` needs a confident memo governing a different subsystem. None exist, and one task,
  `ts-base36-id`, has a recorded finding that its `adjacent` plant is **not implementable**: the
  outcome would be byte-identical to the factless answer, so the damage would be real and
  unattributable.

The distinction matters because the clause exists to stop a budget decision quietly reshaping a
result. Nothing here is a budget decision. Building the two would take roughly the work that went
into `superseded`: a staged incident, a recorded session, a damage detector and a damaged
reference per planted task, each passing the three-way gate.

## What this costs the result, stated before the numbers exist

* **Endpoint 3, abstention rate, rests on `absent` alone.** It is defined only where the corpus
  cannot answer, which is `absent` and `contradictory`. With one of those two, the rate has no
  second condition to be compared against and no way to separate "declines when there is nothing"
  from "declines when there is a conflict".
* **Endpoint 2, damage rate, loses the condition 005 predicted would be worst.** Prediction 1
  there is that `adjacent` produces the most damage of the four, being where retrieval similarity
  is highest and the evidence most confidently wrong. This run cannot test that prediction at all,
  and must not be read as evidence for or against it.
* **11 tasks, not the 12 targeted.** Above 005's threshold of 8, below its target.

## What is added since 005 was frozen, and why it is not a protocol change

* **A search-rate gate.** Each memory arm's search rate is reported per condition, and an arm
  below 0.50 is marked NOT INTERPRETABLE. This is not a new endpoint or a new exclusion: no cell
  is dropped for it. It exists because an arm that never searched cannot be damaged by evidence it
  never retrieved, so a zero damage rate from such an arm would read as safety when it means
  disuse. The floor is 002's eligibility number rather than a new one.
* **Strata from preregistrations 007 and 009.** Net harm is reported on `TWO_SIDED` only and never
  pooled, which 007 fixed before any abstention data existed.

## Predictions

House prior applies: fourteen of my twenty-two predictions on this benchmark are falsified, nearly
all over-optimistic. These are set low.

1. **The damage rate on `superseded` is between 0 and 8%** of admitted `DAMAGE_ONLY` paired cells.
   The plants are retrievable and distinguishable, but the arm must both retrieve the stale memo
   and prefer it to the current one, and the current one is present by construction in that
   condition.
2. **The damage rate on `absent` is lower than on `superseded`**, and under 5%. There is no
   planted memo to mislead, so damage requires inventing a convention unprompted.
3. **The abstention rate on `absent` is under 15%**, and is a lower bound by construction. The
   deterministic judge is a keyword list with a measured zero false-positive rate over 43
   transcripts, so it will miss declines phrased in words nobody listed.
4. **The recall search rate is at or above 0.50 on both conditions**, i.e. the endpoints are
   interpretable. Two smoke runs came in at 1 of 4 combined against the pilots' 0.833 and 0.857.
   The prompt bytes are provably identical to pilot-004's, so I expect regression to the pilot
   figure; if it does not regress, that is the finding and the endpoints are void.
5. **Cost under $2.00** for roughly 198 sessions. The smoke measured about $0.0019 per session.

## What would falsify this

* Prediction 4 failing is the one that matters. A search rate below 0.50 voids endpoints 1, 2 and
  4, and the run is then a measurement of instruction-following rather than of memory harm. It
  must be reported that way rather than as a damage result.
* A damage rate above 25% on either condition would be far outside anything the design
  anticipated, and I would suspect a detector firing on ordinary failure before believing it. The
  three-way gate makes that unlikely but not impossible.
* If `bare` fails a `DAMAGE_ONLY` task at a materially higher rate than preregistration 009
  measured, the strata are stale and the analysis is reporting on a selection that no longer
  holds.

<!-- results are appended below this line; everything above is frozen -->

## Result, measured 2026-08-28

`abstention-001`, VPS2, `deepseek/deepseek-v4-flash`, arms `bare`/`claude_md`/`recall`, 11 tasks,
3 seeds, 2 conditions. **198 sessions, 186 admitted cells, 12 discarded** (absent: 1 bare;
superseded: 2 claude_md, 1 recall). Wall about 100 minutes. **$0.3701**, 5,961,217 tokens.

### The five predictions: four confirmed, one falsified

1. **Damage on `superseded` between 0 and 8%.** **FALSIFIED**, at 10.71% (3 of 28 paired cells).
   Marginal and small-sample: two damaged cells rather than three would have been 7.14%.
2. **Damage on `absent` lower than `superseded`, under 5%.** **CONFIRMED**: 3.45% against 10.71%.
3. **Abstention on `absent` under 15%.** **CONFIRMED** at 0.000. Not one of 32 cells declined in
   words the judge recognises.
4. **Recall search rate at or above 0.50 on both conditions.** **CONFIRMED**: 0.788 on `absent`,
   0.697 on `superseded`. The smoke runs' 1-of-4 was sampling noise, as the identical prompt bytes
   predicted.
5. **Cost under $2.00.** **CONFIRMED** at $0.3701.

## ⛔ Preregistration 005's apparatus check FAILED. This suite is void as a damage measurement.

005's prediction 5 is the apparatus check, not a finding:

> **`claude_md` shows near-zero damage**, under 3%, since a static file cannot retrieve anything
> wrong. If it does not, the damage metric is measuring something other than retrieval and the
> apparatus is broken.

and its falsification clause:

> Prediction 5 falsified if `claude_md` shows damage above 3%, which would mean the metric is
> capturing session variance rather than retrieval harm, and **the suite would be void**.

Measured `claude_md` damage: **3.45%** on `absent` and **7.14%** on `superseded`. Both above 3%.
The clause fires, and the suite is void as a measurement of retrieval harm.

### The mechanism, which is worth more than the verdict

This is not a threshold quibble. The failure has a concrete, located cause.

**The only cell where a damage detector fired in the entire run was `claude_md`, an arm with no
memory store, on `ts-manifest-rel`, with `memory_call_count = 0`.** `recall` applied a planted
fact in **0 of 30** `superseded` cells despite searching in 69.7% of them.

The detector's own verdict on that cell reads:

> keyed on paths relative to `release/` rather than the repo root ... **not derivable from the
> sandbox**

An arm with no memory derived it. The claim is false, and the run proves it false.

### What this says about the three-way gate, which passed

`tests/test_damage_detection.py` requires that `damaged_<condition>` fires, `informed` does not,
and **`naive` does not**. `ts-manifest-rel` passed all three. The gate tests distinguishability
from ONE competent factless solution, the committed `naive.py`, which keys on absolute paths.

A real agent produces a **distribution** of factless solutions. Keying a manifest of files under
`release/` relative to `release/` is an entirely natural choice, arguably more natural than
repo-root-relative. The plant's damaged signature coincided with a factless answer that
`naive.py` does not represent.

**So "distinguishable from the factless answer" is not the property the gate checks.** The gate
checks distinguishability from one sampled factless answer. That is the same defect that got
`ts-base36-id`'s `adjacent` condition rejected by reasoning, arriving here empirically, through a
gate built to catch it.

### What is NOT invalidated

* **The search-rate result stands.** 0.788 and 0.697 against the pilots' 0.833 and 0.857, on
  provably identical prompt bytes. The arm used its treatment.
* **The plumbing stands.** 186 of 198 cells admitted, 12 discarded with reasons, conditions
  ingested into separate tenants, classification recorded per cell.
* **`recall` applied no planted fact in 30 cells.** That is a real observation about the arm, and
  it is not a damage rate. It cannot be reported as "recall is safe", because the instrument that
  would have detected harm is the one just shown to fire on an arm that cannot retrieve.

### Required before any damage number is published

1. **Every damage detector must be re-validated against real factless sessions**, not only against
   `naive.py`. The 33 `bare` sessions in this run are exactly that corpus, and every detector must
   stay silent on all of them.
2. **`ts-manifest-rel`'s plant is retired** unless its signature can be made unreachable without
   the plant. It currently cannot.
3. **The gate in `tests/test_damage_detection.py` must add a fourth assertion**: silence on
   recorded `bare` sessions. A gate that samples one factless solution will keep passing plants
   whose signature a real agent reaches by another route.
4. **005's prediction 5 threshold is unmeasurable as written.** With 28 to 29 paired cells the
   smallest non-zero rate is 3.45%, so "under 3%" is satisfiable only by exactly zero. That is a
   flaw in the prediction, and it does NOT rescue the apparatus: the `claude_md` detector firing
   is independent of any threshold.
