# Preregistration 090: Voyage Code 4 direct replacement

Status: frozen when committed. No retrieval result from this experiment may be inspected before
the commit that adds this record.

## Question

Does replacing `voyage-code-3` with `voyage-code-4` improve early retrieval of relevant raw
coding-memory windows when the corpus, BM25 leg, reciprocal-rank fusion, query roster, and result
budget remain unchanged?

This is a direct dense-model replacement experiment. It does not add an independent candidate
leg, combine the two embedding models, reserve rescue slots, alter the raw evidence windows,
generate summaries, or measure final agent task success.

## Motivation and prior boundary

Preregistration 089 rejected an independent exact-identifier candidate leg. Its equal-peer fusion
reduced source recall at 10 from 28/34 to 24/34 and MRR from 0.5210 to 0.4145 while both arms
retained source recall 34/34 at 100. Only one query received relevant raw windows absent from the
baseline top 100. That result closes the frozen identifier leg and its fusion policy, but it does
not test whether a stronger code embedding model can replace the existing dense model.

## Frozen source and corpus

The source checkout before this preregistration is
`f5d23d8a041e7828a7e79d602866a4c94ef3a0b4`. The corpus manifest is
`corpus/manifest.json` with SHA-256
`58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.

The correctly pinned manifest contains 196 session entries and produces 1,220 raw windows. The
query roster is all 34 primary tasks returned by `harness.tasks.discover_tasks()` in task-id
order. Each original task prompt is the query. A source session is relevant exactly when its
manifest path is under `sessions/<task_id>/`. Distractors and sessions for other tasks remain in
the corpus.

Every source session is rendered through the existing corpus reader and split into the existing
160-word windows with a 120-word stride. Both arms return only those original raw windows.

## Frozen retrieval arms

The lexical leg is the repository's canonical `harness.retrieval.Bm25Index`. Its scores and top
100 ranking are computed once per query and shared by both arms. Each dense model embeds the same
1,220 document windows with `input_type="document"` and embeds the same task prompts with
`input_type="query"`.

`C0_code3` uses `voyage-code-3`. For each query, its dense top 100 and the shared BM25 top 100 are
combined by unweighted reciprocal-rank fusion with constant 60.

`C1_code4` uses `voyage-code-4`. It uses the identical candidate depth, BM25 ranking, fusion
constant, and result budget. There is no score comparison across embedding spaces and no fusion
between Code 3 and Code 4.

Both arms return at most 100 raw windows. The two document indexes are built sequentially under
the shared embedding-process lock. The hard spend ceiling is 500,000 document tokens per model,
enforced before paid embedding calls by the existing Voyage backend.

## Endpoints

Primary endpoints are:

1. Relevant source-session recall at 10 for each arm.
2. Mean reciprocal rank of the first relevant source session for each arm, with a missing rank
   scored as zero.
3. Relevant source-session recall at 100 for each arm.

Secondary endpoints are:

1. Relevant source-session recall at 1, 3, 5, and 20.
2. Query-level wins, ties, and regressions in exact first-relevant rank.
3. Query-level wins, ties, and regressions in binary recall at 10 and 100.
4. Number of queries where C1 retrieves at least one relevant raw window absent from C0 top 100,
   and the symmetric C0-only count.
5. Top-100 candidate overlap and Jaccard similarity by raw-window index.
6. Per-model query plus fusion latency, reported as median and nearest-rank p95. Document build
   time is reported separately.
7. Estimated response tokens for the ordered raw-evidence prefix at ranks 10 and 100. The
   estimate uses the existing character-based estimator and is not presented as tokenizer
   billing.

No generated answer quality or Task Solve claim is made by this screen.

## Predictions frozen before implementation

1. C1 source recall at 10 will exceed C0 by at least two queries.
2. C1 MRR will exceed C0 by at least 0.03.
3. C1 source recall at 100 will not be lower than C0.
4. Exact first-relevant-rank improvements under C1 will outnumber regressions.
5. C1 will retrieve a relevant raw window absent from C0 top 100 for at least three queries.
6. Mean estimated response tokens at rank 100 will remain within 5 percent because both arms
   return the same maximum number and shape of raw windows.
7. C1 p95 query plus fusion latency will remain below two times C0 p95. Document embedding time is
   excluded because Add-time indexing and Search-time retrieval are reported separately.

## Decision rules

The direct replacement passes only if prediction 3 passes and one of these two early-ranking
conditions passes:

1. C1 recall at 10 exceeds C0 by at least two queries while C1 MRR is not lower, or
2. C1 MRR exceeds C0 by at least 0.03 while C1 recall at 10 is not lower.

In either case, exact first-relevant-rank improvements must outnumber regressions. A replacement
pass licenses a separately preregistered Task Solve screen for Code 4. It does not license a
multi-model serving configuration.

A future protected-rescue fusion experiment is licensed only if prediction 5 passes. Such an
experiment must preserve a frozen baseline prefix and may not reuse the equal-peer RRF or reserved
ten-slot policy rejected by preregistration 089.

If the replacement gate and the candidate-novelty gate both fail, the Code 4 lane is closed on
this corpus. If replacement passes without candidate novelty, Code 4 proceeds only as a single
dense replacement. If candidate novelty passes while replacement fails, Code 4 may proceed only
as a shadow input to a newly preregistered protected-rescue policy.

<!-- results and append-only corrections go below this line; everything above is frozen -->

## Result: direct replacement passed

Measured 2026-09-20 at `09:24:42Z` on VPS2 under the shared embedding lock. The exact
apparatus commit was `9c98a49eb87e97f2f1a853efb1abdca8367f13e3`. The run used
`voyageai==0.5.0` and `numpy==2.5.3`. Both vendor token counts were 347,634, below the frozen
500,000 token ceiling per model.

The frozen predictions all passed:

| Endpoint | C0 Code 3 | C1 Code 4 | Change |
| --- | ---: | ---: | ---: |
| source recall at 1 | 13/34 | 27/34 | +14 queries |
| source recall at 3 | 18/34 | 28/34 | +10 queries |
| source recall at 5 | 21/34 | 32/34 | +11 queries |
| source recall at 10 | 28/34 | 34/34 | +6 queries |
| source recall at 20 | 33/34 | 34/34 | +1 query |
| source recall at 100 | 34/34 | 34/34 | no change |
| mean reciprocal rank | 0.5063 | 0.8464 | +0.3401 |
| median query plus fusion latency | 267.7 ms | 276.8 ms | 1.034x |
| p95 query plus fusion latency | 306.0 ms | 330.1 ms | 1.079x |
| mean estimated response tokens at 100 | 30,391.2 | 29,589.4 | 0.974x |

Exact first-relevant rank improved for 21 queries, tied for 13, and regressed for zero. Code 4
introduced at least one relevant raw window absent from the Code 3 top 100 for five queries. The
symmetric Code 3-only count was 11 queries, and mean top-100 Jaccard similarity was 0.5118. The
novelty result means the models are not interchangeable candidate generators, but the rank result
shows that Code 4 is the stronger direct retrieval model under the frozen fusion policy.

The direct-replacement decision passed, so a separately preregistered Task Solve screen is
licensed. The candidate-novelty decision also passed, so a separately preregistered protected
rescue experiment is licensed. This result does not itself license cross-model production fusion.
The first next experiment should be Task Solve with Code 4 as the single dense replacement. Any
fusion follow-up remains secondary and must protect the Code 4 baseline prefix.

Evidence:

* `results/retrieval/090-voyage-code4-direct-replacement.json`, SHA-256
  `9ada30c51c6fcbddede0a122d39a3239c05204a661d72a63683ed34d5fcf582a`
* `results/retrieval/090-voyage-code4-direct-replacement.log`, SHA-256
  `104b074450eb265000d1afddfd9d8710b4472b502319b1b4d53dc88bc6aee244`
* script SHA-256
  `c26e5461b62dc5ab5b0afbef061e67ba8ab21607ceef04a1aabc7ae1164d07fd`
* corpus manifest SHA-256
  `58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`

The focused experiment and prior candidate-leg tests passed 9/9. The repository-wide suite
reported 1,331 passed, 18 skipped, and one inherited failure: `test_no_new_file_names_the_serving_host`
already rejects `preregistration/089-code-candidate-generation-leg.md`, which predates this
experiment and is unrelated to its runner or result.
