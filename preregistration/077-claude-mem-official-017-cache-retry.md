# Claude Mem official additive run 017

Status: DRAFT until committed and timestamped. This record freezes the official measurement before
any model call.

## Question

On the frozen AMB task selection, does Claude Mem improve agent task success relative to the already
published arms in official run 003, while its retrieval path is live, searchable, isolated per cell,
and operationally reliable under the pinned DeepSeek V4 Flash gateway?

## Frozen run

The run ID is `claude-mem-official-017`. It executes entirely on VPS2 in
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
returns hits. Each measured cell then receives a fresh isolated namespace. A live namespace is
never shared between cells, seeds, or conditions.

## Admission and publication rules

Every cell must pass corpus admission, Claude Mem preflight, ingestion or verified fixture reuse,
the exact `mcp__mcp-search__search` call, a positive parsed hit count, normal tool execution, and
zero hook failures. The resulting condition artifacts must pass `validate_run_setup` and
`verify_run`. The final additive join must pass both the write and check modes of
`build_arm_submission.py` against official run 003.

The run stops before further model calls on the first zero-hit or missing search, worker
unreachable error, gateway 429 or exhausted retryable failure, missing stream completion, hook
failure, admission failure, or cleanup residue. A partial run is diagnostic and is not published.

If all five conditions complete and all validation gates pass, the resulting Claude Mem arm is
eligible for the official leaderboard comparison. Costs and gateway telemetry are reported from
the generated artifacts; no post hoc retries, task substitutions, seed substitutions, or arm
reruns are allowed.

<!-- results are appended below this line; everything above is frozen -->
