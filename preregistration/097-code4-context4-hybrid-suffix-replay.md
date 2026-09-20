# Preregistration 097: Code 4 plus Context 4 hybrid suffix replay

Status: frozen when committed. No evidence-build output or Task Solve result from this experiment
may be inspected before the commit that adds this record.

## Question

Can a two-slot suffix that combines one Context 4 promotion with one genuinely Context-unique
candidate improve Task Solve while preserving the proven Code 4 top-10 prefix?

This is a new policy after preregistration 096 failed its evidence gate. The failed threshold is
not changed and its artifact is not reused as a result. The new policy addresses the measured
mechanism: all suffix candidates selected by 096 already existed in the Code 4 top 100, so the
test did not isolate the model-specific candidate pool that licensed fusion in preregistration
095.

## Frozen source, corpus, and models

The source checkout before this preregistration is
`a3581e7e7d04e03d5689e971c80d1223ecdcf05b`. The corpus manifest is `corpus/manifest.json`
with SHA-256 `58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.

The manifest contains 196 sessions and produces 1,220 raw windows at 160 words with a 120-word
stride. The query roster is the same 34 primary coding tasks used by preregistrations 090, 091,
095, and 096. Source relevance remains manifest path membership under `sessions/<task_id>/`.

One paid build runs on VPS2 under the shared embedding lock. Code 4 uses
`voyage-code-4` standard document and query embeddings. Context 4 uses
`voyage-context-4` through the contextualized endpoint, grouping all ordered windows from one
session as one document. Both use 1,024-dimensional float32 vectors and a hard ceiling of 500,000
document tokens before paid calls.

Each dense top 100 is fused only with the shared canonical BM25 top 100 by unweighted
reciprocal-rank fusion with constant 60. Code 4 and Context 4 vectors and raw scores are never
compared.

## Frozen hybrid suffix policy

`code4_12_replay` receives Code 4 plus BM25 ranks 1 through 12.

`code4_context4_hybrid_12_replay` receives the identical Code 4 plus BM25 ranks 1 through 10,
followed by two gold-blind Context 4 suffix selections:

1. Rank 11 is the first Context 4 plus BM25 candidate absent from the protected Code 4 top 10.
2. Rank 12 is the first remaining Context 4 plus BM25 candidate absent from the entire Code 4 top
   100.

The two suffix indices must be distinct. If either slot cannot be filled, the build fails. The
selection rule cannot inspect source labels, task IDs, checkers, answer maps, generated summaries,
or participant outcomes. Both arms contain exactly 12 original raw windows.

The evidence artifact records both model rankings through depth 100, every selected window index,
source path, text hash, model identity, Code 4 rank when present, and Context 4 rank. Recording the
full rankings prevents another paid embedding build merely to audit a deterministic suffix rule.

## Frozen evidence gates

Task Solve runs only if the one-shot build passes every gate:

1. Every task has exactly 12 validated windows per arm.
2. The first 10 window indices are identical between arms for all 34 tasks.
3. Every treatment has one valid promotion slot and one distinct candidate absent from the Code 4
   top 100.
4. Code 4 source recall at 10 remains 34/34.
5. The treatment loses no source recall or complete-shard coverage at rank 12 relative to control.
6. The explicitly Code-unique slot is relevant for at least eight queries.
7. The treatment introduces relevant evidence absent from control top 12 for at least eight
   queries.
8. Mean estimated evidence tokens remain within 10 percent between arms.

Failure stops the experiment without a retry or Task Solve call.

## Frozen Task Solve grid

If the evidence gate passes, both arms receive the identical task fixture, user prompt, generic
repository rules, evidence wrapper, 12-window evidence count, participant model, seeds, tools,
timeout, isolation, checker, and signed adjudication path. Evidence order is preserved. Neither arm
receives an MCP server or autonomous memory-search instruction.

The participant model is `deepseek/deepseek-v4-flash`. Seeds are 0, 1, and 2. All 34 tasks run
under both arms, producing 204 sessions and 102 paired cells before exclusions. The run uses
`AMB_BLOCK_CONCURRENCY=3` as requested. At least 90 paired cells must be admitted.

The modification and new-artifact strata are exactly those frozen in preregistration 096. The
candidate-novelty subgroup is the same 16-task list frozen there from preregistration 095.

The intended runner environment and command are:

```text
AMB_BLOCK_CONCURRENCY=3 python -m scripts.pilot \
  --run-id code4-context4-hybrid-001 \
  --namespace code4-context4-hybrid-001 \
  --arms code4_12_replay,code4_context4_hybrid_12_replay \
  --tasks <the frozen 34 task ids> \
  --seeds 3 \
  --model deepseek/deepseek-v4-flash \
  --specialist-retrieval-artifact results/retrieval/097-code4-context4-hybrid-evidence.json \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

