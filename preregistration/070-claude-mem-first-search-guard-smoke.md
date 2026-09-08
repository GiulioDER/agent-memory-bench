# Claude Mem first search guard smoke

Status: DRAFT until committed and timestamped. This is a corrective integration smoke after the
unconstrained DeepSeek session ignored the mandatory search instruction.

## Question

When the AMB Claude Mem protocol guard is enabled, does the official Claude Mem MCP search execute
before file tools, return nonzero results, and then release the normal Claude Code tool surface?

## Frozen setup

The run is on VPS2 in `/home/sentiment/amb-claude-mem-official-001`, from source commit
`7cc11de0` or the exact descendant recorded by the timestamp manifest. It uses the present
condition, task `ts-base36-id`, seed `1`, arm `claude_mem`, the pinned Claude Mem plugin v13.24.0,
the existing semantic corpus prepared on VPS2, and the exact model
`deepseek/deepseek-v4-flash`.

Claude Code receives `ANTHROPIC_BASE_URL=http://127.0.0.1:8794`, served by the local AMB gateway.
The gateway forwards with provider order `nextbit`, `allow_fallbacks=false`, no gateway retry, and
the exact model above. The smoke exports `CLAUDE_MEM_ENFORCE_FIRST_SEARCH=1`. The opt in AMB
PreToolUse guard denies non search tool calls until the exact
`mcp__mcp-search__search` call is attempted, records the denial, and leaves the normal tool surface
available afterward.

The gateway health check, Claude Mem MCP preflight, ingestion, and cleanup must pass. The measured
cell must record a search call with more than zero parsed hits, then at least one normal file tool
call, with all hooks exiting zero. This guard tests protocol compliance and vendor search wiring.
It is not a leaderboard quality result and cannot be pooled with unconstrained arms.

## Prediction

The first attempted model tool call will be `mcp__mcp-search__search`. The guard will deny the
model's initial non search attempt if it occurs, the search will complete with a positive parsed hit
count, and the model will subsequently use normal tools. The cell will complete with clean hooks,
gateway routing, and worker cleanup.

## Failure and publication rules

Stop before any further model call if the gateway does not report NextBit with fallbacks disabled,
if preflight or ingestion fails, if search is not attempted, if parsed hits remain zero, if normal
tools do not become available after search, if a hook fails, or if cleanup leaves a worker or
gateway process alive. This smoke is a corrected integration test only. It does not authorize an
official leaderboard result because the guard changes tool selection behaviour.

<!-- results are appended below this line; everything above is frozen -->

## Invalid setup attempt, appended 2026-09-08

Run `claude-mem-first-search-guard-001-present` reached VPS2 and passed the gateway and Claude Mem
preflight, but it is invalid for this preregistration. The pilot supplies an explicit session
environment and the first implementation failed to propagate `CLAUDE_MEM_ENFORCE_FIRST_SEARCH`
into that environment. The wrapper therefore ran without the guard. The session again called
`Read` first and recorded zero memory calls. No result from this attempt is used. The propagation
bug was fixed in commit `aae2bb12` and a new preregistration is required before rerunning.
