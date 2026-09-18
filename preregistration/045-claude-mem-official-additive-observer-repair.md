# Claude-Mem official additive run 004

This preregistration supersedes the incomplete executions `claude-mem-official-001`,
`claude-mem-official-002`, and `claude-mem-official-003`. Their artifacts remain preserved as
diagnostic evidence and are not leaderboard submissions.

Run 003 exposed the final root cause of its anomalous result. The frozen adapter selected
`xiaomi/mimo-v2.5:free` for Claude-Mem's OpenRouter observer. OpenRouter returned HTTP 404 for that
route and the worker recorded consecutive unrecoverable failures, explicitly directing the paid
slug `xiaomi/mimo-v2.5`. The run therefore produced a valid hook surface but no functioning
Claude-Mem observer and is excluded.

The frozen observer configuration now uses `xiaomi/mimo-v2.5`, verified against the current
OpenRouter model catalog before this preregistration. The worker cleanup and hook admission fixes
from the preceding preregistrations remain in force. Before any benchmark session, the launcher
must confirm worker health and observer readiness with a zero-session smoke check. A worker with a
nonzero consecutive failure count or no successful observer health state is a hard stop.

The official run remains additive and unchanged in experimental scope:

1. Execute only the new `claude_mem` arm on VPS2 in the isolated worktree, using pinned
   Claude-Mem `v13.24.0`, commit `ffe75a81e71b190644195a0ae9a5b6997757317c`, and the frozen
   `deepseek/deepseek-v4-flash` model for benchmark sessions.
2. Run the same five conditions, frozen task allocation, protocol instruction, and five seeds as
   the base comparison. Use four concurrent benchmark workers.
3. Import each condition once through Claude-Mem's official `/api/import` route and reuse that
   condition worker for all five seeds. Copy the frozen `official-003` artifacts only for the
   additive join; do not rerun or re-ingest any base arm.
4. Publish only after all 575 Claude-Mem sessions finish, all five condition artifacts pass setup
   and run verification, the observer health evidence is clean, and the additive join passes
   `build_arm_submission.py --check`.

Admission requires the connected Claude-Mem MCP server and tools, successful `SessionStart`,
`UserPromptSubmit`, and `Stop` evidence, plus successful `PostToolUse` evidence whenever the
session has a tool call. Missing or failing integration evidence, observer failure, import failure,
unhealthy server, sandbox mismatch, or record error is discarded rather than scored. Model task
failures remain ordinary benchmark outcomes when the integration surface and observer are healthy.
