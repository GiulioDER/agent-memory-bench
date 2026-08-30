# validation-001: does the repaired instrument discriminate at all?

Status: DRAFT until committed; a committed record is frozen above the results marker.

⚠️ **This is not a product comparison and no arm-level ranking from it will be published.** It
asks whether the benchmark can now measure anything, after a day of repairs made on the strength
of `official-001`'s failure. If the answer is no, that is the finding, and the expensive run does
not happen.

## Question

`official-001` produced 21 cells of evidence from 118, spent 82.2% of its sessions on cells where
every arm agreed, and had an empty `TWO_SIDED` stratum, so it could measure harm and not benefit.
Five tasks were then planted, four retired, and the task set re-selected on measured `bare`
difficulty. **Does a grid built from the repaired task set produce informative cells, a non-empty
`TWO_SIDED` stratum, and any cell at all where a memory arm beats the static baseline?**

## Why `superseded` and not `present`

The `present` condition is the right home for a benefit measurement and is not on master yet.
`superseded` does not need it: it sets `include_real: true`, so the corpus holds the correct fact
**and** a dated stale rival. A memory arm can therefore win a cell `bare` failed (benefit) and be
misled by the stale memo into losing a cell `bare` solved (damage), in the same condition and on
the same task. That is exactly the two-sided measurement `official-001` could not make.

Confirmed for all six tasks below: `include_real=True` and present in the `superseded` selection.

## Arms and configs

| arm | role | config |
|---|---|---|
| `bare` | reference; damage is defined against it | none |
| `claude_md` | baseline; every delta is quoted against it | fixture README bundle |
| `recall` | the memory arm under test | `recall-rag[fastembed,mcp,voyage]==0.11.0`, host transport, strict trust |

Only one memory arm, deliberately. This measures the INSTRUMENT, and a second product would double
the cost while answering the same question. `recall` rather than the undisclosed vendor because
this project owns it and no vendor should appear in a validation whose numbers may be quoted
loosely.

## Grid

Six tasks, chosen because `resolution-001` measured every one of them strictly between 0 and 1
with the memory-free arm, which is the only band where damage and benefit are both expressible:

| task | `bare` from `resolution-001` |
|---|---:|
| `ts-mig-name` | 0.33 |
| `ts-golden-regen` | 0.50 |
| `ts-tz-utc` | 0.75 |
| `ts-bom-merge` | 0.83 |
| `ts-legacy-hash` | 0.83 |
| `ts-manifest-rel` | 0.83 |

One condition (`superseded`), 3 seeds, 3 arms. **18 cells, 54 sessions.** Model
`deepseek/deepseek-v4-flash`, which is what both calibration screens and every prior run used, so
this is comparable to them. Prices `--price-in 0.0574 --price-out 0.1148 --price-as-of
2026-08-22`, matching preregistration 002's frozen protocol.

⚠️ Restricting `--tasks` does **not** shrink the corpus: non-selected tasks keep their sessions,
so the retrieval problem is unchanged and only the grid is smaller.

## Prerequisites, each of which blocks the run

1. `corpus/manifest.json` lists every session on disk. It does not today:
   `sessions/fa-dedup-key/p01.jsonl` is unlisted, so the feed is inconsistent and every adapter
   ingests the wrong set.
2. `recall`'s `bench-*-superseded` tenant rebuilt against the current corpus. The existing one was
   built for the old task selection and `RecallAdapter.ingest` will refuse a fingerprint mismatch,
   which is the guard working.

## Endpoints, in reporting order

1. **Informative-cell fraction.** Cells where the three arms did not all agree, over admitted
   cells. `official-001` measured 21/118 = 0.178 on five arms.
2. **`TWO_SIDED` occupancy.** Tasks whose `bare` rate in THIS run is strictly between 0 and 1.
   `official-001` measured zero, which is what made endpoint 1 of record 014 structurally empty.
3. **Any benefit at all.** Cells where `recall` succeeded and `claude_md` failed. `official-001`
   measured **0 of 118**.
4. **Damage**, `recall` failing a cell `bare` solved, reported beside benefit and never alone.

Search rate is reported per memory arm; below 0.50 the endpoints are not interpretable, per
preregistration 002's floor.

## Predictions

House prior: I over-predict magnitudes by two to four times, and eleven of twelve past predictions
were too high. These are set low deliberately.

1. **Informative-cell fraction rises above 0.40**, against `official-001`'s 0.178. Mechanism
   metric beside it: the number of tasks whose three arms disagree at least once, which I predict
   is at least 4 of 6.
2. **`TWO_SIDED` is non-empty: at least 3 of the 6 tasks land strictly between 0 and 1.** All six
   did on a 12-seed screen, but 3 seeds is coarse and a task at 0.83 collapses to 1.000 whenever
   all three seeds succeed, which happens about 57% of the time by chance alone.
3. **At least one cell where `recall` beats `claude_md`.** `official-001` produced none in 118.
   This is the weakest prediction I am willing to make and the one I would most like to be wrong
   about in the generous direction.
4. **Damage is non-zero.** Between 1 and 4 cells. `superseded` plants a dated stale rival
   precisely to be applied, and an arm that never falls for it would suggest the plants are inert
   rather than that the product is careful.
5. **`recall`'s search rate lands between 0.70 and 0.90**, matching the 0.828 to 0.857 measured in
   `official-001`.
6. **Cost under $0.40** for 54 sessions plus one corpus rebuild.

## Exclusion and truncation rules

A cell is discarded unless every arm proves its treatment was applied, and every discard is
published with its reason. Retries are triggered by wiring only, never by outcome. If the budget
binds, truncate seeds and never tasks. **Six tasks is below the eight-task floor record 011 sets
for reporting a condition as a result**, which is accepted here because this is an instrument
check and not a result, and is the reason no arm-level figure from it may be quoted.

## What would falsify this

- Prediction 1 falsified if the informative fraction stays below 0.25, which would mean the task
  re-selection did not buy dynamic range and the whole day's work did not fix the thing it was
  aimed at.
- Prediction 2 falsified if `TWO_SIDED` is empty again. That would be the strongest possible
  signal that difficulty measured on a 12-seed screen does not survive into a 3-seed grid, and
  that admission needs more seeds rather than better tasks.
- Prediction 3 falsified if `recall` beats `claude_md` in zero cells for a second time. Two runs
  with no benefit anywhere, on tasks specifically chosen to have room for it, stops being a
  property of the grid and starts being a property of the product.
- The run is void if the corpus manifest is inconsistent when it starts, or if `recall`'s tenant
  serves a generation built from a different corpus than the run assembled.

<!-- results are appended below this line; everything above is frozen -->
