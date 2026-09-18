# Claude Mem AMB smoke through the pinned NextBit gateway

Status: DRAFT until committed and timestamped. This record covers one corrected live smoke
measurement after the preceding telemetry smoke used the default direct OpenRouter endpoint by
mistake.

## Question

Does the pinned Claude Mem integration complete one AMB present cell on VPS2 when DeepSeek V4
Flash is sent through the local AMB gateway, with Claude Mem search called before file tools and
with nonzero parsed search results?

## Frozen setup

The run is on VPS2 in `/home/sentiment/amb-claude-mem-official-001`, from source commit
`3d10b3b5` or the exact descendant recorded by the timestamp manifest. It uses the present
condition, task `ts-base36-id`, seed `1`, arm `claude_mem`, the pinned Claude Mem plugin v13.24.0,
and the existing semantic corpus prepared on VPS2. The model is exactly
`deepseek/deepseek-v4-flash`.

Claude Code receives `ANTHROPIC_BASE_URL=http://127.0.0.1:8794`, served by
`scripts.openrouter_anthropic_gateway` on VPS2. The gateway forwards to OpenRouter with provider
order `nextbit`, `allow_fallbacks=false`, no retry, and the exact model above. The gateway log is
the routing evidence. The gateway is started only after the port is checked free and is stopped
after the run.

The gateway health check and Claude Mem MCP preflight must pass before the model call. The measured
session must call `mcp__mcp-search__search` before Read, Write, Edit, Glob, Grep, or Bash, return a
positive parsed Claude Mem result count, complete all hooks with exit code zero, and leave no
Claude Mem worker or MCP process behind.

## Prediction

The gateway and MCP preflight will pass. The first model tool call will be
`mcp__mcp-search__search`, and the retrieval telemetry will record at least one successful call
with more than zero hits. The session will complete without transport or hook failure. Task
correctness is not part of the integration pass prediction and will be reported separately.

## Stop and publication rules

Stop before further model calls if the gateway does not report NextBit with fallbacks disabled, if
the preflight fails, if the first Claude Mem search returns zero parsed hits, if search is not the
first model tool call, if a hook fails, or if a worker remains alive after cleanup. This is a live
integration smoke and not a leaderboard result. It authorizes no official leaderboard publication.

## Evidence to append after measurement

Append the run id, source commit, gateway health response, gateway log summary, preflight result,
admission result, retrieval telemetry, hook exit summary, task checker result, and cleanup check
below this line. Do not edit the frozen sections above.

<!-- results are appended below this line; everything above is frozen -->

## Measured result, appended 2026-09-08

Run `claude-mem-nextbit-gateway-001-present` completed on VPS2 from source commit `77c33a04`.
The gateway health check passed with model `deepseek/deepseek-v4-flash`, provider order `nextbit`,
and `allow_fallbacks=false`. The gateway log recorded successful responses from `NextBit` and no
gateway retry. It also recorded upstream HTTP 429 responses before later successful responses;
Claude Code reported 11 client retries. This is a transport reliability warning, not evidence of
fallback routing.

Claude Mem ingestion stored 196 of 196 offered sessions. The Claude Mem MCP preflight passed, with
all three required tools observed and a successful direct `search` call. The measured session had
the complete prompt, all 14 Claude Mem tools in its live tool list, and the `mcp-search` server
connected. Every worker hook and vendor hook exited with code zero, and the gateway and worker
cleanup checks were clean.

The smoke failed its behavioural gate. The first model tool call was `Read`, followed by `Grep`,
`Write`, and `Bash`. `memory_call_count=0`, `memory_calls_succeeded=0`, and
`memory_hits_returned=0`. The task was also incorrect, producing `ORD-24GI` instead of
`ORD-24GJ`. The cell was admitted by the harness because admission records memory availability
separately from model discoverability, but it is not a Claude Mem integration pass and is not
publishable.

The evidence separates wiring from model behaviour: the Claude Mem server was connected, the
search tool succeeded in preflight, and the full instruction was present in `prompt.md`. The
remaining defect is nondeterministic DeepSeek tool selection, not absent ingestion, MCP setup, or
gateway routing. No official AMB leaderboard run is authorized by this result.
