# Preregistration: Claude Mem retrieval telemetry smoke

Date written: 2026-09-08

Source commit: `6a0a6d32`

## Question

Does AMB record Claude Mem progressive search results as retrieved hits instead of reporting zero
hits when the vendor MCP call succeeds and returns its textual result table?

## Frozen integration

This smoke keeps the pinned Claude Mem v13.24.0 plugin, the Bun runtime path correction, the direct
MCP preflight, the one imported present corpus, the DeepSeek V4 Flash model through NextBit on VPS2,
the task, seed, and `protocol` instruction fixed. The only change from the prior retry is the
telemetry parser, which recognizes Claude Mem's `Found N result(s)` search response for the pinned
`mcp__mcp-search__` tool prefix.

## Smoke cell

One present condition cell:

* task: `ts-base36-id`
* arm: `claude_mem`
* seed: 0
* memory instruction: `protocol`
* model: `deepseek/deepseek-v4-flash`

## Prediction

The setup preflight will pass. The measured session will call Claude Mem search before its first
file operation, receive at least one result, and record `memory_calls_succeeded` greater than zero
and `memory_hits_returned` greater than zero. All required hooks will pass and the MCP server will
remain connected. The run will record successful NextBit responses with fallback disabled.

## Pass and stop rules

The smoke passes only if the prediction is true. I will stop without further model calls if the MCP
preflight fails, the session search is absent, a search call fails or returns zero results, a hook
fails, the worker exits, or the gateway reports a provider or policy error.

## Relation to earlier smokes

The 066 run failed because the preflight retry exposed the missing Bun path. The 067 retry fixed
that and proved live search, but its record reported zero hits because AMB did not parse Claude
Mem's progressive result text. Those artifacts remain separate and are not pooled with this smoke.
