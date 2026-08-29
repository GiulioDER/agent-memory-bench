# pilot-003: freeze the model for the multi-product benchmark

Status: FROZEN above the results marker once committed.

## Question

Pilot 002 showed that the shipped check-memory-before-acting skill repaired the
discoverability failure on `deepseek/deepseek-v4-flash`. The next uncertainty is model
choice. This run selects the model for the production comparison before any competitor
result is collected.

## Candidate models

The candidates are fixed from the OpenRouter models endpoint read on 2026-08-24.

1. `deepseek/deepseek-v4-flash`, input price `0.0574` USD per million tokens and
   output price `0.1148` USD per million tokens. This is the pilot 002 control.
2. `openai/gpt-5.3-codex`, input price `1.75` USD per million tokens and output price
   `14.00` USD per million tokens. The one cell compatibility smoke passed for both
   `claude_md` and `recall` before this preregistration.

The model ID, endpoint, prices, CLI version, corpus manifest, task files, and recall
instruction remain fixed during both runs.

## Grid

Each candidate runs 3 arms (`bare`, `claude_md`, `recall`), 24 tasks, and 3 seeds:
`3 x 24 x 3 = 216` sessions per model and 432 sessions overall. The recall arm uses
the shipped skill from pilot 002. The `claude_md` arm receives the same static bundle
without the skill. The `bare` arm receives neither. The runner uses Claude Code 2.1.238,
600 second session timeouts, one cell at a time, and the same executable checker.

Run IDs are `pilot-003-deepseek` and `pilot-003-gpt53`.

## Endpoints

1. Eligibility: paired cell admission, search rate, reached-given-searched, and reached
   overall for the recall arm.
2. Capability: per arm task success, per-task rates, and the same ceiling and floor
   screening rules used by pilot 001.
3. Memory effect: recall versus `claude_md`, per-task cluster bootstrap interval and
   cell McNemar test. This is descriptive model selection evidence, not the final
   competitor claim.
4. Cost and latency: input tokens, output tokens, estimated USD, wall time, and
   discarded cells.

## Eligibility and selection rule

A model is eligible only when at least 95 percent of its cells admit as complete paired
cells, recall search rate is at least `0.50`, and reached-given-searched is at least
`0.50`. If neither model is eligible, the competitor run does not start. The failure
is reported as an infrastructure or model integration result and the protocol is
revised in a new preregistration.

Among eligible models, select the model with the higher `claude_md` success rate. This
chooses the more useful production capability level without selecting on the observed
memory delta. If the success rates differ by less than `0.05`, select the model with
the lower estimated USD per admitted `claude_md` success. The selected model is then
frozen for the full multi-product comparison.

## Predictions

1. `deepseek/deepseek-v4-flash` search rate: `0.80`, reached-given-searched: `0.88`,
   reached overall: `0.70`, `claude_md` success: `0.40`, recall success: `0.64`.
2. `openai/gpt-5.3-codex` search rate: `0.70`, reached-given-searched: `0.80`, reached
   overall: `0.56`, `claude_md` success: `0.55`, recall success: `0.68`.
3. The stronger model will have the higher `claude_md` success rate and will therefore
   be selected, even if its recall delta is smaller.
4. Each model will discard fewer than 15 of its 216 sessions after the fresh database
   migration and startup preflight.
5. Total spend will be about `$15`, with a hard cap of `$40`. If the cap is reached,
   truncate seeds in reverse order and never truncate tasks.
6. Total wall time will be between 3 and 7 hours.

## Operational controls

The model runs use a fresh disposable PostgreSQL database whose migration ledger is
verified before launch. The recall tenant is indexed from the committed corpus manifest
using the adapter write path. A startup check must report the current migration checksum,
721 corpus chunks, and a connected recall MCP server before the first model session.

<!-- results are appended below this line; everything above is frozen -->

## Results

### `pilot-003-deepseek`

Model: `deepseek/deepseek-v4-flash`. The run completed all 216 sessions as 72 paired
cells with zero discards. Wall time was 95 minutes and estimated spend was `$0.4964`.

