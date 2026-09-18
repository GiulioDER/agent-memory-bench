# Claude Mem synchronous first search guard retry

Status: DRAFT until committed and timestamped. This record retries the corrected Claude Mem smoke
after the first guard response was ignored because the vendor `PreToolUse` hook was asynchronous.

## Question

Does the synchronous AMB Claude Mem protocol guard block a non search tool, allow the exact Claude
Mem search call, record positive search telemetry, and then release normal Claude Code tools?

## Frozen setup

The run is on VPS2 in `/home/sentiment/amb-claude-mem-official-001`, from source commit
`9d8a03d6` or the exact descendant recorded by the timestamp manifest. It uses the present
condition, task `ts-base36-id`, seed `1`, arm `claude_mem`, the pinned Claude Mem plugin v13.24.0,
the existing semantic corpus prepared on VPS2, and the exact model
`deepseek/deepseek-v4-flash`.

Claude Code receives `ANTHROPIC_BASE_URL=http://127.0.0.1:8794`, served by the local AMB gateway.
The gateway forwards with provider order `nextbit`, `allow_fallbacks=false`, no gateway retry, and
the exact model above. The smoke exports `CLAUDE_MEM_ENFORCE_FIRST_SEARCH=1`, and the adapter
propagates that value into the explicit session environment. The generated isolated settings make
the Claude Mem `PreToolUse` wrapper synchronous. The guard denies non search tool calls until the
exact `mcp__mcp-search__search` call is attempted, records the denial, and leaves the normal tool
surface available afterward.

The gateway health check, Claude Mem MCP preflight, ingestion, and cleanup must pass. The measured
cell must record a search call with more than zero parsed hits, then at least one normal file tool
call, with all hooks exiting zero. This smoke tests protocol compliance and vendor search wiring.
It is not a leaderboard quality result and cannot be pooled with unconstrained arms.

## Prediction

The first attempted model tool call will be `mcp__mcp-search__search`, or a denied non search call
will be recorded before it. The search will complete with a positive parsed hit count, and the model
will subsequently use normal tools. The cell will complete with clean hooks, gateway routing, and
worker cleanup.

## Failure and publication rules

Stop before any further model call if the gateway does not report NextBit with fallbacks disabled,
if preflight or ingestion fails, if search is not attempted, if parsed hits remain zero, if normal
tools do not become available after search, if a hook fails, or if cleanup leaves a worker or
gateway process alive. This smoke is a corrected integration test only. It does not authorize an
official leaderboard result because the guard changes tool selection behaviour.

<!-- results are appended below this line; everything above is frozen -->

## Measured result, appended 2026-09-08

Run `claude-mem-first-search-guard-003-present` completed on VPS2 from source commit `680862ee`.
The gateway health check passed with model `deepseek/deepseek-v4-flash`, provider order `nextbit`,
and `allow_fallbacks=false`. All gateway requests completed through `NextBit`, with no gateway
retry or fallback.

Claude Mem ingestion stored 196 of 196 sessions. MCP preflight passed, all 14 vendor tools were
available, and the live server search probe succeeded. The synchronous guard recorded two denied
initial `Read` attempts. DeepSeek then called the exact
`mcp__mcp-search__search` tool successfully. Retrieval telemetry recorded one attempted and one
successful memory call with 35 parsed hits. Normal `Bash` and `Write` tools ran afterward. All
vendor and guard hook entries exited zero, and gateway and worker cleanup were clean.

The integration smoke therefore passes. The task checker still failed because the model output
`ORD-24GI` instead of the expected `ORD-24GJ`. The cell is not a leaderboard quality result and
must not be pooled with unconstrained arms. The guard is an explicit AMB protocol enforcement for
this smoke, not a claim that DeepSeek naturally discovers Claude Mem search.
