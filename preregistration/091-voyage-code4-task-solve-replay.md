# Preregistration 091: Voyage Code 4 Task Solve evidence replay

Status: frozen when committed. No evidence-build output or Task Solve result from this experiment
may be inspected before the commit that adds this record.

## Question

Does the early-ranking improvement from replacing `voyage-code-3` with `voyage-code-4` produce
more executable coding-task successes when both arms receive the same evidence budget and differ
only in which model supplied the dense ranking?

This is the Task Solve screen licensed by preregistration 090. It is not an official leaderboard
submission and does not combine Code 3 and Code 4. It tests a frozen evidence replay so agent
behavior is separated from embedding API latency, MCP availability, and autonomous search choice.

## Prior evidence and frozen source

Preregistration 090 compared Code 3 and Code 4 over the same 1,220 raw windows, shared canonical
BM25 top 100, unweighted reciprocal-rank fusion with constant 60, and all 34 primary task prompts.
Code 4 raised source recall at 10 from 28/34 to 34/34 and mean reciprocal rank from 0.5063 to
0.8464. Exact first-relevant rank improved for 21 queries, tied for 13, and regressed for zero.

This experiment starts from result commit
`4f79a449fe6fab262954b622e5684c3483c2a95d`. The corpus manifest is
`corpus/manifest.json` with SHA-256
`58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.
The manifest contains 196 sessions and deterministically produces 1,220 raw windows at 160 words
with a 120-word stride.

## Frozen evidence build

One paid evidence build will run on VPS2 under the shared embedding lock. There is no retry or
replacement build if its retrieval gate fails. It embeds the same 1,220 windows sequentially with
`voyage-code-3` and `voyage-code-4`, using `input_type="document"`, and embeds each task prompt
with `input_type="query"`. The hard document-token ceiling is 500,000 per model.

For each task and model, the dense top 100 is fused with the same canonical BM25 top 100 by
unweighted reciprocal-rank fusion with constant 60. The artifact records the ordered top 10 raw
window indices, source paths, and text hashes for each arm. The replay adapter reconstructs each
window from the pinned corpus and refuses any index, path, text hash, manifest hash, model name,
ranking depth, or source-screen hash mismatch.

The evidence build must pass all of these gates before any agent session runs:

1. Code 4 source recall at 10 is at least 32/34.
2. Code 4 source recall at 10 exceeds Code 3 by at least two queries.
3. Code 4 mean reciprocal rank is not lower than Code 3.
4. Code 4 exact first-relevant-rank wins outnumber regressions.
5. Every task has exactly ten validated replay windows per arm.

Failure stops the experiment. The build is not repeated to obtain a favorable embedding draw.

## Frozen Task Solve arms

`code3_replay` receives its ordered top 10 evidence windows from Code 3 plus BM25.

`code4_replay` receives its ordered top 10 evidence windows from Code 4 plus BM25.

Both arms receive the identical task fixture, user prompt, generic repository rules, evidence
wrapper, evidence count, model, seed, tools, timeout, isolation, checker, and adjudication path.
Evidence appears before the shared static repository notes. Neither arm receives an MCP server,
autonomous memory-search instruction, hidden oracle bundle, answer map, checker content, or any
window outside its frozen top 10. Rank order is preserved and recorded in per-session diagnostics.

## Frozen grid

The participant model is `deepseek/deepseek-v4-flash`. Seeds are 0, 1, and 2. The 34 primary
tasks run under both arms, producing 204 sessions and 102 paired cells before exclusions.

The modification stratum is frozen as:

`ts-append-only`, `ts-atomic-write`, `ts-bool-env`, `ts-config-layer`, `ts-crlf-export`,
`ts-golden-regen`, `ts-ignore-gen`, `ts-legacy-hash`, `ts-log-mask`, `ts-quote-shell`,
`ts-retry-cap`, `ts-schema-additive`, `ts-semver-pin`, and `xs-evolve-lease`.

The new-artifact stratum is frozen as:

`fa-dedup-key`, `ts-base36-id`, `ts-bom-merge`, `ts-casefold-sort`, `ts-cli-exitcode`,
`ts-csv-quote`, `ts-dedup-order`, `ts-empty-input`, `ts-glob-hidden`, `ts-idempotent-run`,
`ts-json-sorted`, `ts-manifest-rel`, `ts-mig-name`, `ts-natural-order`, `ts-nfc-count`,
`ts-round-money`, `ts-stable-sort`, `ts-tz-utc`, `xs-join-batch`, and `xs-widen-manifest`.

The six preregistration-090 tasks where Code 4 moved a relevant source into the top 10 are a
frozen mechanism subgroup: `ts-append-only`, `ts-crlf-export`, `ts-golden-regen`, `ts-mig-name`,
`ts-natural-order`, and `ts-schema-additive`.

The intended runner command is:

```text
python -m scripts.pilot \
  --run-id code4-task-solve-001 \
  --namespace code4-task-solve-001 \
  --arms code3_replay,code4_replay \
  --tasks <the 34 task ids above, comma separated> \
  --seeds 3 \
  --model deepseek/deepseek-v4-flash \
  --code-retrieval-artifact results/retrieval/091-code4-task-solve-evidence.json \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

