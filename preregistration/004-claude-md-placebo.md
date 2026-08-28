# pilot-004: length-matched CLAUDE.md placebo ablation

Status: FROZEN above the results marker once committed. No model session may start until this
file and the placebo generator are committed.

## Question

Pilot-003 found that the static `claude_md` arm scored 36.1%, 13.9 percentage points below the
bare arm at 50.0%. This ablation separates two explanations:

1. **Context dilution:** adding a project-shaped file of this length reduces performance,
   regardless of its content.
2. **Content misdirection:** the specific `CLAUDE.md` prose causes the loss; length is incidental.

## Design

The run uses the same 24 `ts-*` tasks, 3 seeds, executable checkers, model, endpoint, CLI version,
timeouts, task order, recall skill, and admission rules as pilot-003. It runs four arms in one
fresh paired block:

| arm | treatment |
|---|---|
| `bare` | no appended system prompt file |
| `placebo` | deterministic neutral project-shaped prose |
| `claude_md` | the existing task-specific static bundle |
| `recall` | the same static bundle plus the frozen recall skill |

The placebo is generated separately for every task from the corresponding `claude_md` bundle.
It matches the reference bundle's line count and whitespace-delimited token count exactly. Markdown
line markers are retained, but all words come from the fixed neutral vocabulary in
`harness/placebo.py`. The generated file contains no task facts, commands, repository paths, or
task-specific instructions. The runner records every placebo and reference hash and the actual
model input-token totals remain a secondary audit.

The length metric is explicitly whitespace-delimited tokens plus line count. This is a reproducible
pre-run proxy; it is not claimed to be identical to the provider's hidden BPE tokenizer.

## Grid and cost

The grid is `4 x 24 x 3 = 288` sessions and 72 paired cells. The model is
`deepseek/deepseek-v4-flash`, selected provisionally by pilot-003. At pilot-003's observed pricing,
the added placebo arm is expected to cost about `$0.09` and the complete four-arm block about
`$0.58`; actual gateway accounting is authoritative. The hard cap is `$2.00`. If the cap is
reached, truncate seeds in reverse order and never truncate tasks.

## Endpoints and contrasts

The primary ablation endpoints are task-cluster bootstrap intervals and paired cell McNemar tests
for:

1. `placebo - bare`, the length/dilution contrast.
2. `claude_md - placebo`, the content contrast.

The existing `recall - claude_md` contrast and recall mechanism metrics are reported as secondary
continuity checks. All four arm rates, costs, latency, admission, and per-task outcomes are
published.

## Interpretation rule

Interpretation is based on both contrasts and their confidence intervals, not on the phrase "near"
alone:

- If `placebo` is materially below `bare` and close to `claude_md`, the result supports context
  dilution.
- If `placebo` is close to `bare` and `claude_md` is materially below `placebo`, the result supports
  content-specific misdirection.
- If both contrasts are nonzero or the placebo is intermediate, report mixed or unresolved
  effects. Do not force a binary conclusion.

The practical equivalence margin for the phrase "close" is 0.10 absolute success rate, fixed
before the run. This is an interpretive margin, not a claim of formal equivalence at this sample
size.

## Readiness and execution

Preflight without model calls:

    python -m scripts.placebo_preflight

Run only after preflight passes and the provider credit check is confirmed:

    python -m scripts.pilot --run-id pilot-004-placebo --model deepseek/deepseek-v4-flash --seeds 3 --recall-instruction skill --arms bare,placebo,claude_md,recall

Analyze after all cells finish:

    python -m scripts.analyze_pilot --run-id pilot-004-placebo --arms bare,placebo,claude_md,recall

The run is exploratory follow-up evidence and does not alter pilot-003's frozen model-selection
decision or the planned competitor comparison.

<!-- results are appended below this line; everything above is frozen -->

## Results

Run: `pilot-004-placebo`, model `deepseek/deepseek-v4-flash`, Claude Code `2.1.238`.
The run completed all 288 sessions. The admission gate admitted 63 of 72 paired cells
and discarded 9, which is inside the preregistered limit of fewer than 10 discarded cells.
Eight discarded cells were recall MCP startup failures and one was a placebo admission
failure. Discarded cells were not scored as failures.

| arm | success |
|---|---:|
| bare | 26/63, 41.3% |
| placebo | 30/63, 47.6% |
| claude_md | 27/63, 42.9% |
| recall | 39/63, 61.9% |

The placebo-minus-bare per-task mean delta was `+0.0556`, with cluster bootstrap 95%
interval `[-0.0278, +0.1528]` and cell McNemar `p = 0.21875`. The claude_md-minus-placebo
delta was `-0.0486`, interval `[-0.1875, +0.0903]`, and `p = 0.453125`. Neither
preregistered ablation contrast supports a confirmed dilution or content-misdirection
effect. Pilot-003's 13.9-point bare-versus-claude_md gap did not replicate in this block.

Recall remained a secondary continuity check. Recall-minus-claude_md was `+0.1736`,
interval `[+0.0486, +0.3125]`, with `p = 0.001831`; there were 13 recall-only successes
and 1 claude_md-only success. Search rate was `0.857`, reached-given-searched was `0.926`,
and reached overall was `0.794`.

The run used 9,386,264 metered tokens and had estimated session spend `$0.5836`. Full
analysis and limitations are recorded in `reports/pilot-004-placebo-report.md`.


## Protocol change, appended 2026-08-29 (nothing above the results marker edited)

See `docs/audit/2026-08-29-protocol-change-record.md`. Two points bear on this run's reported
figures, and neither changes a recorded number here:

- This run's `estimated_usd` was computed at `scripts/pilot.py`'s argparse defaults
  (0.05866 / 0.11732), not at the frozen preregistration 002 rates (0.0574 / 0.1148) that
  `pilot-003-deepseek` used. Recomputing at the defaults reproduces this run's per-arm figures to
  four decimal places, which is how the basis was identified: the artifact recorded
  `pricing_as_of` but never the prices. **`pilot-003` and `pilot-004` dollar figures are therefore
  not directly comparable.**
- Cache reads were charged at the fresh-input rate. They are 68.2% of the recall arm's input here
  against 55-58% for the three baselines, so the overstatement is uneven across arms. The
  recomputation at several cache discount ratios is in the change document.

Success rates, deltas, CIs and p-values in this record are unaffected: the cost model feeds no
outcome.
