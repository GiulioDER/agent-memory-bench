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
