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
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.io import read_jsonl
from harness.reached import mechanism, reached_by_content, reached_by_path
from harness.stats import cluster_bootstrap as _cluster_bootstrap
from harness.stats import effect_concentration, mcnemar_exact
from harness.tasks import discover_tasks

DEFAULT_ARMS = ("bare", "claude_md", "recall")
SUPPORTED_ARMS = ("bare", "placebo", "claude_md", "recall")


#: Re-exported so `scripts/discard_sensitivity.py` keeps importing it from here, while there is
#: only ONE implementation. This module used to carry a second copy with seed=42 against
#: harness.stats's 12345, and it computed every published headline interval.
def cluster_bootstrap(per_task_deltas, iterations: int = 10_000, seed: int = 12345):
    interval = _cluster_bootstrap(per_task_deltas, iterations=iterations, seed=seed)
    if interval is not None:
        return interval
    # Every delta identical, so every resample returns that same value. `harness.stats` answers
    # None here because a zero-width interval reads as precision and is the opposite of it; this
    # analyser still has to emit two numbers, so it emits the constant the sample actually holds.
    # NOT (0.0, 0.0): for a survivor subset where every task moved by the same nonzero amount that
    # would report an interval straddling zero for a sample that never touched it.
    values = [float(d) for d in per_task_deltas]
    constant = values[0] if values else 0.0
    return (constant, constant)


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

    # The governing fact, from the two places it is already written down: the audited fact_terms,
    # and the authored decision turn that `scripts/build_oracle_bundles.py` extracts. Neither is a
    # new hand-maintained list, which is what keeps the mechanism metric honest.
    fact_terms = {task.task_id: task.fact_terms for task in discover_tasks()}
    evidence: dict[str, str] = {}
    bundles_path = REPO / "corpus" / "oracle_memory" / "bundles.jsonl"
    if bundles_path.is_file():
        for line in bundles_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            bundle = json.loads(line)
            items = bundle.get("items") or []
            if items:
                evidence[str(bundle["task_id"])] = str(items[0].get("evidence_text", ""))

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
            r for r in mech if reached_by_content(r, fact_terms.get(task, ()))[0]
        ]
        reached_path = [r for r in mech if reached_by_path(r)]
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
            "recall_reached_by_path": len(reached_path),
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
            # How few tasks carry the mean. A headline delta over 24 tasks that lives on 9 of them
            # is a different claim from one spread across all 24, and the mean cannot tell them
            # apart.
            "concentration": effect_concentration(dict(zip(task_set, deltas, strict=True))),
            "ci_note": (
                "resamples tasks within THIS run; it does not include run-to-run variance, which "
                "the pilot-003/pilot-004 replication measures at r=0.625 across per-task deltas"
            ),
        }

    # (3) mechanism, overall. Three bracketing signals rather than the filename match alone;
    # see harness/reached.py for why the published figure was the loosest of them.
    recall_records = [r for r in admitted if r.arm == "recall"]

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
        "mechanism": mechanism(recall_records, fact_terms, evidence_by_task=evidence),
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