| arm | success |
|---|---:|
| bare | 36/72, 50.0% |
| claude_md | 26/72, 36.1% |
| recall | 42/72, 58.3% |

Recall search rate was `0.833`, reached-given-searched was `0.850`, and reached overall
was `0.708`.

The primary recall versus `claude_md` task-level delta was `+0.2222`, with cluster
bootstrap 95% CI `[+0.1111, +0.3333]`. The cell-level McNemar p-value was
`0.00014495849609375`, with 17 recall-only successes and 1 `claude_md`-only success.

On the eight pilot-survivor tasks, the delta was `+0.4583`, CI `[+0.2917, +0.625]`,
McNemar p `0.0009765625`, with 11 recall-only successes and 0 `claude_md`-only
successes.

The exploratory bare versus `claude_md` delta was `+0.1389`, CI
`[+0.0417, +0.2639]`, McNemar p `0.001953125`. The static `claude_md` arm therefore
underperformed bare in this run.

### `pilot-003-gpt53`

Model: `openai/gpt-5.3-codex`. The run attempted 216 sessions but admitted only 40 of
72 paired cells and discarded 32, so it failed the preregistered 95% admission rule.
Wall time was 71 minutes and estimated spend was `$13.4845`.

The discarded sessions were primarily caused by OpenRouter HTTP 402 credit and
in-flight request limits. One discarded cell also reported a transient recall MCP
startup failure. This is an operationally incomplete run, not a model-quality result.

Descriptive admitted-cell success rates were:

| arm | success |
|---|---:|
| bare | 19/40, 47.5% |
| claude_md | 12/40, 30.0% |
| recall | 20/40, 50.0% |

These GPT numbers are not used for model selection or pooled comparison.

### Eligibility outcome

DeepSeek met all eligibility criteria and is the only eligible candidate. GPT-5.3 Codex
met the recall mechanism thresholds but failed paired-cell admission because of the
provider credit failure. DeepSeek is therefore the provisionally selected model under
the frozen rule. A fair model head-to-head requires a complete GPT rerun after the
provider capacity issue is fixed.

## Correction, 2026-08-28: `reached-given-searched` does not measure what its name says

Found by the adversarial audit on `claude/audit-fixes`, verified independently here before being
written down. This is the most serious defect found in this benchmark so far, and its consequence
for a competitor comparison is worse than its consequence for anything above.

### The defect

`scripts/analyze_pilot.py:87` counts a session as having reached the governing memo when the
string `sessions__<task_id>__` appears in a retrieved context or an MCP tool output. That string
is **our own rendered filename**. `harness/transcripts.py::render_corpus` flattens
`sessions/<task>/p01.jsonl` into `sessions__<task>__p01.md`, and recall echoes the filename back
in each hit's source field.

So the metric asks "did a hit come from the right FILE", not "did the agent receive the governing
decision". A chunk drawn from the correct precursor that contains only the opening investigation,
and never the closing turn where the convention is stated, counts as reached.

### Verified, and the replacement numbers disagree

Recomputed here from `records.final.jsonl` for both published runs, over admitted `recall` cells
with at least one memory call:

| signal | pilot-003-deepseek | pilot-004-placebo |
|---|---:|---:|
| by filename (**the published metric**) | **0.850** (51/60) | **0.926** (50/54) |
| by fact-term content in the retrieved text | 0.617 (37/60) | 0.704 (38/54) |
| by overlap with the precursor's decision turn | 0.083 (5/60) | 0.111 (6/54) |

The filename row reproduces the `0.850` published above exactly, which confirms the
reimplementation is measuring the same thing the run did.

⚠️ **The audit's independent implementation gives different replacement figures**: 0.550/0.648
for fact content and 0.333/0.444 for decision overlap, against 0.617/0.704 and 0.083/0.111 here.
The direction is identical and robust, the magnitudes are not. That disagreement is not noise to
be averaged away, it is the finding: **there is no single obvious operationalisation of "reached",
so the quantity must be reported as a bracket rather than as a point estimate**, and any single
number published for it is a choice that has to be argued for.

