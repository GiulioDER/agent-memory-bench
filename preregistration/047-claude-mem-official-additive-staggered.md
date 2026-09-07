# Claude-Mem official additive run 006

This preregistration supersedes `046-claude-mem-official-additive-staggered.md` because the prior
run ID has preserved partial diagnostic artifacts. No prior run is joined or resumed.

## Frozen source and environment

The run uses repository commit `f298bc0b`, pinned Claude-Mem `v13.24.0` at commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`, and isolated VPS2 worktree
`/home/sentiment/amb-claude-mem-official-001`. The benchmark model is
`deepseek/deepseek-v4-flash`. Claude-Mem's observer uses the paid OpenRouter route
`xiaomi/mimo-v2.5`; the retired `:free` route is excluded.

The scheduler uses four concurrent benchmark workers through `AMB_BLOCK_CONCURRENCY=4` and a
15-second `AMB_CELL_START_STAGGER_SECONDS` between cell starts. This pacing changes only request
arrival timing and preserves the task, seed, arm, prompt, and admission definitions. The launcher
sources `/home/sentiment/amb-secrets.env`, exports the pinned Claude and Bun paths, and fails
before model calls if required credentials or paths are absent.

## Frozen experiment

1. Run only the new `claude_mem` arm on VPS2.
2. Use the five frozen conditions, task selections, protocol instruction, and five seeds from the
   additive launcher.
3. Import each condition once through Claude-Mem's official `/api/import` route and reuse the
   condition worker across all five seeds. Copy only frozen `official-003` artifacts for the
   additive join. Do not rerun or re-ingest any base arm.
4. Require successful `SessionStart`, `UserPromptSubmit`, and `Stop` evidence, plus
   `PostToolUse` evidence whenever a session makes a tool call.

## Publication gate

Publish only if every planned Claude-Mem cell completes, every condition passes setup and run
verification, observer health has zero unrecoverable failures, all required hooks are admitted,
and `build_arm_submission.py --check` passes against `official-003`. Any silent zero-output
session, observer failure, import failure, missing hook evidence, or sandbox mismatch is a hard
stop and the run is diagnostic only.
