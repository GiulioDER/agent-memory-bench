# 025: does naming `recall_evidence` instead of `recall_search` convert an ignored gate into a working one?

Status: DRAFT until committed; a committed record is frozen above the results marker.

**Date:** 2026-09-01

Written before the instruction variant exists and before any session runs.

## Question

On the `superseded`, `contradictory` and `present` conditions, does instructing the recall arm to
consult memory with **`recall_evidence`** rather than **`recall_search`** reduce the share of
sessions in which a non-current or rival plant reaches the agent, and what does that enforcement
cost on the condition where the answer is genuinely present?

## Why this, and why it is not one of the closed lanes

Three separate measurements in this project say the same thing, and nothing has yet acted on it:

| observation | where |
|---|---|
| `abstained: true` ships alongside five hits and **zero agents in 686 responses acted on it**, on three models | `no-agent-abstains-across-three-models` |
| `verdict: superseded` arrives on 3 of 5 hits in `superseded` and the agent answers from them anyway | `graph-reasoning-cannot-move-superseded` |
| the arm's own appendix explains the verdicts in prose, and the prose changed nothing measurable | `the-recall-arm-runs-in-a-degraded-configuration` |

**Every gate recall has is advisory, and the agent ignores all of them.** The bench's own memo
states the conclusion without testing it: a gate the consumer ignores is not a gate, and to change
behaviour it has to change what comes back rather than annotate it.

`recall_evidence` already does exactly that, and it already ships. Read from
`recall_mcp/server.py` at the pinned version, its contract is *"It returns only passages the trust
layer cleared"* and *"When `decision` is `abstain` the bundle is EMPTY"*. It is on this arm's
allow-list. It took **14 of 544 tool calls in official-002 against `recall_search`'s 529**, because
the frozen instruction interpolates one tool name and that name is `recall_search`
(`adapters/recall/config.frozen.json` `instruction`, rendered by `adapters/recall/adapter.py`
`_write_prompt_at` as `{prefix}recall_search`).

This is not the lineage lane and not the graph lane. Both of those changed the CORPUS. This changes
which shipped surface the agent is pointed at, and rebuilds nothing.

### What sizes the prize

From official-002's `superseded` decomposition, recall arm:

| what recall surfaced | sessions | solved |
|---|---:|---:|
| current plant only | 19 (36%) | **1.00** |
| both plants | 9 (17%) | 0.56 |
| stale only | 1 | 0.00 |
| neither | 24 (45%) | 0.46 |

And from `recall-lineage-fields-are-unpopulated`: of 307 hits across 53 `superseded` sessions,
**147 carried `low_confidence`** and every one of them reached the agent as text.

On `bench-lineage-t2-superseded` the enforcement was observed directly and is the reason this
record exists: the query "timezone dubai local timestamps" returns 5 hits of which 3 carry
`verdict: superseded`, while `trusted_evidence.items` contains **exactly 2, both `verdict: ok`,
both the current plant** (`graph-reasoning-cannot-move-superseded`). The mechanism that fixes the
both-plants stratum is already built, already certified, and the agent has never been sent to it.

🔑 That also reframes `lineage-tier-result-t0-vs-t2`, which measured declared lineage at **1 cell of
30**. The lineage was declared into a path the agent does not take. This record tests whether the
path, not the annotation, was the binding constraint.

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `recall` (treatment and baseline) | `ae92863ce399c46766c5b9cc566bee6cf22e39a416c8f53af5892cb7f7220a6d` | `recall-rag[fastembed,mcp,voyage]==0.11.0`, `strict` trust, `voyage:voyage-4`, reranker OFF |
| `bare` | n/a | pairing baseline |

`adapters/recall/instruction_appendix.md` sha256
`9a3fa555e41d236a155c7d4038f173189b2fb41590ab122a29435bc35d71d895`. Repo at `bb25d34`.

**The only variable is the instruction.** The adapter config, the corpus, the generation, the
embedder, the trust mode and the allow-list are unchanged, and `recall_evidence` is already on that
allow-list, so nothing about the arm's capability changes. What changes is which tool the one-line
instruction names.