The run uses the ordinary isolated participant, checker, admission, cost, and signed adjudication
paths. A partial run is not mixed with a fresh challenge. Infrastructure retries follow the
existing harness rules and are reported separately from participant outcomes.

## Endpoints

The primary endpoint is paired checker success for Code 4 versus Code 3 across admitted
task-seed cells, reported as both-success, Code-4-only, Code-3-only, both-fail, net wins, and
paired success-rate difference.

Secondary endpoints are:

1. The same paired outcome in the modification and new-artifact strata.
2. The same paired outcome in the frozen six-task mechanism subgroup.
3. Per-task paired outcomes across three seeds.
4. Participant errors, timeouts, failed tool calls, model turns, input and output tokens, wall
   time, and estimated spend by arm.
5. Injected evidence tokens, prompt hashes, ordered window indices, and source-path overlap by
   task.

At least 90 of 102 paired cells must be admitted. Any cell enters analysis only when both arms
pass the existing setup and execution gates.

## Predictions frozen before implementation

1. The evidence build will pass all five retrieval gates.
2. Code 4 will produce at least three net paired Task Solve wins overall.
3. Code 4 will produce at least two net paired wins in the frozen six-task mechanism subgroup.
4. Neither the modification nor new-artifact stratum will have more Code-3-only than Code-4-only
   wins.
5. Code 4 will have no more participant errors or timeouts than Code 3 plus one cell.
6. Mean input tokens will remain within 10 percent and mean wall time within 20 percent between
   arms because the evidence count and wrapper are identical.

## Decision rule

Code 4 advances as the coding retrieval candidate for an official CAMBench Coding run only if the
evidence build passes, at least 90 paired cells are admitted, Code 4 has at least three net paired
Task Solve wins overall, neither task stratum is worse by more than one net cell, and prediction 5
passes. Otherwise the direct retrieval gain is not sufficient evidence for an official run.

The protected cross-model rescue lane remains secondary and is not tested here. No result from
this experiment licenses equal-peer fusion, concatenating vectors from different embedding
spaces, or applying Code 4 to conversational or multimodal corpora.

<!-- results and append-only corrections go below this line; everything above is frozen -->

## Evidence build result

Measured 2026-09-20 at 10:22:58 UTC from apparatus commit
`a26c3fb13963fcea952cfd4ed77109ef105c37ec`. The one shot build completed with status 0 and all
five frozen gates passed.

* Code 3 source recall at 10 was 28/34.
* Code 4 source recall at 10 was 34/34, a gain of six queries.
* Mean reciprocal rank rose from 0.5063 to 0.8464.
* Exact first relevant rank produced 21 Code 4 wins, 13 ties, and zero regressions.
* Every task and arm contains exactly ten replay windows, and the replay catalog validated all 34
  task prompts, window indices, source paths, text hashes, model names, and corpus identity.

