# The bench corpus certifies, and a calibrated recall arm abstains

Measured 2026-08-29, against the `absent` condition's feed, after `abstention-002` finished.

This is a **feasibility result, not an endpoint measurement**. It answers one question: can the
benchmark serve recall in the certified configuration it actually ships, rather than with
`RECALL_TRUST_MODE=development` and no calibration? The answer is yes, and the numbers are here so
the re-run does not have to rediscover them.

## Why it was needed

`abstention-002` measured endpoint 3, the abstention rate, at **0.000 across all 351 sessions**.
The arm ran with the trust gate relaxed, and the server says so at startup:

> `RECALL_TRUST_MODE=development`: the trust gate is RELAXED for this server. Uncalibrated and
> unbound corpora will be served instead of refused.

So that run measured whether the MODEL declines. It could not measure whether the PRODUCT does.

There is a second, sharper reason. `adapters/recall/instruction_appendix.md` tells the agent, in
recall's own words, that `DEGRADED:INDEX_NOT_READY` appears on every result and "the threshold is a
placeholder rather than a measurement". The MemPalace appendix carries no equivalent caveat because
MemPalace ships no such banner. That is honest on both sides and it still means **recall's system
prompt tells the agent recall is unreliable while its competitor's does not**.

⛔ The fix is NOT to flip the trust mode. Under strict, an uncalibrated corpus abstains on
everything and scores worse. The fix is to calibrate, so the caveat stops being true and can be
removed with it, in the same change.

## The pipeline, and the three things that are not obvious

```
recall manifest inventory <feed> --output objects.json
recall --tenant T manifest create --corpus-version V --objects objects.json --output manifest.json
recall --tenant T generation build manifest.json --unverified-development
recall --tenant T generation validate <gen>
recall --tenant T calibration calibrate --generation <gen> --queries <queries> --publish
RECALL_ENV=production recall --tenant T generation promote <gen>
```

1. `manifest inventory` emits an object LIST. `generation build` wants a canonicalised manifest, so
   `manifest create` sits between them, and skipping it gives `manifest root must be an object`.
2. The manifest carries its own tenant, so `--tenant` belongs on **create**, not only on build.
   Otherwise: `manifest tenant 'default' does not match authenticated tenant`.
3. `promote` refuses under a development environment (`development promotion requires
   unsafe_development=True`). Promotion is a production operation, which is the target anyway.

`recall index` refuses under `RECALL_ENV=production`, so the adapter's current ingest and the
calibrated configuration are mutually exclusive. Switching is a rewrite of the ingest path, not a
flag.

## Measured

Generation `gen_2f40f943b7314f278209ceebb2779d05`: **121 sources, 633 chunks**, validated `ready`,
promoted to active. Calibration `cal_dcd44ceeb1fc455db6091b554462e5c1`, lifecycle `published`:

```
certification_reason: separability 1.000 [1.000, 1.000] over 20/26 samples
query_set_digest:     20e914c915df9a88ace0a47a65a2000063bea9d66fd480394633fd6c19e0faeb
embedder:             fastembed BAAI/bge-small-en-v1.5, 384d
```

That matches what `validate_queryset.py` predicted from the live corpus before any calibration
existed: answerable min 0.746 against unanswerable max 0.743, zero overlap either way.

⚠️ The margin is 0.003. Separability is 1.000 because the ordering is perfect, not because the gap
is wide, and carry-forward onto the three planted corpora is where that thinness will show.

## The gate fires

Served under `RECALL_ENV=production` with strict trust, via the MCP server the arm actually uses:

| query | abstained | trust_state | calibrated |
|---|---|---|---|
| how are invoice totals rounded to cents | `False` | trusted | true |
| what is our kubernetes pod eviction policy | **`True`** | trusted | true |
| what timezone are the timestamps in app.log | **`True`** | trusted | true |

The third row is the point. On the `absent` corpus that fact is deliberately withheld, and the
calibrated server declines the question the relaxed run answered.

⚠️ **Abstention is a FLAG on the response, not an empty result**: `n_results` was 5 on both
abstained rows. The harness scores endpoint 3 from decline markers in the agent's PROSE, so the
chain is server abstains → agent notices the flag → detector sees a marker. The re-run therefore
measures *the agent honouring the product's refusal*, which is a more honest quantity than either
half alone, and must be reported in those words rather than as "the product abstains".

## Operational note

The build died once with an onnxruntime `bad allocation` at `RECALL_FASTEMBED_BATCH=16`, with
2,758 MB free while another session ran its own test suite. It completed at **batch 4** (a ~50 MB
attention buffer against ~201 MB). Batch size does not change the vectors: measured bit-identical
at batch 4 and 64, recorded in preregistration 013.

## What remains

1. Certify the other three conditions. Calibrate once on `absent` and **carry forward**, so one
   fixed threshold serves all four and cross-condition abstention is not confounded by a refitted
   threshold per corpus.
2. Replace the adapter's `recall index` ingest with this pipeline, and put `RECALL_ENV=production`
   with strict trust in the server env.
3. Remove the `INDEX_NOT_READY` caveat from `instruction_appendix.md` and `skill.md` **in the same
   change**, never before: today it is true of the corpus the harness serves, and removing it early
   would put a false claim in recall's favour into its own system prompt.
4. Extend the preflight to assert `trust_state=trusted` and `calibrated=true`, because a promoted
   but unbound corpus would fail as silently as the dead server did.
5. Preregister, because this changes what endpoint 3 measures and alters the arm's frozen prompt
   hash, then re-run.

This work belongs on the MemPalace lineage, since that is where the comparison runs.
