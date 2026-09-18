# Claude Mem present condition retry with one worker

Status: DRAFT until committed and timestamped. This record freezes the new measurement before any
model call.

## Question

Does the upstream rate limit persist for the Claude Mem AMB present arm when concurrency is reduced
to one worker, using the same frozen task selection, seeds, model, gateway, and VPS2 corpus as the
three-worker diagnostic retry?

## Frozen setup

The run executes only on VPS2 in `/home/sentiment/amb-claude-mem-official-001` from the exact
source content and timestamp manifest recorded before launch. It uses the pinned Claude Mem
v13.24.0 plugin, the existing VPS2 present corpus, the frozen 27-task present selection, five
seeds, and `AMB_BLOCK_CONCURRENCY=1`. The arm is `claude_mem` and the model is exactly
`deepseek/deepseek-v4-flash`.

Claude Code receives `ANTHROPIC_BASE_URL=http://127.0.0.1:8794`, served by the local AMB gateway.
The gateway uses provider order `nextbit`, `allow_fallbacks=false`, and no gateway retry. The
synchronous Claude Mem first-search guard is enabled. The run may reuse the prepared VPS2 input
corpus and plugin ingestion state, but each measured cell remains isolated and may not read
observations or results from another cell.

Every admitted present cell must pass Claude Mem preflight and ingestion, attempt the exact
`mcp__mcp-search__search` tool, return more than zero parsed hits, continue to normal tools, and
finish with zero hook failures. Gateway 429, 502, missing stream completion, worker-unreachable,
or zero-hit cells are setup failures and stop the run before further model calls.

## Prediction

With one worker, the upstream rate limit will not recur during the first measured cell. Present
cells will record positive Claude Mem hits and clean hook traces, and successful gateway responses
will report NextBit with fallbacks disabled.

## Stop and publication rules

Stop before further model calls at the first present cell with zero parsed hits, no search attempt,
gateway rate-limit or transport failure, worker-unreachable error, missing final stream event, hook
failure, or cleanup residue. This is a diagnostic retry and is not a leaderboard publication unless
all frozen present cells complete and the resulting artifacts pass the official validation gates.

<!-- results are appended below this line; everything above is frozen -->
