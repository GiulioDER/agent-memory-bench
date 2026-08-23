# pilot-002: does the check-memory-before-acting skill fix the search rate?

Status: FROZEN above the results marker once committed.

## Question

pilot-001 ended in the decision gate's "mechanism unhealthy on the search side" branch:
search rate 0.211 against reached-given-searched 0.733. The committed remedy class is
instruction/skill/model. This run measures the first candidate: replacing the one-line
instruction with recall's shipped check-memory-before-acting skill, copied verbatim from
recall origin/master `438779ff` (sha256 prefix `0ea85e7aab4736d5`, 5,428 chars). The skill
teaches searching by operations and symptoms rather than goal, and carries its own prior
measurement (run `agent-ab-skill-001`, 2026-08-23, recall's harness: search rate to 1.0,
reached 0.674 vs 0.319, p=0.0006, with the honest half that query quality barely moved).

## Grid

2 arms (`claude_md`, `recall` with `--recall-instruction skill`) x 24 tasks x 3 seeds = 144
sessions. Everything else identical to pilot-001 (model deepseek/deepseek-v4-flash, CLI
2.1.238, timeout 600 s, same corpus manifest `db31946e82a2aa14`, same tenant, same tools,
`block_concurrency=1`). Runner: `scripts/pilot.py --run-id pilot-002 --arms
claude_md,recall --recall-instruction skill`.

The `bare` arm is dropped: its pilot-001 rates stand as the screening reference, and this
run's question is the mechanism delta, which is within the recall arm. The comparison of
this run's recall arm against pilot-001's is CROSS-RUN and is reported as descriptive, never
tested: same tasks, seeds, model and corpus, but a different day and a 5.4k-char heavier
system prompt.

## Endpoints, in reporting order

1. **Mechanism (the run's reason to exist)**: search rate; reached-given-searched; reached
   overall. Beside pilot-001's 0.211 / 0.733 / 0.155, descriptively.
2. **Primary paired contrast**: task success, recall(skill) vs claude_md, per-task cluster
   bootstrap CI, cell McNemar. All 24 tasks, and the 13 pilot-001 survivors as a labelled
   subset.
3. **Costs**, including the skill's own overhead: recall-arm input tokens per session vs
   pilot-001's recall arm.

## Predictions

1. Search rate **0.60** (skill moved recall's own harness to 1.0; flash follows
   instructions worse, and the house prior says predict low).
2. Reached given searched **0.70** (the skill's own result says query quality barely
   moves; retrieval already works here).
3. Reached overall **0.42**.
4. Primary delta vs claude_md, all 24 tasks: **+0.06**, CI likely crossing zero at this
   size; on the 13-survivor subset **+0.10**.
5. Recall-arm input tokens: **+40%** vs pilot-001's recall arm (the 5.4k-char skill rides
   on every request of every turn).
6. Discarded cells fewer than 7 of 72; spend **$0.30**, cap $5 (truncate seeds, never
   tasks); wall **50 to 90 minutes**.

## Decision reading (committed now)

- Search rate >= 0.5: the skill is the fix's backbone; the full run's recall arm carries it,
  and the remaining gap is model choice.
- Search rate < 0.35: the skill text alone does not move flash; the next candidate is the
  model, and instruction work should wait for the full run's frozen model.
- Between: both knobs stay live and the full-run prereg says which is primary.

<!-- results are appended below this line; everything above is frozen -->
