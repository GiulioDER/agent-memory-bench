"""How much of a run's headline contrast is an artefact of which cells were discarded.

The admission gate discards a paired cell when any arm cannot prove its treatment was applied.
That is correct, and it is also asymmetric: in pilot-004 every one of the nine discarded cells was
discarded because a RECALL session failed operationally, while bare and claude_md never lost a
cell. An arm that gets to drop the cells where its own wiring broke is being reported under a
condition the other arms are not, so the published rate is conditional on that wiring working.

This script recomputes the same contrasts twice on the same records:

- PER-PROTOCOL, over the admitted cells only. This reproduces `scripts/analyze_pilot.py` and
  should match `analysis.json` exactly. If it does not, one of the two is wrong.
- INTENTION-TO-TREAT, over every cell that has a record for every arm, scoring the dropped
  sessions as they were actually recorded rather than removing them.

Neither replaces the preregistered analysis. The preregistered contrast is the per-protocol one;
this exists so that a reader can see how much the discard rule is carrying, and so that the
difference is a published number rather than a question nobody ran.

    python -m scripts.discard_sensitivity --run-id pilot-004-placebo \\
        --arms bare,placebo,claude_md,recall

Written 2026-08-25, after the pilot-004 discard accounting was rechecked against admission.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.stats import mcnemar_exact
from scripts.analyze_pilot import cluster_bootstrap

DEFAULT_CONTRASTS = (
    ("recall", "claude_md"),
    ("recall", "bare"),
    ("placebo", "bare"),
    ("claude_md", "placebo"),
)


def contrast(by_cell, cells, arm_a, arm_b):
    per_task = defaultdict(lambda: {arm_a: [], arm_b: []})
    for cell in sorted(cells):
        task_id, _seed = cell
        per_task[task_id][arm_a].append(bool(by_cell[cell][arm_a]["success"]))
        per_task[task_id][arm_b].append(bool(by_cell[cell][arm_b]["success"]))
    tasks = sorted(per_task)
    deltas = [
        sum(per_task[t][arm_a]) / len(per_task[t][arm_a])
        - sum(per_task[t][arm_b]) / len(per_task[t][arm_b])
        for t in tasks
    ]
    low, high = cluster_bootstrap(deltas)
    outcomes_a = [bool(by_cell[cell][arm_a]["success"]) for cell in sorted(cells)]
    outcomes_b = [bool(by_cell[cell][arm_b]["success"]) for cell in sorted(cells)]
    p_value, only_a, only_b = mcnemar_exact(outcomes_a, outcomes_b)
    return {
        "per_task_mean_delta": round(sum(deltas) / len(deltas), 4),
        "cluster_ci95": [round(low, 4), round(high, 4)],
        "mcnemar_p": p_value,
        "discordant": {f"only_{arm_a}": only_a, f"only_{arm_b}": only_b},
        "n_tasks": len(tasks),
        "n_cells": len(outcomes_a),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="pilot-004-placebo")
    parser.add_argument("--arms", default="bare,placebo,claude_md,recall")
    args = parser.parse_args()
    arms = tuple(item.strip() for item in args.arms.split(",") if item.strip())

    run_dir = REPO / "results" / args.run_id
    records = [
        json.loads(line)
        for line in (run_dir / "records.final.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    admission = json.loads((run_dir / "admission.json").read_text(encoding="utf-8"))
    discarded = {tuple(cell) for cell in admission["discarded_cells"]}

    by_cell: dict[tuple[str, int], dict[str, dict]] = defaultdict(dict)
    for record in records:
        by_cell[(record["task_id"], record["seed"])][record["arm"]] = record
    complete = {cell for cell, held in by_cell.items() if all(arm in held for arm in arms)}

    print(f"run {args.run_id}: {len(complete)} cells with a record for every arm")
    print("\nsessions the admission gate dropped, and what they actually recorded:")
    for verdict in admission["verdicts"]:
        if verdict["admitted"]:
            continue
        record = by_cell[(verdict["task_id"], verdict["seed"])].get(verdict["arm"])
        kind = "wiring" if any("MCP server" in r for r in verdict["reasons"]) else "provider"
        scored = "n/a" if record is None else record["success"]
        print(
            f"  {verdict['task_id']:18s} seed={verdict['seed']} {verdict['arm']:10s} "
            f"{kind:8s} success={scored}"
        )

    for label, cells in (
        ("PER-PROTOCOL (preregistered: admitted cells only)", complete - discarded),
        ("INTENTION-TO-TREAT (every complete cell, dropped sessions scored as recorded)", complete),
    ):
        print(f"\n=== {label}: n={len(cells)} ===")
        for arm in arms:
            wins = sum(1 for cell in cells if by_cell[cell][arm]["success"])
            print(f"  {arm:10s} {wins}/{len(cells)} = {wins / len(cells):.3f}")
        for arm_a, arm_b in DEFAULT_CONTRASTS:
            if arm_a in arms and arm_b in arms:
                print(f"  {arm_a} - {arm_b}: {json.dumps(contrast(by_cell, cells, arm_a, arm_b))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
