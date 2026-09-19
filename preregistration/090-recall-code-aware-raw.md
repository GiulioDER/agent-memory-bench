# 090: RE-call code-aware raw retrieval

Status: DRAFT until committed. The committed record is frozen above the results marker.

## Question

Does a deterministic exact code-token ranking leg plus bounded raw source-neighbour restoration
improve executable AML Coding performance over RE-call's validated raw Voyage Context 4 dense plus
exact lexical baseline, without changing the stored corpus or invoking another model?

This experiment selects a local candidate. It does not estimate the private CAMBench score and
does not authorize AML Smoke or Full.

## Arms and fixed identities

| Arm | Fixed behavior |
| --- | --- |
| `M0_raw` | Raw evidence, `voyage-context-4-v1`, exact PostgreSQL lexical retrieval, code-aware stage OFF, reranker OFF, graph OFF. |
| `M1_code_neighbors` | The identical M0 corpus and fused candidates, followed only by the frozen code-aware stage below. Reranker and graph remain OFF. |

Candidate width is 100 for dense retrieval and 100 for exact lexical retrieval. Reciprocal-rank
fusion uses constant 60. Search returns at most 100 stored evidence items in participant rank
order. Compilation, facets, task routing, SPLADE, Voyage reranking, graph expansion, entailment,
confidence abstention, generated Search answers, and context packing are excluded.

M0 creates exactly one raw corpus tenant and dense embedding pass for the initial present screen.
M1 reuses that exact tenant without Delete, Add, compilation, embedding, or sparse backfill.

## Exact code-token profile

The profile identifier is `aml-code-exact-v1`. Query and candidate text use Unicode case folding
and replace backslashes with forward slashes after extraction. The following forms are recognized:

1. Paths matching an optional Windows drive followed by one or more slash-separated components.
2. Filenames ending in `py`, `js`, `jsx`, `ts`, `tsx`, `json`, `jsonl`, `yaml`, `yml`, `toml`,
   `ini`, `cfg`, `sql`, `sh`, `md`, `txt`, `csv`, `log`, `lock`, or `env`, plus the exact names
   `Dockerfile`, `Makefile`, `VERSION`, and `.gitignore`.
3. Flags matching `--` followed by letters, digits, or hyphens.
4. Uppercase configuration or environment names beginning with a letter and containing at least
   three letters, digits, or underscores.
5. Identifiers ending in `Error` or `Exception`.
6. Identifiers immediately followed by an opening parenthesis, snake case identifiers, and camel
   case identifiers with an internal case transition.
7. Atoms composed of letters, digits, underscore, dot, colon, slash, backslash, or hyphen inside a
   one-line Markdown inline-code span of at most 128 characters.

Empty tokens, tokens shorter than three characters, and the rendering labels `role`, `content`,
and `timestamp` are excluded. A normalized token is deduplicated and receives the maximum weight
of every form it matches: three for forms 1 through 5, two for form 7, and one for form 6.

## Exact code fusion

M0 first produces its ordinary dense plus lexical RRF candidate list. For each candidate, M1 sums
the weights of distinct exact query tokens also present in that candidate. Candidates with a
positive sum form one additional ranking ordered by descending sum, then M0 rank, then chunk
identifier. The additional leg contributes exactly `0.5 / (60 + rank)` to the M0 fused score.
Candidates are then sorted by descending combined score and chunk identifier.

Fuzzy matching, substrings, stemming, edit distance, semantic token expansion, task labels, gold
terms, checker data, and model-generated terms are forbidden.

## Exact neighbour restoration

After code fusion, at most the first eight code-matched raw candidates are neighbour seeds. For
each seed, raw chunks with the same exact source are ordered by integer message `ordinal`, integer
`segment`, and chunk identifier. M1 inserts the immediate predecessor and immediate successor,
when present, directly after the seed in predecessor-then-successor order. Identifiers are
deduplicated globally. Compiled chunks are ineligible. A missing or malformed ordinal or segment
makes only that seed ineligible and increments the ineligible-seed counter.

