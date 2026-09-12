# Claude Mem full AMB run, absent first, guarded protocol

Status: DRAFT until committed and timestamped. This record freezes the full run before any new
model call.

## Question

Does the corrected Claude Mem AMB integration complete the full frozen additive run on VPS2,
starting with the absent condition, while recording nonzero Claude Mem retrieval for every admitted
cell and preserving clean gateway, worker, and hook state?

## Frozen setup

The run is executed only on VPS2 in `/home/sentiment/amb-claude-mem-official-001`, from the exact
source commit recorded by the timestamp manifest. It uses the pinned Claude Mem plugin v13.24.0,
the existing VPS2 semantic corpus, the official frozen task selections, five seeds, and four
concurrent cells. The condition order is `absent`, `present`, `superseded`, `contradictory`, and
`adjacent`, so the run restarts from absent. The measured arm is `claude_mem` and the model is
exactly `deepseek/deepseek-v4-flash`.

Claude Code receives `ANTHROPIC_BASE_URL=http://127.0.0.1:8794`, served by the local AMB gateway.
The gateway forwards with provider order `nextbit`, `allow_fallbacks=false`, no gateway retry,
and the exact model above. The gateway is started only after its port is checked free and is
stopped after the run. The run exports `CLAUDE_MEM_ENFORCE_FIRST_SEARCH=1`. The generated
Claude Mem PreToolUse guard is synchronous and denies non-search tools until the exact
`mcp__mcp-search__search` call is attempted, then releases normal tools. This guard is part of
the corrected integration protocol and is disclosed because it changes tool selection behaviour.

Ingestion may reuse the already prepared condition corpus on VPS2. It must not reuse observations
or results across isolated cells. The adapter must run its MCP preflight and record the full
Claude Mem tool surface before the first model call. Each admitted cell must record a successful
Claude Mem search with more than zero parsed hits, followed by normal tool use, and all hooks must
exit zero. Cleanup must leave no Claude Mem worker, MCP process, or gateway listener behind.

## Prediction

The gateway will report `NextBit` with fallbacks disabled. Each admitted cell will pass Claude Mem
preflight and ingestion, record at least one successful search with positive parsed hits, then
complete with normal tools and clean hooks. The absent-first condition will complete before the
remaining frozen conditions begin. Any task correctness failures will be reported separately from
the integration gate.

## Stop and publication rules

Stop before further model calls if the gateway is not pinned to NextBit, fallback is enabled,
preflight or ingestion fails, a cell has no Claude Mem search attempt, parsed hits are zero, normal
tools do not become available after search, a hook fails, or cleanup leaves a worker or gateway
alive. A condition or full run with any such failure is not publishable as a clean Claude Mem
leaderboard result. The guard-enabled measurements must remain labelled as guarded and must not be
pooled with unconstrained arms without an explicit protocol decision.

<!-- results are appended below this line; everything above is frozen -->
