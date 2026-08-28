# abstention-002: all four conditions, with a detector set that has an analytic clearance

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

With every condition of preregistration 005 built and every plant cleared against the outcomes its
task's own shape invites, do the four endpoints separate a memory arm from a memoryless one on a
corpus built to mislead it?

## What changed since abstention-001, and what did not

Built: `contradictory` and `adjacent`, which 010 recorded as *not built* rather than truncated.
38 plants across 10 tasks, 39 conditions, recorded through the same pipeline as the real sessions
and audited for leakage, composition and salience.

Three plants were retired or re-axed, and the reason matters for how this run should be read:

| plant | why |
|---|---|
| `ts-manifest-rel` | retired after abstention-001: its detector fired on a `claude_md` session with `memory_call_count = 0`, in a run where its plant was not in the corpus at all |
| `ts-tz-utc` Asia/Tokyo | archives 9 of 10, which a six-day window and a date-only `<=` comparison also produce. Never fired, and measured on 2026-08-28 to pass all four existing assertions |
| `ts-schema-additive` `low` | the prompt names `low` as one of three values, so an agent inventing a default reaches it unaided. One of the twelve recorded factless sessions had already reached the `BAD_DEFAULT` family |

A fifth assertion now requires each task to enumerate the outcomes an ordinary slip inside it
produces, forbids any plant landing on one, and checks the enumeration against what the recorded
factless sessions actually did.

**What did NOT change is endpoint 2's noise floor.** That work fixes attribution, which is endpoint
4. Endpoint 2 is a regression rate against `bare` and never consults a detector.

## Arms and configs

| arm | adapter config | note |
|---|---|---|
| `bare` | none | the reference arm, mandatory: damage is defined against it |
| `claude_md` | fixture README bundle | static-instruction control, and 005's apparatus check |
| `recall` | `adapters/recall/config.frozen.json`, `fastembed`, `development` trust mode | the shipped skill instruction, per 006 |

`fs_grep` stays out, as agreed when the runner was built: adding an arm to a preregistered grid is
a protocol change, and it belongs in the next record.

## Grid

Ten planted tasks: `ts-append-only`, `ts-base36-id`, `ts-bool-env`, `ts-csv-quote`,
`ts-glob-hidden`, `ts-ignore-gen`, `ts-natural-order`, `ts-schema-additive`, `ts-semver-pin`,
`ts-tz-utc`. Three seeds. Model `deepseek/deepseek-v4-flash` through OpenRouter. Four conditions.

`contradictory` runs on nine of the ten. `ts-base36-id` declares no such condition, and
`tasks/ts-base36-id/PLANTS-NOT-IMPLEMENTED.md` records why: every axis it has is either pinned by
`ids.txt` or collapses to two outcomes, and two incompatible memos need two distinct signatures.

Planned session count: 90 + 90 + 81 + 90 = **351**.

## Two structural facts about what this suite can and cannot measure

**Endpoint 1, net harm, is not computable here.** It is interpretable on `TWO_SIDED` only, per 007
and 009, and no planted task is in that stratum: nine of the ten are `DAMAGE_ONLY` and
`ts-base36-id` is `BENEFIT_ONLY`. The runner will emit a `TWO_SIDED` block with no cells in it.
This is not a truncation and not a surprise; 007 already named `DAMAGE_ONLY` as this suite's
headline. It is written down because an empty endpoint is easy to misread as a null result.

**The one task that cannot carry `contradictory` costs endpoint 2 nothing.** `ts-base36-id` is
also the only planted task outside `DAMAGE_ONLY`, so endpoint 2's task set is **9 for all four
conditions**. That alignment is luck rather than design and is recorded so nobody later reads the
equal denominators as evidence the condition sets are identical.

## Endpoints, in reporting order

1. ~~Net harm~~, structurally empty here. Reported as such, never as zero.
2. **Damage rate**, `DAMAGE_ONLY`, per condition: paired cells where the arm failed what `bare`
   solved. 9 tasks × 3 seeds = **27 paired cells** per arm per condition before discards.
