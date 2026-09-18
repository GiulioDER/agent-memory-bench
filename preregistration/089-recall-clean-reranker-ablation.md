# 089: RE-call clean raw reranker ablation

Status: DRAFT until committed; the committed record is frozen above the results marker.

## Question

Does Voyage `rerank-2.5` improve executable AML coding memory performance when it is added directly
to the leading raw Voyage Context 4 dense plus lexical configuration, without changing the corpus,
candidate construction, prompt, or any other retrieval stage?

This experiment selects one local release candidate. It does not estimate the private CAMBench
score and does not authorize an AML Full run.

## Arms and fixed identities

| arm | fixed behavior |
|---|---|
| `B0_raw` | raw evidence, `voyage-context-4-v1`, exact PostgreSQL lexical retrieval, reranker OFF, graph OFF |
| `B1_raw_rerank` | identical B0 corpus and candidates, then Voyage `rerank-2.5`, graph OFF |

Both arms return stored evidence only. Entailment, SPLADE, procedure compilation, query facets,
task-conditioned packing, confidence abstention, generated Search answers, and alternative coding
agent models are excluded.

The local coding agent is exactly `deepseek/deepseek-v4-flash`. It is used only to reduce local
diagnostic cost. It is not an internal RE-call reasoning model. The official AML model policy is
GPT 4o mini and remains outside this local comparison.

Candidate width is 100 for dense retrieval and 100 for exact lexical retrieval. Reciprocal-rank
fusion uses constant 60. Voyage reranking receives the complete unique fused candidate list and
must return a permutation of that list. Search returns at most 100 items in participant rank order.

## Graph eligibility preflight

Before retrieval replay, count authored and eligible semantic relations in the raw corpus and the
served relation store. Graph is ineligible when either the relation count or relations inspected
is zero. If both are unexpectedly nonzero, stop before task execution and write a separately
committed graph preregistration. Graph is never added to this matrix by amendment after results are
visible.

## Retrieval grid

Conditions, in fixed order:

1. `present`
2. `absent`
3. `superseded`
4. `contradictory`
5. `adjacent`

Run all 34 executable tasks as retrieval queries under both arms with three captures per query.
The complete task roster is:

1. `fa-dedup-key`
2. `ts-append-only`
3. `ts-atomic-write`
4. `ts-base36-id`
5. `ts-bom-merge`
6. `ts-bool-env`
7. `ts-casefold-sort`
8. `ts-cli-exitcode`
9. `ts-config-layer`
10. `ts-crlf-export`
11. `ts-csv-quote`
12. `ts-dedup-order`
13. `ts-empty-input`
14. `ts-glob-hidden`
15. `ts-golden-regen`
16. `ts-idempotent-run`
17. `ts-ignore-gen`
18. `ts-json-sorted`
19. `ts-legacy-hash`
20. `ts-log-mask`
21. `ts-manifest-rel`
22. `ts-mig-name`
23. `ts-natural-order`
24. `ts-nfc-count`
25. `ts-quote-shell`
26. `ts-retry-cap`
27. `ts-round-money`
28. `ts-schema-additive`
29. `ts-semver-pin`
30. `ts-stable-sort`
31. `ts-tz-utc`
32. `xs-evolve-lease`
33. `xs-join-batch`
34. `xs-widen-manifest`

For each condition, B0 creates exactly one raw corpus tenant and dense embedding pass. B1 reuses
that exact tenant without Delete, Add, or dense embedding. The full experiment therefore performs
exactly five dense embedding passes. Embedding and indexing are serial and never overlap.

Report ranks 1, 5, 10, and 100; complete coverage at ranks 5, 10, and 100; reciprocal rank;
source-session recall; duplicate-session concentration; items and characters; Search median and
p95 latency; reranker calls, fallback count, model identity, input and output candidate counts,
permutation validity, Top 10 and Top 100 order and membership changes, candidate character volume,
and estimated provider cost. Gold terms and task labels are applied only after Search.

B1 reaches executable screening only when every expected Search invokes Voyage `rerank-2.5`,
fallback count is zero, the full pretruncation candidate set is preserved, present mean reciprocal
rank improves, present complete coverage at 100 and source-session recall do not decline, and B1
Search p95 is below 5,000 ms and below three times B0 p95.

## Executable screen