### What this does to the frozen eligibility rule

The rule above requires `reached-given-searched` of at least `0.50`. DeepSeek clears it on the
filename signal and on fact content, under both implementations, and fails it on decision overlap
under both. So the threshold is met or missed depending on a definition the record never pinned
down.

**The selection outcome does not change.** GPT-5.3 Codex was excluded for failing paired-cell
admission after a provider credit failure, which this defect does not touch, so DeepSeek remains
the only candidate that passed admission and remains provisionally selected. What changes is the
justification: one of the three eligibility criteria was evaluated with an instrument that does
not measure the construct it names, and that must not be restated as though it had.

### The consequence that matters more, and it is disqualifying

**A filename match zeroes every extraction-based memory product by construction.** mem0,
Supermemory, Zep and Cognee extract and re-express memories; they have no reason to echo our
rendered filenames, and several cannot, because they do not store our files at all. Run as
published, this metric would report those products at or near zero "reached" while recall scored
0.85, and the gap would be an artefact of who happens to quote our path format.

That is not a measurement error to disclose in a footnote. **Any competitor comparison using this
metric as published would be indefensible**, and a competitor would be right to say so.

### What must happen before any competitor arm runs

1. The reached metric is reported as a **bracket over at least the three signals above**, with the
   operationalisation of each stated, and never as a single number.
2. The signal used for any **eligibility gate** must be content-based, since a filename signal is
   not portable across products and an eligibility rule must mean the same thing for every arm.
3. Preregistration 000's and this record's published `reached` figures are to be cited **only**
   alongside this correction.
4. The two implementations must be reconciled, or both reported with their difference stated. They
   are not yet reconciled.

Nothing above the results marker in this record has been edited. The eligibility rule, the
predictions and the run results stand as written; this section corrects how one of the reported
quantities may be read.

## Correction to the correction, 2026-08-28, same day

Three things in the section above are wrong or incomplete. Per the standing rule, none of its
numbers are edited; they stand as written and are corrected here.

### 1. My decision-overlap figures were an artefact. They are 0.333 and 0.444

The section above reports decision-turn overlap as `0.083` (5/60) and `0.111` (6/54), and treats
the audit's `0.333` / `0.444` as an unexplained disagreement. **Mine were wrong.**

The implementation filtered the decision turn's words by length and *then* joined adjacent
survivors into shingles, producing strings such as `"failure. decision: restricted alphabet:"`
that occur in no real text, because the intervening words had been dropped. It matched almost
nothing, and the low rate was a property of my shingle construction rather than of retrieval.

Recomputed with contiguous shingles over the same cells:

| shingle | pilot-003-deepseek | pilot-004-placebo |
|---|---:|---:|
| 8 contiguous words | **0.333** (20/60) | **0.444** (24/54) |
| 4 contiguous words | 0.433 (26/60) | 0.463 (25/54) |

The 8-word row reproduces the audit's figures to three decimals from an independent
implementation, which is the confirmation that matters.

### 2. The fact-content gap was version skew, not a disagreement

`0.617` / `0.704` above was computed with the ORIGINAL `fact_terms`. The audit's `0.550` / `0.648`
is the same measurement after three terms were tightened that day (`ts-empty-input`,
`ts-log-mask`, `ts-round-money`) to close over-generic matches. Both are correct for their term
set, and no retrieval differed between them.

### 3. So the claim that the operationalisations disagree does not stand

The section above concludes that "there is no single obvious operationalisation of 'reached', so
the quantity must be reported as a bracket". **The premise was two errors, not a genuine
divergence**: once my shingle bug is fixed and the term sets are matched, the two independent
implementations agree.

What survives, restated honestly:

* The **choice of signal** (filename, fact content, decision overlap) is a real methodological
  choice with a wide spread, 0.850 against 0.617 against 0.333 on pilot-003, and it must be stated
  rather than left implicit. Reporting a bracket is still right, for that reason and not the one
  given above.
