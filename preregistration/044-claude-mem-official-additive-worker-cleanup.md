# Claude-Mem official additive run 003

This preregistration supersedes the incomplete executions `claude-mem-official-001` and
`claude-mem-official-002`. Their artifacts remain preserved as diagnostic evidence and are not
leaderboard submissions. Run 001 exposed a SessionStart race and an unconditional PostToolUse
admission check. Run 002 confirmed those repairs and completed `present` with 134 admitted cells,
then stopped because workers from prior attempts were still resident and the next worker did not
become healthy.

The corrected launcher now retries only the transient Claude-Mem SessionStart context failure,
makes PostToolUse conditional on a real tool call, and kills only benchmark-owned Claude-Mem
workers for the current namespace after every condition and on failure. No benchmark corpus,
base result, or source checkout is deleted by this cleanup.

The official run remains additive and unchanged in experimental scope:

1. Execute only the new `claude_mem` arm on VPS2 in the isolated worktree, using pinned
   Claude-Mem `v13.24.0`, commit `ffe75a81e71b190644195a0ae9a5b6997757317c`, and the frozen
   `deepseek/deepseek-v4-flash` model.
2. Run the same five conditions, frozen task allocation, protocol instruction, and five seeds as
   the base comparison. Use four concurrent workers.
3. Import each condition once through Claude-Mem's official `/api/import` route and reuse that
   worker for all five seeds. Copy the frozen `official-003` artifacts only for the additive join;
   do not rerun or re-ingest any base arm.
4. Publish only after all 575 Claude-Mem sessions finish, all five condition artifacts pass setup
   and run verification, and the additive join passes `build_arm_submission.py --check`.

Admission requires the connected Claude-Mem MCP server and tools, successful `SessionStart`,
`UserPromptSubmit`, and `Stop` evidence, plus successful `PostToolUse` evidence whenever the
session has a tool call. Missing or failing integration evidence, import failure, unhealthy
server, sandbox mismatch, or record error is discarded rather than scored. Model task failures
remain ordinary benchmark outcomes when the integration surface is healthy.
