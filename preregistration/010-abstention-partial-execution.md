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
