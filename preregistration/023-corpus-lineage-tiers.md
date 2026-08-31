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
