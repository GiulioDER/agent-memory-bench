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

## Correction and robustness appendix, added 2026-08-25

This section was appended after the report was published. Nothing above it has been edited, and
`preregistration/004-claude-md-placebo.md` has not been touched at all: its results section stands
as written, including the discard sentence corrected below. A preregistration is evidence of what
was believed at the time, and correcting it in place would destroy the more useful artifact.

### The discard accounting above is imprecise

The Data quality section says eight cells were recall MCP startup failures and one cell was
discarded because its placebo arm did not pass admission. Rechecked against
`results/pilot-004-placebo/admission.json`, the true accounting is nine discarded cells covering
ten non-admitted arm sessions:

| Cell | Arm | Reason |
|---|---|---|
| ts-atomic-write seed 1 | placebo | provider `api_error`, session did not complete |
| ts-atomic-write seed 1 | recall | MCP server `recall` reported status `failed` |
| ts-atomic-write seed 2 | recall | MCP server `recall` reported status `failed` |
| ts-base36-id seed 1 | recall | MCP server `recall` reported status `failed` |
| ts-bom-merge seed 0 | recall | MCP server `recall` reported status `failed` |
| ts-casefold-sort seed 1 | recall | MCP server `recall` reported status `failed` |
| ts-empty-input seed 1 | recall | provider `api_error`, session did not complete |
| ts-ignore-gen seed 1 | recall | MCP server `recall` reported status `failed` |
| ts-legacy-hash seed 0 | recall | MCP server `recall` reported status `failed` |
| ts-legacy-hash seed 1 | recall | MCP server `recall` reported status `failed` |

Two things the original sentence obscured. No cell was discarded solely because of the placebo:
ts-atomic-write seed 1 also lost its recall session, so it would have been discarded anyway. And
one recall session was lost to a provider `api_error` rather than to MCP startup, which the
original sentence does not mention at all. The count of eight MCP startup failures is correct.

### Every discarded cell was discarded because a recall session failed

`bare` and `claude_md` never lost a cell in this run. That is a structural asymmetry rather than
bad luck: the recall arm is the only one carrying an MCP server, so it is the only arm that can
fail to wire up, and a cell dies whenever any arm does. The published recall rate is therefore
conditional on the recall wiring having worked, and the honest reading is that it measures recall
when recall is running, not recall including the times it does not start.

### Intention-to-treat sensitivity, exploratory and not preregistered

To see how much of the headline the discard rule is carrying, the same contrasts were recomputed
with the same estimator over all 72 complete cells, scoring the dropped sessions exactly as they
were recorded. This is a robustness check reported beside the preregistered analysis, not a
replacement for it, and the selection rule was not changed: the preregistered contrast remains the
per-protocol one over 63 admitted cells.

| Contrast | Per-protocol, 63 cells (preregistered) | Intention-to-treat, 72 cells |
|---|---|---|
| Recall minus `CLAUDE.md` | +0.1736 [+0.0486, +0.3125], p=.00183 | +0.1667 [+0.0417, +0.3056], p=.00183 |
| Recall minus bare | +0.1806 [+0.0139, +0.3472], p=.00098 | +0.1528 [-0.0000, +0.3056], p=.01273 |
| Placebo minus bare | +0.0556 [-0.0278, +0.1528], p=.21875 | +0.0417 [-0.0417, +0.1528], p=.45313 |
| `CLAUDE.md` minus placebo | -0.0486 [-0.1875, +0.0903], p=.45313 | -0.0556 [-0.1528, +0.0278], p=.28906 |

Arm rates under intention-to-treat: bare `30/72` (41.7%), placebo `33/72` (45.8%), `CLAUDE.md`
`29/72` (40.3%), recall `41/72` (56.9%).

