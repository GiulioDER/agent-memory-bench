# official-010-recall-context4-graph-rerank: RE-call graph and Voyage reranker evaluation

Status: DRAFT until committed. The committed record is frozen above the results marker.

## Question

Does the current RE-call production path, with Voyage Context 4 embeddings, persisted structural
graph relations, one-hop graph retrieval, and Voyage rerank-2.5, improve coding-task outcomes over
the previously measured RE-call Context 4 arm across the five AMB corpus conditions?

This is a standalone RE-call evaluation. It runs one arm only, so it does not claim paired AMB
harm or benefit against `bare`. Any comparison with `official-003` or another run is a cross-run
joined comparison on common admitted cells.

## Frozen treatment

- Run ID: `official-010-recall-context4-graph-rerank`
- Namespace prefix: `amb-graph-rerank-official-010`
- Arm: `recall_graph_rerank` only
- Conditions: `absent`, `adjacent`, `contradictory`, `present`, `superseded`
- Corpus seed: `1`
- Session seeds: `5`
- Model: `deepseek/deepseek-v4-flash`
- Memory instruction: `protocol`
- RE-call source: `5366770ea96a8ee4438a3bc8a749f521a20e4335`
- Package pin: `recall-rag[fastembed,mcp,voyage,rerank]==0.13.0`
- Embedder: `voyage-context:voyage-context-4`, registered profile `voyage-context-4-v1`
- Graph metadata mode: `structural_session_order`
- Graph query: `recall_reasoning_query`, `graph_expansion=one_hop`, `expand_retrieval=false`
- Reranker: `RECALL_RERANK=1`, `RECALL_RERANK_MODEL=voyage:rerank-2.5`
- Transport: host MCP transport on VPS2, with the detached RE-call serving checkout

The graph renderer emits only exact bidirectional `references` relations between adjacent session
files in the same task directory. It does not infer semantic relations from transcript prose. The
graph mode is included in the corpus fingerprint, so a no-graph generation cannot pass the arm's
identity check. The graph arm's instruction names `recall_reasoning_query` explicitly because an
ordinary `recall_search` call does not exercise graph expansion.

## Frozen grid

| condition | tasks | seeds | cells |
|---|---:|---:|---:|
| `absent` | 11 | 5 | 55 |
| `adjacent` | 11 | 5 | 55 |
| `contradictory` | 10 | 5 | 50 |
| `present` | 27 | 5 | 135 |
| `superseded` | 10 | 5 | 50 |
| total | 69 | 5 | 345 |

The selected task roster is the AMB `selection_for` roster at this commit, after the committed
retirement and out-of-class rules. No task subset is permitted.

## Preconditions and verification gates

Before the first measured session, every condition must have its own assembled corpus, manifest,
generation, calibration, promotion, and corpus fingerprint. The generation must be served by the
VPS2 checkout named above and `generation list` must report it active. The graph smoke gate must
show persisted relation rows, `graph_readiness=ready`, `graph_expansion_mode=one_hop`, and
`graph_relations_inspected>0`. The reranker smoke gate must show `embedding_profile` equal to
`voyage-context-4-v1`, `reranking_ran=true`, and `rerank_ms>0`.

The measured artifacts must show at least one successful `recall_reasoning_query` attempt for the
graph arm. Every graph query records its graph diagnostics. The run is invalid if the graph route
is never called, if graph readiness is not ready, if a no-graph corpus fingerprint is served, or if
the reranker is absent, zero-latency, or replaced by a local fallback. A graph gate refusal for an
individual query is recorded as an outcome of the graph policy, not silently counted as graph use.

## Command

```text
python -m scripts.abstention \
  --run-id official-010-recall-context4-graph-rerank \
  --namespace amb-graph-rerank-official-010 \
  --conditions absent,adjacent,contradictory,present,superseded \
  --arms recall_graph_rerank --recall-only --seeds 5 \
  --model deepseek/deepseek-v4-flash \
  --memory-instruction protocol --resume \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

The run uses the ordinary AMB admission, stream, cost, and signed adjudication rules. A partial
condition is archived and receives a new run ID; it is never resumed into this record. The full
result is not published as a leaderboard row until its admitted-cell join and all verification
artifacts pass.

<!-- results are appended below this line; everything above is frozen -->
