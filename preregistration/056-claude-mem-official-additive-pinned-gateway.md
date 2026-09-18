# Claude Mem official additive run 014, pinned gateway

This preregistration covers the official additive Claude Mem submission after the gateway smoke
test. It supersedes the execution path in `054` only for this new run. The earlier diagnostic and
failed qualification artifacts remain unchanged and are not resumed.

## Frozen source and environment

The run uses the repository commit containing this preregistration, the isolated VPS2 worktree
`/home/sentiment/amb-claude-mem-official-001`, Claude Mem `v13.24.0` at commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`, Claude Code `2.1.259`, and the exact benchmark model
`deepseek/deepseek-v4-flash`. Claude Code requests are sent to the local AMB Anthropic gateway.
The gateway forwards them to OpenRouter with provider order `digitalocean` and
`allow_fallbacks=false`. The provider policy is recorded in every condition's environment artifact.

The run uses four concurrent benchmark workers and a 15 second cell start stagger. It runs the
five frozen conditions and five seeds: 27 present task cells, 11 absent task cells, 10 superseded
task cells, 10 contradictory task cells, and 11 adjacent task cells, for 345 Claude Mem session
cells. The corpus for each condition is imported once through Claude Mem's official import route.
The verified post import worker snapshot is cloned into one namespace per task and seed. No cell
re-ingestion is allowed.

## Frozen experiment

1. Run only the new `claude_mem` arm on VPS2.
2. Reuse the frozen `official-003` comparator artifacts for the additive join. Do not rerun or
   re-ingest any base arm.
3. Use the protocol instruction, five seeds, four workers, 15 second stagger, and the bounded
   five attempt silent completion safeguard from `054`.
4. Require successful setup validation, run verification, required lifecycle hooks, cell namespace
   isolation, and no cross cell memory contamination.
5. Record the gateway model, provider order, fallback policy, and source commit. A gateway failure
   is a run failure, never a reason to fall back to the public OpenRouter endpoint.

## Publication gate

Publish the additive arm only if all five condition runs complete, all 345 planned Claude Mem cells
are admitted, no silent completion remains after the bounded safeguard, every condition passes
`validate_run_setup` and `verify_run`, and `build_arm_submission.py --check` passes against the
frozen `official-003` artifacts. Any unresolved silence, provider failure, gateway bypass,
observer failure, import failure, missing hook evidence, cross cell contamination, or sandbox
mismatch makes the run diagnostic only.
