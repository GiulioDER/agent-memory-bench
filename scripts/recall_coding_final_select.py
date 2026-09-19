"""Apply the preregistered 102-cell present-condition confirmation gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from harness.tasks import discover_tasks

FINAL_TASKS = frozenset(
    task.task_id for task in discover_tasks() if task.task_id != "smoke-config-port"
)
EXPECTED_CELLS = frozenset((task, seed) for task in FINAL_TASKS for seed in range(3))


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def load_run(path: Path, variant: str) -> dict[str, Any]:
    environment = _json(path / "environment.json")
    version = _json(path / "service-version.json")
    admission = _json(path / "admission.json")
    if environment.get("model") != "deepseek/deepseek-v4-flash":
        raise ValueError(f"model drift for {variant}")
    if environment.get("arms") != ["recall_hosted"]:
        raise ValueError(f"arm drift for {variant}")
    if environment.get("memory_instruction") != "protocol" or environment.get(
        "condition"
    ) != "present":
        raise ValueError(f"prompt or condition drift for {variant}")
    if version.get("variant") != variant:
        raise ValueError(f"served variant mismatch for {variant}")
    records: dict[tuple[str, int], dict[str, Any]] = {}
    for line in (path / "records.final.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        cell = (str(record["task_id"]), int(record["seed"]))
        if record.get("arm") != "recall_hosted" or cell in records:
            raise ValueError(f"record identity drift for {variant}")
        records[cell] = record
    if set(records) != set(EXPECTED_CELLS):
        raise ValueError(f"task or seed drift for {variant}")
    admitted = {
        (str(item["task_id"]), int(item["seed"]))
        for item in admission.get("verdicts", [])
        if item.get("arm") == "recall_hosted" and item.get("admitted") is True
    }
    return {"records": records, "admitted": admitted, "version": version}


def select_final(
    baseline: dict[str, Any], candidate: dict[str, Any], candidate_name: str
) -> dict[str, Any]:
    common = set(baseline["admitted"]) & set(candidate["admitted"])
    baseline_records = baseline["records"]
    candidate_records = candidate["records"]
    candidate_only = sum(
        bool(candidate_records[cell]["success"])
        and not bool(baseline_records[cell]["success"])
        for cell in common
    )
    baseline_only = sum(
        bool(baseline_records[cell]["success"])
        and not bool(candidate_records[cell]["success"])
        for cell in common
    )
    net = candidate_only - baseline_only
    complete_admission = common == set(EXPECTED_CELLS)
    return {
        "schema_version": 1,
        "baseline": "C0_raw_lexical",
        "candidate": candidate_name,
        "paired_cells": len(common),
        "candidate_only_wins": candidate_only,
        "baseline_only_wins": baseline_only,
        "net_wins": net,
        "complete_admission": complete_admission,
        "passed": complete_admission and net >= 8,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    baseline = load_run(args.results_root / f"{args.run_prefix}-C0_raw_lexical", "C0_raw_lexical")
    candidate = load_run(args.results_root / f"{args.run_prefix}-{args.candidate}", args.candidate)
    result = select_final(baseline, candidate, args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
