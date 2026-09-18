# Claude Mem plugin loader live smoke

Status: DRAFT until committed and timestamped. This record freezes the live integration check
before its model call.

## Question

Does the Claude Mem adapter load the pinned official plugin through Claude Code's `--plugin-dir`,
while retaining the isolated AMB hook and MCP configuration, and does the model call the real
Claude Mem search tool before touching the task files?

## Frozen source and environment

The source is commit `d3bdd426`, with the complete commit recorded by the timestamp manifest.
Claude Mem is `v13.24.0` at commit `ffe75a81e71b190644195a0ae9a5b6997757317c`. The model is
`deepseek/deepseek-v4-flash`, routed on VPS2 through the local AMB gateway to OpenRouter with
provider order `nextbit` and `allow_fallbacks=false`.

The adapter now passes the copied pinned plugin directory as `--plugin-dir`, in addition to the
strict generated MCP config and the isolated hook settings. The Chroma MCP environment is
prewarmed on VPS2 before the call.

## Smoke cell

Run exactly one absent condition cell, task `ts-base36-id`, seed `0`, arm `claude_mem`. Reuse the
existing absent import where the runner permits it, and do not start any other cell if this smoke
fails. This smoke is diagnostic and cannot be published.

## Prediction and stop rule

The MCP server will connect, the official plugin will be present in the Claude Code session, and
the transcript will contain at least one call named `mcp__mcp-search__search` before the first
file operation. A zero search count, absent plugin evidence, missing MCP connection, hook failure,
gateway policy drift, or provider error stops the experiment before the 55 cell absent retry.

<!-- results are appended below this line; everything above is frozen -->
