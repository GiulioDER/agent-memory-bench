# official-005-graphiti-bare: Graphiti vendor run on VPS2

Status: DRAFT until committed. The prediction block is frozen above the results marker before
the first live measurement.

## Question

Does the official Graphiti integration change task outcomes relative to the bare control across
the present corpus and the four adversarial corpus conditions, using the same DeepSeek benchmark
model and the same isolated harness?

## Arms and fixed configuration

| arm | integration | participant surface |
|---|---|---|
| `bare` | no memory integration | no memory tools |
| `graphiti` | official Graphiti MCP server through the brokered bridge | six read and status tools only |

The model is `deepseek/deepseek-v4-flash`, reached through the trusted VPS2 model broker. The
Graphiti upstream pin, disposable FalkorDB store, broker allowlist, controller only ingestion,
and six tool allowlist remain those already verified for the Graphiti adapter. The participant
cannot write to Graphiti. The OpenRouter credential is read from the VPS2 secret file outside the
repository and is never stored in this record, a participant environment, or a result artifact.

Each condition is assembled into its own corpus directory and Graphiti namespace. Graphiti
ingestion runs once per condition before that condition's task and seed cells, then the same
namespace is reused by every Graphiti cell in that condition. The `present` corpus contains the
real precursor. `absent` withholds it. `superseded` contains the real and stale precursors.
`contradictory` contains two rival undated decisions without an authoritative member.
`adjacent` contains a confident decision about a different subsystem while withholding the real
precursor. The intentionally non measurable `ts-base36-id` contradictory plan is excluded by the
task selector and is not silently treated as a zero.

## Frozen grid

The runner's selection function is frozen at launch and announces retired tasks. The resulting
task counts are:

| condition | selected tasks | seeds | arms | cells |
|---|---:|---:|---:|---:|
| `present` | 27 | 5 | 2 | 270 |
| `contradictory` | 10 | 5 | 2 | 100 |
| `adjacent` | 11 | 5 | 2 | 110 |
| `absent` | 12 | 5 | 2 | 120 |
| `superseded` | 11 | 5 | 2 | 110 |

The condition total is 710 session cells. No task is removed after launch. The four retired tasks
are excluded before assembly and are recorded by the runner's retirement messages.

The exact runner is:

```bash
.venv/bin/python -m scripts.abstention \
  --run-id official-005-graphiti-bare \
  --namespace amb-graphiti-official-005 \
  --conditions present,contradictory,adjacent,absent,superseded \
  --arms bare,graphiti \
  --seeds 5 \
  --model deepseek/deepseek-v4-flash \
  --memory-instruction skill \
  --resume \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

The run is executed on VPS2 with rootless Docker, the pinned participant and checker image
digests, the benchmark network policy digest, signed per session broker capabilities, and the
trusted adjudication receipt path. A failed preflight prevents any participant session.

## Endpoints and predictions

1. Primary: paired Graphiti versus bare success by task and condition, with exact discordance and
   per task cluster bootstrap intervals.
2. Secondary: Graphiti search rate, tool mix, successful MCP calls, episode visibility, node and
   fact evidence, and governing marker retrieval rate.
3. Integrity: admitted and discarded cells, setup checks, prompt and configuration digests,
   condition manifest digests, model and CLI versions, wall time, tokens, and estimated cost.

Predictions made before the live run:

1. The preflight will pass and Graphiti will expose exactly the six allowed participant tools.
2. Graphiti will search in at least 50% of admitted sessions and produce nonzero node or episode
   evidence.
3. Graphiti's mean success will be within 0.10 of bare overall. The direction is uncertain.
4. The contradictory and adjacent conditions will produce nonzero attributable damage in at least
   one Graphiti task, while the present condition will not classify abstention as a benefit.
5. Fewer than 10% of task seed cells will be discarded. A session error is a discard, not a zero.

## Exclusion and stop rules

The existing admission gate is frozen. A cell is admitted only when both arms produce valid
records and matching setup metadata. The run stops before starting a new cell if the hard cost cap
is reached. A partial condition is archived and receives a new run ID; it is never mixed into a
later attempt. Results are not promoted unless the ordinary verifier and trusted adjudication
receipt both pass.

<!-- results are appended below this line; everything above is frozen -->
