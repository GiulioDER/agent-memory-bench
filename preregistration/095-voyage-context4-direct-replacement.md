# Preregistration 095: Voyage Context 4 direct replacement

Status: frozen when committed. No retrieval result from this experiment may be inspected before
the commit that adds this record.

## Question

Does session-aware `voyage-context-4` retrieve better evidence from coding-memory transcripts than
the proven `voyage-code-4` baseline when the corpus, raw windows, BM25 leg, reciprocal-rank fusion,
query roster, and result budget remain unchanged?

This is a direct dense-model replacement screen. It tests whether the content of the indexed
memory, which is a set of conversational coding sessions rather than a source-code repository,
benefits from contextualized document encoding. It does not fuse Code 4 and Context 4, compare raw
scores across their embedding spaces, concatenate their vectors, alter the evidence budget, or
measure final agent task success.

## Prior evidence and boundary

Preregistration 090 established Code 4 as a strong direct replacement for Code 3 on this corpus.
Code 4 plus BM25 achieved source recall 34/34 at rank 10, mean reciprocal rank 0.8464, 21 exact-rank
wins, and zero regressions against Code 3. Preregistration 091 then measured eight net paired Task
Solve wins for Code 4 across 100 admitted cells. Code 4 is therefore the control, not an unproven
candidate.

Earlier RE-call work registered Context 4 with ordered session grouping and exercised it through
an autonomous memory-tool surface. That work does not answer this experiment's question because
tool invocation, serving gates, graph policy, and evidence selection were not held equal to the
Code 4 replay. This screen isolates retrieval over the same frozen windows.

Voyage documentation explicitly describes shared embedding compatibility for the general Voyage
4 models, but the current Code 4 and Context 4 documentation does not explicitly guarantee that
their vectors share one directly comparable space. This experiment therefore treats them as
separate spaces and compares only within-model rankings.

## Frozen source and corpus

The source checkout before this preregistration is
`867c4987b99ba657a81d8bdbd6767a0c4f66f48f`. The corpus manifest is `corpus/manifest.json`
with SHA-256 `58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.

The manifest contains 196 session entries and deterministically produces 1,220 raw windows at 160
words with a 120-word stride. The query roster is all 34 primary tasks returned by
`harness.tasks.discover_tasks()` in task-id order. Each original task prompt is the query. A source
session is relevant exactly when its manifest path is under `sessions/<task_id>/`. Distractors and
sessions for other tasks remain in the corpus.

Both arms return only the original raw windows. No summaries, generated context, task identifiers,
checker content, answer maps, or compiled memories enter either ranking.

## Frozen embedding and grouping policy

`C0_code4` uses `voyage-code-4` with `input_type="document"` for every raw window and
`input_type="query"` for every task prompt.

`C1_context4` uses `voyage-context-4` through the contextualized embedding endpoint. All windows
from one manifest session are passed as one ordered document group with `input_type="document"`.
The returned vectors must preserve one-to-one chunk order. Each task prompt is embedded as one
singleton query with `input_type="query"`. The output dimension is 1,024 and output type is
float32.

Context 4 request batching may combine document groups, but it may split only between raw windows
and may never mix chunks from different sessions into one document group. A session that exceeds
a request limit may be split between windows. Such a split is recorded, and each part remains
session-local. No automatic chunking is used because the benchmark windows must remain identical
between arms.

The two document indexes are built sequentially under the shared embedding-process lock. Before
the first paid call, each arm enforces a hard ceiling of 500,000 document tokens. The Context 4
arm also refuses a response that changes group count, group order, vector count, or vector width.

## Frozen retrieval arms

The lexical leg is the repository's canonical `harness.retrieval.Bm25Index`. Its scores and top
100 ranking are computed once per query and shared by both arms.

For each arm, the model's dense top 100 and the shared BM25 top 100 are combined by unweighted
reciprocal-rank fusion with constant 60. Each arm returns at most 100 windows. There is no score
normalization across models and no cross-model candidate fusion.

## Endpoints

Primary endpoints are:

1. Relevant source-session recall at 10 for each arm.
2. Mean reciprocal rank of the first relevant source session for each arm, with a missing rank
   scored as zero.
3. Relevant source-session recall at 100 for each arm.

Secondary endpoints are:

1. Relevant source-session recall at 1, 3, 5, and 20.
2. Exact first-relevant-rank wins, ties, and regressions.
3. Binary recall wins, ties, and regressions at 10 and 100.
4. Per-query relevant raw-window novelty in each direction at ranks 10, 20, and 100.
5. Top-10, top-20, and top-100 candidate overlap and Jaccard similarity by raw-window index.
6. For multi-session synthesis tasks, the number of relevant source sessions represented at 10,
   20, and 100, plus complete-shard coverage at those depths.
7. Per-model query plus fusion latency, reported as median and nearest-rank p95. Document build
   time and Context 4 group batching diagnostics are reported separately.
8. Estimated response tokens for the ordered evidence prefix at 10 and 100. The estimate uses the
   existing character-based estimator and is not presented as tokenizer billing.

No generated answer quality or Task Solve claim is made by this screen.

## Predictions frozen before implementation

1. Context 4 source recall at 10 will remain 34/34.
2. Context 4 mean reciprocal rank will not be lower than Code 4 by more than 0.03.
3. Context 4 source recall at 100 will remain 34/34.
4. Context 4 exact first-relevant-rank wins will be at least as numerous as regressions.
5. Context 4 will retrieve at least one relevant raw window absent from the Code 4 top 100 for at
   least three queries.
6. Code 4 will also retain model-specific relevant windows, so mean top-100 Jaccard similarity
   will be below 0.85.
7. Mean estimated response tokens at rank 100 will remain within 5 percent.
8. Context 4 p95 query plus fusion latency will remain below two times Code 4 p95. Document
   embedding time is excluded because Add-time indexing and Search-time retrieval are separate
   benchmark operations.

## Decision rules

Context 4 passes as a direct replacement only if predictions 1 and 3 pass, its mean reciprocal
rank is not lower than Code 4, and exact first-relevant-rank wins outnumber regressions. A direct
replacement pass licenses a separately preregistered Context 4 Task Solve replay with exactly the
same evidence count as the Code 4 control.

A protected cross-model fusion experiment is licensed only if prediction 3 passes and prediction
5 passes. That future experiment must keep Code 4 and Context 4 as independent ranking spaces,
preserve the frozen Code 4 evidence prefix, and use an equal evidence count in both Task Solve
arms. It may not use equal-peer three-leg RRF, because preregistration 089 already showed that an
unprotected extra ranking can displace stronger early evidence.

If direct replacement fails but the protected-fusion license passes, Code 4 remains the primary
ranking and Context 4 may be tested only as a bounded suffix candidate source. If both gates fail,
Context 4 is closed for the coding suite on this corpus. Neither outcome makes a multimodal claim.

<!-- results and append-only corrections go below this line; everything above is frozen -->
