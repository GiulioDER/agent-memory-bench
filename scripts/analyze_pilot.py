"""Analyse pilot-001 in the preregistered order. Reads artifacts, writes analysis.json.

Endpoints, from preregistration/000-pilot.md: (1) primary recall vs claude_md, per-task
cluster bootstrap CI plus cell McNemar; (2) per-task screening (ceiling and floor);
(3) mechanism (search rate, governing-session-reached); (4) costs; (5) exploratory
bare vs claude_md. Nothing here chooses thresholds: they were committed before the run.

    python -m scripts.analyze_pilot --run-id pilot-001
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.io import read_jsonl  # noqa: E402
from harness.stats import mcnemar_exact  # noqa: E402

DEFAULT_ARMS = ("bare", "claude_md", "recall")
SUPPORTED_ARMS = ("bare", "placebo", "claude_md", "recall")


def cluster_bootstrap(per_task_deltas: list[float], iterations: int = 10_000, seed: int = 42):
    rng = random.Random(seed)
    n = len(per_task_deltas)
    means = []
    for _ in range(iterations):
        sample = [per_task_deltas[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return means[int(0.025 * iterations)], means[int(0.975 * iterations)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="pilot-001")
    parser.add_argument(
        "--arms",
        default=",".join(DEFAULT_ARMS),
        help="comma-separated arms in the run; pilot-004 adds placebo",
    )
    args = parser.parse_args()
    run_arms = tuple(arm.strip() for arm in args.arms.split(",") if arm.strip())
    unknown = [arm for arm in run_arms if arm not in SUPPORTED_ARMS]
    if unknown:
        raise SystemExit(f"unknown arms {unknown}; choose from {SUPPORTED_ARMS}")
    run_dir = REPO / "results" / args.run_id

    records = read_jsonl(run_dir / "records.final.jsonl")
    admission = json.loads((run_dir / "admission.json").read_text(encoding="utf-8"))
    discarded = {tuple(cell) for cell in admission["discarded_cells"]}
    admitted = [r for r in records if (r.task_id, r.seed) not in discarded]

    by_cell: dict[tuple[str, int], dict[str, object]] = defaultdict(dict)
    for record in admitted:
        by_cell[record.cell][record.arm] = record

    tasks = sorted({task_id for task_id, _ in by_cell})
    per_task: dict[str, dict[str, list[bool]]] = {
        task: {arm: [] for arm in run_arms} for task in tasks
    }
    for (task_id, _seed), arms in sorted(by_cell.items()):
        for arm in run_arms:
            per_task[task_id][arm].append(bool(arms[arm].success))

    def rate(outcomes: list[bool]) -> float:
        return sum(outcomes) / len(outcomes) if outcomes else float("nan")

    # (2) preregistered screens
    screening = {}
    for task in tasks:
        bare_r, cmd_r = rate(per_task[task]["bare"]), rate(per_task[task]["claude_md"])
        ceiling = cmd_r >= 0.7 or bare_r >= 0.5
        mech = [
            r
            for r in admitted
            if r.task_id == task and r.arm == "recall" and r.memory_call_count > 0
        ]
        reached = [
            r
            for r in mech
            if any(f"sessions__{task}__" in c for c in r.retrieved_contexts)
            or any(
                f"sessions__{task}__" in str(call.get("output", ""))
                for call in r.tool_calls
                if str(call.get("name", "")).startswith("mcp__")
            )
        ]
        floor = not any(
            per_task[task][arm][i]
            for arm in run_arms
            for i in range(len(per_task[task][arm]))
        ) and len(reached) >= 2
        screening[task] = {
            **{arm: round(rate(per_task[task][arm]), 3) for arm in run_arms},
            "screen": "ceiling" if ceiling else ("floor" if floor else "keep"),
            "recall_searched": len(mech),
            "recall_reached": len(reached),
        }

    survivors = [task for task in tasks if screening[task]["screen"] == "keep"]

    def contrast(arm_a: str, arm_b: str, task_set: list[str]):
        deltas = [
            rate(per_task[t][arm_a]) - rate(per_task[t][arm_b]) for t in task_set
        ]
        mean = sum(deltas) / len(deltas)
        lo, hi = cluster_bootstrap(deltas)
        cells_a, cells_b = [], []
        for (task_id, _s), arms in sorted(by_cell.items()):
            if task_id in task_set:
                cells_a.append(bool(arms[arm_a].success))
                cells_b.append(bool(arms[arm_b].success))
        p, only_a, only_b = mcnemar_exact(cells_a, cells_b)
        return {
            "per_task_mean_delta": round(mean, 4),
            "cluster_ci95": [round(lo, 4), round(hi, 4)],
            "mcnemar_p": p,
            "discordant": {"only_" + arm_a: only_a, "only_" + arm_b: only_b},
            "n_tasks": len(task_set),
            "n_cells": len(cells_a),
        }

    # (3) mechanism, overall
    recall_records = [r for r in admitted if r.arm == "recall"]
    searched = [r for r in recall_records if r.memory_call_count > 0]
    reached_all = [
        r
        for r in searched
        if any(f"sessions__{r.task_id}__" in c for c in r.retrieved_contexts)
        or any(
            f"sessions__{r.task_id}__" in str(call.get("output", ""))
            for call in r.tool_calls
            if str(call.get("name", "")).startswith("mcp__")
        )
    ]

    analysis = {
        "run_id": args.run_id,
        "admitted_cells": len(by_cell),
        "discarded_cells": sorted(discarded),
        "arm_success": {
            arm: round(rate([bool(a[arm].success) for a in by_cell.values()]), 3)
            for arm in run_arms
        },
        "primary_recall_vs_claude_md_all_tasks": contrast("recall", "claude_md", tasks),
        "primary_recall_vs_claude_md_survivors": (
            contrast("recall", "claude_md", survivors) if survivors else None
        ),
        "exploratory_bare_vs_claude_md": contrast("bare", "claude_md", tasks),
        "mechanism": {
            "search_rate": round(len(searched) / len(recall_records), 3),
            "reached_given_searched": (
                round(len(reached_all) / len(searched), 3) if searched else None
            ),
            "reached_overall": round(len(reached_all) / len(recall_records), 3),
        },
        "screening": screening,
        "survivors": survivors,
        "n_survivors": len(survivors),
    }
    if "placebo" in run_arms:
        analysis["placebo_vs_bare"] = contrast("placebo", "bare", tasks)
        analysis["claude_md_vs_placebo"] = contrast("claude_md", "placebo", tasks)
    (run_dir / "analysis.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in analysis.items() if k != "screening"}, indent=2))
    print("\nper-task screening:")
    for task in tasks:
        s = screening[task]
        print(
            f"  {task:<20} "
            + " ".join(f"{arm}={s[arm]:.2f}" for arm in run_arms)
            + f" {s['screen']:<8} "
            f"searched={s['recall_searched']}/3 reached={s['recall_reached']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
