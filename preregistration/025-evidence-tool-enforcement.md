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

## Amendment 1 (2026-09-01, before any session runs)

Nothing above this line is edited. Two design facts were found while building the variant, and the
user chose the corpus. Both are recorded here because a prediction that moves after the fact is not
a prediction, and this moves BEFORE.

### 1. The baseline is `protocol`, not `skill`. The record's choice was not buildable.

The frozen text says the two variants are "the existing `skill` (baseline) and a new `evidence`
variant", differing by the tool name and one sentence, with "no other wording moves".

**Those two requirements cannot both hold.** `adapters/recall/skill.md` is the provenance anchor for
`pilot-002` through `pilot-004`, its sha256 is pinned by `tests/test_recall_instruction.py`, and it
names `recall_search` in its own prose. Varying the tool against it means editing the anchor, which
`test_the_skill_still_matches_the_one_pilot_004_ran` exists to prevent.

So the baseline is `protocol`, and `evidence` is `protocol` with the one sentence filling
`{search_instruction}` replaced. **That is a cleaner contrast than the one registered**, not a
weaker one: the two arms are now byte-identical apart from a single sentence, `assert_shared_protocol`
covers the protocol half, and `tests/test_evidence_instruction.py` covers the sentence half, which
that assertion is structurally blind to because it substitutes the sentence out before comparing.
Mutation-tested three ways, including one mutation that passes `assert_shared_protocol` and is caught
only by the new test.

### 2. The corpus is `bench-official-002`, not `bench-lineage-t2-superseded`.

The user's decision, taken on cost. A `protocol` recall arm on `present`, `superseded` and
`contradictory` at 5 seeds, on `deepseek/deepseek-v4-flash` at the same frozen prices, is being
produced right now by an unrelated live run, so the baseline is contemporaneous and free and this
record's run is one arm rather than two.

⚠️ **What that costs, stated before measuring rather than after.** `bench-official-002` declares no
lineage. No document has a successor, so `_verdict` can never return `superseded`, and the strip
that was directly observed on `bench-lineage-t2-superseded` (5 hits returned, 3 marked superseded,
`trusted_evidence.items` holding only the 2 current ones) **cannot occur here**. What remains is the
`low_confidence` filter, which is real and large (147 of 307 hits in official-002's `superseded`
condition) but is the weaker half of the mechanism.

🔑 **Therefore a null on this run does NOT close the enforcement lane**, and must not be reported as
if it did. It closes only the low-confidence-filter half. The lineage-t2 form stays unrun and its
prize is undiminished by anything measured here.

### 3. New predictions for the corpus actually being run

The frozen predictions were written for t2 and stand as written. These are additional, made now:

1b. **Both-plant share falls from 0.17 to 0.13** (range 0.10 to 0.17), less than half the frozen
    prediction's move, because only the low-confidence filter is available. Probability it moves in
    the predicted direction at all: **0.55**, down from 0.70.
3b. Prediction 3 (`contradictory` does not improve) is UNCHANGED and if anything strengthened: with
    no lineage the bundle has even less basis to choose between rivals. Probability **0.75**.
5b. **The bundle omits at least one returned hit in more than 0.30 of calls.** If it omits nothing,
    the treatment is inert on this corpus and every other endpoint is uninterpretable.

### 4. The apparatus check that had to change, and it is now the binding one

Frozen check 3 was a positive control on the supersession strip. It is impossible on this corpus, so
it is replaced, not dropped:

> Re-issue a recorded query against the run's own tenant and generation through both tools, and
> confirm the evidence bundle omits at least one hit that `recall_search` returns. **If the bundle
> equals the hits on every probe query, the mechanism is absent on this corpus and the run is
> cancelled before it is paid for.**

Frozen checks 1 and 2 are unchanged and still apply.

### 5. A name collision worth recording

A live run on the serving host carries `--run-id protocol-025` and writes to `results/protocol-025-*`.
It is an unrelated experiment: the shared-protocol fairness grid, arms `bare,protocol,recall,mempalace`,
`--memory-instruction protocol`, five conditions. **It is not this record**, no preregistration 025
exists on that checkout or on any branch but this one, and a later reader who joins the two by number
will be wrong. This record's run will carry a run id naming the treatment rather than the number.

### 6. A confound apparatus check 1 found, and the direction it runs in

The rendered `evidence` prompt still contains the string `recall_search` **once**: in the heading of
`adapters/recall/instruction_appendix.md`, *"## Reading a `recall_search` result"*. The appendix body
describes the verdict vocabulary (`ok`, `superseded`, `low_confidence`, abstention), which applies to
both tools, since `recall_evidence` filters on exactly those verdicts.

**The appendix is held BYTE-IDENTICAL across the two arms** rather than rewritten for the treatment,
because rewriting it would move a second thing and the record's whole constraint is that one sentence
moves. Verified: the two rendered prompts have the same line count and differ on exactly one line.

