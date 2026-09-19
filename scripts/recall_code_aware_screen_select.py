"""Apply preregistration 090's 72-cell executable screen gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VARIANTS = ("M0_raw", "M1_code_neighbors")
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


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def _trace_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _validate_mechanism(
    trace: dict[str, Any], variant: str, version: dict[str, Any], corpus_sha256: str
) -> None:
    headers = trace.get("headers", {})
    required = {
        "x-recall-variant": variant,
        "x-recall-corpus-sha256": corpus_sha256,
        "x-recall-served-commit": version.get("git_commit"),
        "x-recall-generation": version.get("generation_id"),
        "x-recall-code-aware-fallback": "0",
        "x-recall-neighbour-invalid": "0",
        "x-recall-code-duplicate-outputs": "0",
    }
    if not required.items() <= headers.items():
        raise ValueError(f"Search trace identity or safety drift for {variant}")
    if variant == "M0_raw":
        expected = {
            "x-recall-code-aware-attempted": "0",
            "x-recall-code-profile": "none",
            "x-recall-code-rrf-weight": "0.000000",
            "x-recall-neighbour-seed-limit": "0",
        }
    else:
        expected = {
            "x-recall-code-aware-attempted": "1",
            "x-recall-code-profile": "aml-code-exact-v1",
            "x-recall-code-rrf-weight": "0.500000",
            "x-recall-neighbour-seed-limit": "8",
        }
    if not expected.items() <= headers.items():
        raise ValueError(f"code-aware mechanism drift for {variant}")
    wall_time_ms = trace.get("wall_time_ms")
    if not isinstance(wall_time_ms, (int, float)) or isinstance(wall_time_ms, bool):
        raise TypeError(f"outer Search latency is missing for {variant}")


def load_run(
    path: Path,
    variant: str,
    expected_corpus_sha256: str,
    *,
    expected_cells: frozenset[tuple[str, int]] = EXPECTED_CELLS,
) -> dict[str, Any]:
    environment = _json(path / "environment.json")
    version = _json(path / "service-version.json")
    admission = _json(path / "admission.json")
    costs = _json(path / "costs.json")
    if environment.get("model") != "deepseek/deepseek-v4-flash":
        raise ValueError(f"model drift for {variant}")
    if environment.get("arms") != ["recall_hosted"]:
        raise ValueError(f"arm drift for {variant}")
    if (
        environment.get("condition") != "present"
        or environment.get("memory_instruction") != "protocol"
    ):
        raise ValueError(f"condition or prompt drift for {variant}")
    if version.get("variant") != variant:
        raise ValueError(f"served variant drift for {variant}")
    records: dict[tuple[str, int], dict[str, Any]] = {}
    for line in (path / "records.final.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        cell = (str(record["task_id"]), int(record["seed"]))
        if record.get("arm") != "recall_hosted" or cell in records:
            raise ValueError(f"record identity drift for {variant}")
        records[cell] = record
    if set(records) != set(expected_cells):
        raise ValueError(f"task or seed drift for {variant}")
    admitted = {
        (str(item["task_id"]), int(item["seed"]))
        for item in admission.get("verdicts", [])
        if item.get("arm") == "recall_hosted" and item.get("admitted") is True
    }
    traces = _trace_rows(path / "search-trace.jsonl")
    expected_trace_count = sum(
        int(record.get("memory_call_count", 0)) for record in records.values()
    )
    if len(traces) != expected_trace_count:
        raise ValueError(
            f"Search trace count drift for {variant}: "
            f"expected {expected_trace_count}, got {len(traces)}"
        )
    for trace in traces:
        _validate_mechanism(trace, variant, version, expected_corpus_sha256)
    return {
        "records": records,
        "admitted": admitted,
        "traces": traces,
        "version": version,
        "estimated_usd": costs.get("estimated_usd"),
    }


def select_screen(runs: dict[str, dict[str, Any]], retrieval: dict[str, Any]) -> dict[str, Any]:
    if set(runs) != set(VARIANTS):
        raise ValueError("screen requires exactly M0 and M1")
    common = set(runs["M0_raw"]["admitted"]) & set(runs["M1_code_neighbors"]["admitted"])
    baseline = runs["M0_raw"]["records"]
    candidate = runs["M1_code_neighbors"]["records"]
    candidate_only = sum(
        bool(candidate[cell]["success"]) and not bool(baseline[cell]["success"]) for cell in common
    )
    baseline_only = sum(
        bool(baseline[cell]["success"]) and not bool(candidate[cell]["success"]) for cell in common
    )
    task_deltas: dict[str, int] = {}
    for task in SCREEN_TASKS:
        baseline_success = sum(bool(baseline[(task, seed)]["success"]) for seed in range(3))
        candidate_success = sum(bool(candidate[(task, seed)]["success"]) for seed in range(3))
        task_deltas[task] = candidate_success - baseline_success
    task_wins = sum(delta > 0 for delta in task_deltas.values())
    task_losses = sum(delta < 0 for delta in task_deltas.values())

    def every_task_has(field: str) -> bool:
        return all(
            any(
                int(run["records"][(task, seed)].get("memory_call_count", 0)) > 0
                if field == "memory_call_count"
                else bool(run["records"][(task, seed)].get(field))
                for seed in range(3)
            )
            for run in runs.values()
            for task in SCREEN_TASKS
        )

    gates = {
        "retrieval_authorized": retrieval.get("screen_authorized") is True
        and retrieval.get("selected") == "M1_code_neighbors",
        "all_cells_valid_and_paired": common == set(EXPECTED_CELLS),
        "every_task_searched": every_task_has("memory_call_count"),
        "every_task_received_evidence": every_task_has("retrieved_contexts"),
        "candidate_cell_wins_exceed_losses": candidate_only > baseline_only,
        "candidate_task_wins_at_least_losses": task_wins >= task_losses,
        "no_task_regresses_by_more_than_one_seed": all(
            delta >= -1 for delta in task_deltas.values()
        ),
        "search_traces_present": all(bool(run["traces"]) for run in runs.values()),
    }
    passed = all(gates.values())
    return {
        "schema_version": 1,
        "baseline": "M0_raw",
        "candidate": "M1_code_neighbors",
        "selected": "M1_code_neighbors" if passed else "M0_raw",
        "confirmation_authorized": passed,
        "paired_cells": len(common),
        "candidate_only_wins": candidate_only,
        "baseline_only_wins": baseline_only,
        "candidate_task_wins": task_wins,
        "candidate_task_losses": task_losses,
        "task_seed_deltas": dict(sorted(task_deltas.items())),
        "estimated_usd": {variant: runs[variant]["estimated_usd"] for variant in VARIANTS},
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--retrieval-selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    retrieval = _json(args.retrieval_selection)
    corpus_hash = str(retrieval["lineage"]["corpus_sha256"])
    paths = {variant: args.artifact_root / variant for variant in VARIANTS}
    result = select_screen(
        {variant: load_run(path, variant, corpus_hash) for variant, path in paths.items()},
        retrieval,
    )
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
