# pilot-001: does adding a memory layer make the work succeed more often, on the new task set?

Status: FROZEN above the results marker once committed. Never edit a number here; append
corrections below the marker.

## Question

On 24 tasks whose governing facts live only in the experience corpus, does Claude Code with
recall (additive: static bundle plus MCP retrieval) succeed more often than with the static
bundle alone? Secondarily: which tasks survive the ceiling and floor screens, what variance
should size the full run, and does the memory MECHANISM fire (search rate, governing session
reached)?

This pilot is also the shakedown of the whole grid pipeline; it is preregistered because its
screening decisions shape the full run and must not be chosen after seeing outcomes.

## Arms and configs

| arm | integration | admission signal |
|---|---|---|
| `bare` | none | negative checks only |
| `claude_md` | per-task static bundle (generic rules + fixture README), `--append-system-prompt-file` | negative checks; per-session `prompt_sha256` recorded in metadata and environment artifact |
| `recall` | same bundle byte-identical, tool instruction at TOP, MCP stdio server, tenant `bench-recall-pilot` | `mcp__recall__` tools present and connected |

recall frozen config sha256 (first 16): `a7abee7ae7e96f58`. Corpus manifest sha256 (first
16): `db31946e82a2aa14` (125 transcripts: 24 precursors, 99 distractors, 2 pipeline-
validation smoke transcripts; distractor-to-signal 4.1:1). One shared tenant across seeds,
disclosed: recall's eval-time surface is read-only (`recall_search`, `recall_evidence`), so
per-seed store isolation protects against nothing here.

## Grid

24 tasks (every `ts-*` under `tasks/`) x 3 seeds x 3 arms = 216 sessions. Model
`deepseek/deepseek-v4-flash` via OpenRouter (Anthropic-compatible endpoint), Claude Code CLI
2.1.238, timeout 600 s per session, tools Read/Grep/Glob/Bash/Write/Edit plus recall's two
tools on its arm only, docker denied everywhere, one cell's arms launched together,
`block_concurrency=1`. Runner: `scripts/pilot.py --run-id pilot-001`.

⚠️ Model caveat, stated now: the full run's model is a SEPARATE preregistration decision.
Screening thresholds measured under deepseek-v4-flash transfer to a different model only as
estimates, and the pilot may need a partial re-screen if the full run freezes another model.

## Endpoints, in reporting order

1. **Primary: task success, recall vs claude_md**, paired per (task, seed) cell over
   admitted cells; per-task cluster bootstrap CI is the headline; exact McNemar over cells
   reported as the consistency check that overstates confidence.
2. **Screening**: per task, `bare` and `claude_md` success rates over 3 seeds. Drop rules
   below.
3. **Mechanism**: recall-arm search rate (fraction of sessions with at least one
   `mcp__recall__` call); governing-session-reached rate (the task's own precursor file
   appears in the retrieved contexts of at least one search), overall and among searching
   sessions.
4. **Costs**: per arm, tokens and estimated USD (pricing as of 2026-08-22 from the
   OpenRouter models endpoint), wall time, discarded cells per arm.
5. Exploratory, no hypothesis: bare vs claude_md (does the README bundle matter at all).

## Predictions

House priors applied: effects predicted at a quarter to a half of intuition (eleven of
twelve past predictions ran 2 to 4x high); costs predicted at 5x the naive estimate.

1. claude_md mean per-task success: **0.25** (naive-equivalent behaviour, plus a few tasks
   where the convention is guessable at coin-flip).
2. bare mean per-task success: **0.20**.
3. Primary delta (recall minus claude_md), per-task mean: **+0.12**, cluster CI
   half-width around 0.12, so the CI **likely crosses zero at this pilot size**; the pilot
   sizes the full run rather than deciding the claim.
4. Mechanism: search rate **0.55**; governing-session-reached among searching sessions
   **0.55**; reached overall **0.30**. (Prior run measured 0.53 and 0.60 with the
   instruction buried mid-prompt in early smokes; the instruction is at the top here.)
5. Screening: **4 to 7 tasks** fail a screen (ceiling or floor), leaving 17 to 20.
6. Discarded cells: **fewer than 10 of 72**, dominated by recall MCP startup flakes.
7. Total spend: naive estimate is about $0.60; predicted **$3**, hard cap **$15** (the
   5x cost prior), enforced by the truncation rule below.
8. Wall time: **3 to 5 hours**.

## Screening thresholds (preregistered, applied per task after the run)

- **Ceiling**: drop if `claude_md` success >= 0.7 (2 of 3 seeds and up... recorded as >= 2/3)
  or `bare` success >= 0.5 (>= 2/3 counts as failing this screen at n=3).
