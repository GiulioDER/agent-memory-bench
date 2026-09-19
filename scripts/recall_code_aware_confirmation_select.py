"""Apply preregistration 090's 204-cell present confirmation gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

from harness.tasks import discover_tasks
from scripts.recall_code_aware_screen_select import VARIANTS, load_run

TASKS = frozenset(task.task_id for task in discover_tasks() if task.task_id != "smoke-config-port")
EXPECTED_CELLS = frozenset((task, seed) for task in TASKS for seed in range(3))


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def _clustered_ci(deltas: dict[str, float], *, repetitions: int = 20_000) -> tuple[float, float]:
    ordered = sorted(deltas)
    rng = random.Random(90090)
    draws = [
        sum(deltas[rng.choice(ordered)] for _ in ordered) / len(ordered)
        for _ in range(repetitions)
    ]
    draws.sort()
    lower = draws[math.floor(0.025 * (len(draws) - 1))]
    upper = draws[math.ceil(0.975 * (len(draws) - 1))]
    return lower, upper


def _outcome_rate(run: dict[str, Any], outcome: str) -> float:
    values = [
        str(record.get("metadata", {}).get("outcome", "")) == outcome
        for record in run["records"].values()
    ]
    return sum(values) / len(values)


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def select_confirmation(
    runs: dict[str, dict[str, Any]], retrieval: dict[str, Any], screen: dict[str, Any]
) -> dict[str, Any]:
    if set(runs) != set(VARIANTS):
        raise ValueError("confirmation requires exactly M0 and M1")
    if (
        screen.get("confirmation_authorized") is not True
        or screen.get("selected") != "M1_code_neighbors"
    ):
        raise ValueError("screen did not authorize M1 confirmation")
    for run in runs.values():
        if set(run["records"]) != set(EXPECTED_CELLS):
            raise ValueError("confirmation task or seed population drift")
    baseline = runs["M0_raw"]["records"]
    candidate = runs["M1_code_neighbors"]["records"]
    task_deltas: dict[str, float] = {}
    for task in TASKS:
        differences = [
            float(bool(candidate[(task, seed)]["success"]))
            - float(bool(baseline[(task, seed)]["success"]))
            for seed in range(3)
        ]
        task_deltas[task] = sum(differences) / len(differences)
    overall_delta = sum(task_deltas.values()) / len(task_deltas)
    ci_lower, ci_upper = _clustered_ci(task_deltas)
    task_wins = sum(delta > 0 for delta in task_deltas.values())
    task_losses = sum(delta < 0 for delta in task_deltas.values())
    damaged = {variant: _outcome_rate(runs[variant], "damaged") for variant in VARIANTS}
    latency = {
        variant: _p95([float(trace["wall_time_ms"]) for trace in runs[variant]["traces"]])
        for variant in VARIANTS
    }
    all_admitted = all(run["admitted"] == set(EXPECTED_CELLS) for run in runs.values())
    retrieval_gates = retrieval.get("retrieval_gates", {})
    gates = {
        "all_cells_valid_and_paired": all_admitted,
        "overall_task_solve_improves": overall_delta > 0,
        "candidate_task_wins_exceed_losses": task_wins > task_losses,
        "clustered_ci_lower_positive": ci_lower > 0,
        "damaged_outcome_nondecline": damaged["M1_code_neighbors"] <= damaged["M0_raw"],
        "zero_mechanism_fallbacks": all(
            trace["headers"].get("x-recall-code-aware-fallback") == "0"
            for run in runs.values()
            for trace in run["traces"]
        ),
        "retrieval_gates_still_passed": bool(retrieval_gates)
        and all(bool(value) for value in retrieval_gates.values()),
        "search_p95_below_1000_ms": latency["M1_code_neighbors"] < 1_000,
        "search_p95_below_2x_baseline": latency["M1_code_neighbors"] < 2 * latency["M0_raw"],
    }
    passed = all(gates.values())
    return {
        "schema_version": 1,
        "baseline": "M0_raw",
        "candidate": "M1_code_neighbors",
        "selected": "M1_code_neighbors" if passed else "M0_raw",
        "robustness_authorized": passed,
        "paired_cells": len(EXPECTED_CELLS) if all_admitted else 0,
        "overall_task_solve_delta": overall_delta,
        "task_clustered_bootstrap_95_ci": [ci_lower, ci_upper],
        "candidate_task_wins": task_wins,
        "candidate_task_losses": task_losses,
        "damaged_outcome_rate": damaged,
        "search_p95_ms": latency,
        "task_deltas": dict(sorted(task_deltas.items())),
        "estimated_usd": {variant: runs[variant]["estimated_usd"] for variant in VARIANTS},
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--retrieval-selection", type=Path, required=True)
    parser.add_argument("--screen-selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    retrieval, screen = _json(args.retrieval_selection), _json(args.screen_selection)
    corpus_hash = str(retrieval["lineage"]["corpus_sha256"])
    paths = {variant: args.artifact_root / variant for variant in VARIANTS}
    runs = {
        variant: load_run(path, variant, corpus_hash, expected_cells=EXPECTED_CELLS)
        for variant, path in paths.items()
    }
    result = select_confirmation(runs, retrieval, screen)
    result["input_sha256"] = {
        variant: {
            name: hashlib.sha256((path / name).read_bytes()).hexdigest()
            for name in (
                "records.final.jsonl",
                "admission.json",
                "costs.json",
                "service-version.json",
                "search-trace.jsonl",
            )
        }
        for variant, path in paths.items()
    }
    result["retrieval_selection_sha256"] = hashlib.sha256(
        args.retrieval_selection.read_bytes()
    ).hexdigest()
    result["screen_selection_sha256"] = hashlib.sha256(
        args.screen_selection.read_bytes()
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
