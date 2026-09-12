# Claude Mem semantic backfill live smoke

Status: DRAFT until committed and timestamped. This record freezes the live integration check
before its model call.

## Question

Does the Claude Mem adapter wait for the official semantic Chroma backfill after import, copy the
completed vector state into the isolated namespace, and serve a successful Claude Mem MCP search
before the model reads the task files?

## Frozen source and environment

The source is commit `b35379f8`, with the complete commit recorded by the timestamp manifest.
Claude Mem is `v13.24.0` at commit `ffe75a81e71b190644195a0ae9a5b6997757317c`. The model is
`deepseek/deepseek-v4-flash`, routed on VPS2 through the local AMB gateway to OpenRouter with
provider order `nextbit` and `allow_fallbacks=false`.

The Chroma MCP runtime is prewarmed on VPS2. The adapter restarts the worker after the official
import route completes, waits for `chroma-sync-state.json` to report no pending rows, verifies the
official `/api/chroma/status?deep=1` endpoint, and only then clones the namespace.

## Smoke cell

Run exactly one absent condition cell, task `ts-base36-id`, seed `0`, arm `claude_mem`. Do not
start the 55 cell absent retry unless this smoke returns at least one successful
`mcp__mcp-search__search` call and no search timeout.

## Prediction and stop rule

The plugin will load, MCP will connect, the search tool will be called before the first file
operation, and the call will return at least one observation. A zero search count, search timeout,
pending Chroma state, missing plugin evidence, missing MCP connection, hook failure, gateway policy
drift, or provider error stops the experiment before the 55 cell absent retry.

<!-- results are appended below this line; everything above is frozen -->
