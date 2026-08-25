# Oracle memory and proactive retrieval diagnostic

The benchmark measures whether an agent completes a task. It does not by itself identify which
part of the memory path caused success or failure. The diagnostic adds two reference tracks.

`oracle_memory` injects the exact relevant corpus evidence before the session. It is a ceiling
control, not a product and not a leaderboard competitor. It answers whether the agent can use
correct evidence when retrieval and query formulation are removed.

`recall_prefetch` runs RE call retrieval in the harness with the exact task prompt, then injects
the returned evidence without giving the agent memory tools. It measures retrieval quality when
the query is already available. The natural `recall` arm still measures whether the agent decides
to search and formulates a useful query.

The comparison is intentionally decomposed:

* oracle headroom: `oracle_memory` minus `claude_md`
* natural memory lift: `recall` minus `claude_md`
* prefetch memory lift: `recall_prefetch` minus `claude_md`
* access gap: `oracle_memory` minus `recall`
* prefetch gap: `recall_prefetch` minus `recall`

Each oracle item is tied to a corpus source hash and an exact evidence excerpt. The harness stores
query and evidence payloads in run artifacts through hashes, not in session metadata. Bundle files
are never copied into sandboxes. Hidden evaluation bundles may be supplied through
`ORACLE_MEMORY_ROOT`, with only the manifest digest committed publicly.

For example, the `ts-tz-utc` bundle contains the recorded decision that `app.log` timestamps are
UTC, along with its session source and validity metadata. The oracle supplies that evidence, not a
solution instruction. If the agent ignores it, that remains a real behavioral observation.

Diagnostic arms are not combined into a product ranking. A gap is evidence about a causal path,
not a claim that a product is first or unique. A public result must include the run identifier,
search cutoff, bundle and source digests, generated analysis, and discarded cell reasons.
