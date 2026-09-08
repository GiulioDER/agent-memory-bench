# Preregistration: Claude Mem Bun path retry smoke

Date written: 2026-09-08

Source commit: `57365eb8`

## Question

Does the Claude Mem adapter remain functional when its runtime is started from a clean VPS2
environment, without relying on the operator shell to expose Bun?

## Frozen integration

This is a retry of preregistration 066 after a setup failure. The pinned official Claude Mem plugin,
the AMB gateway, the model, the present corpus, task, seed, and instruction remain unchanged. The
adapter now adds the pinned user Bun directory, `~/.bun/bin`, to the runtime PATH alongside
`~/.local/bin` before Claude Mem worker and hook commands start.

## Smoke cell

One present condition cell:

* task: `ts-base36-id`
* arm: `claude_mem`
* seed: 0
* memory instruction: `protocol`
* model: `deepseek/deepseek-v4-flash`

## Prediction

The direct MCP preflight will pass with all three allowed Claude Mem tools observed and a successful
`search` call. The measured session will start and stop the worker successfully, all required hooks
will exit successfully, and the model will make a successful `mcp__mcp-search__search` call before
the first file operation with at least one present corpus hit. The gateway will record successful
NextBit responses with fallback disabled.

## Pass and stop rules

The smoke passes only if the prediction is true. I will stop without further model calls if the
worker or a hook fails, the MCP preflight fails, the session search is absent, the search returns
zero hits, the MCP server disconnects, or the gateway reports a provider or policy error.

## Relation to preregistration 066

The 066 artifacts remain an invalid setup failure and are not pooled with this retry. The only
reason for this new record is the adapter PATH correction identified from the 066 hook stderr.
