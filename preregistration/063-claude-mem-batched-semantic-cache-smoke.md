# Claude Mem batched semantic cache live smoke

Status: DRAFT until committed and timestamped. This record freezes the live integration check
before its model call.

## Question

Does the Claude Mem adapter prepare the vendor semantic cache without waiting hours on the
upstream one observation at a time loop, then run the untouched pinned plugin so its hooks and
MCP search return a real result before the model reads task files?

## Frozen source and environment

The source is commit `c59b350b`, with the complete commit recorded by the timestamp manifest.
Claude Mem is `v13.24.0` at commit `ffe75a81e71b190644195a0ae9a5b6997757317c`. The model is
`deepseek/deepseek-v4-flash`, routed on VPS2 through the local AMB gateway to OpenRouter with
provider order `nextbit` and `allow_fallbacks=false`.

The adapter still imports through Claude Mem's shipped `/api/import` route. During preparation it
uses a copy of the pinned worker that preserves the vendor formatter, document IDs, metadata,
Chroma writer, and watermark store while batching the same documents. The copy is never passed to
Claude Code. The model session must use the untouched pinned plugin, official `.mcp.json`, official
hooks, and `--plugin-dir`.

## Smoke cell

Run exactly one absent condition cell, task `ts-base36-id`, seed `0`, arm `claude_mem`. Do not
start the 55 cell absent retry unless this smoke returns at least one successful
`mcp__mcp-search__search` call with at least one hit.

## Prediction and stop rule

The batched preparation will complete, the final worker will report healthy Chroma state, the
official plugin will load, the MCP server will connect, the search tool will be called before the
first file operation, and the call will return at least one observation. A zero search count, zero
hits, search timeout, pending Chroma state, missing plugin evidence, missing MCP connection, hook
failure, gateway policy drift, or provider error stops the experiment before the absent retry.

<!-- results are appended below this line; everything above is frozen -->
