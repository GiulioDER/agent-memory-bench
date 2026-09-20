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

## Measured result, 2026-09-20

The retrieval screen **failed**. The deterministic leg often reached relevant evidence, but the
baseline top 100 was already saturated and adding the leg harmed early ordering.

Measurement provenance:

- Implementation commit: `de83bbf4ca38e5db4482660afb1cc062fec57309`.
- Manifest SHA-256: `58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.
- Experiment script SHA-256:
  `f19eff670af37efccf44f18f5d72d78f0d09ce4b31350e5d5addc7492b42fcb8`.
- Result artifact SHA-256:
  `40a788c0b4bc15541f7d76f7c1d248651afd7c625ff0c543d94488ff62dcf2fe`.
- Measured at `2026-09-20T08:33:40.514075+00:00` on VPS2 under the shared embedding
  lock. The vendor tokenizer counted 347,634 document tokens, below the frozen 500,000 token
  ceiling.
- Remeasure command:
  `python -m scripts.code_candidate_experiment --corpus corpus --model voyage-code-3
  --max-tokens 500000 --out results/retrieval/089-code-candidate-generation.json`.

### Code token oracle

| Endpoint | Result |
|---|---:|
| Queries with an identifier also present in relevant evidence | 28 / 34 |
| Queries where the code leg reached relevant evidence in its top 100 | 26 / 34 |
| Queries where the code leg found relevant evidence absent from M0 top 100 | 1 / 34 |
| Behavior-only queries under the frozen zero-identifier definition | 0 / 34 |

The only query with genuinely new relevant raw windows was `xs-widen-manifest`, where M1 added
three windows and moved the first relevant rank from 7 to 2. Because all 34 prompts emitted at
least one identifier, the recorded zero false activations is vacuous rather than evidence about
behavior-only questions.

### Paired retrieval

| Metric | M0 raw | M1 code candidate leg | Delta |
|---|---:|---:|---:|
| Relevant source recall at 10 | 28 / 34 (0.8235) | 24 / 34 (0.7059) | -4 queries |
| Relevant source recall at 100 | 34 / 34 (1.0000) | 34 / 34 (1.0000) | 0 |
| MRR | 0.5210 | 0.4145 | -0.1065 |
| Mean estimated response tokens at 10 | 3,102.3 | 3,140.5 | +1.23% |
| Mean estimated response tokens at 100 | 30,395.4 | 30,531.5 | +0.45% |

At the binary recall-at-10 endpoint there were 0 M1 wins, 30 ties, and 4 regressions. At rank
100 all 34 queries tied. Comparing exact first-relevant ranks produced 3 wins, 13 ties, and 18
regressions.

Exact relevant-identifier micro recall at 10 was unchanged for paths (22/27), symbols (9/10),
modules (22/27), and config keys (1/3). It fell for commands from 4/7 to 3/7 and packages from
4/6 to 3/6. At 100 both arms covered every relevant identifier with a nonzero denominator. No
relevant error, flag, environment-variable, constant, or test identifier occurred, so those
classes had no denominator.

The deterministic index built 2,044 unique identifier keys in 1,309 ms. Per-query added latency
was 1.111 ms median and 2.116 ms p95. Total M1 latency was 255.295 ms median and 326.601 ms p95,
including the shared query embedding call.

### Prediction and decision record

Predictions 1, 2, 5, 7, and 8 passed. Predictions 3 and 4 failed. Prediction 6 is mechanically
true but uninformative because the roster contained no zero-identifier query. The mandatory
candidate novelty and early-ranking conditions therefore failed, so the retrieval screen did not
license Task Solve or the M2 compiler-sidecar comparison.

The result localizes the failure to fusion and baseline saturation, not extractor reach: the code
leg reached relevant evidence on 26 queries, but only one query had relevant evidence outside M0's
top 100. Treating the code ranking as an equal RRF peer displaced strong dense and lexical results
more often than it improved them.

### Append-only corpus-count correction

The frozen prediction text calls this a 206-session corpus. The manifest pinned by the correct
SHA-256 above contains 196 session entries and generated 1,220 raw windows. This is a
preregistration transcription error, not a corpus change; the hash, task roster, retrieval arms,
and thresholds used in the measurement were the frozen ones.
