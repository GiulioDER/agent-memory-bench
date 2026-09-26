# official-007-graphiti-bare: no-deadline Graphiti vendor run on VPS2

Status: DRAFT until committed. This is a fresh run after the archived partial attempts for
`official-005-graphiti-bare` and `official-006-graphiti-bare`; it uses a new run ID and Graphiti namespace and never mixes their
episodes or session records.

## Question

Does the official Graphiti integration change task outcomes relative to the bare control across
the present corpus and the four adversarial corpus conditions, using the same DeepSeek benchmark
model and isolated harness?

## Fixed protocol

The arms are `bare` and `graphiti`. The model is `deepseek/deepseek-v4-flash`. The Graphiti
upstream pin, FalkorDB backend, broker allowlist, controller-only ingestion, and six participant
read and status tools are unchanged from preregistration 082. The participant cannot write to
Graphiti.

The repaired controller rotates its signed controller-only Graphiti capability for each broker
request. Broker HTTP failures retain their response reason, and ingestion failures write a
diagnostic artifact before the run exits. Whole-ingest timeout is disabled because the official
Graphiti queue is asynchronous and serial; each short MCP request retains a bounded transport
timeout. Progress is emitted whenever the visible episode count changes. These are execution
reliability repairs; they do not change the measured participant surface or scoring rules.

## Frozen grid

| condition | selected tasks | seeds | arms | cells |
|---|---:|---:|---:|---:|
| `present` | 27 | 5 | 2 | 270 |
| `contradictory` | 10 | 5 | 2 | 100 |
| `adjacent` | 11 | 5 | 2 | 110 |
| `absent` | 12 | 5 | 2 | 120 |
| `superseded` | 11 | 5 | 2 | 110 |

Total: 710 session cells. The `ts-base36-id` contradictory plan remains excluded as specified by
the original preregistration.

The exact runner is:

```bash
.venv/bin/python -m scripts.abstention \
  --run-id official-007-graphiti-bare \
  --namespace amb-graphiti-official-007 \
  --conditions present,contradictory,adjacent,absent,superseded \
  --arms bare,graphiti \
  --seeds 5 \
  --model deepseek/deepseek-v4-flash \
  --memory-instruction skill \
  --resume \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

The run is executed on VPS2 with rootless Docker, the pinned participant and checker image
digests, the benchmark network policy digest, signed per-session broker capabilities, a fresh
Graphiti namespace, durable stdout and stderr logs, and the trusted adjudication receipt path.

## Predictions

1. Preflight will pass and Graphiti will expose exactly the six allowed participant tools.
2. Graphiti will search in at least 50% of admitted sessions and produce nonzero node or episode
   evidence.
3. Graphiti's mean success will be within 0.10 of bare overall. The direction is uncertain.
4. Contradictory and adjacent conditions will produce nonzero attributable damage in at least one
   Graphiti task, while present will not classify abstention as a benefit.
5. Fewer than 10% of task seed cells will be discarded. A session error is a discard, not a zero.

## Exclusion and stop rules

The existing admission gate is frozen. A cell is admitted only when both arms produce valid
records and matching setup metadata. The run stops before a new cell if the hard cost cap is
reached. A partial condition is archived and receives a new run ID; it is never mixed into a
later attempt. Results are not promoted unless the ordinary verifier and trusted adjudication
receipt both pass.

<!-- results are appended below this line; everything above is frozen -->
