# 023 — What declared lineage is worth, and what timestamps alone are worth

Written 2026-08-31, before the render is implemented and before any tier is run.

## The defect

official-002 measured recall at **-7 on `superseded`** and **-10 on `contradictory` (p=0.021)**, with
one shared mechanism: conflicting or outdated documents arrive as undifferentiated peers.

recall already has the machinery to mark them. `recall/frontmatter.py` parses `valid_from`,
`valid_until` and `supersedes`; `recall/trust.py::_verdict` returns `ok | superseded | expired |
not_yet_valid`; and `trust.py:9` states that a superseded or out-of-window memory **"loses even with
a top cosine"**. Every hit in the response carries `verdict` and `superseded_by`.

**Measured across official-002: 307 hits, `superseded_by` null on every one, verdict never once
`superseded`.**

The cause is in the HARNESS, not the product. `harness/transcripts.py::render_corpus` writes each
session as Markdown beginning `# Session notes: <id>` with no frontmatter, and frontmatter is the
only place `supersedes` can live. So the benchmark measures recall with a working feature disabled
by corpus format and reports the result as a product weakness. That understates recall in exactly
the two conditions the benchmark exists to probe.

## The constraint, checked rather than assumed

`_verdict` returns `superseded` **only when a successor is present**. `valid_from` alone yields
`not_yet_valid`, and only for as-of queries; it does not demote a stale hit in an ordinary search.

So marking the stale plant requires knowing WHICH document supersedes which, and the raw transcripts
do not carry that. A corpus change therefore cannot be a pure re-derivation of existing data, and
any design pretending otherwise smuggles in the answer.

## Design

Three renderings of the `superseded` condition. Tasks, plants, seeds, arms and grid unchanged.
Arms: `bare` and `recall`, so each tier yields a paired delta rather than a bare rate.

* **Tier 0 — control.** No frontmatter. Reproduces official-002 as a REBUILD, so the other tiers are
  compared against a fresh measurement rather than a remembered number.
* **Tier 1 — timestamps only.** `valid_from` on every session from its earliest existing `ts`. No
  new information; what any dated corpus offers for free.
* **Tier 2 — declared lineage.** On `superseded` plants only: `valid_until` on the stale document
  ending the day before its successor's `valid_from`, and `supersedes: <stale file>` on the current
  one. This ADDS information the corpus lacked. Deliberately circular for retrieval; a ceiling, not
  a product number.

🔑 **The deliverable is Tier 2 minus Tier 1**, which is the value of automatic supersession
detection and therefore whether building it is worth doing. Neither tier alone answers that.

## Predictions

Deliberately low, per `i-over-predict-effect-magnitudes`: predicted benefits have run 2-4x too high
across twelve registered predictions.

1. **Tier 1 changes `superseded` net harm by fewer than 3 solved cells** versus Tier 0. Probability
   the two are statistically indistinguishable: **0.75**.
2. **Tier 2 lifts the both-plants sessions from 0.56 toward 0.80** (range 0.65-0.95). In
   official-002, sessions retrieving only the current plant solved 19/19 and sessions retrieving
   both solved 0.56.
3. **Tier 2 does not reach 1.00**, because a demoted hit still occupies a slot in the top-5 and the
   agent still reads it.
4. **Tier 2's paired net harm improves by 3 to 8 cells** over Tier 0. Point estimate **+5**.
5. **No tier moves a condition with no supersession relation.** Not tested here directly; if a later
   run shows `absent`, `adjacent` or `present` moving, the render is wrong rather than lineage
   working.

## What would falsify the idea rather than a prediction

* **Tier 2 produces no hit with `verdict == "superseded"`.** Then the frontmatter is not being
  parsed, every tier is secretly Tier 0, and no comparison in this record means anything. A guard
  asserts this BEFORE the grid runs; see below.
* **Tier 2 shows no improvement over Tier 0.** Then supersession marking does not help this agent
  even when perfectly declared, and automatic detection is not worth building at any price.
* **Tier 1 matches Tier 2.** Then timestamps alone suffice and the successor pointer is unnecessary,
  which would contradict the reading of `_verdict` above and should be treated as evidence the
  render is wrong before it is treated as a finding.

## The guard, which is not optional

Before any session runs, a Tier 2 smoke search must return at least one hit with
`verdict == "superseded"`. Without it, a silently unparsed frontmatter block reproduces Tier 0
exactly and would be reported as "lineage does not help" — the same false-negative shape that has
cost this project a day twice today, once through a build reported as failed and once through three
wrong-field reads.

## Out of scope, deliberately

* **`contradictory`.** Its plants are `rival_*` PAIRS with no authoritative version; declaring one
  supersedes the other invents the fact the condition exists to withhold. Conflict needs detection,
  not lineage.
* **The 45% retrieval miss.** Lineage cannot rank a document that never surfaced.
* **recall's reasoning tools**, exposed and called ZERO times in 2,181 sessions while
  `recall_search` took 97.2%. A separate probe.

## Cost

~$0.80 per condition-run on deepseek measured in official-002, three tiers on `superseded` only:
**~$2.40**.

<!-- results are appended below this line; everything above is frozen -->

