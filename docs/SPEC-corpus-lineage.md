# Spec — making corpus lineage reachable, and measuring what it is worth

Status: **draft, uncommitted**, 2026-08-31. Not yet preregistered.

## The defect this fixes

official-002 measured recall at **-10 on `contradictory` (p=0.021)** and **-7 on `superseded`**, and
the mechanism is the same in both: recall returns conflicting or outdated documents as
undifferentiated peers, and the agent cannot tell which to trust.

But recall **already has** the machinery to mark them:

| component | what it does |
|---|---|
| `recall/frontmatter.py` | parses `valid_from`, `valid_until`, `supersedes` from Markdown frontmatter |
| `recall/trust.py::_verdict` | returns `ok` / `superseded` / `expired` / `not_yet_valid` |
| `recall/trust.py:9` | a superseded or out-of-window memory **"loses even with a top cosine"** |
| response schema | every hit carries `verdict`, `superseded_by`, `valid_from`, `valid_until` |

Measured across the run: **307 hits, `superseded_by` null on every one, verdict never once
`superseded`.** The layer is inert.

**It is inert because nothing declares lineage.** `harness/transcripts.py::render_corpus` writes
each session as Markdown beginning `# Session notes: <id>` with **no frontmatter at all**. There is
nowhere for `supersedes` to live, so recall's lineage layer is unreachable by construction and the
benchmark reports its absence as a product weakness.

⚠️ **This understates recall in exactly the two conditions the benchmark exists to probe.** That is
a validity defect in the harness, not a finding about the product.

## The constraint that shapes the design

Timestamps alone are **not sufficient**, and this was checked rather than assumed. `_verdict`
returns `superseded` only when a **successor** is present. `valid_from` alone yields `not_yet_valid`
and only for as-of queries; it does not demote a stale hit in an ordinary search.

To mark the stale plant you must know **which document supersedes which**. The raw transcripts do
not carry that. So a corpus change cannot be a pure re-derivation of existing data, and any design
that pretends otherwise is smuggling in an answer.

## Design: three tiers, because the gap between them is the actual result

Each tier is a corpus rendering. The tasks, plants, seeds, arms and grid are unchanged.

### Tier 0 — control (current behaviour)

No frontmatter. Reproduces official-002. Exists so the other two tiers are measured against a
rebuild rather than against a remembered number.

### Tier 1 — timestamps only (realistic)

Emit `valid_from: YYYY-MM-DD` on every rendered session, taken from that transcript's earliest
`ts`, which already exists in every record. **No new information.** This is what any real corpus of
dated transcripts could offer for free.

**Expected to change little**, and that is the point: it establishes what recency alone buys, which
the project currently assumes rather than knows.

### Tier 2 — declared lineage (ceiling)

On `superseded` plants only, emit on the **stale** document:

```yaml
---
valid_from: 2026-02-19
valid_until: 2026-08-06        # the day before its successor's valid_from
---
```

and on the **current** document `supersedes: sessions__<task>__stale_<name>.md`.

This adds information the corpus did not have. It is **deliberately circular for retrieval** and
must never be reported as recall's ordinary performance. It measures a ceiling: *if lineage were
perfectly declared, how much of the superseded harm disappears?*

🔑 **The Tier 2 minus Tier 1 gap is the deliverable.** It is the value of automatic supersession
detection, and therefore whether building such detection is worth anyone's time. Neither tier alone
answers that.

## What each tier can and cannot claim

| | Tier 1 | Tier 2 |
|---|---|---|
| honest as a product number | **yes** | **no** |
| tests a real recall feature | partly (validity window) | yes (supersession) |
| adds information to the corpus | no | yes |
| answers "should we build auto-detection" | no, alone | only against Tier 1 |

## Not covered, deliberately

* **`contradictory` is out of scope.** Its plants are `rival_*` PAIRS with **no authoritative
  version** — neither supersedes the other, and declaring one would invent a fact the condition is
  designed not to have. Contradiction needs conflict *detection*, not lineage, and that is a
  separate spec.
* **The 45% retrieval miss.** Lineage cannot rank a document that was never retrieved. That is the
  formulation gap, measured four ways, generation-side lane closed.
* **Whether recall's reasoning tools would help.** They were exposed and called **zero times** in
  2,181 sessions while `recall_search` took 97.2%. Worth probing separately before building
  anything new.

## Implementation

One function, one call site, and a flag:

1. `harness/transcripts.py::render_transcript` gains an optional `frontmatter: Mapping | None`.
   When present it emits a YAML block before the `# Session notes` heading. Absent, byte-identical
   output to today, so Tier 0 needs no code path of its own.
2. `render_corpus` gains `lineage: "none" | "timestamps" | "declared"`, defaulting to `"none"`.
3. For `"declared"`, the stale/current pairing comes from the plant filenames already in the corpus
   (`stale_*.jsonl` beside `p01.jsonl`), which `scripts/assemble_condition_corpus.py` knows.
4. Dates as `YYYY-MM-DD`, UTC, per `recall/frontmatter.py`.

**A guard is required, not optional:** assert that a Tier 2 render produces at least one hit whose
`verdict == "superseded"` in a smoke search. Without it, a silently unparsed frontmatter block would
reproduce Tier 0 and be reported as "lineage does not help" — the same false-negative shape that has
cost this project a day twice.

## Predictions to register before running

Deliberately low, per the standing over-prediction correction.

1. **Tier 1 changes `superseded` net harm by less than 3 solved cells.** Probability it is
   indistinguishable from Tier 0: **0.75**.
2. **Tier 2 recovers most of the both-plants penalty.** Sessions retrieving both currently solve
   0.56 against 1.00 for current-only; Tier 2 point estimate **0.80** (range 0.65-0.95).
3. **Tier 2 does not reach Tier 0's `current-only` rate of 1.00**, because a demoted hit still
   occupies a slot in the top-5.
4. **Neither tier moves `absent`, `adjacent` or `present`**, which have no supersession relation. If
   one moves, something is wrong with the render rather than right with lineage.

## Cost

Three renders x five conditions x the existing grid. At official-002's measured ~$0.80 per
condition on deepseek, a `superseded`-only comparison across three tiers is **~$2.40**. There is no
reason to re-run the other four conditions except as prediction 4's control, which one condition
can serve.
