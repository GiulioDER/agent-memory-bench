# Claude Mem official additive run 016, repaired NextBit route

Status: DRAFT until committed and timestamped. The prediction and execution rules below are
frozen before the first benchmark session.

## Question

Does the repaired Claude Mem `v13.24.0` integration improve or damage task success relative to
the frozen `official-003` controls when both use DeepSeek V4 Flash through the pinned NextBit
provider?

## Frozen source and environment

The adapter source is commit `51c30a0f`, in the isolated VPS2 worktree
`/home/sentiment/amb-claude-mem-official-001`. The run uses Claude Mem `v13.24.0` at commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`, Claude Code `2.1.259`, and the exact benchmark model
`deepseek/deepseek-v4-flash`. Claude Code requests are sent to the local AMB Anthropic gateway.
The gateway forwards them to OpenRouter with provider order `nextbit` and `allow_fallbacks=false`.
No provider fallback or gateway retry is permitted.

The repaired adapter adds two operational guarantees. It makes `$HOME/.local/bin` available to
Claude Mem child processes so the pinned `uvx` executable is discoverable. It clones each stopped
worker snapshot with bounded retries for transient SQLite journal races, while preserving the
database and vector store files.

The run uses four concurrent benchmark workers and a 15 second cell start stagger. It runs the
five frozen conditions and five seeds: 27 present task cells, 11 absent task cells, 10 superseded
task cells, 10 contradictory task cells, and 11 adjacent task cells, for 345 Claude Mem session
cells. The corpus for each condition is imported once through Claude Mem's official import route.
The verified post import worker snapshot is cloned into one namespace per task and seed. No cell
reingestion is allowed.

The repaired source must first pass a live VPS2 smoke test using the same plugin, model, provider,
gateway policy, import route, namespace cloning path, and Claude Code hooks. The smoke test must
show a healthy Chroma search dependency, a successful Claude Mem search when the task invokes the
memory tool, and no vendor hook failure in the exercised lifecycle. A failed smoke test blocks the
official run and consumes no full run cells.

## Frozen experiment

1. Run only the new `claude_mem` arm on VPS2.
2. Reuse the frozen `official-003` comparator artifacts for the additive join. Do not rerun or
   reingest any base arm.
3. Use the protocol instruction, five seeds, four workers, 15 second stagger, and the bounded
   five attempt silent completion safeguard.
4. Require successful setup validation, run verification, required lifecycle hooks, cell namespace
   isolation, and no cross cell memory contamination.
5. Record the gateway model, provider order, fallback policy, source commit, prices, and all
   admitted and discarded cells.

## Predictions

1. The repaired NextBit route will complete the 345 session cells without provider errors or
   unresolved silent completions.
2. The repaired Claude Mem arm will improve success on present condition tasks relative to the
   frozen controls.
3. The repaired Claude Mem arm will not produce a measurable damage signal on absent, superseded,
   contradictory, or adjacent conditions.
4. Reusing one import per condition and cloning namespaces will leave the ingestion count at one
   vendor import per condition with no per cell reingestion.

## Publication gate

Publish the additive arm only if the smoke prerequisite passes, all five condition runs complete,
all 345 planned Claude Mem cells are admitted, no silent completion remains after the bounded
safeguard, every condition passes `validate_run_setup` and `verify_run`, every required lifecycle
hook is evidenced, and `build_arm_submission.py --check` passes against the frozen `official-003`
artifacts. Any unresolved silence, provider failure, gateway bypass, import failure, missing hook
evidence, cross cell contamination, sandbox mismatch, or incomplete condition makes the run
diagnostic only.

Prices for the frozen NextBit endpoint are recorded as $0.15 per million input tokens and $0.35
per million output tokens, as of 2026-09-07. These values are accounting metadata and do not alter
the model or routing policy.

<!-- results are appended below this line; everything above is frozen -->

