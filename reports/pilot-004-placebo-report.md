# Pilot-004 placebo ablation report

Date: 2026-08-25
Run: `pilot-004-placebo`
Model: `deepseek/deepseek-v4-flash`
Claude Code: `2.1.238`

## Executive summary

Pilot-004 was designed to explain the 13.9-point gap observed in pilot-003 between
the bare arm and the static `CLAUDE.md` arm. It added a deterministic placebo file
that matched the task-specific `CLAUDE.md` bundle in line count and whitespace-token
count, while containing no task-relevant facts or instructions.

The follow-up does not support either simple explanation for the earlier gap:

- The placebo was not materially worse than bare: per-task mean delta `+0.0556`,
  95% cluster interval `[-0.0278, +0.1528]`, McNemar `p=.21875`.
- `CLAUDE.md` was not materially worse than placebo: per-task mean delta `-0.0486`,
  95% cluster interval `[-0.1875, +0.0903]`, McNemar `p=.453125`.

The practical conclusion is that the pilot-003 bare-versus-static-file gap did not
replicate in this follow-up. It should be treated as unstable evidence, not as proof
that static instructions are harmful or that file length is the cause.

The memory-layer result remained strong as a secondary continuity check. Recall scored
`39/63` admitted cells (`61.9%`) versus `27/63` for `CLAUDE.md` (`42.9%`). The paired
per-task delta was `+0.1736`, with 95% cluster interval `[+0.0486, +0.3125]` and
McNemar `p=.001831`. This is evidence for the tested recall configuration on this
task grid, not a general ranking of memory products.

## Frozen design

The run used 24 executable coding tasks, three seeds, and four arms:

| Arm | Treatment |
|---|---|
| `bare` | No appended project prompt |
| `placebo` | Neutral project-shaped prose, length-matched to `CLAUDE.md` |
| `claude_md` | Existing task-specific static bundle |
| `recall` | Static bundle plus the frozen recall skill and MCP retrieval |

The planned grid was `24 x 3 x 4 = 288` sessions and 72 paired cells. The placebo
matched every reference bundle on the preregistered proxy metric: whitespace-delimited
tokens and line count. The provider's hidden BPE tokenization was not used as the
matching target.

## Data quality and admission

The run completed all 288 sessions. The admission gate admitted 63 of 72 paired cells
and discarded 9, which is just inside the preregistered limit of fewer than 10 discarded
cells. Eight discarded cells were caused by recall MCP startup failures and one cell
was discarded because its placebo arm did not pass admission. Discarded cells were not
scored as failures.

All four arms were present in the admitted cells. The recall MCP server was connected
in admitted recall sessions, and its search mechanism fired in the majority of them.

The run required a repair to the environment before execution. The first launch used a
stale DSN pointing to a removed database and was invalidated. A fresh disposable VPS2
database was then created, migrated through schema version `0016`, loaded with the
committed 721-chunk corpus, and validated with a Claude MCP preflight before the real
run. Those invalid attempts are archived separately and excluded from every result.

## Main results

Rates below are calculated over the 63 admitted paired cells.

| Arm | Successful cells | Rate |
|---|---:|---:|
| Bare | 26/63 | 41.3% |
| Placebo | 30/63 | 47.6% |
| `CLAUDE.md` | 27/63 | 42.9% |
| Recall | 39/63 | 61.9% |

The raw rate differences are descriptive. The preregistered inferential quantities are
paired, per-task contrasts:

| Contrast | Per-task mean delta | 95% cluster interval | McNemar p |
|---|---:|---:|---:|
| Placebo minus bare | +0.0556 | [-0.0278, +0.1528] | .21875 |
| `CLAUDE.md` minus placebo | -0.0486 | [-0.1875, +0.0903] | .453125 |
| Recall minus `CLAUDE.md` | +0.1736 | [+0.0486, +0.3125] | .001831 |
| Bare minus `CLAUDE.md` | -0.0069 | [-0.1667, +0.1458] | 1.0 |

The recall contrast had 13 cells where recall succeeded and `CLAUDE.md` failed, versus
one in the opposite direction. On the seven preregistered survivor tasks, recall's
per-task delta was `+0.4286`, with interval `[+0.1429, +0.7143]` and McNemar `p=.00390625`.
That survivor result is secondary and more selective than the all-task result.

## Recall mechanism

Among admitted cells:

- Search rate: `54/63 = 0.857`.
- Reached given searched: `50/54 = 0.926`.
- Reached overall: `50/63 = 0.794`.

This run measured whether the agent searched and whether it reached the task's governing
precursor. It did not yet classify the remaining failures into did-not-search,
searched-but-found-nothing, found-the-wrong-memory, or found-and-ignored-the-right-memory.
That taxonomy remains the next mechanism experiment.

## Cost and latency

The corrected four-arm run used 9,386,264 metered tokens and had an estimated session
cost of `$0.5836` at the frozen pricing snapshot.

| Arm | Total tokens | Estimated cost | Session wall time |
|---|---:|---:|---:|
| Bare | 1,461,929 | $0.0933 | 60.7 min summed |
| Placebo | 1,347,187 | $0.0864 | 66.7 min summed |
| `CLAUDE.md` | 1,316,056 | $0.0842 | 56.4 min summed |
| Recall | 5,261,092 | $0.3196 | 147.4 min summed |

The arm wall times are sums across sessions, not elapsed wall time for the whole run,
because the four arms ran in parallel within each paired cell. Recall used substantially
more input tokens and wall time. The task-success gain therefore needs to be evaluated
alongside cost and latency, not in isolation.

## Interpretation

The placebo result changes the interpretation of pilot-003. The earlier 13.9-point
static-file loss was not reproduced when the comparison was made on the same admitted
cells with a length-matched neutral control. The confidence intervals are wide enough
that this is not formal proof of equivalence, but both preregistered contrasts are
inside the fixed 0.10 practical-equivalence margin on their point estimates or overlap
it substantially. The correct claim is unresolved or noisy, not dilution confirmed and
not content-specific misdirection confirmed.

Recall's secondary advantage did reproduce on the same follow-up block, with a positive
paired interval against `CLAUDE.md`. That is the strongest result in this run, but it
still describes one model, one recall configuration, one corpus, and one coding-task
grid. It is not yet an industry-wide leaderboard result.

## Limitations and next work

1. The run had 9 discarded paired cells, concentrated in recall MCP startup. The result
   passes the preregistered discard threshold by one cell, so the operational margin is
   thin. A repeat should make MCP startup deterministic before increasing the grid.
2. The placebo was length-matched by whitespace tokens and lines, not hidden BPE tokens.
3. The checker suite used executable oracles, but the proposed known-bad repository twin
   audit has not yet been completed. Before making an industry benchmark claim, each
   checker should be shown to fail on a deliberately wrong repository state.
4. Retrieval failures need the four-way taxonomy: no search, no result, wrong result,
   and right result ignored.
5. A `wrong_memory` arm should inject plausible stale evidence and measure the cost of
   retrieval when memory is bad, not only when it is useful.
6. More seeds and a second model are needed before making broad claims about static
   project instructions or memory layers.

## Reproducibility

Primary artifacts:

- `results/pilot-004-placebo/records.final.jsonl`
- `results/pilot-004-placebo/admission.json`
- `results/pilot-004-placebo/costs.json`
- `results/pilot-004-placebo/environment.json`
- `preregistration/004-claude-md-placebo.md`

The full analysis command was:

```bash
python -m scripts.analyze_pilot --run-id pilot-004-placebo --arms bare,placebo,claude_md,recall
```