## Execution note, appended 2026-08-31 before any tier was run

**Tier 1 is DEFERRED, not cancelled. Tier 0 and Tier 2 run first.** The design above is unchanged
and nothing in it is edited; this records only the order in which it is executed.

Reasoning, the user's: Tier 0 and Tier 2 together answer "does declared lineage help at all", and
that is the question worth the compute. Tier 1 earns its own run only if Tier 2 shows an effect; if
the ceiling is flat, timestamps alone cannot move it.

Two consequences that must be stated rather than discovered later:

* **Prediction 1 is unscored for now.** It compares Tier 1 against Tier 0 and no Tier 1 exists yet.
  It is not withdrawn.
* **The "Tier 1 matches Tier 2" falsifier cannot fire in this pass.** That check exists to catch a
  broken render before it is read as a finding, so the Tier 2 `verdict == "superseded"` guard is now
  carrying that load alone, which makes it strictly more load-bearing than when it was written.

Cost of the deferral, measured rather than assumed: `declared` annotates **all 207 sessions** with
`valid_from`, so Tier 2 needs a full embedding pass whatever the order. Tier 1 and Tier 2 differ on
only **22 of 207** documents, so a later Tier 1 is largely served from the content-addressed cache.
Deferring costs nothing and makes the deferred run cheaper.

## Result (2026-09-01)

**Status:** measured. Three tiers, 110 records each, 4,911-document corpus with the scale-25
haystack, 11 tasks, 5 seeds, arms `bare` and `recall`, model `deepseek/deepseek-v4-flash`.

| tier | damage (superseded) | damage-only net | two-sided | benefit | search |
|---|---|---|---|---|---|
| T0 control | 0.1667 (5/30) | +0.100 (5 harmed / 2 helped) | -0.100 | 0/5 | 0.745 |
| T1 timestamps | 0.0667 (2/30) | +0.067 (2/0) | +0.150 | 2/5 | 0.673 |
| T2 declared | 0.0333 (1/30) | -0.067 (1/3) | +0.050 | 3/5 | 0.727 |

### The deliverable, which this record defined as T2 minus T1

```
T0 -> T1  embedding perturbation alone : -0.1000   75% of the total move
T1 -> T2  supersession verdict alone   : -0.0333   25%
T0 -> T2  the T0/T2 pair alone         : -0.1333
```

**The supersession verdict is worth 2 cells to 1 cell out of 30.** One cell. Three quarters of the
apparent improvement is the corpus rewrite perturbing every embedding: Tier 2 writes `valid_from`
onto all 4,911 documents, so it changes every chunk's text and therefore retrieval itself. Direct
evidence on `ts-legacy-hash`: the verdict mix moved `{ok 2, low_confidence 4}` to
`{ok 5, superseded 1}`, and lineage cannot raise a hit's confidence.

**So the answer to whether automatic supersession detection is worth building is: no measurable
case for it.** The deliverable this record defined turns out to be the smallest of the three
differences rather than the largest.

### Predictions scored

* **Prediction 4** ("net harm improves by 3 to 8 cells, point estimate +5"): against T0 the swing is
  **exactly 5 cells**. Against the correct baseline T1 it is **1 cell**, below the registered range.
  Scored as **wrong**, and the near-miss against T0 was measuring the perturbation.
* **Prediction 1** (T1 changes net harm by fewer than 3 cells versus T0, p=0.75 they are
  indistinguishable): T1 moved 3 cells against T0 (5 harmed to 2). **Falsified**, and in the
  direction that matters: the tier registered as adding "no new information" produced the larger
  half of the effect.
* **Prediction 2** (both-plants sessions 0.56 toward 0.80): **not scored**, needs a record-level
  breakdown not computed here.
* **Prediction 3** (Tier 2 does not reach 1.00): consistent, damage 0.0333 not 0.
* **Prediction 5** (no tier moves a condition with no supersession relation): **not tested**, only
  `superseded` was run.

### Significance, stated plainly

Fisher exact, T0 against T2 on 5/30 versus 1/30: **p = 0.1945**. All strata, 10 harmed to 6:
**p = 0.418**. **Nothing here is significant.** At n=30 paired cells the entire effect is four
cells. T1's two-sided net harm is +0.150, the worst of the three tiers, which at n=20 is noise but
is noise pointing the other way.

### The guard held, and two apparatus failures did not reach the result

* The Tier 2 `verdict == "superseded"` guard passed before any session ran: 25 hits, 13 superseded,
  all 25 carrying a real `valid_from` where official-002 had `valid_from=-` on all 307.
* **Two corpora and 94 sessions were discarded** before this result, because a first attempt built
  207-document corpora: `AMB_HAYSTACK` is exported by the caller, the haystack is gitignored, and a
  `git worktree` does not carry it. Every gate stayed green throughout. A reasoning-graph probe run
  for an unrelated question caught it by printing a `diagnostic_count` that did not match.
* A stale sandbox work root made the first t0 grid refuse rather than silently discard 10 cells.

### What this record does not license

The corpus-side lane is closed by this result. The retrieval miss, 45% of `superseded` sessions
where neither plant surfaces and worth roughly three times the lineage term, is not addressed here
and is registered separately as **024**.