- **Floor**: drop if NO arm succeeded in any seed AND the recall arm's mechanism fired
  (searched and reached) in at least 2 of 3 seeds; that pattern means the task is too hard
  independent of memory.

## Exclusion and truncation rules

- Admission per the gate: a (task, seed) cell is discarded unless all three arms are
  admissible; discard counts published per arm.
- Budget: if spend reaches the $15 cap, truncate SEEDS (drop seed 2, then seed 1 cells not
  yet run), never tasks.
- A session error (timeout, API failure) discards the cell via the gate; it is not a zero.

## Decision gate (committed before outcomes, from the approved plan)

- Mechanism healthy (search rate >= 0.5 and reached-given-searched >= 0.5) but primary delta
  null: **redesign tasks**, do not fund the 8-arm run.
- Mechanism unhealthy: fix the instruction placement or the retrieval surface, not the
  tasks.
- Either way, all numbers are published.

## What would falsify the design (not just the predictions)

More than half the tasks failing screens; or discard rate above 25%, which would mean the
harness, not the treatment, decides outcomes.

<!-- results are appended below this line; everything above is frozen -->

## Results, appended 2026-08-24 (run pilot-001, artifacts in results/pilot-001/)

Wall 77 minutes. 71 of 72 cells admitted; 1 discard (`ts-empty-input` seed 2, bare arm
session error). Spend $0.34 for 5.37M tokens.

### Endpoints, in the preregistered order

1. **Primary, all 24 tasks**: recall 0.394 vs claude_md 0.380; per-task mean delta
   **+0.0139**, cluster CI **[-0.0278, +0.0556]**, McNemar p=1.0 (discordant 2 vs 1).
   **Null.** On the 13 screen survivors: delta +0.0256, CI [0.0, +0.0769], driven by one
   discordant cell (`ts-nfc-count`, the one session that searched, reached the governing
   precursor, and succeeded where every other arm and seed failed).
2. **Screening**: 10 tasks fail ceiling, 1 fails floor (`ts-retry-cap`: no arm ever
   succeeds although recall searched and reached 2 of 3), **13 survivors** against the 15+
   target. Eight of the 13 survivors show zero success in every arm, which under this
   model reads as capability shortfall rather than task discrimination.
3. **Mechanism**: search rate **0.211**; reached given searched **0.733**; reached overall
   0.155. The layer works when it fires and rarely fires: the ancestor benchmark's
   diagnosis, reproduced on a neutral corpus.
4. **Costs**: totals above; per-arm detail in costs.json.
5. **Exploratory**: bare vs claude_md +0.0417, CI [-0.0278, +0.125], p=0.45. The README
   bundle does not measurably help this model.

### Predictions against measurements

| # | predicted | measured | verdict |
|---|---|---|---|
| 1 | claude_md 0.25 | 0.380 | falsified, under-predicted |
| 2 | bare 0.20 | 0.423 | falsified, under-predicted |
| 3 | delta +0.12, CI crossing zero | +0.014, CI crossing zero | direction and CI right, magnitude over-predicted again |
| 4 | search 0.55 / reached-given-searched 0.55 | 0.211 / 0.733 | search falsified low; retrieval falsified HIGH |
| 5 | 4 to 7 tasks screened out | 11 | falsified, attrition under-predicted |
| 6 | fewer than 10 discards | 1 | correct |
| 7 | spend $3, cap $15 | $0.34 | over-predicted 9x; the 5x cost prior overcorrected |
| 8 | wall 3 to 5 h | 1.3 h | over-predicted |

### Decision gate verdict

Search rate 0.211 is below the 0.5 health bar while reached-given-searched 0.733 is above
it: **mechanism unhealthy on the search side only**. Per the committed gate, the next move
is the instruction/placement/model, not task redesign. Concretely: the one-line instruction
at the top does not make deepseek-v4-flash search; the candidates to test next are the
shipped check-memory-before-acting skill path, a stronger instruction, and a more capable
model, and the ceiling/floor screens must be re-estimated under whatever model the full run
freezes (the caveat written above before the run).

### Defects found by or during the run

- Caught BEFORE launch by the sanity search: transcript renders collided on `p01.jsonl`
  names and the ingested corpus held one precursor of twenty-four; fixed (self-identifying
  names, collisions raise, regression test) and re-ingested before any session ran.
- Found at artifact review: stream files were named without the seed, so a grid run keeps
  one raw stream per (task, arm) and seeds overwrite one another; pilot-001 retains 72 of
  216 raw streams. The fsynced per-session records are complete, so analysis is unaffected;
  fixed for every future run by putting the seed in the stream name.
