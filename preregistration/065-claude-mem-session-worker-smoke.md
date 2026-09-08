# Preregistration: Claude Mem isolated session worker smoke

Date written: 2026-09-08

Source commit: `9fa919a8`

## Question

Does Claude Mem v13.24.0 complete one AMB session when the isolated worker is started before
Claude Code dispatches its lifecycle hooks, the semantic cache is prepared in batch mode, and the
imported observations are inside the vendor's default recent search window?

## Frozen integration

The vendor plugin is the pinned official checkout at tag `v13.24.0`, commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`. The adapter imports through `/api/import`, prepares a
copy of the pinned worker with the vendor formatter and writer batched, then gives the untouched
plugin to Claude Code. Imported timestamps are anchored to ingestion time. Each isolated cell
worker is started immediately before its session and stopped after the session.

The benchmark model is DeepSeek V4 Flash through the AMB gateway on VPS2. The gateway provider
order is `nextbit` and `allow_fallbacks=false`.

## Prediction

The one session will complete with a successful `mcp__mcp-search__search` call returning at least
one hit before the first file operation. The MCP server will be connected, the prestarted worker
will remain available through `UserPromptSubmit` and `Stop`, all required lifecycle hooks will
exit successfully, and the plugin metadata will identify Claude Mem 13.24.0.

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
response with fallback disabled. I will stop without additional model calls if the worker exits,
the search call is missing, the search returns zero hits, a required hook fails, the MCP server is
disconnected, or the gateway reports a provider or policy error.

## Reuse boundary

The prepared fixture may be reused for later cells of this arm after this smoke passes. Each cell
keeps an isolated SQLite and Chroma namespace, and no other arm's fixture or result is changed.
