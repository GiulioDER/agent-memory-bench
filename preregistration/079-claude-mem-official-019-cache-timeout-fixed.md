# Claude Mem official additive run 019

Status: DRAFT until committed and timestamped. This record freezes the replacement official
measurement before any model call.

## Relation to earlier attempts

Run 017 was stopped after two cells because its preregistration incorrectly required positive hits
for every condition. Run 018 was stopped before its first cell because cached fixture verification
used a ten second request timeout against a large worker search. Neither run is a leaderboard
result, and neither is edited or reused as a measurement.

This record freezes the corrected admission rule and the cache verification timeout fix. A zero-hit
search is a valid retrieval miss. A missing search attempt or failed search call is an integration
failure.

## Question

On the frozen AMB task selection, does Claude Mem improve agent task success relative to the already
published arms in official run 003, while its retrieval path is live, searchable, isolated per cell,
and operationally reliable under the pinned DeepSeek V4 Flash gateway?

## Frozen run

The run ID is `claude-mem-official-019`. It executes entirely on VPS2 in
`/home/sentiment/amb-claude-mem-official-001`. The source commit and preregistration hash are
recorded in the timestamp manifest before launch. The base evidence is official run 003 and is
copied into the isolated VPS2 checkout only for the additive join. No base arm is rerun.

The measured arm is `claude_mem`, using the pinned Claude Mem v13.24.0 plugin, the existing VPS2
corpora, five seeds, and one benchmark worker. The model is exactly
`deepseek/deepseek-v4-flash`. Claude Code uses the local AMB gateway at
`http://127.0.0.1:8787`. The gateway provider order is `nextbit`, `allow_fallbacks=false`, with
three total attempts and a 20 second exponential backoff. Only pre-response 502, 503, 504, and
transport failures are retryable. A 429 and any failure after stream start are not retried.

The benchmark uses `AMB_BLOCK_CONCURRENCY=1` and no cell start stagger. The synchronous Claude Mem
first-search guard is enabled. The gateway and benchmark run only on VPS2. No other provider,
model, or host is eligible.

## Frozen task grid

The launcher runs the five conditions in this order: `absent`, `present`, `superseded`,
`contradictory`, `adjacent`.

The present condition has 27 tasks:

`fa-dedup-key,ts-atomic-write,ts-base36-id,ts-bom-merge,ts-casefold-sort,ts-cli-exitcode,ts-config-layer,ts-crlf-export,ts-dedup-order,ts-empty-input,ts-golden-regen,ts-idempotent-run,ts-ignore-gen,ts-json-sorted,ts-legacy-hash,ts-log-mask,ts-manifest-rel,ts-mig-name,ts-natural-order,ts-nfc-count,ts-quote-shell,ts-retry-cap,ts-round-money,ts-schema-additive,ts-semver-pin,ts-stable-sort,ts-tz-utc`.

The absent and superseded conditions each have 11 tasks:

`ts-base36-id,ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc`.

The contradictory condition has 11 tasks:

`ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc`.

The adjacent condition has 11 tasks:

`ts-base36-id,ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc`.

This is 71 task selections times five seeds, or 355 measured cells. Each condition has its own
corpus. Within a condition, Claude Mem ingestion is performed once or loaded from a persistent
fixture cache only when the cache key matches the corpus, plugin tree, adapter source, and config,
the cache is younger than 48 hours, Chroma synchronization is complete, and a verification search
returns hits. The cached verification search uses the full 180 second ingestion request budget so
large but healthy indexes are not rejected by the ordinary ten second session request timeout.
Each measured cell then receives a fresh isolated namespace. A live namespace is never shared
between cells, seeds, or conditions.

## Admission and publication rules

Every cell must show the Claude Mem MCP surface connected, the required hooks present without
errors, and at least one attempted Claude Mem search. The attempted search calls must complete
without tool errors. A search returning zero hits is valid evidence of a retrieval miss and remains
in the denominator. Positive hits are not required for admission because the absent condition is
defined to have no governing fact and present condition misses are part of the retrieval endpoint.

Every cell must complete with a recorded stream or an explicit recorded session error. A normal
model answer that fails the deterministic task checker is a measured task failure, not an
integration failure. The resulting condition artifacts must pass `validate_run_setup` and
`verify_run`. The final additive join must pass both the write and check modes of
`build_arm_submission.py` against official run 003.

The run stops before further model calls on the first cell with no search attempt, a failed search
call, disconnected MCP surface, hook failure, worker-unreachable error, gateway 429 or exhausted
retryable failure, missing stream completion without a recorded error, admission failure, or
cleanup residue. A zero-hit search alone does not stop the run. A partial run is diagnostic and is
not published.

If all five conditions complete and all validation gates pass, the resulting Claude Mem arm is
eligible for the official leaderboard comparison. Costs and gateway telemetry are reported from
the generated artifacts; no post hoc retries, task substitutions, seed substitutions, or arm
reruns are allowed.

<!-- results are appended below this line; everything above is frozen -->
