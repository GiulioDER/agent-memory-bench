"""Select preregistration 089's 72 cell executable screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VARIANTS = ("B0_raw", "B1_raw_rerank")
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


def load_run(path: Path, variant: str, expected_corpus_sha256: str) -> dict[str, Any]:
    environment = _json(path / "environment.json")
    version = _json(path / "service-version.json")
    admission = _json(path / "admission.json")
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
    if set(records) != set(EXPECTED_CELLS):
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
        headers = trace.get("headers", {})
        expected = {
            "x-recall-variant": variant,
            "x-recall-corpus-sha256": expected_corpus_sha256,
            "x-recall-served-commit": version.get("git_commit"),
            "x-recall-generation": version.get("generation_id"),
            "x-recall-reranker-fallback": "0",
            "x-recall-reranker-permutation-valid": "1",
        }
        if not expected.items() <= headers.items():
            raise ValueError(f"Search trace identity or mechanism drift for {variant}")
        if variant == "B0_raw" and headers.get("x-recall-reranker-attempted") != "0":
            raise ValueError("B0 unexpectedly invoked reranking")
        if (
            variant == "B1_raw_rerank"
            and not {
                "x-recall-reranker-attempted": "1",
                "x-recall-reranker-completed": "1",
                "x-recall-reranker-provider": "voyage",
                "x-recall-reranker-model": "rerank-2.5",
            }.items()
            <= headers.items()
        ):
            raise ValueError("B1 reranker mechanism gate failed")
    return {"records": records, "admitted": admitted, "traces": traces, "version": version}


def select_screen(runs: dict[str, dict[str, Any]], retrieval: dict[str, Any]) -> dict[str, Any]:
    if set(runs) != set(VARIANTS):
        raise ValueError("screen requires exactly B0 and B1")
    common = set(runs["B0_raw"]["admitted"]) & set(runs["B1_raw_rerank"]["admitted"])
    baseline = runs["B0_raw"]["records"]
    candidate = runs["B1_raw_rerank"]["records"]
    candidate_only = sum(
        candidate[cell]["success"] and not baseline[cell]["success"] for cell in common
    )
    baseline_only = sum(
        baseline[cell]["success"] and not candidate[cell]["success"] for cell in common
    )
    task_wins = 0
    task_losses = 0
    for task in SCREEN_TASKS:
        baseline_success = sum(bool(baseline[(task, seed)]["success"]) for seed in range(3))
        candidate_success = sum(bool(candidate[(task, seed)]["success"]) for seed in range(3))
        task_wins += int(candidate_success > baseline_success)
        task_losses += int(candidate_success < baseline_success)
    gates = {
        "retrieval_authorized": retrieval.get("screen_authorized") is True,
        "all_cells_valid_and_paired": common == set(EXPECTED_CELLS),
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
        "candidate_cell_wins_exceed_losses": candidate_only > baseline_only,
        "candidate_task_wins_at_least_losses": task_wins >= task_losses,
        "search_traces_present": all(bool(run["traces"]) for run in runs.values()),
    }
    passed = all(gates.values())
    return {
        "schema_version": 1,
        "baseline": "B0_raw",
        "candidate": "B1_raw_rerank",
        "selected": "B1_raw_rerank" if passed else "B0_raw",
        "confirmation_authorized": passed,
        "paired_cells": len(common),
        "candidate_only_wins": candidate_only,
        "baseline_only_wins": baseline_only,
        "candidate_task_wins": task_wins,
        "candidate_task_losses": task_losses,
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--retrieval-selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    retrieval = _json(args.retrieval_selection)
    corpus_hash = str(retrieval["lineage"]["present"]["corpus_sha256"])
    paths = {variant: args.results_root / f"{args.run_prefix}-{variant}" for variant in VARIANTS}
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
