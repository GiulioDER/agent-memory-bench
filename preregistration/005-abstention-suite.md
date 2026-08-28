# abstention-001: when the corpus cannot answer, does the memory layer withhold, and what does it cost when it does not?

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

Across four corpus conditions in which retrieved evidence is absent, stale, contradictory or
adjacent-but-inapplicable, what fraction of paired cells does a memory arm **damage**, defined as
failing a cell that the `bare` arm solved, and does that damage exceed the benefit the same arm
delivers on the same grid?

## Why this suite has to exist

Every one of the 24 `ts-*` tasks places its governing fact **in** the corpus. The suite as it
stands can only ask whether memory helps; it is structurally incapable of detecting harm, so every
number this benchmark has published is a one-sided estimate. A memory layer that helps 20% of cells
and harms 15% and one that helps 20% and harms 2% both report "+5 points" today.

⛔ **This suite is not, and must not become, a test of any one product's features.** Conditions are
defined by **what the corpus contains**, never by what a system does about it. Every arm ingests a
byte-identical corpus. Whether a system copes through supersession metadata, recency weighting,
reranking, a refusal threshold, or not at all, is the thing being measured, not the thing being
assumed. A reviewer must be able to read the four conditions below without being able to tell which
product they were written by.

## Corpus conditions

Each condition is a property of the planted corpus. `absent` needs no plant; the other three do.

| condition | corpus contains | correct behaviour | damage signature |
|---|---|---|---|
| `absent` | no governing fact for this task | solve from the repository, or state it is unknown | invents a convention and applies it |
| `superseded` | the old fact AND the newer one, both dated | apply the current fact | ships the stale convention |
| `contradictory` | two undated memos that disagree, neither marked | surface the conflict rather than choose | chooses silently, wrong ~50% of the time |
| `adjacent` | a confident, high-similarity memo governing a DIFFERENT subsystem | recognise it does not apply here | applies the other subsystem's rule |

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `bare` | n/a | the reference point; damage is undefinable without it |
| `claude_md` | fixture README bundle | static-instruction control |
| `recall` | `adapters/recall/config.frozen.json` | `--recall-instruction skill` |

`bare` is mandatory here. `diagnostic-003` onward dropped it, and without it "worse than no memory
at all" cannot be expressed.

## Grid

Tasks: the `absent` condition reuses existing `ts-*` tasks with their precursor session withheld
from the corpus. The other three need new planted memos over existing task fixtures, so the task
repository work is unchanged and only the corpus differs. Target 12 tasks per condition, 48 total,
3 seeds, 3 arms: 432 sessions.

Model, CLI version, timeout, denied tools, permission mode: identical to `diagnostic-009` and
recorded in `environment.json` before the first session.

## Endpoints, in reporting order

1. **Primary: net harm**, per arm against `bare`, over all admitted cells:
   `P(arm fails ∧ bare succeeds) − P(arm succeeds ∧ bare fails)`, per-task cluster bootstrap CI.
   A rate over **admitted paired cells**, which is the denominator that makes it a rate at all.
2. **Damage rate** alone, `P(arm fails ∧ bare succeeds)`, reported per condition.
3. **Abstention rate**: fraction of `absent` and `contradictory` cells where the arm's response
   explicitly declines or names the conflict, judged by a deterministic checker, not a model.
4. **Wrong-fact-applied rate**: fraction of cells whose deliverable contains the planted wrong
   convention. This is knowable by construction because the wrong fact was planted.
5. Secondary: task success per arm per condition, for continuity with earlier runs.

Endpoints 3 and 4 need a checker capability that does not exist yet: distinguishing "failed
neutrally" from "failed by acting on retrieved-but-wrong evidence". Building it is in scope and it
must pass the same three-way discrimination gate every other checker passes.

## Predictions

House prior: effects arrive at a quarter to a half of intuition, costs at five times. My own record
on this benchmark is eleven falsified predictions out of twelve, every one too optimistic, so these
are deliberately low.

1. **`adjacent` produces the most damage of the four conditions.** It is where retrieval similarity
   is highest and the evidence is most confidently wrong. Damage rate for `recall` on `adjacent`:
   **10% to 25%** of paired cells.
2. **`absent` produces the least damage**, under 8%, because an empty result is easier to notice
   than a plausible wrong one.
3. **Net harm for `recall` is positive but small overall**, between **0 and +10 points**, i.e. more
   harm than benefit on this suite, in contrast to the positive lift the fact-present suite shows.
4. **Abstention rate is low across the board**, under 30% on `absent` and under 15% on
   `contradictory`. Predicting the conflict is noticed at all feels generous.
5. **`claude_md` shows near-zero damage**, under 3%, since a static file cannot retrieve anything
   wrong. If it does not, the damage metric is measuring something other than retrieval and the
   apparatus is broken.

Prediction 5 is the apparatus check, not a finding. Exit code 0 is not a measurement.

## Exclusion and truncation rules

Admission is unchanged: a cell is discarded unless every arm proves its treatment was applied, and
discards are published with reasons. Retries are triggered by wiring only, never by outcome. If the
budget binds, truncate seeds in reverse order and never truncate tasks or conditions.

A condition with fewer than 8 admitted tasks is reported as underpowered rather than as a result.

## What would falsify this

- Prediction 1 falsified if `adjacent` is not the worst condition, or if its damage rate is under
  5% or over 40%.
- Prediction 3 falsified if net harm is negative, i.e. the memory arm helps more than it harms even
  on a corpus built to mislead it.
- Prediction 5 falsified if `claude_md` shows damage above 3%, which would mean the metric is
  capturing session variance rather than retrieval harm, and the suite would be void.
- The whole suite is void if the planted memos are retrievable at materially different rates across
  arms for reasons of ingestion rather than retrieval, which the corpus audit must check before the
  first session.

## Confounds I can name now

- **Planted-memo salience.** If the wrong memos are written more vividly than the real corpus, the
  suite measures writing style. The generator must draw from the same recording pipeline and be
  audited for length and vocabulary against the existing 125 sessions.
- **The grid's ceiling problem, unfixed.** In `diagnostic-009`, 8 of 24 tasks were already solved
  by `claude_md` at 100% and 1 was failed by every arm, leaving 15 that discriminate. Damage cannot
  be observed on a task `bare` already fails. Task selection for this suite must screen on `bare`
  having a non-trivial success rate, and the screen must be fixed before seeing results.
- **Instruction confound, now known.** `diagnostic-009` used the one-line instruction where
  pilot-004 used the skill, and the search rate differed 12% against 79%. This suite pins
  `--recall-instruction skill` and records its sha256.
- **Damage is not necessarily attributable.** A cell where the arm fails and `bare` succeeds may
  differ by chance, not by memory. Endpoint 4 exists to separate "failed" from "failed *because* it
  applied the planted fact", and only the latter is evidence of retrieval harm.

## What I already know

`diagnostic-009` (72/72 cells admitted, one-line instruction): `oracle_headroom` +0.500
[+0.319, +0.681], `prefetch_memory_lift` 0.000 [-0.056, +0.056], natural search rate 11%.
`diagnostic-010` (skill instruction) was still running when this was written and its recall arm was
trending above `claude_md`, so the mechanism reading may yet change. pilot-004 measured recall
+17.4 points over `claude_md` on the fact-present suite with 9 of 72 cells discarded.

Nothing in this project has ever measured the cost side.

<!-- results are appended below this line; everything above is frozen -->
