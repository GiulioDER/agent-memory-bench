# Additive leaderboard runs

The official leaderboard has a frozen base run and a set of independently validated arm
submissions. A contributor does not rerun the base arms.

## The base run

`site/data/leaderboard.config.json` keeps `official_run` as the calibration base. Its
`leaderboard_summary.json` is immutable once published. The base defines the model, task roster,
conditions, seeds, baseline, reference tracks and the common admission frame.

## A single arm

An accepted arm is recorded by adding its run id under `arm_runs`:

```json
{
  "official_run": "official-003",
  "arm_runs": {
    "cognee": "cognee-001"
  },
  "updated": "2026-09-02"
}
```

The submission run contains `results/cognee-001/arm_summary.json`:

```json
{
  "schema": 1,
  "generated_by": "scripts/build_arm_submission.py",
  "run": {
    "id": "cognee-001",
    "date": "2026-09-02",
    "cli": "claude-code",
    "model": "deepseek/deepseek-v4-flash",
    "tasks": 26,
    "sessionsPerCell": 1,
    "prereg": "preregistration/027-cognee-joined-pass.md"
  },
  "arm": "cognee",
  "base_run": "official-003",
  "result": {
    "success": 0.0,
    "delta": 0.0,
    "ci": [0.0, 0.0],
    "discarded": 0,
    "tokensPerTask": 0,
    "costPerTask": 0.0,
    "searchRate": 0.0,
    "byCondition": {}
  },
  "join": {
    "baseRun": "official-003",
    "baseAdmittedCells": 317,
    "joinedCells": 0,
    "baseCellsLostToJoin": 317,
    "conditions": ["absent", "adjacent", "contradictory", "present", "superseded"]
  }
}
```

The zeroes above are schema placeholders only and are not a valid submission because the joined
cell count must be positive. A real submission must be generated from its published records and
costs, not typed by hand. The builder checks the arm name, run id, base run, model, task count,
session count, join metadata and every published result field. CI runs the builder in `--check`
mode, which regenerates the summary from the records and fails if anybody edits a number.

## What makes a submission acceptable

1. The adapter and frozen config were recorded and hashed before measurement. Vendor review is
   requested after publication; it is a disclosure and challenge path, not a reason to discard a
   completed anonymous arm.
2. The preregistration was committed before the first session.
3. The run used the base model, task roster, conditions, seeds, instruction and corpus manifest.
4. Every condition has the ordinary records, streams, costs and admission artifacts.
5. `verify_run` passes for every condition, and a join check intersects the arm with the base
   admitted cells by `(task_id, seed, condition)`.
6. The report states the joined cell count and the base cells lost to the join. It never presents a
   joined result as if it enlarged the frozen base grid.
7. Search rate is reported as a diagnostic column. It does not invalidate the accuracy result,
   because a product's decision not to search is itself part of the measured behaviour. Ingestion
   tokens and wall time remain reported separately.
8. The arm is not named publicly while its vendor review hold is active. An otherwise accepted arm
   may appear under an anonymous label during that window.

The page carries the source run for every row. An additive row is labelled as joined to the base
run, so a reader can distinguish a new arm measurement from a rerun of the official grid.

## Why this is statistically honest

The existing leaderboard already compares arm records cell by cell. The additive path keeps that
same unit of analysis, but intersects a new arm with the frozen base admission set. It does not
pretend that a new run can repair or enlarge the base run, and it does not require unrelated
vendors to spend money again. The uncertainty note must identify the comparison as a cross-run join,
because the product and base sessions were not captured at the same time.
