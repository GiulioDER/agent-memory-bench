# official-012: RE-call graph retrieval after broker full-tools repair

Status: DRAFT until committed; a committed record is frozen above the results marker.

This is a new superseded-only repair confirmation. It does not amend or overwrite `official-010`
or `official-011`; its results live in a separate run directory and use the same verified frozen
superseded corpus.

## Question

Does exposing the complete live RE-call MCP tool surface to the participant, rather than the
broker's accidental hardcoded subset of eight tools, restore the intended graph-first protocol
and produce verified graph retrieval during the benchmark?

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `recall_graph_fulltools` | `60ca046979be796dc342f6d5e89c53b1b975cb8add1d1ded6a19ec6d65a93519` | RE-call `0.13.0` code path, `voyage-context-4-v1`, graph metadata `structural_session_order`, no reranker |

The repaired participant broker advertises the 22 tool names published by the live RE-call
server: search, evidence, graph, reasoning, related, state, calibration, indexing, ingest,
mutation and operational endpoints. The prompt explicitly instructs the participant not to
mutate or ingest the frozen store. No `RECALL_RERANK` or `RECALL_RERANK_MODEL` setting is supplied.

## Grid

Run: `official-012-recall-graph-broker-fulltools`. Condition: `superseded`. Tasks:
`ts-base36-id`, `ts-bom-merge`, `ts-golden-regen`, `ts-ignore-gen`, `ts-legacy-hash`,
`ts-mig-name`, `ts-natural-order`, `ts-schema-additive`, `ts-semver-pin`, `ts-tz-utc`.
Five seeds, 50 sessions, model `deepseek/deepseek-v4-flash`, memory-instruction variant
`protocol`. The same frozen superseded corpus and task checker are used for every session. The
MCP transport has a 180-second request safety bound; there is no whole-ingest deadline. Base tools
remain the standard AMB surface and Docker remains denied.

The run reuses the already verified rendered and ingested corpus in tenant
`amb-graph-rerank-official-010-superseded`. This is a repair confirmation of the participant
tool boundary, not a new corpus or ingestion comparison.

## Pre-run smoke and verification

Before the first model session, verify through the participant broker that `tools/list` contains
all 22 configured names, graph readiness is true, a one-hop graph query inspects positive
relations, and no reranker setting is present. After the run, inspect every participant record
for its advertised tool set, actual tool calls, graph expansion, positive relation inspection and
reranking flags. Record any mutation or ingest call even though the prompt forbids it.

## Endpoints, in reporting order

1. Broker repair: fraction of participant records exposing all 22 live tool names, with the exact
   observed set recorded.
2. Mechanism: memory-search rate and the proportion of searched cells whose first memory operation
   is `recall_reasoning_query` with `graph_expansion=one_hop` and `expand_retrieval=false`.
3. Graph verification: successful graph calls, `graph_relations_inspected`, graph readiness and
   relation-seed activations, reported from server diagnostics and session records.
4. Safety: actual mutation or ingest calls and any reranking events.
5. Outcome: admitted task success, neutral failure rate and damage rate for the superseded
   condition, interpreted only if the search-rate floor is met.
6. Exploratory comparison with `official-011`, `official-010` and `official-003` on explicitly
   labelled common task and seed cells. These comparisons are not causal because prompt, tool
   surface and benchmark revisions differ.

## Predictions

1. At least `0.90` of participant records expose all 22 configured tool names.
2. The searched-cell rate is at least `0.90`.
3. At least `0.90` of sessions that complete a graph query report `graph_expansion=one_hop` and
   positive relation inspection.
4. No session reports reranking as active, and the run contains no reranker environment setting.
5. No participant calls a mutation or ingest endpoint.
6. The graph arm's admitted success rate is interpreted as exploratory relative to prior runs;
   no directional outcome prediction is preregistered for this repair confirmation.

## Exclusion and truncation rules

Use the existing AMB admission gate and the condition's declared discard rules. A missing stream,
missing checker result or failed integrity check is discarded according to the existing harness
rule and reported separately. The search-rate floor is `0.50`; below it, outcome endpoints are
not interpreted. If runtime capacity requires truncation, truncate seeds rather than tasks and
never mix this run with another run's records.

## What would falsify this

The broker repair claim is falsified if any participant record exposes fewer than the 22 configured
tools, if graph calls do not inspect positive relations, or if graph calls are absent despite a
live MCP server. The no-reranker and no-mutation claims are falsified by the corresponding event
or environment record.

<!-- results are appended below this line; everything above is frozen -->