## Endpoints and predictions

The primary endpoint is paired checker success across admitted cells, reported as both-success,
treatment-only, control-only, both-fail, net wins, and paired success-rate difference.

Secondary endpoints are the paired result by frozen stratum, by the candidate-novelty subgroup,
and by task, plus participant errors, timeouts, failed tool calls, model turns, token counts, wall
time, estimated spend, injected evidence identities, and whether discordant cells received a
relevant explicitly novel suffix window.

Predictions frozen before implementation:

1. The evidence build will pass all eight gates.
2. The treatment will produce at least three net paired Task Solve wins overall.
3. The candidate-novelty subgroup will produce at least two net paired wins.
4. Neither task stratum will be worse by more than one net cell.
5. The treatment will have no more participant errors or timeouts than control plus one cell.
6. Mean input tokens will remain within 10 percent and mean wall time within 20 percent.

## Decision rule

The hybrid suffix advances into the official CAMBench Coding candidate only if the evidence build
passes, at least 90 paired cells are admitted, the treatment has at least three net paired wins,
neither task stratum is worse by more than one net cell, and prediction 5 passes.

Otherwise the official candidate remains the single-model Code 4 configuration established by
preregistration 091. A failure closes this exact promotion-plus-novelty suffix policy and does not
reopen equal-peer fusion, direct Context 4 replacement, or vector-space mixing.

<!-- results and append-only corrections go below this line; everything above is frozen -->

## Evidence build result, 2026-09-20

The one-shot build failed gate 6 and stopped before Task Solve. No participant model call was
made.

The build ran from apparatus commit `5837a37a0a2d56c4096219e943b9f7e94caca456` on VPS2 under
the shared embedding lock. Each model processed 347,634 document tokens by the vendor tokenizer.
All 1,220 Context 4 windows retained their 196 session groups and response alignment.

Seven of eight gates passed. All 34 tasks had equal 12-window arms, identical Code 4 top-10
prefixes, distinct promotion and Code-4-unique suffix slots, Code 4 recall 34/34 at rank 10, equal
source recall 34/34 at rank 12, equal complete-shard coverage 33/34, and a mean treatment to
control evidence-token ratio of 1.0055.

The treatment introduced relevant evidence absent from the control top 12 for 10 queries, above
the frozen minimum of eight. The promotion slot itself was relevant for seven queries. The
explicitly Code-4-unique slot was relevant for only five queries, below the frozen minimum of
eight, so gate 6 failed and the three-worker Task Solve grid was not licensed.

Together with preregistrations 095 and 096, this localizes the limitation. Context 4 has broad
candidate novelty, but its earliest model-specific candidates are not precise enough to consume a
scarce coding evidence slot under a gold-blind rule. The exact hybrid policy is closed. The
single-model Code 4 configuration from preregistration 091 remains the official coding candidate.

Evidence:

* `results/retrieval/097-code4-context4-hybrid-evidence.json`, SHA-256
  `44f145e839dfd0f0cbdad7ff2b04f37952fb0fc28f1f4a4263fd8edc7a329661`
* `results/retrieval/097-code4-context4-hybrid-evidence.log`, SHA-256
  `772afb5e80b179dd239ec7ce44e1995a338167c3bfdb8bbd76a0df0de0d94537`
* evidence builder SHA-256
  `61733f04a6c061bc8e190cf03e7942dc25f3f73647dda7a5a214157afa272029`