## Grid

- Corpus: **`bench-lineage-t2-superseded`** (declared lineage, 4,911 documents, scale-25 haystack),
  because that is where the trust layer has successors to act on and therefore where the mechanism
  is live. A t0 replication is a secondary and is explicitly NOT part of the primary.
- Conditions: `superseded` (benefit), `contradictory` (the harm this may not fix), `present` (the
  cost of enforcement).
- Arms: `bare`, `recall`. Seeds: 5. Model: `deepseek/deepseek-v4-flash`. Timeout 600s.
- Two instruction variants of the recall arm: the existing `skill` (baseline) and a new `evidence`
  variant.

⚠️ **The `evidence` variant does not exist.** `scripts/pilot.py`'s `--memory-instruction` takes
`("oneliner", "skill", "protocol")` only. Writing it is part of this work and its content is frozen
here: the same one-liner with the tool name changed, plus one sentence stating that an empty bundle
means answer that you do not know. No other wording moves, or the run measures prompt engineering
instead of enforcement.

## Endpoints, in reporting order

1. **Primary, mechanism: both-plant share.** Denominator: recall-arm `superseded` sessions that
   issued at least one memory call. Numerator: those in which BOTH the current and the stale plant's
   fact terms reach the agent, by `harness.reached`'s content signal.
2. **Primary, cost: task success on `present`**, recall against bare, per-task cluster bootstrap CI.
3. Task success on `superseded`, recall against bare, same CI.
4. Rival-dose distribution on `contradictory` (none / one / both), and damage rate.
5. Compliance: share of memory calls that are `recall_evidence` rather than `recall_search`.
6. Retrieved-text tokens per session, and cost per admitted cell.

`harness/reached.py` keys on the **tool prefix** `mcp__recall__`, not on a tool name, and scores by
CONTENT, so the existing instrument reads both variants without modification. That is asserted, not
assumed: see the apparatus checks.

## Predictions

Deliberately low. `i-over-predict-effect-magnitudes` stands at twelve of thirteen registered
predictions too high by two to four times, and its instruction is to predict a quarter to a half of
the ceiling and to predict the mechanism metric beside the outcome.

1. **Both-plant share falls from 0.17 to 0.08** (range 0.05 to 0.14). Probability it moves in the
   predicted direction at all: **0.70**.
2. **Task success on `superseded` rises by +3 points** (range -2 to +8). Probability the CI excludes
   zero at this n: **0.15**. Registered as probably underpowered.
3. **`contradictory` does NOT improve.** Both-rivals share unchanged within ±0.05 and damage rate
   unchanged within ±0.05. Probability: **0.65**. The bundle has no authority to choose between two
   rivals with no successor, so the trust layer has nothing to strip. **This prediction is the one
   that decides whether conflict detection is worth building**, and I am registering the expectation
   that it is.
4. **Compliance above 0.80** of memory calls using the named tool. Below 0.50 and endpoints 1 to 4
   mean nothing.
5. **Retrieved-text tokens per session fall by 30%** (range 10% to 50%), because a cleared bundle is
   narrower than five ranked hits.

## The prediction I most expect to be wrong, stated now

**Enforcement costs more on `present` than it wins on `superseded`.**

`recall-abstention-is-calibrated-out-of-distribution` measured, on this corpus family, tool-level
abstention of **0.195 when the fact was planted against 0.048 when it was stripped**: four times
more abstention when the answer exists. An empty bundle on abstain is exactly the mechanism that
converts that inversion from a harmless annotation into a withheld answer. `present` is also the
condition where recall's only large win lives, +27 paired wins at p<0.001.

So I predict **`present` success falls by 0 to 8 points**, at probability **0.50**, and I am
registering that a fall at the top of that range makes enforcement a net loss on this corpus and
closes the lane here rather than after a wider run.

