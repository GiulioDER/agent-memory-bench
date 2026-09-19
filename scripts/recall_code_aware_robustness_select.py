"""Apply preregistration 090's five-condition retrieval robustness gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.recall_code_aware_select import (
    CODE_PROFILE,
    CODE_RRF_WEIGHT,
    EXPECTED_CAPTURES,
    NEIGHBOUR_SEED_LIMIT,
    VARIANTS,
    _task_rows,
    _validate_artifact,
)

CONDITIONS = ("present", "absent", "adjacent", "contradictory", "superseded")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def _condition_verdict(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    _validate_artifact(baseline, "M0_raw")
    _validate_artifact(candidate, "M1_code_neighbors")
    if baseline["namespace"] != candidate["namespace"]:
        raise ValueError("tenant lineage drift")
    if baseline["corpus_manifest_sha256"] != candidate["corpus_manifest_sha256"]:
        raise ValueError("corpus manifest drift")
    if baseline["task_set_sha256"] != candidate["task_set_sha256"]:
        raise ValueError("task set drift")
    if baseline["corpus_status"]["corpus_sha256"] != candidate["corpus_status"]["corpus_sha256"]:
        raise ValueError("corpus lineage drift")
    if baseline["version"]["git_commit"] != candidate["version"]["git_commit"]:
        raise ValueError("served commit drift")
    if (
        baseline.get("dense_embedding_pass") is not True
        or baseline.get("corpus_reused") is not False
    ):
        raise ValueError("M0 embedding ownership drift")
    if (
        candidate.get("dense_embedding_pass") is not False
        or candidate.get("corpus_reused") is not True
    ):
        raise ValueError("M1 embedding ownership drift")
    baseline_cells = {(str(row["task_id"]), int(row["capture"])): row for row in baseline["rows"]}
    candidate_cells = {
        (str(row["task_id"]), int(row["capture"])): row for row in candidate["rows"]
    }
    if set(baseline_cells) != set(candidate_cells):
        raise ValueError("paired retrieval cells drifted")
    for cell, row in baseline_cells.items():
        other = candidate_cells[cell]
        if row.get("query_sha256") != other.get("query_sha256"):
            raise ValueError(f"query identity drift for {cell}")
        if row.get("fact_terms_sha256") != other.get("fact_terms_sha256"):
            raise ValueError(f"scoring identity drift for {cell}")
    baseline_telemetry = [row["code_aware"] for row in baseline["rows"]]
    candidate_telemetry = [row["code_aware"] for row in candidate["rows"]]
    grouped = _task_rows(candidate)
    changed_tasks = [
        task
        for task, rows in grouped.items()
        if len(rows) == EXPECTED_CAPTURES
        and all(
            row["code_aware"]["top_10_order_changed"]
            or row["code_aware"]["top_10_membership_changed"]
            for row in rows
        )
    ]
    neighbour_tasks = [
        task
        for task, rows in grouped.items()
        if len(rows) == EXPECTED_CAPTURES
        and all(row["code_aware"]["neighbour_restored_count"] > 0 for row in rows)
    ]
    tokenized_tasks = [
        task
        for task, rows in grouped.items()
        if len(rows) == EXPECTED_CAPTURES
        and all(row["code_aware"]["query_token_count"] > 0 for row in rows)
    ]
    mechanism = {
        "m0_stage_off": all(
            telemetry["attempted"] is False
            and telemetry["fallback"] is False
            and telemetry["profile"] == "none"
            and telemetry["rrf_weight"] == 0
            and telemetry["neighbour_seed_limit"] == 0
            and telemetry["neighbour_invalid_count"] == 0
            and telemetry["duplicate_output_count"] == 0
            for telemetry in baseline_telemetry
        ),
        "m1_stage_exact": all(
            telemetry["attempted"] is True
            and telemetry["fallback"] is False
            and telemetry["profile"] == CODE_PROFILE
            and telemetry["rrf_weight"] == CODE_RRF_WEIGHT
            and telemetry["neighbour_seed_limit"] == NEIGHBOUR_SEED_LIMIT
            and telemetry["neighbour_invalid_count"] == 0
            and telemetry["duplicate_output_count"] == 0
            for telemetry in candidate_telemetry
        ),
        "m1_changes_at_least_17_tasks": len(changed_tasks) >= 17,
        "m1_restores_at_least_10_tasks": len(neighbour_tasks) >= 10,
    }
    base_metrics, candidate_metrics = baseline["aggregate"], candidate["aggregate"]
    retrieval = {
        "mrr_loss_within_0_02": candidate_metrics["mean_reciprocal_rank"]
        >= base_metrics["mean_reciprocal_rank"] - 0.02,
        "coverage_100_nondecline": candidate_metrics["complete_coverage_at_100"]
        >= base_metrics["complete_coverage_at_100"],
        "source_session_recall_nondecline": candidate_metrics["mean_source_session_recall"]
        >= base_metrics["mean_source_session_recall"],
        "search_p95_below_1000_ms": candidate_metrics["search_p95_ms"] < 1_000,
        "search_p95_below_2x_baseline": candidate_metrics["search_p95_ms"]
        < 2 * base_metrics["search_p95_ms"],
    }
    return {
        "passed": all(mechanism.values()) and all(retrieval.values()),
        "namespace": baseline["namespace"],
        "corpus_sha256": baseline["corpus_status"]["corpus_sha256"],
        "mechanism_gates": mechanism,
        "retrieval_gates": retrieval,
        "changed_task_count": len(changed_tasks),
        "neighbour_task_count": len(neighbour_tasks),
        "tokenized_task_count": len(tokenized_tasks),
        "baseline": base_metrics,
        "candidate": candidate_metrics,
    }


def select_robustness(
    artifacts: dict[tuple[str, str], dict[str, Any]], confirmation: dict[str, Any]
) -> dict[str, Any]:
    expected = {(condition, variant) for condition in CONDITIONS for variant in VARIANTS}
    if set(artifacts) != expected:
        raise ValueError("robustness requires all five conditions and both variants")
    if (
        confirmation.get("robustness_authorized") is not True
        or confirmation.get("selected") != "M1_code_neighbors"
    ):
        raise ValueError("confirmation did not authorize robustness")
    conditions = {
        condition: _condition_verdict(
            artifacts[(condition, "M0_raw")], artifacts[(condition, "M1_code_neighbors")]
        )
        for condition in CONDITIONS
    }
    namespaces = [value["namespace"] for value in conditions.values()]
    distinct_tenants = len(namespaces) == len(set(namespaces))
    passed = distinct_tenants and all(value["passed"] for value in conditions.values())
    return {
        "schema_version": 1,
        "baseline": "M0_raw",
        "candidate": "M1_code_neighbors",
        "selected": "M1_code_neighbors" if passed else "M0_raw",
        "raw_base_promoted": passed,
        "distinct_condition_tenants": distinct_tenants,
        "conditions": conditions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--confirmation-selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    paths = {
        (condition, variant): args.artifact_root / f"{condition}-{variant}.json"
        for condition in CONDITIONS
        for variant in VARIANTS
    }
    result = select_robustness(
        {key: _json(path) for key, path in paths.items()},
        _json(args.confirmation_selection),
    )
    result["input_sha256"] = {
        f"{key[0]}/{key[1]}": hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in paths.items()
    }
    result["confirmation_selection_sha256"] = hashlib.sha256(
        args.confirmation_selection.read_bytes()
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
