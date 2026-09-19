"""Select the executable-screen winner under preregistration 041."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.recall_hosted_replay import CODING_MATRIX_VARIANTS

SCREEN_TASKS = frozenset(
    {
        "xs-evolve-lease",
        "xs-join-batch",
        "xs-widen-manifest",
        "fa-dedup-key",
        "ts-mig-name",
        "ts-semver-pin",
        "ts-retry-cap",
        "ts-config-layer",
        "ts-atomic-write",
        "ts-idempotent-run",
        "ts-glob-hidden",
        "ts-quote-shell",
    }
)
EXPECTED_CELLS = frozenset((task, seed) for task in SCREEN_TASKS for seed in range(3))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def _load_run(path: Path, variant: str) -> dict[str, Any]:
    environment = _load_json(path / "environment.json")
    version = _load_json(path / "service-version.json")
    admission = _load_json(path / "admission.json")
    costs = _load_json(path / "costs.json")
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
    return {
        "records": records,
        "admitted": admitted,
        "invalid_cells": len(EXPECTED_CELLS - admitted),
        "estimated_usd": costs.get("estimated_usd"),
        "version": version,
    }


def select_screen(
    runs: dict[str, dict[str, Any]], retrieval: dict[str, Any]
) -> dict[str, Any]:
    if set(runs) != set(CODING_MATRIX_VARIANTS):
        raise ValueError("screen selection requires exactly one C0 through C4 run")
    common = set(EXPECTED_CELLS)
    for run in runs.values():
        common &= set(run["admitted"])
    baseline = runs["C0_raw_lexical"]["records"]
    deepest = str(retrieval.get("deepest_retrieval_eligible"))
    eligible = set(CODING_MATRIX_VARIANTS[: CODING_MATRIX_VARIANTS.index(deepest) + 1])
    summaries: dict[str, dict[str, Any]] = {}
    for name in CODING_MATRIX_VARIANTS:
        records = runs[name]["records"]
        candidate_only = sum(
            bool(records[cell]["success"]) and not bool(baseline[cell]["success"])
            for cell in common
        )
        baseline_only = sum(
            bool(baseline[cell]["success"]) and not bool(records[cell]["success"])
            for cell in common
        )
        summaries[name] = {
            "successes": sum(bool(records[cell]["success"]) for cell in common),
            "paired_cells": len(common),
            "candidate_only_wins": candidate_only,
            "baseline_only_wins": baseline_only,
            "net_wins": candidate_only - baseline_only,
            "invalid_cells": runs[name]["invalid_cells"],
            "memory_calls": sum(int(records[cell].get("memory_call_count", 0)) for cell in common),
            "evidence_deliveries": sum(
                bool(records[cell].get("retrieved_contexts")) for cell in common
            ),
            "estimated_usd": runs[name]["estimated_usd"],
        }
    metrics = retrieval["variants"]
    candidates = [
        name
        for name in CODING_MATRIX_VARIANTS[1:]
        if name in eligible and summaries[name]["net_wins"] > 0
    ]
    winner = "C0_raw_lexical"
    if candidates:
        winner = max(
            candidates,
            key=lambda name: (
                summaries[name]["successes"],
                float(metrics[name]["complete_coverage_at_10"]),
                float(metrics[name]["mean_reciprocal_rank"]),
                -float(metrics[name]["mean_character_count"]),
                -float(metrics[name]["search_p95_ms"]),
            ),
        )
    return {
        "schema_version": 1,
        "baseline": "C0_raw_lexical",
        "promoted_candidate": winner,
        "common_admitted_cells": len(common),
        "retrieval_eligibility_ceiling": deepest,
        "variants": summaries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--retrieval-selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    runs = {
        name: _load_run(args.results_root / f"{args.run_prefix}-{name}", name)
        for name in CODING_MATRIX_VARIANTS
    }
    selected = select_screen(runs, _load_json(args.retrieval_selection))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
