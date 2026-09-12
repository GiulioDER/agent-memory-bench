# Claude-Mem official additive run 012

This preregistration supersedes `052-claude-mem-official-additive-cell-isolation.md` because
the prior run ID and its diagnostic artifacts are preserved. No prior run is joined or resumed.

## Frozen source and environment

The run uses the repository commit containing this preregistration, based on source commit
`f9dc78ab`, pinned Claude-Mem `v13.24.0` at commit `ffe75a81e71b190644195a0ae9a5b6997757317c`,
and isolated VPS2 worktree `/home/sentiment/amb-claude-mem-official-001`. The benchmark model is
`deepseek/deepseek-v4-flash`. Claude-Mem's observer uses the paid OpenRouter route
`xiaomi/mimo-v2.5`; the retired `:free` route is excluded.

The scheduler uses four concurrent benchmark workers and a 15-second cell start stagger. Claude
Code session persistence is disabled for every cell. Stream output and the lifecycle hook ledger
are the retained evidence; no Claude Code session resume state is part of the measurement. Each
task and seed uses its own identical Claude Code configuration directory and its own Claude-Mem
worker namespace. The condition corpus is imported once through Claude-Mem's official import
route. After import, the worker is stopped and its verified post-import data directory is cloned
for every task-seed cell. This reuses the imported corpus without re-ingesting it and prevents
live lifecycle observations from one benchmark cell entering another cell's startup context.
The launcher sources `/home/sentiment/amb-secrets.env`, exports the pinned Claude and Bun paths,
and fails before model calls if required paths or credentials are absent.

The harness allows at most five retries only for a completed session with no user-visible response,
no tool calls, and no reported API error. Retries use an increasing 2, 4, 6, 8, and 10 second
delay. Ordinary model responses, tool failures, and checker failures are never retried. The retry
count is recorded in every affected session. This is a bounded admission safeguard and does not
convert a silent cell into a success.

## Frozen experiment

1. Run only the new `claude_mem` arm on VPS2.
2. Use the five frozen conditions, task selections, protocol instruction, and five seeds from the
   additive launcher.
3. Import each condition once through Claude-Mem's official `/api/import` route and reuse the
   post-import snapshot for each task-seed worker namespace. Copy only frozen `official-003`
   artifacts for the additive join. Do not rerun or re-ingest any base arm.
4. Require successful `SessionStart`, `UserPromptSubmit`, and `Stop` evidence, plus
   `PostToolUse` evidence whenever a session makes a tool call.

## Publication gate

Publish only if every planned Claude-Mem cell completes, every condition passes setup and run
verification, observer health has zero unrecoverable failures, all required hooks are admitted,
and `build_arm_submission.py --check` passes against `official-003`. Any unresolved silent
completion after five retries, observer failure, import failure, missing hook evidence, cross-cell
memory contamination, or sandbox mismatch is a hard stop and the run is diagnostic only.
