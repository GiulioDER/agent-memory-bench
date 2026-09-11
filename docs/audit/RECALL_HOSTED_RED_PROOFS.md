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

## Mandatory Search fallback telemetry

Test node:
`tests/test_recall_hosted_replay.py::test_replay_refuses_missing_search_fallback_telemetry`

Production symbol: `scripts.recall_hosted_replay._fallback_header`

Baseline: interpret a missing fallback header as false.

Observed assertion failure: replay completed instead of raising the expected `RuntimeError`.

Green restoration: both fallback headers must exist and contain exactly `0` or `1` for every Search
row, otherwise the replay is invalid.

## Registered context selection rule

Test node:
`tests/test_recall_hosted_select.py::test_selector_chooses_smallest_a4_arm_within_one_absolute_point`

Production symbol: `scripts.recall_hosted_select.select_replay`

Mutation: require the maximum observed A4 coverage instead of the registered one absolute
percentage point eligibility margin.

Observed assertion failure: the selector chose the 9,000 character arm instead of the eligible
5,000 character arm.

Green restoration: all A4 arms within 0.01 of the best complete coverage remain eligible, and the
smallest context budget wins.

## Paired replay product identity

Test node:
`tests/test_recall_hosted_select.py::test_selector_refuses_population_or_product_identity_drift`

Production symbol: `scripts.recall_hosted_select.select_replay`

Mutation: remove product identity equality after removing only the served variant name.

Observed assertion failure: an arm with a different facet prompt digest was accepted instead of
raising the expected `ValueError`.

Green restoration: corpus, task population, commit, models, and both prompt identities must match
across all seven replay artifacts.