⚠️ **It is still a confound and it runs AGAINST the treatment.** The evidence arm is pointed at
`recall_evidence` by its instruction and handed a schema note headed with the other tool's name, which
can only push compliance (prediction 4) down. That is the conservative direction: it makes the
treatment harder to detect, not easier, so a positive result is not explained by it and a null is
partly attributable to it. If compliance lands below 0.50, this heading is the first thing to suspect
and the rerun should vary the appendix heading alone.

### 7. Pre-run apparatus measurement (2026-09-01, from already-recorded data, no credit spent)

Prediction 5b asks whether the bundle withholds anything on a corpus with no lineage. That is
answerable for free from the baseline run's own recorded `recall_search` responses, without driving
the server, because a hit the trust layer did not clear is a hit the bundle drops.

Across the three completed conditions of the contemporaneous `protocol` run, recall arm, **235
recall_search calls, 1,176 hits**:

| | count | share |
|---|---:|---:|
| hits `ok` | 802 | 0.682 |
| hits `low_confidence` | 374 | **0.318** |
| calls returning at least one non-`ok` hit | 123 / 235 | **0.523** |
| calls flagged `abstained` | 35 / 235 | 0.149 |

**Prediction 5b stands exactly as written and is now expected to pass comfortably.** It is not
revised: recording that a registered floor looks safe is a fact about the prediction, and moving the
floor after seeing the data would make it worthless. The number that matters for the cancel
condition is 0.523 against a registered floor of 0.30.

Two things this also settles before the run rather than after:

* **The treatment is not inert here.** The `low_confidence` filter alone touches half of all calls,
  so the evidence arm and the protocol arm will genuinely receive different text. The worry recorded
  in Amendment 1 section 2, that this corpus might reduce the contrast to nothing, is answered.
* **Roughly one call in seven returns an empty bundle**, which is the enforcement mechanism firing
  at full strength. That is the cost side of the frozen "most expect to be wrong" prediction, and
  0.149 is now its measured base rate rather than a guess.

⚠️ It does NOT settle that the bundle's field layout is what the checker expects. That is still
apparatus check 3's job against a live server, and the checker discovers the field rather than
assuming it, having already been wrong once this session about a record field it guessed.

### 8. Attempt 1 aborted on the apparatus, 2026-09-01, $0 spent

`evidence-tool-001` launched at 14:44:23Z and exited 1 at 14:47:21Z with **every cell discarded**:
55, 135 and 55 cells across the three conditions, both arms equally, `admitted cells 0`, estimated
spend `$0.0`.

**Cause: `claude` is not on PATH in a non-interactive shell** (it lives under the user's npm prefix).
`scripts/launch_official.sh` exports that PATH and then checks `command -v claude`; the queue script
deliberately does not use that launcher, and its first version copied the launcher's REFUSALS while
dropping its environment setup. The check that was dropped is the one that catches the export that
was dropped. Both are now in `scripts/queue_evidence.sh`.

⚠️ **Nothing about the treatment was measured and nothing may be inferred from it.** Both arms
discarded identically, which is the signature of an environmental failure rather than a treatment
defect. The admission gate did exactly its job: it refused to score sessions that never ran.

**Apparatus checks 1 and 3 both PASSED before that launch, and check 3's result stands as a
measurement**, taken against the live server on `bench-official-002-superseded` with 12 real agent
queries harvested from the baseline run's records:

| | value |
|---|---:|
| queries where the bundle withheld at least one returned hit | **8 / 12 = 0.667** |
| queries where the bundle was empty (`decision: abstain`) | 2 / 12 |
| registered floor (prediction 5b) | 0.30 |

Observed shapes included `5 hits -> 3 items`, `5 hits -> 0 items (abstain)` and `5 hits -> 5 items`.
So the registered CANCEL condition does not fire: the treatment is live on this corpus and the two
arms genuinely receive different text.

🔑 **One field name is now verified rather than assumed.** `recall_evidence` returns its cleared
passages under a top-level **`items`** key, alongside `decision`, `trust_state`, `system_prompt` and
`user_message`. Section 7 said this was unverified; it is verified now, read off a live response.

### 9. Restart procedure, prepared 2026-09-01

The queue was removed from the host at the user's instruction while `official-003` was still
running. Nothing is pending and nothing is half-done. To restart:

On the serving host, whose alias this repository does not carry (see `.gitignore`'s first three
lines), run:

```bash
cd ~ && setsid nohup bash ~/amb-evidence/scripts/queue_evidence.sh \
  > ~/amb-evidence/results/logs/queue-boot.log 2>&1 < /dev/null &
```

Preconditions the script now checks for itself, each refusing rather than proceeding: the host is
free of any grid, `claude` is on PATH, the venv python exists, the haystack holds more than 4,000
documents, OpenRouter credit is above the $4 reserve, `preregistration/` is clean, the run id has no
existing artifacts or work root, and apparatus checks 1 and 3 pass.

⛔ **`evidence-tool-001` is a burned run id.** Its three conditions wrote `admission.json` with zero
admitted cells, which reads as COMPLETE to `archive_partial.py` and as "skip" to `--resume`, so
restarting into it would run nothing and exit 1. The default is now `evidence-tool-002`, and the
script refuses any id that already has artifacts. Nothing was deleted: the burned directories remain
as the record of what the failed attempt did.
