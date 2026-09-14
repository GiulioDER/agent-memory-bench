# official-008-recall-context4: RE-call Voyage Context 4 benchmark

Status: DRAFT until committed. This is a fresh RE-call measurement after the previous official
arms. It uses new condition tenants and new session records; no episodes, generations, or results
from the older `voyage:voyage-4` RE-call arm are reused.

## Question

Does the current RE-call release, using the registered Voyage Context 4 embedder and the current
generation/graph serving path, change coding-task outcomes relative to the bare control across the
present corpus and the four adversarial corpus conditions?

## Fixed implementation

The RE-call source of truth is the GitHub branch `codex/voyage-context4-production-20260913` at
commit `5366770ea96a8ee4438a3bc8a749f521a20e4335`, package version `0.13.0`. VPS2 is required to
serve that exact commit from a clean detached checkout. The old serving checkout is retained only
as a rollback target and is not part of this run.

The measured RE-call profile is `voyage-context:voyage-context-4`, registered as
`voyage-context-4-v1`, with 1024-dimensional contextualized embeddings, the
`voyage-context-document-v1` document grouping policy, and the production GenerationStore path.
Each condition receives its own immutable corpus, generation, calibration, and tenant. Generation
building and promotion happen before the suite; the benchmark only verifies and reads the prepared
generation during measurement. The current profile fingerprint is recorded in the run artifacts.

The RE-call participant surface is the existing frozen adapter: read/navigation tools only, no
write tools, with the shared `protocol` memory instruction and host MCP transport used by
`official-003`. This keeps the new result comparable to the published RE-call reference and
prevents the product-specific `skill` appendix from becoming an uncontrolled treatment. The bare
arm is the same benchmark control. No reranking or extra retrieval setting is introduced. On
VPS2, a dedicated signed capability relay fronts the RE-call stdio server; the
controller's preflight uses its loopback listener while participant containers use its Docker DNS
service name. Both endpoints terminate at the same relay process and enforce the same allow-list.

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
  --run-id official-008-recall-context4 \
  --namespace amb-recall-context4-official-008 \
  --conditions present,contradictory,adjacent,absent,superseded \
  --arms bare,recall \
  --seeds 5 \
  --model deepseek/deepseek-v4-flash \
  --memory-instruction protocol \
  --resume \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

The run is executed on VPS2 with the pinned participant and checker image digests, the benchmark
network policy digest, the trusted adjudication receipt path, durable logs, and a detached runner
that survives the launching session. The run uses no whole-ingest deadline; individual broker
transport requests retain their existing 180-second safety timeout.

## Predictions

1. VPS2 source, Python package, profile, and serving generation checks will agree with this record
   before the first measured cell.
2. RE-call preflight will expose exactly the frozen read/navigation tool surface and search will
   return evidence from the condition-specific Context 4 generation.
3. RE-call's mean task success will be within 0.10 of bare overall. The direction is uncertain.
4. Context 4 will improve or preserve the older RE-call arm's retrieval attribution on at least one
   adversarial condition, but no condition-level benefit is assumed in advance.
5. Fewer than 10% of task-seed cells will be discarded. A session error is a discard, not a zero.

## Exclusion and stop rules

The existing admission gate is frozen. A cell is admitted only when both arms produce valid records
and matching setup metadata. The run stops before a new cell if the hard cost cap is reached. A
partial condition is archived and receives a new run ID; it is never mixed into this run. Results
are not promoted unless the ordinary verifier and trusted adjudication receipt both pass.

The run is invalid and must not publish a score if any measured process resolves to a RE-call SHA
other than `5366770e`, if a condition tenant serves a different corpus fingerprint, if the Context
4 profile or generation lineage differs from this record, or if the old `voyage:voyage-4` profile is
used by any RE-call measured session.

<!-- results are appended below this line; everything above is frozen -->
