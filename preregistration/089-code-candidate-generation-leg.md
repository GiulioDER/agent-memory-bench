# Preregistration 089: deterministic code candidate generation leg

Status: frozen when committed. No retrieval result from this experiment may be inspected before
the commit that adds this record.

## Question

Can a deterministic code identifier index introduce relevant raw session evidence that is absent
from the existing dense and lexical candidate pool, while preserving early ranking and remaining
inactive on questions that contain no code identifiers?

This is a candidate generation experiment. It does not test a stronger weight inside an unchanged
pool, neighboring chunk expansion, compiled memories as direct peers, generated answers, or final
agent task success.

## Frozen source and corpus

The source checkout is `f2cb6dfc9e918b6c1f041add4ad66c7037b5c676`. The corpus manifest is
`corpus/manifest.json` with SHA-256
`58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.

The query roster is all 34 primary tasks returned by `harness.tasks.discover_tasks()` in task id
order. Each original task prompt is the query. A source session is relevant exactly when its
manifest path is under `sessions/<task_id>/`. Distractors and sessions for other tasks remain in
the corpus.

Every source session is rendered through the existing corpus reader and split into the existing
160 word windows with a 120 word stride. A returned item is always one of those raw windows. The
experiment may attach diagnostics to an artifact, but it may not return synthetic summaries,
identifier records, or compiler records as evidence.

## Frozen retrieval arms

The dense leg uses `voyage-code-3` with document and query input types. The lexical leg uses the
repository's canonical `harness.retrieval.Bm25Index`. Each leg contributes its top 100 raw windows.
Reciprocal rank fusion uses constant 60.

`M0_raw` is unweighted RRF over the dense and lexical legs.

`M1_code_candidate_leg` adds one independent deterministic code leg. At index time the leg derives
identifiers from every raw window. At query time it applies the same extractor to the original task
prompt. The extractor covers these classes:

1. Full paths, normalized path suffixes, and basenames.
2. Module and package names.
3. Functions, classes, methods, constants, and test names with their stripped implementation name.
4. Exception types and normalized error signatures.
5. Commands, flags, environment variables, and configuration keys.

The code leg scores only exact normalized identifier matches. Each match is weighted by inverse
document frequency over raw windows. There is no semantic expansion, learned model, task id lookup,
fact term lookup, oracle bundle lookup, or checker access.

M1 applies unweighted RRF over dense, lexical, and code rankings. At rank 100 it protects 10 raw
rescue slots for the highest code candidates not already present in the first 90 fused positions.
The first 10 positions remain the ordinary fused order, so recall at 10 measures early ranking
rather than tail reservation. If the query extractor emits no identifiers, M1 must be byte for byte
identical to M0 and the code leg must return no candidates.

Both arms return at most 100 raw windows. Dense and lexical scores are computed once per query and
shared by the paired arms.

## Code token oracle analysis

Before the paired comparison, report for every query:

1. Extracted identifier count by class.
2. Identifier classes present in both the query and at least one relevant source session.
3. Whether the code leg can reach any relevant raw window within its top 100.
4. Whether that relevant raw window is absent from the M0 top 100.

This analysis describes reachability. It does not change the extractor, task roster, ranking,
predictions, or rescue allocation after results are observed.

## Endpoints

Primary endpoints are:

1. Number of queries with at least one relevant code candidate absent from M0 top 100.
2. Relevant source session recall at 10 and 100 for each arm.
3. Mean reciprocal rank of the first relevant source session for each arm, with missing ranks
   scored as zero.

Secondary endpoints are:

1. Micro recall at 10 and 100 for exact query identifiers found in relevant source windows,
   reported separately for paths, symbols, errors, commands, flags, environment variables,
   configuration keys, modules, packages, and tests.
2. Query level wins, ties, and regressions at ranks 10 and 100.
3. False activation count on behavior only questions, operationally defined as questions for which
   the frozen extractor emits zero identifiers.
4. Added code leg latency and paired total search latency, with median and p95.
5. Estimated response tokens for the ordered raw evidence prefix at ranks 10 and 100. The estimate
   uses the existing benchmark character based token estimator and is not presented as tokenizer
   billing.

No generated answer quality or Task Solve claim is made by this screen.

## Predictions frozen before implementation

1. At least 17 of 34 questions will contain one or more identifiers that also occur in a relevant
   source session.
2. The code leg will place a relevant raw window in its top 100 for at least 14 questions.
3. M1 will introduce a relevant raw window absent from M0 top 100 for at least two questions.
4. M1 relevant source recall at 10 will exceed M0 by at least two questions, and M1 mean reciprocal
   rank will not be lower than M0.
5. M1 relevant source recall at 100 will not be lower than M0.
6. False activation will be zero on every behavior only question.
7. The added deterministic code leg will have p95 latency below 50 milliseconds on the committed
   206 session corpus, excluding the shared dense API call.
8. M1 estimated response tokens at rank 100 will remain within 5 percent of M0 because both arms
   return the same maximum number and shape of raw windows.

## Decision rule

The candidate generation lane passes the retrieval screen only if predictions 3, 5, and 6 pass,
and either the recall at 10 or mean reciprocal rank part of prediction 4 passes with at least one
strict query level improvement. A pass licenses an executable Task Solve screen, split into Bug Fix
and New Feature tasks. It does not license compiler sidecars, file or symbol cards, or query
expansion.

If prediction 1 fails, the next test is bounded query expansion for identifier free questions. If
prediction 1 passes but prediction 2 fails, the extractor or exact index is the bottleneck. If the
code leg reaches relevant evidence but predictions 3 or 4 fail, fusion or early ordering is the
bottleneck. If prediction 5 fails, the rescue policy is rejected even if shallow ranking improves.

The next sequential comparison after a retrieval pass is
`M1_code_candidate_leg` versus `M2_code_plus_compiler_sidecar`. It must receive a separate
preregistration and may not be inferred from this result.

<!-- results and append-only corrections go below this line; everything above is frozen -->
