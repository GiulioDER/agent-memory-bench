# Preregistration 096: Code 4 plus Context 4 protected suffix replay

Status: frozen when committed. No evidence-build output or Task Solve result from this experiment
may be inspected before the commit that adds this record.

## Question

Can session-aware Context 4 contribute complementary coding-memory evidence when it is restricted
to two suffix slots and the proven Code 4 top-10 prefix is preserved exactly?

This is the protected cross-model experiment licensed by preregistration 095. It is not an
equal-peer fusion, does not compare raw scores across embedding spaces, and does not allow Context
4 to displace any Code 4 evidence in ranks 1 through 10.

## Prior evidence and boundary

Preregistration 091 showed that Code 4 plus BM25 produced eight net paired Task Solve wins over
Code 3 across 100 admitted cells. Preregistration 095 then showed that Context 4 is a poor direct
replacement: source recall at 10 fell from 34/34 to 30/34, mean reciprocal rank fell from 0.8464
to 0.5997, and exact first-relevant rank produced zero wins and 16 regressions.

Context 4 nevertheless retrieved relevant raw windows absent from the Code 4 top 100 for 16 of 34
queries, with mean top-100 Jaccard similarity 0.5126. That passed the frozen protected-fusion
license. The current experiment tests only whether this complementary window set helps as a small
suffix after the complete Code 4 prefix.

## Frozen source and corpus

The source checkout before this preregistration is
`8b7befef61ed182a615878fd42b6bdc0fa21e954`. The corpus manifest is `corpus/manifest.json`
with SHA-256 `58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.

The manifest contains 196 session entries and deterministically produces 1,220 raw windows at 160
words with a 120-word stride. The query roster is all 34 primary tasks returned by
`harness.tasks.discover_tasks()` in task-id order. Each original task prompt is the query. A source
session is relevant exactly when its manifest path is under `sessions/<task_id>/`.

## Frozen evidence build

One paid evidence build runs on VPS2 under the shared embedding lock. There is no retry or
replacement build if its gate fails. It builds the same three rankings used by preregistration
095:

1. Code 4 dense top 100 from `voyage-code-4` standard document and query embeddings.
2. Context 4 dense top 100 from `voyage-context-4`, with all ordered raw windows from one manifest
   session encoded as one contextualized document group.
3. The shared canonical BM25 top 100.

Code 4 and Context 4 each fuse only with the shared BM25 ranking by unweighted reciprocal-rank
fusion with constant 60. Their vectors and raw scores are never compared. Each model enforces a
500,000 document-token ceiling before its first paid call. Context 4 uses 1,024-dimensional
float32 vectors and must preserve document-group and window alignment.

For each task, `code4_12_replay` receives the first 12 windows from the Code 4 plus BM25 ranking.

For each task, `code4_context4_suffix_12_replay` receives the first 10 Code 4 plus BM25 windows in
exactly the same order. Ranks 11 and 12 are then filled by the first two windows in the Context 4
plus BM25 ranking that are absent from the protected Code 4 top 10. If fewer than two such windows
exist, the build fails rather than changing the policy or duplicating evidence.

Both arms therefore receive exactly 12 raw windows. The treatment changes only two suffix slots.
It is allowed to select a window that appears below rank 12 in the Code 4 ranking, because the
question is whether Context 4 can promote a complementary candidate. No gold label, task ID,
checker content, answer map, generated summary, or outcome is used in suffix selection.

The evidence artifact records every ordered window index, source path, text hash, model identity,
and whether each treatment suffix window appears elsewhere in the Code 4 top 100.

## Frozen evidence gates

The Task Solve grid runs only if the one-shot build passes all of these gates:

1. Every task has exactly 12 validated windows in each arm.
2. The first 10 window indices are byte-for-byte identical between arms for every task.
3. Every treatment has exactly two suffix windows selected by the frozen Context 4 rule, with no
   duplicate index inside the treatment evidence.
4. Code 4 source recall at 10 remains 34/34.
5. The treatment loses no source recall or complete-shard coverage at rank 12 relative to control.
6. A treatment suffix contains at least one relevant raw window for at least 12 queries.
7. The treatment introduces a relevant raw window absent from the control top 12 for at least
   eight queries.
8. Mean estimated evidence tokens remain within 10 percent between arms.

Failure stops the experiment. The evidence build is not repeated to obtain a favorable draw.

## Frozen Task Solve arms and grid

Both arms receive the identical task fixture, user prompt, generic repository rules, evidence
wrapper, evidence count, participant model, seeds, tools, timeout, isolation, checker, and signed
adjudication path. Evidence appears before the shared static repository notes. Neither arm
receives an MCP server, autonomous memory-search instruction, hidden oracle bundle, checker
content, or evidence outside its frozen 12-window list.

The participant model is `deepseek/deepseek-v4-flash`. Seeds are 0, 1, and 2. The 34 primary tasks
run under both arms, producing 204 sessions and 102 paired cells before exclusions. The runner uses
`AMB_BLOCK_CONCURRENCY=3`, so three task-seed cells and six participant sessions may be in flight.
At least 90 paired cells must be admitted.

The modification stratum is frozen as:

`ts-append-only`, `ts-atomic-write`, `ts-bool-env`, `ts-config-layer`, `ts-crlf-export`,
`ts-golden-regen`, `ts-ignore-gen`, `ts-legacy-hash`, `ts-log-mask`, `ts-quote-shell`,
`ts-retry-cap`, `ts-schema-additive`, `ts-semver-pin`, and `xs-evolve-lease`.

The new-artifact stratum is frozen as:

`fa-dedup-key`, `ts-base36-id`, `ts-bom-merge`, `ts-casefold-sort`, `ts-cli-exitcode`,
`ts-csv-quote`, `ts-dedup-order`, `ts-empty-input`, `ts-glob-hidden`, `ts-idempotent-run`,
`ts-json-sorted`, `ts-manifest-rel`, `ts-mig-name`, `ts-natural-order`, `ts-nfc-count`,
`ts-round-money`, `ts-stable-sort`, `ts-tz-utc`, `xs-join-batch`, and `xs-widen-manifest`.

The Context 4 candidate-novelty subgroup is frozen from preregistration 095 as:

`fa-dedup-key`, `ts-base36-id`, `ts-bom-merge`, `ts-crlf-export`, `ts-dedup-order`,
`ts-empty-input`, `ts-glob-hidden`, `ts-golden-regen`, `ts-json-sorted`, `ts-legacy-hash`,
`ts-log-mask`, `ts-mig-name`, `ts-natural-order`, `ts-nfc-count`, `xs-join-batch`, and
`xs-widen-manifest`.

The intended runner environment and command are:

```text
AMB_BLOCK_CONCURRENCY=3 python -m scripts.pilot \
  --run-id code4-context4-suffix-001 \
  --namespace code4-context4-suffix-001 \
  --arms code4_12_replay,code4_context4_suffix_12_replay \
  --tasks <the 34 task ids above, comma separated> \
  --seeds 3 \
  --model deepseek/deepseek-v4-flash \
  --specialist-retrieval-artifact results/retrieval/096-code4-context4-suffix-evidence.json \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

