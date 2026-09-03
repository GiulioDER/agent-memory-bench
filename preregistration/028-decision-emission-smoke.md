# 028: decision-emission-smoke, does the live Claude stream carry the decision object?

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

When the pilot is run with `--emit-decisions`, does Claude Code emit one schema constrained
terminal decision object that the benchmark records in `runtime_decisions`?

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `bare` | none | no memory surface |

The smoke uses the bare arm so that this is an instrumentation check, not a memory comparison.

## Grid

One session: task `ts-base36-id`, seed `0`, model `deepseek/deepseek-v4-flash`, Claude Code
version as reported by the live init event, timeout 600 seconds, and the standard denied Docker
tools. The run uses `--emit-decisions` and the current benchmark schema. No result from this smoke
will be pooled with an official task comparison.

## Endpoints, in reporting order

1. Primary: the raw stream contains a terminal structured decision with `decision` and numeric
   `confidence`.
2. The resulting record contains the same decision under `runtime_decisions`, with a source naming
   the terminal result rather than a memory tool.
3. The recorded confidence is in the closed interval 0 to 1.
4. The ordinary task checker still produces a verdict and the session remains verifiable.

## Prediction

I predict endpoint 1, endpoint 2 and endpoint 3 will pass, and endpoint 4 will remain unchanged.
The likely live shape is either `result.structured_output` or an exact JSON string in the terminal
`result` field. The parser must not accept a decision embedded in prose.

## Exclusion and truncation rules

The smoke is invalid if the process does not produce a result event, if the stream is malformed, or
if the session is discarded by the normal setup or admission checks. There is no truncation rule:
one session is the complete smoke.

## What would falsify this

The instrumentation is not ready for a live benchmark if the CLI rejects `--json-schema` with the
stream format, emits no structured terminal object, or the parser fails to persist an explicit
decision that is present in the raw stream.

<!-- results are appended below this line; everything above is frozen -->

## Results appended, 2026-09-03

The corrected smoke ran on the serving host from benchmark commit `59dddff0` under
`decision-emission-smoke-20260903-matched`. Both sessions were admitted and both produced a
terminal `structured_output` object in the raw gzip stream:

| arm | terminal object | recorded decision | confidence | checker |
|---|---|---|---:|---|
| `bare` | present | `answer` | 1.0 | failed: produced `ORD-24GI`, expected `ORD-24GJ` |
| `protocol` | present | `answer` | 1.0 | failed: produced `ORD-24GI`, expected `ORD-24GJ` |

The two records contain `runtime_decisions` with source `result.structured_output`, and the raw
streams contain the same decision and confidence. The process produced 45,883 model tokens and the
estimated spend was $0.003. `scripts.verify_run` passed the session, token, discard, admission and
stream consistency checks. The checker failures are task outcomes and do not falsify the decision
emission question.

## Setup correction, 2026-09-03, before any model session

The first launch was refused before a Claude process started because the existing setup gate
requires `instruction_arms_matched: true`, and a bare only grid has no matched instruction. The
refusal spent no model tokens and produced no session record.

The smoke is therefore rerun under `decision-emission-smoke-20260903-matched` with the same task,
seed, model and output contract, but with two arms: `bare` and `protocol`. The shared protocol is
used so the normal instruction parity check remains meaningful. The endpoints and prediction above
are unchanged; the grid now contains two sessions instead of one.