The evidence artifact is `results/retrieval/091-code4-task-solve-evidence.json`, SHA-256
`ef85baa699a1a9e0d769d39e028b3b5eac317b542e31a7288451e86e016d79df`. The frozen retrieval
gate therefore licenses the Task Solve grid. It does not determine the Task Solve result.

## Task Solve result

Measured 2026-09-20 from run `code4-task-solve-003`, executed from apparatus commit
`e66e58d8fad444916e86ca2c4048d52406c9de26`. The run completed all 204 sessions in 112 minutes
with zero runner errors and an estimated participant spend of $0.4284 for 7,137,867 tokens.

The signed artifact contains 204 public session records and 204 raw session streams. Independent
verification rederived its session count, token count, two-cell discard set, 100 admitted paired
cells, and two-arm completeness, then verified the adjudication receipt against the external
Ed25519 public key. The principal artifact hashes are:

* `records.final.jsonl`: `2379acb89d41bc81214528032df30156ab68c0c910d5847baf46c3371a15ba6c`
* `adjudication.receipt.json`: `3fd9b2dc37e2c751c0ee94a2c26ee557d767819398096e315b38adef312d38c1`
* `code4-task-solve-analysis.json`: `31b8cc7dee888211561f12707024d40ae1d0df19e21bf0f5f446258fb7d1c9ec`

Two cells were excluded by the frozen admission rule. `ts-golden-regen` seed 1 had no terminal
result event in the Code 3 stream, and `xs-widen-manifest` seed 2 had no terminal result event in
the Code 4 stream. This left one participant error in each arm, zero classified timeouts, and 100
paired cells, above the preregistered minimum of 90.

The primary paired endpoint was:

| Outcome | Cells |
| --- | ---: |
| Both succeeded | 55 |
| Code 4 only | 12 |
| Code 3 only | 4 |
| Both failed | 29 |

Code 4 therefore produced eight net paired wins and an 0.08 paired success-rate difference.
Among admitted cells, Code 3 succeeded in 59/100 and Code 4 in 67/100. Across all attempted
sessions, including discarded cells, the counts were 59/102 and 68/102 respectively.

Both frozen strata were positive. The modification stratum produced five Code 4 only cells and
two Code 3 only cells, for three net wins across 41 admitted pairs. The new-artifact stratum
produced seven Code 4 only cells and two Code 3 only cells, for five net wins across 59 admitted
pairs. The six-task mechanism subgroup did not support its secondary prediction: it produced zero
Code 4 only cells and one Code 3 only cell across 17 admitted pairs, for one net loss.

The balance checks passed. Mean input tokens were 33,576.8 for Code 3 and 33,870.9 for Code 4,
within 0.9 percent. Mean wall time was 49,916 ms and 51,256 ms respectively, within 2.7 percent.
Each arm had one participant error, and neither had a classified timeout. All four frozen decision
checks passed, so Code 4 advances as the coding retrieval candidate for an official CAMBench
Coding run.

This result supports direct Code 4 replacement for this coding retrieval lane. It does not license
equal-peer fusion, vector concatenation across embedding spaces, Code 4 routing for conversational
memory, or any multimodal claim.

## Append-only apparatus correction

The first analysis attempt found that `memory_diagnostic` was available during execution and
admission but was removed by the public receipt allowlist during sealing. The signed run artifact
was not modified. Commit `10a76ef6c4cb577f05d5dd2aed81075edc421caf` repaired the analyzer to
reconstruct the same bounded replay identity from the immutable evidence artifact, pinned corpus,
and published prompt hashes, and added the bounded diagnostic to future public receipts. The
repair passed 1,344 tests with 17 skips before it was applied to the result.

Two earlier bring-up directories are retained on VPS2 under the isolated checkout's
`results/archive/` directory. Run 001 stopped at setup because the replay arms were not yet
declared instruction matched. Run 002 stopped at the first isolation checks because the pinned
image digests lacked their required `sha256:` prefixes. Neither attempt made a participant model
call or produced a session record. Run 003 used a fresh challenge and is the only Task Solve result
analyzed above.
