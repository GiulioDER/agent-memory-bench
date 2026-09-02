"""Build or verify one additive leaderboard arm from published run artifacts.

The additive path has one important distinction from the official grid: the submitted arm is
measured in its own run, then joined to the frozen base run on ``(task_id, seed, condition)``.
This script is the only supported writer for ``results/<run_id>/arm_summary.json``.

Examples::

    python scripts/build_arm_submission.py --write --run-id cognee-001 --arm cognee \
        --base-run official-003 --date 2026-09-02 \
        --prereg preregistration/027-cognee-joined-pass.md
    python scripts/build_arm_submission.py --check --run-id cognee-001 --arm cognee \
        --base-run official-003 --date 2026-09-02 \
        --prereg preregistration/027-cognee-joined-pass.md
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

from harness.damage import CORPUS_CONDITIONS
from harness.stats import cluster_bootstrap


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"missing published records file: {path}")
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON in {path}:{line_no}: {exc}") from exc
    return rows


def _condition_dir(results_root: Path, run_id: str, condition: str) -> Path:
    return results_root / f"{run_id}-{condition}"


def _records_by_cell(run_dir: Path, arm: str) -> dict[tuple[str, int], dict]:
    records = _read_jsonl(run_dir / "records.final.jsonl")
    selected: dict[tuple[str, int], dict] = {}
    for record in records:
        if record.get("arm") != arm:
            continue
        cell = (str(record["task_id"]), int(record["seed"]))
        if cell in selected:
            raise SystemExit(f"duplicate {arm} record for {cell} in {run_dir}")
        selected[cell] = record
    if not selected:
        raise SystemExit(f"no records for arm {arm!r} in {run_dir}")
    return selected


def _discarded(run_dir: Path) -> set[tuple[str, int]]:
    path = run_dir / "admission.json"
    if not path.is_file():
        raise SystemExit(f"missing admission report: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    return {(str(task), int(seed)) for task, seed in report.get("discarded_cells", [])}


def _costs(run_dir: Path, arm: str) -> dict:
    path = run_dir / "costs.json"
    if not path.is_file():
        raise SystemExit(f"missing cost ledger: {path}")
    costs = json.loads(path.read_text(encoding="utf-8"))
    value = costs.get("arms", {}).get(arm)
    if not isinstance(value, dict):
        raise SystemExit(f"cost ledger has no arm {arm!r}: {path}")
    return value


def _mean_rate(rows: list[dict]) -> float:
    if not rows:
        raise SystemExit("cannot calculate a rate over zero joined cells")
    return sum(bool(row["success"]) for row in rows) / len(rows)


def _result(
    *,
    results_root: Path,
    run_id: str,
    arm: str,
    base_run: str,
    conditions: tuple[str, ...],
) -> tuple[dict, dict]:
    base_summary_path = results_root / base_run / "leaderboard_summary.json"
    if not base_summary_path.is_file():
        raise SystemExit(f"missing frozen base summary: {base_summary_path}")
    base_summary = json.loads(base_summary_path.read_text(encoding="utf-8"))
    base_meta = base_summary.get("run", {})
    if not base_meta:
        raise SystemExit(f"base summary has no run metadata: {base_summary_path}")
    if arm in base_summary.get("arms", {}):
        raise SystemExit(
            f"{arm!r} is already in {base_run}; additive submissions cannot replace base arms"
        )

    joined_by_condition: dict[str, list[dict]] = {}
    baseline_by_condition: dict[str, list[dict]] = {}
    all_product_discarded: set[tuple[str, str, int]] = set()
    total_tokens = 0
    total_usd = 0.0
    total_sessions = 0

    for condition in conditions:
        base_dir = _condition_dir(results_root, base_run, condition)
        product_dir = _condition_dir(results_root, run_id, condition)
        base_records = _records_by_cell(base_dir, "claude_md")
        product_records = _records_by_cell(product_dir, arm)
        base_discarded = _discarded(base_dir)
        product_discarded = _discarded(product_dir)
        all_product_discarded.update((condition, task, seed) for task, seed in product_discarded)

        base_cells = set(base_records) - base_discarded
        product_cells = set(product_records) - product_discarded
        joined = sorted(base_cells & product_cells)
        if not joined:
            raise SystemExit(f"no joined cells for condition {condition!r}")
        joined_by_condition[condition] = [product_records[cell] for cell in joined]
        baseline_by_condition[condition] = [base_records[cell] for cell in joined]

        cost = _costs(product_dir, arm)
        total_tokens += int(cost.get("total_tokens") or 0)
        total_usd += float(cost.get("estimated_usd") or 0.0)
        total_sessions += int(cost.get("sessions") or len(product_records))

    joined_records = [row for rows in joined_by_condition.values() for row in rows]
    baseline_records = [row for rows in baseline_by_condition.values() for row in rows]
    product_success = _mean_rate(joined_records)
    baseline_success = _mean_rate(baseline_records)

    product_by_task: dict[str, list[bool]] = defaultdict(list)
    baseline_by_task: dict[str, list[bool]] = defaultdict(list)
    for product, baseline in zip(joined_records, baseline_records, strict=True):
        product_by_task[str(product["task_id"])].append(bool(product["success"]))
        baseline_by_task[str(baseline["task_id"])].append(bool(baseline["success"]))
    task_deltas = [
        sum(product_by_task[task]) / len(product_by_task[task])
        - sum(baseline_by_task[task]) / len(baseline_by_task[task])
        for task in sorted(product_by_task)
    ]
    interval = cluster_bootstrap(task_deltas)

    by_condition = {
        condition: {
            "solved": sum(bool(row["success"]) for row in rows),
            "cells": len(rows),
        }
        for condition, rows in joined_by_condition.items()
    }
    joined_cells = sum(len(rows) for rows in joined_by_condition.values())
    result = {
        "success": round(product_success, 4),
        "delta": round(product_success - baseline_success, 4),
        "ci": [round(float(interval[0]), 4), round(float(interval[1]), 4)]
        if interval is not None
        else None,
        "discarded": len(all_product_discarded),
        "tokensPerTask": round(total_tokens / total_sessions) if total_sessions else None,
        "costPerTask": round(total_usd / total_sessions, 4) if total_sessions else None,
        "byCondition": by_condition,
    }
    join = {
        "baseRun": base_run,
        "baseAdmittedCells": sum(
            len(set(_records_by_cell(_condition_dir(results_root, base_run, condition), "claude_md"))
                - _discarded(_condition_dir(results_root, base_run, condition)))
            for condition in conditions
        ),
        "joinedCells": joined_cells,
        "baseCellsLostToJoin": sum(
            len(set(_records_by_cell(_condition_dir(results_root, base_run, condition), "claude_md"))
                - _discarded(_condition_dir(results_root, base_run, condition)))
            for condition in conditions
        ) - joined_cells,
        "conditions": list(conditions),
    }
    return result, join


def build(args: argparse.Namespace) -> dict:
    results_root = Path(args.results_root)
    base_summary = json.loads(
        (results_root / args.base_run / "leaderboard_summary.json").read_text(encoding="utf-8")
    )
    result, join = _result(
        results_root=results_root,
        run_id=args.run_id,
        arm=args.arm,
        base_run=args.base_run,
        conditions=tuple(args.conditions),
    )
    return {
        "schema": 1,
        "generated_by": "scripts/build_arm_submission.py",
        "run": {
            "id": args.run_id,
            "date": args.date,
            "cli": args.cli,
            "model": base_summary["run"]["model"],
            "tasks": base_summary["run"]["tasks"],
            "sessionsPerCell": base_summary["run"]["sessionsPerCell"],
            "prereg": args.prereg,
        },
        "arm": args.arm,
        "base_run": args.base_run,
        "result": result,
        "join": join,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--base-run", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--cli", default="claude-code")
    parser.add_argument(
        "--results-root", default=str(REPO / "results"), type=Path
    )
    parser.add_argument("--conditions", nargs="+", default=list(CORPUS_CONDITIONS))
    args = parser.parse_args()

    expected = build(args)
    out = Path(args.results_root) / args.run_id / "arm_summary.json"
    if args.check:
        if not out.is_file():
            print(f"missing {out}")
            return 1
        actual = json.loads(out.read_text(encoding="utf-8"))
        if actual != expected:
            print(f"{out} does not match regeneration")
            return 1
        print(f"{out} matches its regeneration")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