## Endpoints

The primary endpoint is paired checker success for the protected-suffix treatment versus the
Code 4 control across admitted task-seed cells, reported as both-success, treatment-only,
control-only, both-fail, net wins, and paired success-rate difference.

Secondary endpoints are:

1. The same paired outcome in the modification and new-artifact strata.
2. The same paired outcome in the frozen Context 4 candidate-novelty subgroup.
3. Per-task paired outcomes across three seeds.
4. Participant errors, timeouts, failed tool calls, model turns, input and output tokens, wall
   time, and estimated spend by arm.
5. Injected evidence tokens, prompt hashes, ordered window indices, and source-path overlap.
6. Whether each treatment-only or control-only outcome received a relevant Context 4 suffix
   window under the frozen source labels.

## Predictions frozen before implementation

1. The evidence build will pass all eight gates.
2. The protected suffix will produce at least three net paired Task Solve wins overall.
3. The Context 4 candidate-novelty subgroup will produce at least two net paired wins.
4. Neither frozen task stratum will be worse by more than one net cell.
5. The treatment will have no more participant errors or timeouts than control plus one cell.
6. Mean input tokens will remain within 10 percent and mean wall time within 20 percent because
   both arms receive the same evidence count and wrapper.

## Decision rule

The protected suffix advances into the official CAMBench Coding candidate only if the evidence
build passes, at least 90 paired cells are admitted, the treatment has at least three net paired
wins overall, neither task stratum is worse by more than one net cell, and prediction 5 passes.

If the treatment does not pass, the official coding candidate remains the single-model Code 4
configuration established by preregistration 091. A failure closes this exact two-slot suffix
policy. It does not reopen equal-peer fusion, direct Context 4 replacement, vector concatenation,
or multimodal routing.

<!-- results and append-only corrections go below this line; everything above is frozen -->

## Evidence build result, 2026-09-20

The one-shot evidence build failed gate 6 and stopped before Task Solve. No participant model call
was made.

The build ran from apparatus commit `4077865bf4f0b8c57acbe4954e9aabcc5d671d18` on VPS2 under
the shared embedding lock. Each model processed 347,634 document tokens by the vendor tokenizer.
Context 4 encoded all 1,220 windows as 196 intact session groups in 21 requests, with no split
session or alignment error.

Seven of eight frozen gates passed:

| Evidence endpoint | Result | Gate |
| --- | ---: | --- |
| tasks with 12 windows per arm | 34/34 | pass |
| tasks with identical Code 4 top-10 prefix | 34/34 | pass |
| tasks with two unique Context 4 suffix windows | 34/34 | pass |
| Code 4 source recall at 10 | 34/34 | pass |
| source recall at 12, control and treatment | 34/34, 34/34 | pass |
| complete-shard coverage at 12, control and treatment | 33/34, 33/34 | pass |
| queries with a relevant Context 4 suffix | 11/34 | **fail, required 12** |
| queries with new relevant evidence versus control top 12 | 9/34 | pass, required 8 |
| mean treatment to control evidence-token ratio | 1.0082 | pass |

Because gate 6 missed by one query, the preregistered stop rule applies. The 204-session
three-worker Task Solve grid is not licensed and was not started. The threshold is not lowered
after inspection.

All 34 queries selected at least one suffix candidate that also appeared somewhere in the Code 4
top 100. The tested policy therefore acted primarily as a Context 4 reprioritizer over Code 4's
existing candidate pool. It did not isolate the genuinely model-specific candidates observed in
preregistration 095. A future experiment, if pursued, must receive a new preregistration and use
an explicit gold-blind novelty rule rather than modifying this result.

Evidence:

* `results/retrieval/096-code4-context4-suffix-evidence.json`, SHA-256
  `12549dbc27e37ab2d6a2d9a40ad0ce0953bd3cda5e0392fdf9d730aac71aa509`
* `results/retrieval/096-code4-context4-suffix-evidence.log`, SHA-256
  `2178585918c94390add77ca892db8707c4d508b091e31a8bf33516d24dcbd836`
* evidence builder SHA-256
  `2b28c54ee52a75eba38383a6c3cab5ac82b0900c8fcabdebb84b6aaf2e37c663`