The reason to run it anyway is that the inversion is corpus-specific: the production corpus shows
the correct direction (0.14 abstention where the memo was retrievable against 0.23 where it was
not, Fisher p=0.689), and this benchmark's 4,704 adversarially-generated haystack documents are the
suspected cause. A result here bounds enforcement's cost under the worst calibration this project
has measured.

## What would falsify this

- **Compliance below 0.50.** The instruction was not followed; the record is about prompt compliance
  and nothing about enforcement is learned.
- **Both-plant share unchanged.** The trust layer does not strip in the agent's query distribution
  the way it did in the six hand-issued probe queries, and the enforcement idea fails at its
  mechanism rather than at its outcome.
- **Both-plant share falls while `superseded` success does not.** The both-plants penalty measured
  at 1.00 against 0.56 was not causal, and the 45% neither-plant miss is the only term that matters.
- **`present` falls by more than `superseded` rises.** Enforcement is a net loss under this
  calibration, and the next move is the calibration, not the tool.

## Exclusion and truncation rules

- The frozen admission gate applies unchanged. Cells failing admission are discarded and counted in
  the published discard accounting, prominently, per `pilot-004-discard-accounting-correction`.
- Budget truncation removes **seeds, never tasks or conditions**. If credit runs short the order of
  removal is seed 5, then seed 4, then `contradictory` in full, and `contradictory`'s removal voids
  prediction 3 rather than reporting it at reduced n.
- A cell whose MCP server did not answer is retried once per `mcp-startup-race-is-a-transient`, then
  discarded.

## Apparatus verification, before any session runs

Three checks, because predicting the outcome does not reveal a broken harness and this project has
paid for that twice.

1. **The rendered `prompt.md` differs** between the `skill` and `evidence` variants and names
   `recall_evidence`. Assert on the written file, not on the config.
2. **`harness.reached` scores an `recall_evidence` transcript.** Take one recorded evidence-tool
   response, run it through `reached_by_content`, and confirm a non-zero score on a session whose
   plant is known present. If the bundle's text lands in a transcript field the extractor does not
   read, every mechanism endpoint reads zero and the run fabricates the predicted direction on
   endpoint 1 while destroying endpoints 2 and 3. This is the `a-null-is-the-cheapest-result-to-
   fabricate` shape and it is the check most likely to matter.
3. **Positive control on the strip.** Re-issue the recorded probe query against
   `bench-lineage-t2-superseded` through both tools and confirm `recall_search` returns a
   `verdict: superseded` hit that the evidence bundle omits. If it does not, the mechanism is absent
   on this generation and the run is cancelled before it is paid for.

## What I already know

- `no-agent-abstains-across-three-models`, `graph-reasoning-cannot-move-superseded`,
  `recall-lineage-fields-are-unpopulated`, `official-002-two-sided-result`,
  `lineage-tier-result-t0-vs-t2`, `recall-abstention-is-calibrated-out-of-distribution`.
- Closed lanes this must not re-open: memo rewriting (0 of 14, twice), LLM query expansion (3 of
  15), fusion-weight gating (zero viable points), threshold recalibration (no knee), per-write
  automatic search (killed on base rate), declaring lineage (1 cell of 30), all three graph
  mechanisms (inert, corpus has 0 relations).

## Confounds I can name now

- **The `evidence` one-liner is a different string, not only a different tool name.** Any wording
  change beyond the tool name and the empty-bundle sentence confounds enforcement with instruction
  strength, which `001-skill-instruction` showed is a large effect on its own.
- **`recall_evidence` returns a fixed system instruction and a delimited data message**, a different
  shape from ranked hits. A success change could come from the FORMAT rather than the filtering.
  Endpoint 1 separates them: filtering predicts the both-plant share moves, format alone does not.
- **`present` is roughly 2.5x the session count of the other conditions** (27 tasks against 11 to
  12), so its CI will be tighter and must not be read as a stronger effect.
- The corpus feed changed on 2026-08-29, so no number here may be differenced against `pilot-003` or
  `pilot-004`.

<!-- results are appended below this line; everything above is frozen -->
