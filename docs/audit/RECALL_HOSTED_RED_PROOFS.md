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

## Replay latency percentile

Test node:
`tests/test_recall_hosted_replay.py::test_replay_p95_uses_nearest_rank_for_sixteen_requests`

Production symbol: `scripts.recall_hosted_replay._percentile`

Baseline: use a zero-based floor of `(n minus 1) times p` for the percentile index.

Observed assertion failure: p95 of request latencies 1 through 16 was reported as 15 instead of
16.

Green restoration: replay uses the nearest rank definition and therefore includes the slowest
request in a sixteen request p95.

## Source session concentration

Test node:
`tests/test_recall_hosted_replay.py::test_replay_scoring_reports_duplicate_session_concentration`

Production symbol: `scripts.recall_hosted_replay.score_items`

Mutation: report duplicate session concentration as zero for every nonempty result.

Observed assertion failure: a four item pack containing two records from `p01` reported `0.0`
instead of the expected duplicate concentration `0.25`.

Green restoration: the metric reports the fraction of returned items beyond the first item from
each distinct source session. Source session recall separately reports how many labeled source
sessions were represented.

## Engineering experience promotion and fallback

Test nodes:
`tests/test_recall_experience_select.py::test_selector_promotes_compiled_plus_raw_when_it_recovers_compiler_losses`
and
`tests/test_recall_experience_select.py::test_selector_falls_back_to_raw_when_compiled_arms_miss_the_registered_gates`

Production symbol: `scripts.recall_experience_select.select_experience`

Mutations: force the selected candidate to `E0_raw` when E2 passed, then force it to
`E2_compiled_raw` when both compiled arms failed their gates.

Observed assertion failures: the first mutation returned E0 instead of E2 after E2 recovered the
only task lost by compiled-only. The second returned E2 instead of E0 when both compiled arms had
lower coverage and MRR than raw.

Green restoration: E2 is selected only after its registered coverage or recovery condition and
raw-MRR floor pass. E1 is the next eligible arm. Otherwise the selector retains E0.

## Engineering experience paired identity

Test node:
`tests/test_recall_experience_select.py::test_selector_refuses_population_product_or_task_identity_drift`

Production symbol: `scripts.recall_experience_select.select_experience`

Mutation: remove product identity equality across the three artifacts.

Observed assertion failure: an E2 artifact with a different compiler prompt digest completed
selection instead of raising the expected product identity drift error.

Green restoration: corpus, task set, message count, served commit, model and prompt identities,
and per-task query and label hashes must match before any representation can be selected.
