# Claude-Mem official additive run 002

This preregistration supersedes the incomplete execution attempt recorded under
`claude-mem-official-001`. That attempt was stopped on VPS2 before all five conditions completed.
Its artifacts remain preserved as diagnostic evidence and are not a leaderboard submission.

The first attempt exposed two harness issues. Claude Code can dispatch the two official
`SessionStart` hooks concurrently, so the context hook occasionally ran before the worker-start
hook finished. The AMB wrapper now retries only that transient context failure, recording the
retry count. Also, `PostToolUse` is conditional on an actual tool call; a model turn with no tool
call must not be discarded for lacking an event that Claude Code never emits.

The corrected run keeps the original design and scope:

1. Run only the new `claude_mem` arm on VPS2, in an isolated worktree, with the pinned Claude-Mem
   `v13.24.0` plugin and commit `ffe75a81e71b190644195a0ae9a5b6997757317c`.
2. Use the frozen `deepseek/deepseek-v4-flash` model, five seeds, the protocol instruction, the
   same five corpus conditions and frozen task allocation as `042`.
3. Use four concurrent benchmark workers. Ingest each condition once through Claude-Mem's
   official `/api/import` route, then reuse that worker and corpus for all five seeds and all arms
   within the condition. The base `official-003` evidence is copied only for the additive join;
   no base arm is rerun or re-ingested.
4. Publish only after all 575 Claude-Mem sessions finish, every condition passes setup and run
   verification, and the additive join passes `build_arm_submission.py --check`.

The corrected admission rule requires the Claude-Mem MCP server and tools, successful
`SessionStart`, `UserPromptSubmit`, and `Stop` lifecycle evidence, and successful `PostToolUse`
evidence whenever the session contains a tool call. Nonzero hooks, missing MCP tools, unhealthy
servers, missing conditional evidence, import failures, sandbox mismatch, or record errors remain
discarded rather than scored.

The previous incomplete attempt is explicitly excluded because it used the pre-repair wrapper and
admission behavior. No result from it may be joined, quoted, or published.
