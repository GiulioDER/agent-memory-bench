"""Independent selector for preregistration 089's clean reranker replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CONDITIONS = ("present", "absent", "superseded", "contradictory", "adjacent")
VARIANTS = ("B0_raw", "B1_raw_rerank")
EXPECTED_TASKS = 34
EXPECTED_CAPTURES = 3
EXPECTED_REQUESTS = EXPECTED_TASKS * EXPECTED_CAPTURES


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_artifact(value: dict[str, Any], condition: str, variant: str) -> None:
    if value.get("variant") != variant:
        raise ValueError(f"variant identity drift for {condition}/{variant}")
    if value.get("task_count") != EXPECTED_TASKS:
        raise ValueError(f"task population drift for {condition}/{variant}")
    if value.get("capture_count") != EXPECTED_CAPTURES:
        raise ValueError(f"capture population drift for {condition}/{variant}")
    if value.get("request_count") != EXPECTED_REQUESTS:
        raise ValueError(f"request population drift for {condition}/{variant}")
    version = value.get("version", {})
    expected_version = {
        "variant": variant,
        "embedding_profile": "voyage-context-4-v1",
        "reranker_provider": "voyage",
        "reranker_model": "rerank-2.5",
        "candidate_width": 100,
        "rrf_constant": 60,
    }
    if not expected_version.items() <= version.items():
        raise ValueError(f"service identity drift for {condition}/{variant}")
    expected_cells = {(str(row["task_id"]), int(row["capture"])) for row in value.get("rows", [])}
    if len(expected_cells) != EXPECTED_REQUESTS:
        raise ValueError(f"missing or duplicate retrieval cells for {condition}/{variant}")
    for row in value["rows"]:
        telemetry = row.get("reranker")
        if not isinstance(telemetry, dict):
            raise TypeError(f"missing reranker telemetry for {condition}/{variant}")
        if telemetry.get("variant") != variant:
            raise ValueError(f"served variant header drift for {condition}/{variant}")
        if telemetry.get("served_commit") != version.get("git_commit"):
            raise ValueError(f"served commit header drift for {condition}/{variant}")
        if telemetry.get("corpus_sha256") != value["corpus_status"]["corpus_sha256"]:
            raise ValueError(f"corpus header drift for {condition}/{variant}")
        if telemetry.get("generation_id") != value["corpus_status"]["generation_id"]:
            raise ValueError(f"generation header drift for {condition}/{variant}")


def select_clean_retrieval(
    artifacts: dict[tuple[str, str], dict[str, Any]], graph_preflight: dict[str, Any]
) -> dict[str, Any]:
    expected = {(condition, variant) for condition in CONDITIONS for variant in VARIANTS}
    if set(artifacts) != expected:
        raise ValueError("selection requires exactly ten condition and variant artifacts")
    if graph_preflight.get("verdict") != "ineligible_zero_relations":
        raise ValueError("graph preflight did not record the preregistered zero relation verdict")
    for (condition, variant), value in artifacts.items():
        _validate_artifact(value, condition, variant)
    lineage: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        baseline = artifacts[(condition, "B0_raw")]
        candidate = artifacts[(condition, "B1_raw_rerank")]
        if baseline["namespace"] != candidate["namespace"]:
            raise ValueError(f"tenant lineage drift for {condition}")
        if (
            baseline["corpus_status"]["corpus_sha256"]
            != candidate["corpus_status"]["corpus_sha256"]
        ):
            raise ValueError(f"corpus lineage drift for {condition}")
        if baseline.get("dense_embedding_pass") is not True:
            raise ValueError(f"B0 did not own the dense embedding pass for {condition}")
        if (
            candidate.get("dense_embedding_pass") is not False
            or candidate.get("corpus_reused") is not True
        ):
            raise ValueError(f"B1 did not reuse the B0 corpus for {condition}")
        lineage[condition] = {
            "namespace": baseline["namespace"],
            "corpus_sha256": baseline["corpus_status"]["corpus_sha256"],
            "b0_dense_embedding_pass": True,
            "b1_dense_embedding_pass": False,
        }

    baseline_present = artifacts[("present", "B0_raw")]["aggregate"]
    candidate_present = artifacts[("present", "B1_raw_rerank")]["aggregate"]
    candidate_rows = [
        row for condition in CONDITIONS for row in artifacts[(condition, "B1_raw_rerank")]["rows"]
    ]
    baseline_rows = [
        row for condition in CONDITIONS for row in artifacts[(condition, "B0_raw")]["rows"]
    ]
    mechanism = {
        "b0_reranker_attempts_zero": all(
            row["reranker"]["attempted"] is False for row in baseline_rows
        ),
        "b1_every_request_attempted": all(
            row["reranker"]["attempted"] is True for row in candidate_rows
        ),
        "b1_every_request_completed": all(
            row["reranker"]["completed"] is True for row in candidate_rows
        ),
        "b1_provider_model_exact": all(
            row["reranker"]["provider"] == "voyage" and row["reranker"]["model"] == "rerank-2.5"
            for row in candidate_rows
        ),
        "b1_zero_fallbacks": all(row["reranker_fallback"] is False for row in candidate_rows),
        "b1_full_candidate_permutations": all(
            row["reranker"]["permutation_valid"] is True
            and row["reranker"]["input_count"] == row["reranker"]["output_count"]
            for row in candidate_rows
        ),
    }
    retrieval_gates = {
        "present_mrr_improves": (
            candidate_present["mean_reciprocal_rank"] > baseline_present["mean_reciprocal_rank"]
        ),
        "present_coverage_100_nondecline": (
            candidate_present["complete_coverage_at_100"]
            >= baseline_present["complete_coverage_at_100"]
        ),
        "present_source_session_recall_nondecline": (
            candidate_present["mean_source_session_recall"]
            >= baseline_present["mean_source_session_recall"]
        ),
        "search_p95_below_5000_ms": candidate_present["search_p95_ms"] < 5_000,
        "search_p95_below_3x_baseline": (
            candidate_present["search_p95_ms"] < 3 * baseline_present["search_p95_ms"]
        ),
    }
    passed = all(mechanism.values()) and all(retrieval_gates.values())
    return {
        "schema_version": 1,
        "baseline": "B0_raw",
        "candidate": "B1_raw_rerank",
        "selected": "B1_raw_rerank" if passed else "B0_raw",
        "screen_authorized": passed,
        "dense_embedding_passes": 5,
        "lineage": lineage,
        "mechanism_gates": mechanism,
        "retrieval_gates": retrieval_gates,
        "present": {"baseline": baseline_present, "candidate": candidate_present},
        "estimated_reranker_cost_usd": sum(
            float(
                artifacts[(condition, "B1_raw_rerank")]["aggregate"]["estimated_reranker_cost_usd"]
            )
            for condition in CONDITIONS
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--graph-preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    paths = {
        (condition, variant): args.artifacts_root / f"{condition}-{variant}.json"
        for condition in CONDITIONS
        for variant in VARIANTS
    }
    selected = select_clean_retrieval(
        {key: _json(path) for key, path in paths.items()}, _json(args.graph_preflight)
    )
    selected["input_sha256"] = {
        f"{condition}/{variant}": _sha256(path) for (condition, variant), path in paths.items()
    }
    selected["graph_preflight_sha256"] = _sha256(args.graph_preflight)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