The stage may add at most 16 neighbour candidates before final Top K truncation. It may not scan
another source, synthesize content, cross the tenant boundary, or silently fall back to a different
neighbour definition.

## Retrieval screen

Run these 34 tasks in this exact order under present memory, both arms, and three captures per
query:

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

This stage has 204 Search requests. Report ranks 1, 5, 10, and 100; complete coverage at ranks 5,
10, and 100; reciprocal rank; source-session recall; duplicate-session concentration; returned
items and characters; Search median and p95 latency; code-token count; matched candidates;
code-order and membership changes at Top 10 and Top 100; eligible, activated, and ineligible
neighbour seeds; restored neighbour count; Add and embedding ownership; corpus lineage; provider
and profile identities; and failures. Gold terms and task labels are applied only after Search.

M1 reaches executable screening only if all expected cells are present and all of these gates pass:

1. M0 reports code-aware OFF for every Search. M1 reports profile `aml-code-exact-v1`, RRF weight
   `0.5`, seed limit `8`, predecessor radius `1`, and successor radius `1` for every Search.
2. The task-set, query, corpus, generation, embedding profile, candidate width, RRF constant, and
   served commit identities match. M1 owns zero Add and dense embedding passes.
3. M1 has zero code-stage fallbacks, cross-source neighbours, non-raw neighbours, duplicate output
   identifiers, and invalid neighbour positions.
4. M1 changes Top 10 order or membership on at least 17 distinct queries and restores at least one
   neighbour on at least 10 distinct queries.
5. Present M1 mean reciprocal rank is greater than M0, complete coverage at 10 and 100 do not
   decline, mean source-session recall does not decline, and M1 p95 Search latency is below 1,000
   milliseconds and strictly below twice M0 p95.

Failure of any gate selects M0 and stops this lane before task execution.

## Executable screen

If retrieval passes, run both arms at seeds 0, 1, and 2 on this frozen present-condition roster:

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

The screen contains 72 paired cells. The coding agent is exactly
`deepseek/deepseek-v4-flash`. Timeout is 600 seconds per session. Exactly three task cells run
concurrently. A timeout is an outcome and is not retried.

M1 reaches confirmation only if every expected cell is valid and paired, every task calls Search
and receives evidence, M1-only cell wins exceed M0-only cell wins, M1 task wins are at least its
task losses, and no task with three valid seeds regresses by more than one seed. A tie or loss
selects M0.

## Present-condition confirmation

If M1 passes the screen, run a fresh confirmation over all 34 tasks, both arms, and seeds 0, 1,
and 2. The confirmation contains 204 paired cells, uses the same coding model, timeout, prompt,
checker, and three-worker limit, and does not reuse screen task outputs.

Cluster inference by task, preserving all seeds inside each resampled task. Use 20,000 bootstrap
resamples with deterministic seed `90090` and empirical 2.5 and 97.5 percent endpoints. M1 wins
only if every expected cell is valid and paired, overall Task Solve is higher, M1 task wins exceed
task losses, the confidence interval lower endpoint is strictly positive, checker outcome
`damaged` does not increase, zero mechanism fallbacks occur, and the retrieval and latency gates
remain true. Failure of any gate selects M0.

Retrieval improvements cannot promote M1 when executable Task Solve loses or ties.

## Five-condition robustness

Only after a confirmation win, build fresh isolated tenants in this order: `present`, `absent`,
`adjacent`, `contradictory`, and `superseded`. Run all 34 queries, both arms, and three captures in
each condition. Each condition has one M0 dense embedding pass and an M1 reuse pass.

M1 becomes the raw base for later M2 and M3 experiments only if every lineage and mechanism gate
still passes, no condition loses more than 0.02 mean reciprocal rank, no condition loses complete
coverage at 100 or source-session recall, and p95 remains within the frozen latency limits. A
robustness failure retains M0 even after a present-condition confirmation win.