* Two implementations agreeing is evidence the signals are well defined, which is a stronger
  position than the section above claims.

### 4. A new defect of the same class as the filename match

Tightening three `fact_terms` moved the fact-content signal by **6.7 points with no retrieval
changing**. `fact_terms` is serving two purposes that pull in opposite directions: containment
wants long distinctive phrases to avoid false positives, and any reached metric built on it wants
short recognisable ones to avoid false negatives.

**If an eligibility number depends on `fact_terms`, then editing a term silently edits the
number.** That is the same failure as measuring a filename: a published quantity moving for a
reason that has nothing to do with what it claims to measure. Not fixed here. The candidate fixes
are a separate `evidence_terms` field, or deriving the metric from the decision turn alone, which
is the only one of the three signals that no audit has an incentive to edit.

### 5. The selection statement was incomplete

The section above says the selection outcome does not change, which is true and understates the
consequence. DeepSeek was the **only** eligible candidate, and the frozen rule says that if
neither model is eligible the competitor run does not start. Criterion 3 is therefore load-bearing
for the run happening at all, not a spare wheel.

Its margin over the `0.50` floor depends entirely on the signal:

| signal | pilot-003 value | margin over 0.50 |
|---|---:|---:|
| filename (as published) | 0.850 | +0.350 |
| fact content, original terms | 0.617 | +0.117 |
| fact content, tightened terms | 0.550 | +0.050 |
| decision overlap, 8-word | 0.333 | **fails** |

DeepSeek remains eligible under the content signal, which is the defensible primary, on a margin
between roughly a third and a seventh of what was reported. It fails the strictest reading. That
is not grounds to re-select, since decision overlap is explicitly a lower bound, but **criterion 3
must not be described as comfortably met**, and any future gate must name its signal before being
frozen rather than after.


## Protocol change, appended 2026-08-29 (nothing above the results marker edited)

Three defects confirmed by the 2026-08-28 CCA audit are fixed in
`docs/audit/2026-08-29-protocol-change-record.md`. Two of them move numbers this record's rules
are stated in terms of, so the instrument this record froze is no longer the instrument in the
tree:

- **`oracles/ts-retry-cap/driver.py`** rejected AWS-canonical full jitter about 40% of the time
  (measured 25/40 passes before, 40/40 after). `ts-retry-cap` success rates move for every arm.
- **`harness/tasks.py run_checker`** now grades a checker exception as a failure instead of
  letting the cell be discarded, so the **paired-cell admission rate** this record's 95%
  eligibility rule is measured against moves strictly upward.

Consequence for the resume plan: a `pilot-003-gpt53` rerun can no longer be "the exact frozen
protocol" of `pilot-003-deepseek`. It is comparable to a DeepSeek rerun on the current code, not
to the recorded DeepSeek result. Rerun both, or report the model contrast as measured on a
revised instrument.

**The frozen prices in this record are unchanged and are still the reference.** Two things about
how they were applied are recorded in the change document rather than here: `estimated_usd`
charged cache reads at the fresh-input rate (the recall arm's input is 68.2% cache reads against
`claude_md`'s 48.6%, so the overstatement is uneven between the arms), and `pilot-004-placebo` was
priced at `scripts/pilot.py`'s argparse defaults rather than at this record's rates, which makes
its dollar figures not directly comparable to `pilot-003`'s. Recorded numbers are left as they
are; the recomputations sit beside them.

---

⚠️ **The corpus feed changed on 2026-08-29, after this record's numbers were measured.**
`corpus/manifest.json` went from 125 entries to 195 (thirteen signal sessions that were on disk
and unlisted, plus 57 distractors to hold the 4:1 ratio), so retrieval here ran over a smaller
haystack than any later run will. Do not difference a number measured after that date against one
above. Nothing above this line was edited.
[`docs/audit/2026-08-29-corpus-feed-change-record.md`](../docs/audit/2026-08-29-corpus-feed-change-record.md)
