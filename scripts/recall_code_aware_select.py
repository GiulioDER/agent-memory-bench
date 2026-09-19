"""Mechanical selector for preregistration 090's M0 versus M1 retrieval screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VARIANTS = ("M0_raw", "M1_code_neighbors")
EXPECTED_TASKS = 34
EXPECTED_CAPTURES = 3
EXPECTED_REQUESTS = EXPECTED_TASKS * EXPECTED_CAPTURES
CODE_PROFILE = "aml-code-exact-v1"
CODE_RRF_WEIGHT = 0.5
NEIGHBOUR_SEED_LIMIT = 8


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_artifact(value: dict[str, Any], variant: str) -> None:
    if value.get("variant") != variant:
        raise ValueError(f"variant identity drift for {variant}")
    if value.get("schema_version") != 3:
        raise ValueError(f"schema identity drift for {variant}")
    if value.get("task_count") != EXPECTED_TASKS:
        raise ValueError(f"task population drift for {variant}")
    if value.get("capture_count") != EXPECTED_CAPTURES:
        raise ValueError(f"capture population drift for {variant}")
    if value.get("request_count") != EXPECTED_REQUESTS:
        raise ValueError(f"request population drift for {variant}")
    version = value.get("version", {})
    expected_version = {
        "variant": variant,
        "embedding_profile": "voyage-context-4-v1",
        "candidate_width": 100,
        "rrf_constant": 60,
        "code_profile": CODE_PROFILE,
        "code_rrf_weight": CODE_RRF_WEIGHT,
        "code_neighbour_seed_limit": NEIGHBOUR_SEED_LIMIT,
        "code_neighbour_predecessor_radius": 1,
        "code_neighbour_successor_radius": 1,
    }
    if not expected_version.items() <= version.items():
        raise ValueError(f"service identity drift for {variant}")
    rows = value.get("rows", [])
    expected_cells = {(str(row["task_id"]), int(row["capture"])) for row in rows}
    if len(expected_cells) != EXPECTED_REQUESTS:
        raise ValueError(f"missing or duplicate retrieval cells for {variant}")
    if {capture for _, capture in expected_cells} != set(range(EXPECTED_CAPTURES)):
        raise ValueError(f"capture identity drift for {variant}")
    for row in rows:
        telemetry = row.get("code_aware")
        if not isinstance(telemetry, dict):
            raise TypeError(f"missing code-aware telemetry for {variant}")
        if telemetry.get("variant") != variant:
            raise ValueError(f"served variant header drift for {variant}")
        if telemetry.get("served_commit") != version.get("git_commit"):
            raise ValueError(f"served commit header drift for {variant}")
        if telemetry.get("corpus_sha256") != value["corpus_status"]["corpus_sha256"]:
            raise ValueError(f"corpus header drift for {variant}")
        if telemetry.get("generation_id") != value["corpus_status"]["generation_id"]:
            raise ValueError(f"generation header drift for {variant}")


def _task_rows(value: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in value["rows"]:
        grouped.setdefault(str(row["task_id"]), []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row["capture"]))
    return grouped


def select_code_aware(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if set(artifacts) != set(VARIANTS):
        raise ValueError("selection requires exactly M0 and M1 retrieval artifacts")
    for variant, value in artifacts.items():
        _validate_artifact(value, variant)

    baseline = artifacts["M0_raw"]
    candidate = artifacts["M1_code_neighbors"]
    if baseline["namespace"] != candidate["namespace"]:
        raise ValueError("tenant lineage drift")
    if baseline["corpus_manifest_sha256"] != candidate["corpus_manifest_sha256"]:
        raise ValueError("corpus manifest drift")
    if baseline["task_set_sha256"] != candidate["task_set_sha256"]:
        raise ValueError("task set drift")
    if baseline["corpus_status"]["corpus_sha256"] != candidate["corpus_status"]["corpus_sha256"]:
        raise ValueError("corpus lineage drift")
    if (
        baseline.get("dense_embedding_pass") is not True
        or baseline.get("corpus_reused") is not False
    ):
        raise ValueError("M0 did not own the dense embedding pass")
    if (
        candidate.get("dense_embedding_pass") is not False
        or candidate.get("corpus_reused") is not True
    ):
        raise ValueError("M1 did not reuse the M0 corpus")

    baseline_rows = baseline["rows"]
    candidate_rows = candidate["rows"]
    baseline_by_cell = {(str(row["task_id"]), int(row["capture"])): row for row in baseline_rows}
    candidate_by_cell = {(str(row["task_id"]), int(row["capture"])): row for row in candidate_rows}
    if set(baseline_by_cell) != set(candidate_by_cell):
        raise ValueError("paired retrieval cells drifted")
    for cell, row in baseline_by_cell.items():
        other = candidate_by_cell[cell]
        if row.get("query_sha256") != other.get("query_sha256"):
            raise ValueError(f"query identity drift for {cell}")
        if row.get("fact_terms_sha256") != other.get("fact_terms_sha256"):
            raise ValueError(f"scoring label drift for {cell}")

    baseline_telemetry = [row["code_aware"] for row in baseline_rows]
    candidate_telemetry = [row["code_aware"] for row in candidate_rows]
    grouped = _task_rows(candidate)
    changed_tasks = sorted(
        task_id
        for task_id, rows in grouped.items()
        if len(rows) == EXPECTED_CAPTURES
        and all(
            row["code_aware"]["top_10_order_changed"]
            or row["code_aware"]["top_10_membership_changed"]
            for row in rows
        )
    )
    neighbour_tasks = sorted(
        task_id
        for task_id, rows in grouped.items()
        if len(rows) == EXPECTED_CAPTURES
        and all(row["code_aware"]["neighbour_restored_count"] > 0 for row in rows)
    )
    tokenized_tasks = sorted(
        task_id
        for task_id, rows in grouped.items()
        if len(rows) == EXPECTED_CAPTURES
        and all(row["code_aware"]["query_token_count"] > 0 for row in rows)
    )

    mechanism = {
        "m0_stage_off": all(
            telemetry["attempted"] is False
            and telemetry["fallback"] is False
            and telemetry["profile"] == "none"
            and telemetry["rrf_weight"] == 0
            and telemetry["query_token_count"] == 0
            and telemetry["match_candidate_count"] == 0
            and telemetry["neighbour_seed_limit"] == 0
            and telemetry["neighbour_restored_count"] == 0
            and telemetry["duplicate_output_count"] == 0
            for telemetry in baseline_telemetry
        ),
        "m1_stage_exact": all(
            telemetry["attempted"] is True
            and telemetry["fallback"] is False
            and telemetry["profile"] == CODE_PROFILE
            and telemetry["rrf_weight"] == CODE_RRF_WEIGHT
            and telemetry["neighbour_seed_limit"] == NEIGHBOUR_SEED_LIMIT
            for telemetry in candidate_telemetry
        ),
        "m1_zero_invalid_neighbours": all(
            telemetry["neighbour_invalid_count"] == 0 for telemetry in candidate_telemetry
        ),
        "m1_zero_duplicate_outputs": all(
            telemetry["duplicate_output_count"] == 0 for telemetry in candidate_telemetry
        ),
        "m1_changes_at_least_17_tasks": len(changed_tasks) >= 17,
        "m1_restores_at_least_10_tasks": len(neighbour_tasks) >= 10,
    }
    base_metrics = baseline["aggregate"]
    candidate_metrics = candidate["aggregate"]
    retrieval = {
        "present_mrr_improves": (
            candidate_metrics["mean_reciprocal_rank"] > base_metrics["mean_reciprocal_rank"]
        ),
        "present_coverage_10_nondecline": (
            candidate_metrics["complete_coverage_at_10"] >= base_metrics["complete_coverage_at_10"]
        ),
        "present_coverage_100_nondecline": (
            candidate_metrics["complete_coverage_at_100"]
            >= base_metrics["complete_coverage_at_100"]
        ),
        "present_source_session_recall_nondecline": (
            candidate_metrics["mean_source_session_recall"]
            >= base_metrics["mean_source_session_recall"]
        ),
        "search_p95_below_1000_ms": candidate_metrics["search_p95_ms"] < 1_000,
        "search_p95_below_2x_baseline": (
            candidate_metrics["search_p95_ms"] < 2 * base_metrics["search_p95_ms"]
        ),
    }
    passed = all(mechanism.values()) and all(retrieval.values())
    return {
        "schema_version": 1,
        "baseline": "M0_raw",
        "candidate": "M1_code_neighbors",
        "selected": "M1_code_neighbors" if passed else "M0_raw",
        "screen_authorized": passed,
        "dense_embedding_passes": 1,
        "lineage": {
            "namespace": baseline["namespace"],
            "corpus_sha256": baseline["corpus_status"]["corpus_sha256"],
            "m0_dense_embedding_pass": True,
            "m1_dense_embedding_pass": False,
        },
        "mechanism_gates": mechanism,
        "retrieval_gates": retrieval,
        "changed_tasks": changed_tasks,
        "neighbour_tasks": neighbour_tasks,
        "tokenized_tasks": tokenized_tasks,
        "present": {"baseline": base_metrics, "candidate": candidate_metrics},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    paths = {variant: args.artifacts_root / f"present-{variant}.json" for variant in VARIANTS}
    selected = select_code_aware({variant: _json(path) for variant, path in paths.items()})
    selected["input_sha256"] = {variant: _sha256(path) for variant, path in paths.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