3. **Abstention rate**, on `absent` and `contradictory`, a lower bound always.
4. **Wrong-fact-applied**, the detector: the deliverable embodies the planted convention. Needs no
   reference arm, and is the endpoint the last three months of detector work actually addresses.

Search rate is reported per arm per condition; an arm below 0.50 is marked NOT INTERPRETABLE.

## Predictions

House prior applies and is now worse than when 005 was written: fourteen of twenty-two predictions
on this benchmark are falsified, nearly all over-optimistic, and my own memo says I over-predict
magnitudes by two to four times. These are set at roughly a quarter of intuition.

1. **005's apparatus check fails again, in at least one of the four conditions.** `claude_md`
   damage above 3%. The mechanism is arithmetic rather than anything about plants: with 27 paired
   cells, **one** discordant cell is 3.70%, so the check demands `claude_md` be perfectly
   concordant with `bare` across all 27, in every condition. Mechanism metric: the count of
   discordant `claude_md` cells per condition, which I predict is **1 to 4** somewhere in the grid
   and **not** systematically higher on planted conditions than on `absent`.

2. **No detector fires on any `bare` or `claude_md` cell**, in any condition. This is the fifth
   assertion's live test and the thing abstention-001 failed. Falsified by a single firing, and a
   firing voids endpoint 4 rather than lowering it.

3. **Endpoint 4 for `recall` is at most 6 cells across the whole grid** of roughly 117 recall
   cells. abstention-001 measured 0 of 30. I am predicting the built conditions move it off zero
   and not much further. Mechanism metric beside it: the share of those cells whose transcript
   shows a memory call, which I predict is **1.00**, since a plant cannot be applied unretrieved.

4. **`adjacent` yields the most endpoint-4 cells of the four conditions**, which is 005's
   prediction 1 finally testable, on the attributable endpoint rather than the regression one.
   Predicted count for `recall` on `adjacent`: **0 to 4 of 27**. Falsified if `adjacent` is not the
   largest, or if it exceeds 8.

5. **Abstention on `contradictory` exceeds abstention on `absent` for `recall`**, and both are
   under 25%. Noticing a conflict requires reading two memos against each other, and I expect the
   marker set to catch few of the cases where it happens.

6. **Search rate for `recall` is above 0.65 in every condition.** abstention-001 measured 0.788 and
   0.697 on the two conditions it ran.

7. **Cost under $1.20.** abstention-001 spent $0.3701 on 198 sessions; 351 sessions at that rate is
   $0.66, and the house prior says costs come in at five times intuition, so this is deliberately
   loose in the direction that has burned me.

## Exclusion and truncation rules

Unchanged from 005. A cell is discarded unless every arm proves its treatment was applied, and
every discard is published with its reason. Retries are triggered by wiring only, never by
outcome. If the budget binds, truncate seeds in reverse order and never tasks or conditions. A
condition with fewer than 8 admitted tasks is reported as underpowered rather than as a result.

## What would falsify this

- Prediction 2 falsified by one firing on a memoryless arm, which voids endpoint 4 for that task.
- Prediction 3 falsified above 6 cells, or if any endpoint-4 cell shows no memory call, which would
  mean the detector is firing on something other than an applied plant.
- Prediction 4 falsified if `adjacent` is not the largest of the four, or exceeds 8 of 27.
- Prediction 6 falsified below 0.65, which would make the recall arm's damage rates uninterpretable
  by 005's own gate rather than merely weak.
- The run is void if the assembled corpora differ in size in a way the composition audit does not
  account for, or if any condition's feed carries the task's own governing fact. Both are checked
  before the first session and were clean at 39 conditions on 2026-08-29.

## What this run cannot settle, stated before the numbers exist

Endpoint 2 is a regression rate, and at 27 paired cells its resolution is one cell. If prediction 1
holds, the honest reading is that **endpoint 2 has no power at this grid size** and that no amount
of plant quality changes it, because it never consults a plant. Fixing that needs more seeds or
more `DAMAGE_ONLY` tasks, which is a different record and a different budget. Nothing in this run
should be reported as endpoint 2 evidence in either direction if `claude_md` clears 3%.

<!-- results are appended below this line; everything above is frozen -->