Run both arms at seeds 0, 1, and 2 on this frozen present-condition roster:

1. `xs-evolve-lease`
2. `xs-join-batch`
3. `xs-widen-manifest`
4. `fa-dedup-key`
5. `ts-mig-name`
6. `ts-semver-pin`
7. `ts-retry-cap`
8. `ts-config-layer`
9. `ts-atomic-write`
10. `ts-idempotent-run`
11. `ts-glob-hidden`
12. `ts-quote-shell`

The screen contains 72 cells. Timeout is 600 seconds per coding session. Exactly three task cells
run concurrently. A timeout is an outcome and is not retried.

B1 reaches confirmation only if every expected cell is valid and paired, Search is called and
evidence delivered, candidate-only cell wins exceed baseline-only cell wins, candidate task wins
are at least candidate task losses, and every retrieval and mechanism gate passed. A tie or loss
selects B0 and stops.

## Independent confirmation

If B1 passes the screen, run a fresh confirmation rather than reusing selection cells. Run both
arms over all 34 tasks, all five conditions, and seeds 0, 1, and 2. The confirmation contains
1,020 paired cells and uses exactly three concurrent task workers.

Cluster inference by task, preserving all seeds and conditions inside each resampled task. Promote
B1 only if the 95 percent task-clustered bootstrap confidence interval for its overall Task Solve
delta has a strictly positive lower bound, present Task Solve improves, no individual condition
loses more than 0.02, Youden J floor does not decline, wrong-fact damage does not increase by more
than 0.02 in any adversarial condition, every expected cell is valid and paired, fallback count is
zero, identities match, and the retrieval latency gate still passes.

Failure of any gate selects B0.

## Predictions

1. B1 invokes Voyage once for every Search, has zero fallback, preserves every pretruncation
   candidate, and changes Top 10 order on at least 20 of 34 present queries.
2. B1 improves present mean reciprocal rank by at least 0.02 without lowering complete coverage
   at 100 or source-session recall.
3. B1 has positive net executable wins in the 72-cell screen.
4. If confirmation runs, B1 improves overall mean task success by at least 0.03, with a positive
   task-clustered confidence interval lower bound and no condition delta below negative 0.02.

## Exclusion, invalidation, and stop rules

Invalidate the affected arm if corpus bytes, source chunk bytes, chunk order, task population,
queries, provider identities, model identities, candidate width, prompts, checker, timeout,
condition, or seed drifts. Invalidate B1 if reranker output is not a duplicate-free permutation of
its input or if any fallback occurs. Stop if a benchmark label, checked-in fact term, checker data,
gold answer, or damaged reference enters a product request or stored product metadata.

Do not interrupt a provider-backed request. Do not run two embedding or indexing jobs at once. Do
not overwrite or repair a partial artifact. Continue only into a new run-specific directory and
preserve the failed attempt.

No AML hosted run is authorized. Written organizer confirmation is required for Voyage embedding
and reranking eligibility. If B1 wins but reranking is disallowed, the candidate is B0. If Voyage
embeddings are disallowed, both candidates are blocked.

## Cost and identity record

Record exact RE-call and AMB commits, dependency lock digests, service version payloads, embedding
and reranking provider identities, call counts, input document counts and characters, OpenRouter
tokens and cost for executable sessions, Voyage cost estimate and price source date, wall time,
fallbacks, invalid cells, and every selection verdict. Cost is secondary to the quality and safety
gates and does not rescue a failed arm.

## Expected immutable artifacts

Write new files only under:

1. `results/aml-clean-reranker-v1/<recall>-<amb>-graph-preflight`
2. `results/aml-clean-reranker-v1/<recall>-<amb>-retrieval`
3. `results/aml-clean-reranker-v1/<recall>-<amb>-screen`
4. `results/aml-clean-reranker-v1/<recall>-<amb>-confirmation`
5. `results/aml-clean-reranker-v1/<recall>-<amb>-selection.json`

Every selector records hashes of all input artifacts. Existing paths cause refusal, never reuse.

## What would falsify this

The predictions are falsified by missing their numeric thresholds. The selection is invalid if
the two arms differ in anything other than reranking, if cache lineage does not prove one dense
pass per condition, if graph runs without passing a separately committed eligibility experiment,
or if the selector's output differs from the frozen rules.

<!-- results are appended below this line; everything above is frozen -->
