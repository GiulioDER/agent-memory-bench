# Claude Mem absent diagnostic retry with explicit search

Status: DRAFT until committed and timestamped. This record freezes the diagnostic retry before
the first retry cell is measured.

## Question

Does the strengthened Claude Mem instruction cause the DeepSeek V4 Flash agent to call the real
Claude Mem MCP search tool in the absent condition, while the VPS2 worker and Chroma integration
remain healthy under four concurrent workers?

## Frozen source and environment

The adapter source is commit `f72ef7d5`, with the complete source commit recorded in the run
manifest. Claude Mem is `v13.24.0` at commit `ffe75a81e71b190644195a0ae9a5b6997757317c`.
The benchmark model is exactly `deepseek/deepseek-v4-flash`, sent through the local AMB
Anthropic gateway to OpenRouter with provider order `nextbit` and `allow_fallbacks=false`.
The run is executed entirely on VPS2.

The treatment instruction names the exact callable tool `mcp__mcp-search__search` and requires
one search before the first file read or state changing command. The vendor appendix remains
unchanged. The Chroma MCP runtime is prewarmed once on VPS2 before the retry so concurrent cells
do not race to download the same dependency environment.

The retry uses the frozen absent roster:

`ts-base36-id`, `ts-bom-merge`, `ts-dedup-order`, `ts-golden-regen`, `ts-ignore-gen`,
`ts-legacy-hash`, `ts-mig-name`, `ts-natural-order`, `ts-schema-additive`, `ts-semver-pin`,
`ts-tz-utc`.

There are 11 tasks and five seeds, for 55 planned Claude Mem cells. The run uses four workers, a
15 second cell start stagger, and the existing bounded five attempt silent completion safeguard.
The absent corpus is imported once through Claude Mem's official import route, then reused through
isolated per cell namespaces. No cell reingestion is allowed.

## Predictions

1. At least half of admitted sessions will contain a recorded call to
   `mcp__mcp-search__search`.
2. The retry will record a nonzero search rate and at least one retrieved observation, so a zero
   search result is treated as a failed integration rather than a publishable outcome.
3. The prewarmed runtime will eliminate the prior Chroma dependency prewarm timeout and materially
   reduce vendor hook failures, with no unresolved worker readiness failure.
4. The retry will not be published as an official leaderboard result, because it measures only the
   absent condition and is a diagnostic gate for a later full run.

## Execution and stop rules

Before launch, verify the source commit, preregistration timestamp, VPS2 location, gateway policy,
absence of an active run, and the exact planned cell count. Reuse the one absent import and isolated
snapshots. Do not spend model API calls if the gateway is not pinned or the vendor runtime cannot
pass a no API health and search preflight.

Stop before any full official run if the retry has zero recorded Claude Mem searches, unresolved
worker or Chroma startup failures, provider errors, gateway policy drift, missing required hook
evidence, or an incomplete cell grid. Any retry failure remains diagnostic only.

## Publication boundary

This record authorizes only the absent diagnostic retry. It does not authorize a leaderboard update.
A separate preregistration is required for a full official five condition run after this retry passes.

<!-- results are appended below this line; everything above is frozen -->