Three readings follow. The primary recall versus `CLAUDE.md` result is robust to the discard rule:
the point estimate moves by 0.7 points, the interval still excludes zero, and the discordant counts
are identical at 13 to 1, because recall and `CLAUDE.md` both lose cells to the same nine
discarded pairs. The recall versus bare result is the fragile one: its interval lower bound falls
to zero and its p-value moves by an order of magnitude, so it should be quoted with that caveat.
And this is not a zero-filling artefact: two of the eight MCP-failed recall sessions succeeded at
the task anyway, so the intention-to-treat recall arm is not simply the admitted arm plus nine
losses.

Reproduce both columns, and note that the per-protocol column is expected to match `analysis.json`
exactly, which is what makes the script trustworthy:

```bash
python -m scripts.discard_sensitivity --run-id pilot-004-placebo --arms bare,placebo,claude_md,recall
```

### The MCP failures were a transient, and the harness now retries them

In run order across the seventy-two recall sessions, the eight startup failures sit at positions 4,
5, 7, 9, 13, 34, 36 and 37. There are none in the last thirty-four. A failure clustered in time and
uncorrelated with tasks is a transient, not a property of any task, and `mcp_server_errors` was
empty in all eight, so the run recorded that the server had failed without recording why.

Eight of seventy-two is an 11.1% per-session startup failure rate, and that number is what blocks
the competitor comparison rather than merely annoying it. A paired cell is admitted only when every
arm is wired, so an eight arm grid carrying five memory servers would admit a cell with probability
0.889 to the fifth power, about 0.55, if that rate held and the failures were independent. Against
an admission rule of 95%, the grid cannot be widened until the rate moves. The projection is
illustrative and its assumptions are stated; the direction is not in doubt.

`harness/memory_startup.py` was added in response, with two mechanisms:

1. A preflight probe that speaks MCP to the configured server over stdio before any session is
   paid for, using the exact command, arguments and environment block the session will use, and
   capturing the server's own stderr, which no session record has ever contained.
2. A bounded retry of a session whose treatment failed to wire up. The retry predicate reads the
   admission surface through the gate's own helpers and never reads `success`, the checker verdict,
   or anything the model did, because a retry rule that could see the outcome would be a rule for
   rerunning losses until they win. Every attempt, its outcome and its raw stream are recorded, and
   a failed attempt's stream and sandbox are renamed rather than overwritten.

A recovered cell is a cell this protocol would previously have discarded, so runs using the retry
publish a `recovered_sessions` list in `environment.json` beside the discard count. Reporting the
discard count alone would quietly change what that count means.

### Two disclosures appended 2026-08-29, nothing above them edited

**The artifacts this report names are not committed to the repository.** The Reproducibility
section above lists four paths under `results/pilot-004-placebo/`, and `git ls-files results`
does not return any of them. Every number in this report was computed from those files, and a
reader cannot currently check a single one. This is finding F7 of the
[2026-08-28 adversarial audit](../docs/audit/2026-08-28-adversarial-benchmark-audit.md): either
the run directory is committed or the documents citing it say plainly that it cannot be checked.
This is the saying so. The same holds for `midband-001`, cited by preregistration 008.

**This run's dollar figures are not comparable with `pilot-003-deepseek`'s.** It was priced at
`scripts/pilot.py`'s argparse defaults, 0.05866 / 0.11732, while `pilot-003-deepseek` used the
frozen preregistration 002 rates, 0.0574 / 0.1148, and neither artifact recorded which basis it
had used. The token counts are unaffected and reproduce exactly, so compare the two runs on
tokens. The arithmetic, and the separate question of cache reads priced as fresh input, are in
the [protocol change record](../docs/audit/2026-08-29-protocol-change-record.md). Prices are
required rather than defaulted from 2026-08-29, so this cannot recur silently.

**The grader that produced these outcomes has since changed.** Three protocol-sensitive fixes
landed on 2026-08-29: `ts-retry-cap` rejected correct solutions about 40% of the time, a checker
crash discarded a whole paired cell instead of failing one arm, and cache reads were priced as
fresh input. The recorded numbers above are left exactly as they are, and the retry-cap error was
symmetric across arms, so it inflated variance rather than biasing any contrast. A **new** run is
not protocol-identical to this one and the two must not be differenced.
