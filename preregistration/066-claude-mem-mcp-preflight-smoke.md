# Preregistration: Claude Mem MCP preflight and live search smoke

Date written: 2026-09-08

Source commit: `7ef62b42`

## Question

Does the AMB Claude Mem adapter prove the complete per cell MCP path before spending a model
session, while the live DeepSeek V4 Flash session can still call the vendor search tool through the
official Claude Mem plugin?

## Frozen integration

Claude Mem remains the pinned official plugin at tag `v13.24.0`, commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`. The adapter uses the vendor import route, the pinned
batch semantic preparation, current ingestion timestamps, one cloned worker namespace per cell, and
an isolated worker started before lifecycle hooks. The new preflight starts the first cell worker,
performs MCP initialize, tools/list, and one real `search` tools/call, then stops that worker before
the measured session.

The model is DeepSeek V4 Flash through the AMB gateway on VPS2. The gateway provider order is
`nextbit` with fallback disabled.

## Smoke cell

One present condition cell:

* task: `ts-base36-id`
* arm: `claude_mem`
* seed: 0
* memory instruction: `protocol`
* model: `deepseek/deepseek-v4-flash`

## Prediction

The setup preflight will pass with the configured Claude Mem MCP server connected, all three
allowed memory tools observed, and one successful direct `search` call. The measured session will
complete with a successful `mcp__mcp-search__search` call before the first file operation, return at
least one hit from the present corpus, keep all required lifecycle hooks successful, and record
Claude Mem plugin version 13.24.0. The gateway will record successful NextBit responses with
fallback disabled.

## Pass and stop rules

The smoke passes only if the preflight and prediction are true. I will stop without further model
calls if preflight fails, the session search is absent, the search returns zero hits, a required hook
fails, the MCP server disconnects, the worker exits, or the gateway reports a provider or policy
error.

## Reuse boundary

The prepared fixture may be reused for later cells only after this smoke passes. Each cell keeps an
isolated SQLite and Chroma namespace. The benchmark may reuse the one vendor import and semantic
preparation, but it may not reuse a live worker across cells.
