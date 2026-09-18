# Preregistration: Claude Mem recency window smoke

Date written: 2026-09-08

Source commit: `c17f1466`

## Question

Does Claude Mem v13.24.0 retrieve the imported AMB corpus through its official MCP search tool
when the semantic cache is prepared in batch mode and imported observation timestamps are anchored
to ingestion time?

## Frozen integration

The vendor plugin is the pinned official checkout at tag `v13.24.0`, commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`. The preparation copy preserves the vendor formatter,
document IDs, metadata, Chroma writer, and watermark store. Claude Code sessions receive the
untouched pinned plugin. The adapter uses the vendor `/api/import` route and the lifecycle hooks.

The benchmark model is DeepSeek V4 Flash through the AMB gateway on VPS2. The gateway provider
order is `nextbit` and `allow_fallbacks=false`.

## Prediction

After ingestion and the semantic readiness barrier, the one cell will make at least one successful
`mcp__mcp-search__search` call and return at least one memory hit before the first file operation.
The MCP server will be connected, the required lifecycle hooks will complete without failure, and
the plugin metadata will identify Claude Mem 13.24.0.

## Smoke cell

One absent condition cell:

* task: `ts-base36-id`
* arm: `claude_mem`
* seed: 0
* corpus: the frozen absent seed 1 manifest
* memory instruction: `protocol`
* model: `deepseek/deepseek-v4-flash`

## Pass and stop rules

The smoke passes only if the prediction is true and the gateway records a successful NextBit
response with fallback disabled. I will stop without running additional cells if the search call is
missing, returns zero hits, times out, the Chroma barrier is incomplete, a required hook fails, the
MCP server is disconnected, or the gateway reports a provider or policy error.

## Reuse boundary

The imported and semantically prepared fixture may be reused for this arm's later cells after this
smoke passes. Each cell still receives an isolated filesystem namespace and worker. No other arm's
fixture or result is changed.
