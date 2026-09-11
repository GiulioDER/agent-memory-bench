# RE-call Hosted adapter red proof receipts

## Exact retrieval query boundary

Test node: `tests/test_recall_hosted_replay.py::test_replay_never_sends_fact_terms_to_the_memory_system`

Production symbol: `scripts.recall_hosted_replay.run_replay`

Mutation: append private `fact_terms` to the Search query.

Observed assertion failure: the captured request no longer equaled the exact task prompt payload.

Green restoration: labels are read only by post-retrieval scoring.

## Served variant gate

Test node:
`tests/test_recall_hosted_replay.py::test_replay_refuses_wrong_served_variant_before_mutating_corpus`

Production symbol: `scripts.recall_hosted_replay.run_replay`

Mutation: remove the `/version` variant equality refusal.

Observed assertion failure: the expected `RuntimeError` was not raised before the first corpus
mutation.

Green restoration: replay verifies the exact served arm before Delete or Add.

## Complete evidence coverage

Test node:
`tests/test_recall_hosted_replay.py::test_replay_scoring_reports_rank_coverage_and_context_size`

Production symbol: `scripts.recall_hosted_replay.score_items`

Mutation: calculate complete coverage with `any` fact term rather than `all` fact terms.

Observed assertion failure: a result containing only `alpha` incorrectly covered the registered
`alpha` and `beta` target.

Green restoration: complete coverage requires every registered fact term within returned stored
evidence.

## Request-local Search fallback counts

Test node:
`tests/test_recall_hosted_replay.py::test_replay_counts_request_local_search_fallback_headers`

Production symbol: `scripts.recall_hosted_replay.run_replay`

Mutation: hard-code facet and reranker fallback states to false instead of reading the two response
headers.

Observed assertion failure: `facet_fallbacks` was zero instead of one.

Green restoration: every task row and aggregate count reflects its Search response headers.
