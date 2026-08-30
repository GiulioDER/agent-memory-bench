# official-002: the first run of the repaired instrument

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

`official-001` was retracted. It produced 21 informative cells from 118, spent 82.2% of its
sessions on cells where every arm agreed, and its `TWO_SIDED` stratum was empty, so it could
measure damage and not benefit. On 2026-08-30 the instrument was audited and repaired: five tasks
planted, four retired, a verifier that could not fail made able to fail, a headline endpoint that
was dropping half its cells fixed, and two vacuous gates closed.

**Does the repaired instrument produce a populated `TWO_SIDED` stratum, a majority of informative
cells, and a measurable difference between memory arms and the static baseline?**

## What changed since official-001, and why it should matter

| repair | official-001 | now |
|---|---|---|
| tasks with headroom | 1 | 7 declared `TWO_SIDED`, all measured strictly between 0 and 1 |
| four `bare`=1.00 tasks in the grid | yes | retired: `ts-append-only`, `ts-bool-env`, `ts-csv-quote`, `ts-glob-hidden` |
| endpoint 1 denominator | dropped all but one condition | pairs on `(task, seed, condition)` |
| verifier's endpoint check | tautology, accepted `1e300` | compares values at 1e-9 |
| interpretability floor | passed vacuously for an arm with no records | explicit `None`, floor sees it |

## Grid

**46 task-conditions**, from `selection_for` after retirement:

| condition | tasks | `TWO_SIDED` | `DAMAGE_ONLY` | `BENEFIT_ONLY` |
|---|---:|---:|---:|---:|
| `absent` | 12 | 4 | 7 | 1 |
| `superseded` | 11 | 4 | 6 | 1 |
| `contradictory` | 11 | 4 | 7 | 0 |
| `adjacent` | 12 | 4 | 7 | 1 |

**Arms (5):** `bare`, `claude_md`, `placebo`, `recall`, `mempalace`.
`bare` is the reference every delta is quoted against; `claude_md` is the static-context baseline;
`placebo` controls for the instruction rather than the retrieval.

**Seeds: 5, not 3.** This is the one design change I would not compromise on, and it is arithmetic
rather than judgement. A task at `bare` = p stops carrying two-sided information for a run whenever
every seed agrees, with probability `p^k + (1-p)^k`. Over the seven `TWO_SIDED` tasks at their
measured rates:

| seeds | `TWO_SIDED` tasks expected to stay two-sided |
|---:|---:|
| 3 | **3.1 of 7** |
| 5 | 4.3 of 7 |
| 7 | 5.0 of 7 |

`official-001` used 3 seeds and reported an empty `TWO_SIDED` stratum. No amount of task repair
fixes that: at 3 seeds a task measured at 0.83 collapses to 1.000 about 57% of the time. Five seeds
is the cheapest point that leaves the stratum populated in expectation.

**1,150 sessions.** Model `deepseek/deepseek-v4-flash`, the model every prior run and both
calibration screens used, so this is comparable to them. Prices `--price-in 0.0574 --price-out
0.1148 --price-as-of 2026-08-22`, matching preregistration 002.

## Endpoints, in reporting order

Per preregistration 005, unchanged.

1. **Net harm by stratum**, per arm against `bare`, over all admitted paired cells.
2. **Damage rate by condition**, on `DAMAGE_ONLY` tasks.
3. **Abstention rate**, on `absent` and `contradictory`.
4. **Wrong-fact-applied rate**.

Search rate is reported per memory arm under both denominators; below 0.50 on the admitted one the
endpoints are not interpretable.

## Predictions

House prior, recorded because it has been measured: I over-predict effect magnitudes by two to four
times, and eleven of twelve past predictions were too high. These are set low deliberately, and each
names the mechanism metric beside the outcome.

1. **Informative-cell fraction above 0.45**, against official-001's 0.178. Mechanism: at least 12 of
   the 46 task-conditions show at least one arm disagreeing with another.
2. **`TWO_SIDED` is non-empty in every condition**, and at least 3 of the 7 declared tasks land
   strictly between 0 and 1 pooled across conditions.
3. **At least 8 cells where a memory arm succeeds and `claude_md` fails.** official-001 produced
   **0 of 118**. This is the prediction I most expect to be wrong in the pessimistic direction.
4. **Damage is non-zero and below 0.15** for every memory arm. `superseded` and `contradictory`
   plant a rival fact precisely to be applied; an arm that never falls for it suggests the plants
   are inert rather than that the product is careful.
5. **`recall` search rate between 0.75 and 0.95** on the admitted denominator, matching the 0.823 to
   1.000 measured across pilots.
6. **Cost under $4.00.** official-001 measured $1.6986 for 630 sessions, so 1,150 sessions at the
   same rate is about $3.10 plus ingest.

## What would falsify this, and what happens then

- **1 falsified** (informative fraction below 0.30): the task re-selection did not buy dynamic range
  and the repairs did not fix the thing they were aimed at.
- **2 falsified** (`TWO_SIDED` empty again, at 5 seeds): difficulty measured at 12 seeds does not
  survive into a 5-seed grid, and the answer is more seeds rather than more repairs.
- **3 falsified** (zero benefit cells for a second time, on tasks chosen to have room for it): that
  stops being a property of the grid and starts being a property of the products.
- **5 falsified** (search rate below 0.50): the endpoints are void and nothing is reported.

**The run is void** if the corpus manifest is inconsistent when it starts, if any arm's tenant
serves a generation built from a different corpus than the run assembled, or if
`scripts/verify_run.py --all` does not verify this run's own directories afterwards.

## Preconditions, each of which blocks the launch

1. `corpus/manifest.json` lists every session on disk. **Fixed 2026-08-30**: it was missing
   `sessions/fa-dedup-key/p01.jsonl` (195 of 196), which made the feed inconsistent so every
   adapter ingested a different set.
2. `recall`'s four `bench-*` tenants rebuilt against the current corpus. The manifest fix changes
   the corpus fingerprint, so `RecallAdapter.ingest` will refuse the old tenants; that is the guard
   working.
3. MemPalace's wing rebuilt for the same reason.
4. `scripts/launch_official.sh` refuses a run whose paths would name an account in the published
   records. The current host layout is under `/home/sentiment`, so **either the checkout and the
   CLI move under a neutral root, or `AMB_ALLOW_NAMED_PATHS=1` is set deliberately.** This is a
   choice about the artifact, not a bug to route around.

## Deliberately NOT in this run

- **The `present` condition**, which is the right home for a clean benefit measurement, is not on
  master. `superseded` carries `include_real: true`, so benefit is expressible without it.
- **Endpoint 5** (task success per arm per condition), for the same reason.
- **Moving `ts-tz-utc` and `ts-manifest-rel` to `TWO_SIDED`.** Both measure strictly between 0 and 1
  (0.75 and 0.83) while declared `DAMAGE_ONLY`, so this run credits any benefit they show to
  nothing. Correcting it needs an amendment to preregistration 009 committed before the run, and
  changing strata membership on the strength of one run's measurement is the kind of thing that
  should be decided in the open rather than folded into a launch.

<!-- results are appended below this line; everything above is frozen -->
