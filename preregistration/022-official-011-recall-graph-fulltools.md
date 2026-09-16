# official-011: RE-call graph retrieval with the tested prompt and full tool surface

Status: DRAFT until committed; a committed record is frozen above the results marker.

This is a new superseded-only experiment. It does not amend or overwrite `official-010`; its
results live in a separate run directory and tenant.

## Question

Does an unconditional, graph-first version of the previously tested RE-call prompt increase the
agent's memory-search rate, and does the graph path produce verified relations that improve the
superseded-condition outcome without a reranker?

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `recall_graph_fulltools` | `60ca046979be796dc342f6d5e89c53b1b975cb8add1d1ded6a19ec6d65a93519` | RE-call `0.13.0` code path, `voyage-context-4-v1`, graph metadata `structural_session_order`, no reranker |

The arm exposes the complete 22-tool surface published by the live RE-call server during the
pre-run smoke, including graph, reasoning, search, evidence, related, state, calibration and
operational endpoints. The prompt explicitly instructs the participant not to mutate or ingest the frozen store. No `RECALL_RERANK` or
`RECALL_RERANK_MODEL` setting is supplied.

## Grid

Condition: `superseded`. Tasks: `ts-base36-id`, `ts-bom-merge`, `ts-golden-regen`,
`ts-ignore-gen`, `ts-legacy-hash`, `ts-mig-name`, `ts-natural-order`, `ts-schema-additive`,
`ts-semver-pin`, `ts-tz-utc`. Five seeds, 50 sessions, model `deepseek/deepseek-v4-flash`,
memory-instruction variant `protocol`.
The same frozen superseded corpus and task checker are used for every session. The MCP transport
has a 180-second request safety bound; there is no whole-ingest deadline. Base tools remain the
standard AMB surface and Docker remains denied.

## Endpoints, in reporting order

1. Primary mechanism: memory-search rate and the proportion of searched cells whose first memory
   operation is `recall_reasoning_query` with `graph_expansion=one_hop` and
   `expand_retrieval=false`.
2. Graph verification: successful graph calls, `graph_relations_inspected`, graph readiness and
   relation-seed activations, reported from the server diagnostics and session records.
3. Outcome: admitted task success, neutral failure rate and damage rate for the superseded
   condition.
4. Exploratory comparison with `official-010` and `official-003` on explicitly labelled common
   task and seed cells. These comparisons are not causal because the prompt, tool surface and
   task/checker revisions differ.

## Predictions

1. The unconditional graph-first prompt raises the searched-cell rate to at least `0.70`, above
   the `0.50` interpretability floor.
2. At least `0.90` of sessions that complete a graph query report `graph_expansion=one_hop` and
   positive relation inspection, proving that the graph is reached rather than merely configured.
3. No session reports reranking as active, and the run contains no reranker environment setting.
4. The graph arm's admitted success rate is not materially below the prior Context4 graph result
   on the same condition. This is exploratory because the prior arm had a different prompt and
   tool surface.

## Exclusion and truncation rules

Use the existing AMB admission gate and the condition's declared discard rules. A missing stream,
missing checker result or failed integrity check is discarded according to the existing harness
rule and reported separately. The search-rate floor is `0.50`; below it, outcome endpoints are
not interpreted. If runtime capacity requires truncation, truncate seeds rather than tasks and
never mix this run with another run's records.

## What would falsify this

The mechanism claim is falsified if the prompt does not raise search above `0.70`, if graph calls
do not inspect positive relations, or if graph calls are absent despite a live MCP server. The
configured no-reranker claim is falsified by any reranking event or reranker environment setting.

## Amendment 1, before measurement: bind the allow-list to the live server surface

The initial draft named the 20 tools observed in `official-003`. A live smoke against the current
Context4 tenant showed that the server now publishes 22 tools: it adds `recall_apply_fact`,
`recall_current_facts` and `recall_inventory`, while the older `recall_graph_first_retrieval` name
is not published. The frozen arm config was corrected to the 22 names before the first benchmark
session. The smoke also verified graph readiness, `one_hop` expansion, 8 positive relation
inspections and 3 accepted graph candidates. No reranker setting was present.

## Amendment 2, before measurement: use the gated protocol variant

The first launch reached ingest and setup but produced zero sessions: the setup gate rejected the
`skill` variant because it is intentionally unmatched and its 5,885-byte prompt exceeded the
appendix proportion rule for a single-arm measurement. The run was stopped before any model call.
The retest therefore uses the benchmark's validated `protocol` variant, with the same unconditional
graph-first sentence in the memory slot. This keeps the tested protocol structure and removes the
conditional escape hatch that caused the low search rate in `official-010`.

<!-- results are appended below this line; everything above is frozen -->
