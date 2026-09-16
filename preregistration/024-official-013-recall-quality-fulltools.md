# official-013: RE-call quality skill on the full 22-tool surface

Status: DRAFT until committed. The prediction block is frozen above the results marker before
the first quality-treatment session.

## Question

On the same frozen `superseded` corpus, task set, model, seeds and 22-tool broker surface as
`official-012`, does replacing the graph-first `protocol` instruction with the quality-oriented
RE-call skill improve useful retrieval, tool routing, interpretation and task quality?

`official-012` is the pre-registered comparator. Its final commit is `105184a9`, its result tree
is `results/official-012-recall-graph-broker-fulltools-superseded`, and its instruction variant is
`protocol`. It completed 50 sessions, of which 48 cells were admitted and 2 discarded. The new run
must use a new run id and must not append to or rewrite `official-012`.

## Fixed treatment and grid

Treatment instruction: `adapters/recall/skill-quality.md`. The participant broker must advertise
the exact 22 names already recorded in `official-012`, with the same adapter configuration digest,
RE-call version, model, network policy, namespace, frozen corpus and no reranker settings. The
participant may read memory but must not mutate, ingest, index, forget or recalibrate the corpus.

Grid: condition `superseded`; tasks `ts-base36-id`, `ts-bom-merge`, `ts-golden-regen`,
`ts-ignore-gen`, `ts-legacy-hash`, `ts-mig-name`, `ts-natural-order`, `ts-schema-additive`,
`ts-semver-pin`, `ts-tz-utc`; seeds 0 through 4; 50 sessions. The exact model is
`deepseek/deepseek-v4-flash`. The new run id is
`official-013-recall-quality-fulltools-superseded`.

The prompt digest and skill digest must be recorded for every task. The full 22-tool advertised set
must be recorded before the first session. A preflight must verify graph readiness, positive
one-hop relations and absence of reranker configuration, as in `official-012`.

This is a standalone single-arm quality treatment, so shared-protocol fairness checks that are
defined for cross-arm product comparisons are recorded as `NA` for this run. The quality skill is
intentionally a full coaching treatment rather than a capped vendor appendix; its size and digest
remain primary provenance and are compared descriptively with `official-012`.

## Endpoints

1. Primary quality outcome: admitted checker success rate on the same task and seed cells as
   `official-012`, with the cross-run comparison explicitly labelled descriptive because no arm is
   shared within this run.
2. Search quality: search rate, useful retrieval given search, and retrieval by content, path and
   strict evidence, preserving the existing bracket rather than reporting one optimistic signal.
3. Routing quality: first memory operation, use of `recall_search`, `recall_evidence`,
   `recall_current_facts`, `recall_current_state`, `recall_related` and reasoning tools on applicable
   tasks; repeated and failed calls; and query-construction or rewrite use.
4. Graph quality: successful graph calls, one-hop expansion, positive relation inspection and
   relation count, compared with the `official-012` baseline.
5. Interpretation safety: correct handling of superseded or conflicting memories, current-code
   verification, mutation or ingest attempts and attributable damage under the superseded detector.
6. Cost diagnostics: follow-ups, tool errors, memory latency, model turns and input/output tokens.

No endpoint is converted to zero when its instrumentation is absent. Missing evidence, application
adjudication or relation labels are reported as `NA` with the reason.

## Predictions made before measurement

1. At least 0.90 of admitted sessions will search memory and at least 0.80 of searched sessions
   will execute a successful graph or direct retrieval operation.
2. Relative to `official-012`, useful retrieval given search will improve by at least 0.05, or,
   if it does not, correct application given useful retrieval will improve by at least 0.10.
3. At least 0.25 of applicable sessions will use an evidence, current-state, related or reasoning
   tool after the initial search, increasing the diversity of appropriate tool use above the
   `official-012` baseline.
4. At least 0.90 of completed graph queries will inspect positive one-hop relations, with no
   increase in calls to mutation or ingestion tools.
5. The quality treatment's attributable damage rate will not exceed `official-012` by more than
   0.02. If condition damage cannot be recovered from the records, this prediction is `NA`.
6. Any quality gain will not cost more than 2 additional model turns or 2,000 additional total
   tokens per admitted session on average. Missing telemetry remains missing.

## Exclusions and analysis

The existing admission and adjudication gates remain authoritative. Stream failures, missing
checker results and integrity failures are discarded, not scored as task failures. The two
discarded `official-012` cells are excluded only from the admitted-cell comparison; they are not
re-run or replaced. The comparison uses the intersection of admitted task-seed cells and reports
the exact intersection. No post hoc task removal, prompt editing, corpus refresh, reindexing,
reranker activation or alternate scoring rule is allowed.

The causal variable is the initial instruction. The broker, tool surface, corpus, task grid, seed
grid, model and runtime must remain fixed. Any change to those variables creates a new experiment.

<!-- results are appended below this line; everything above is frozen -->