## Predictions

1. The extractor finds at least one code token for every present query.
2. M1 changes Top 10 order or membership on at least half of the present tasks and restores a
   neighbour on at least ten.
3. M1 improves present mean reciprocal rank without reducing complete coverage at 10 or 100.
4. M1 produces positive net executable wins in the 72-cell screen.
5. If confirmation runs, M1 improves overall present Task Solve with a strictly positive
   task-clustered confidence interval lower bound.

## Exclusion, invalidation, and stop rules

Invalidate the affected arm if corpus bytes, source chunk bytes, chunk order, task population,
queries, provider or model identity, candidate width, RRF constant, code profile, neighbour rule,
prompt, checker, timeout, condition, or seed drifts. Invalidate M1 if a neighbour crosses source or
tenant, is not raw, has an invalid position, or if any code-stage fallback occurs.

Stop if a benchmark label, checked-in fact term, checker datum, gold answer, or damaged reference
enters a product request or stored product metadata. Do not interrupt a provider-backed request.
Do not run two embedding or indexing jobs at once. Do not overwrite or repair a partial artifact.
Continue only into a fresh run-specific directory and preserve every failed attempt.

M5 Voyage reranking is already closed for the current raw candidate pool by preregistration 089's
measured result. It is not repeated or allowed to enter M1.

## Cost and identity record

Record exact RE-call and AMB commits, dependency lock digests, service version payloads, embedding
provider identity, embedding call ownership, OpenRouter tokens and cost for executable sessions,
wall time, fallback counts, invalid cells, mechanism counters, selection verdicts, and SHA-256 for
every selector input. Retrieval is provider-free after the single M0 corpus embedding pass.

## Expected immutable artifacts

Write new files only under:

1. `results/aml-code-aware-raw-v1/<recall>-<amb>-retrieval`
2. `results/aml-code-aware-raw-v1/<recall>-<amb>-screen`
3. `results/aml-code-aware-raw-v1/<recall>-<amb>-confirmation`
4. `results/aml-code-aware-raw-v1/<recall>-<amb>-robustness`
5. `results/aml-code-aware-raw-v1/<recall>-<amb>-selection.json`

Existing paths cause refusal, never reuse. Every selector records hashes of all input artifacts.

No AML hosted run is authorized. The live Coding contract, mandatory official model, Voyage
eligibility, and RE-call licence eligibility must be resolved separately.

## What would falsify this

The predictions are falsified by missing their numeric thresholds. The experiment is invalid if
the two arms differ in stored corpus, embedding, dense or lexical candidate construction, or any
mechanism other than the frozen code-aware stage. A result that advances after a failed gate or a
selector that differs from these rules is not this experiment.

<!-- results are appended below this line; everything above is frozen -->

## Pre-execution implementation clarification, 2026-09-19

This clarification was committed before any M0 or M1 measurement was inspected. It makes the
mechanism counts and latency gate mechanically unambiguous without changing an arm or threshold.

1. A distinct query counts toward the 17-query Top 10 mechanism gate only when all three captures
   report a Top 10 order or membership change.
2. A distinct query counts toward the 10-query neighbour gate only when all three captures restore
   at least one neighbour.
3. The prediction that every query is tokenized means all three captures report at least one
   query token. It is reported as a prediction and is not an additional promotion gate.
4. An ineligible seed is a code-matched raw candidate whose own ordinal or segment is missing or
   malformed, or whose identifier is absent from the exact-source raw ordering. It is reported but
   is not itself an invalid output. An invalid neighbour is a served structural addition that is
   not raw or does not have the seed's exact source. The invalid-neighbour count must be zero.
5. The p95 gate uses the replay client's outer HTTP wall-clock latency, not the server's internal
   Search header. Nearest-rank p95 is used over all 102 requests in an arm.
