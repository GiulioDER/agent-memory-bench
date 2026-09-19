"""Apply preregistration 089's independent 1,020 cell confirmation gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

from harness.tasks import discover_tasks
from scripts.recall_clean_reranker_select import CONDITIONS, VARIANTS

TASKS = frozenset(task.task_id for task in discover_tasks() if task.task_id != "smoke-config-port")
EXPECTED_CELLS = frozenset((task, seed) for task in TASKS for seed in range(3))


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def _traces(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_run(path: Path, condition: str, variant: str, corpus_sha256: str) -> dict[str, Any]:
    environment = _json(path / "environment.json")
    version = _json(path / "service-version.json")
    admission = _json(path / "admission.json")
    if environment.get("model") != "deepseek/deepseek-v4-flash":
        raise ValueError(f"model drift for {condition}/{variant}")
    if environment.get("arms") != ["recall_hosted"] or environment.get("condition") != condition:
        raise ValueError(f"arm or condition drift for {condition}/{variant}")
    if environment.get("memory_instruction") != "protocol" or version.get("variant") != variant:
        raise ValueError(f"prompt or service drift for {condition}/{variant}")
    records: dict[tuple[str, int], dict[str, Any]] = {}
    for line in (path / "records.final.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        cell = (str(record["task_id"]), int(record["seed"]))
        if record.get("arm") != "recall_hosted" or cell in records:
            raise ValueError(f"record identity drift for {condition}/{variant}")
        records[cell] = record
    if set(records) != set(EXPECTED_CELLS):
        raise ValueError(f"task or seed drift for {condition}/{variant}")
    admitted = {
        (str(item["task_id"]), int(item["seed"]))
        for item in admission.get("verdicts", [])
        if item.get("arm") == "recall_hosted" and item.get("admitted") is True
    }
    traces = _traces(path / "search-trace.jsonl")
    expected_trace_count = sum(
        int(record.get("memory_call_count", 0)) for record in records.values()
    )
    if len(traces) != expected_trace_count:
        raise ValueError(
            f"Search trace count drift for {condition}/{variant}: "
            f"expected {expected_trace_count}, got {len(traces)}"
        )
    for trace in traces:
        headers = trace.get("headers", {})
        required = {
            "x-recall-variant": variant,
            "x-recall-corpus-sha256": corpus_sha256,
            "x-recall-served-commit": version.get("git_commit"),
            "x-recall-generation": version.get("generation_id"),
            "x-recall-reranker-fallback": "0",
            "x-recall-reranker-permutation-valid": "1",
        }
        if not required.items() <= headers.items():
            raise ValueError(f"trace identity or fallback drift for {condition}/{variant}")
        attempted = headers.get("x-recall-reranker-attempted")
        completed = headers.get("x-recall-reranker-completed")
        if variant == "B0_raw" and attempted != "0":
            raise ValueError(f"B0 reranker activation in {condition}")
        if variant == "B1_raw_rerank" and (attempted, completed) != ("1", "1"):
            raise ValueError(f"B1 reranker mechanism failure in {condition}")
    return {"records": records, "admitted": admitted, "traces": traces, "version": version}


def _rate(run: dict[str, Any], field: str = "success") -> float:
    values = [bool(record[field]) for record in run["records"].values()]
    return sum(values) / len(values)


def _outcome_rate(run: dict[str, Any], outcomes: set[str]) -> float:
    values = [
        str(record.get("metadata", {}).get("outcome", "")) in outcomes
        for record in run["records"].values()
    ]
    return sum(values) / len(values)


def _clustered_ci(deltas: dict[str, float], *, repetitions: int = 20_000) -> tuple[float, float]:
    ordered = sorted(deltas)
    rng = random.Random(89089)
    draws = []
    for _ in range(repetitions):
        draws.append(sum(deltas[rng.choice(ordered)] for _ in ordered) / len(ordered))
    draws.sort()
    lower = draws[math.floor(0.025 * (len(draws) - 1))]
    upper = draws[math.ceil(0.975 * (len(draws) - 1))]
    return lower, upper


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def select_confirmation(
    runs: dict[tuple[str, str], dict[str, Any]], retrieval: dict[str, Any], screen: dict[str, Any]
) -> dict[str, Any]:
    expected = {(condition, variant) for condition in CONDITIONS for variant in VARIANTS}
    if set(runs) != expected:
        raise ValueError("confirmation requires exactly ten condition and variant runs")
    if (
        screen.get("confirmation_authorized") is not True
        or screen.get("selected") != "B1_raw_rerank"
    ):
        raise ValueError("screen did not authorize B1 confirmation")
    all_admitted = all(run["admitted"] == set(EXPECTED_CELLS) for run in runs.values())
    task_deltas: dict[str, float] = {}
    for task in TASKS:
        differences = []
        for condition in CONDITIONS:
            for seed in range(3):
                baseline = bool(runs[(condition, "B0_raw")]["records"][(task, seed)]["success"])
                candidate = bool(
                    runs[(condition, "B1_raw_rerank")]["records"][(task, seed)]["success"]
                )
                differences.append(float(candidate) - float(baseline))
        task_deltas[task] = sum(differences) / len(differences)
    overall_delta = sum(task_deltas.values()) / len(task_deltas)
    ci_lower, ci_upper = _clustered_ci(task_deltas)
    condition_rates: dict[str, dict[str, float]] = {}
    wrong_damage_deltas: dict[str, float] = {}
    for condition in CONDITIONS:
        baseline = runs[(condition, "B0_raw")]
        candidate = runs[(condition, "B1_raw_rerank")]
        b_rate, c_rate = _rate(baseline), _rate(candidate)
        condition_rates[condition] = {
            "baseline": b_rate,
            "candidate": c_rate,
            "delta": c_rate - b_rate,
        }
        if condition != "present":
            wrong_damage_deltas[condition] = _outcome_rate(candidate, {"damaged"}) - _outcome_rate(
                baseline, {"damaged"}
            )

    def youden_floor(variant: str) -> float:
        present = _rate(runs[("present", variant)])
        adversarial = [
            record
            for condition in CONDITIONS
            if condition != "present"
            for record in runs[(condition, variant)]["records"].values()
        ]
        harm_ceiling = sum(
            str(record.get("metadata", {}).get("outcome", "")) in {"damaged", "ambiguous_failure"}
            for record in adversarial
        ) / len(adversarial)
        return present - harm_ceiling

    baseline_j = youden_floor("B0_raw")
    candidate_j = youden_floor("B1_raw_rerank")
    trace_search_ms = {
        variant: [
            float(trace["headers"]["x-recall-search-ms"])
            for condition in CONDITIONS
            for trace in runs[(condition, variant)]["traces"]
        ]
        for variant in VARIANTS
    }
    gates = {
        "all_cells_valid_and_paired": all_admitted,
        "overall_clustered_ci_lower_positive": ci_lower > 0,
        "present_task_solve_improves": condition_rates["present"]["delta"] > 0,
        "no_condition_loses_over_0_02": all(
            value["delta"] >= -0.02 for value in condition_rates.values()
        ),
        "youden_j_floor_nondecline": candidate_j >= baseline_j,
        "wrong_fact_damage_within_0_02": all(
            delta <= 0.02 for delta in wrong_damage_deltas.values()
        ),
        "every_cell_searched": all(
            int(record.get("memory_call_count", 0)) > 0
            for run in runs.values()
            for record in run["records"].values()
        ),
        "every_cell_received_evidence": all(
            bool(record.get("retrieved_contexts"))
            for run in runs.values()
            for record in run["records"].values()
        ),
        "traces_present": all(bool(run["traces"]) for run in runs.values()),
        "latency_below_5000_ms": _p95(trace_search_ms["B1_raw_rerank"]) < 5_000,
        "latency_below_3x_baseline": (
            _p95(trace_search_ms["B1_raw_rerank"]) < 3 * _p95(trace_search_ms["B0_raw"])
        ),
        "retrieval_gate_still_passed": retrieval.get("screen_authorized") is True,
    }
    passed = all(gates.values())
    return {
        "schema_version": 1,
        "baseline": "B0_raw",
        "candidate": "B1_raw_rerank",
        "selected": "B1_raw_rerank" if passed else "B0_raw",
        "passed": passed,
        "expected_cells": 1_020,
        "paired_contrasts": len(CONDITIONS) * len(EXPECTED_CELLS),
        "overall_delta": overall_delta,
        "task_clustered_bootstrap_95_ci": [ci_lower, ci_upper],
        "condition_rates": condition_rates,
        "wrong_fact_damage_deltas": wrong_damage_deltas,
        "youden_j_floor": {"baseline": baseline_j, "candidate": candidate_j},
        "search_p95_ms": {variant: _p95(values) for variant, values in trace_search_ms.items()},
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--retrieval-selection", type=Path, required=True)
    parser.add_argument("--screen-selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    retrieval, screen = _json(args.retrieval_selection), _json(args.screen_selection)
    paths = {
        (condition, variant): args.results_root / f"{args.run_prefix}-{condition}-{variant}"
        for condition in CONDITIONS
        for variant in VARIANTS
    }
    runs = {
        key: load_run(path, key[0], key[1], retrieval["lineage"][key[0]]["corpus_sha256"])
        for key, path in paths.items()
    }
    result = select_confirmation(runs, retrieval, screen)
    result["input_sha256"] = {
        f"{condition}/{variant}": hashlib.sha256(
            (path / "records.final.jsonl").read_bytes()
        ).hexdigest()
        for (condition, variant), path in paths.items()
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
