"""Mechanical selector for the grounded M2 and M3 retrieval screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VARIANTS = (
    "M0_multiview_raw",
    "M2_repository_raw",
    "M3_experience_raw",
)
VIEW_KINDS = {
    "M0_multiview_raw": frozenset(),
    "M2_repository_raw": frozenset({"architectural decision", "constraint", "repository fact"}),
    "M3_experience_raw": frozenset(
        {
            "failed attempt",
            "procedure",
            "root cause",
            "successful repair",
            "symptom",
            "validation",
        }
    ),
}
EXPECTED_TASKS = 34
EXPECTED_CAPTURES = 3
EXPECTED_REQUESTS = EXPECTED_TASKS * EXPECTED_CAPTURES
MIN_ACTIVATED_TASKS = 9


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid {name}")
    return value


def _stable_version(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("missing served version")
    return {
        key: item
        for key, item in value.items()
        if key not in {"variant", "compiled_kinds", "drop_compiler_fallback"}
    }


def _cells(value: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    rows = value.get("rows")
    if not isinstance(rows, list):
        raise TypeError(f"missing replay rows for {value.get('variant')}")
    cells = {
        (str(row.get("task_id")), int(row.get("capture", -1))): row
        for row in rows
        if isinstance(row, dict)
    }
    if len(cells) != len(rows) or len(cells) != EXPECTED_REQUESTS:
        raise ValueError(f"missing or duplicate retrieval cells for {value.get('variant')}")
    return cells


def _validate_admission(admission: dict[str, Any]) -> None:
    if admission.get("schema_version") != 1:
        raise ValueError("unsupported compiler admission selection schema")
    if admission.get("selected_compiler") != "V2_anchor_raw":
        raise ValueError("anchor compiler v2 was not selected")
    if admission.get("admission_pass") is not True:
        raise ValueError("anchor compiler v2 admission did not pass")
    if admission.get("authorize_m2_m3_retrieval") is not True:
        raise ValueError("compiler admission did not authorize M2 and M3 retrieval")


def _validate_artifact(value: dict[str, Any], variant: str) -> None:
    if value.get("schema_version") != 5 or value.get("variant") != variant:
        raise ValueError(f"artifact identity drift for {variant}")
    for key, expected in (
        ("task_count", EXPECTED_TASKS),
        ("capture_count", EXPECTED_CAPTURES),
        ("request_count", EXPECTED_REQUESTS),
    ):
        if value.get(key) != expected:
            raise ValueError(f"{key} drift for {variant}")
    if value.get("dense_embedding_pass") is not True:
        raise ValueError(f"{variant} did not own its dense embedding pass")
    if value.get("corpus_reused") is not False:
        raise ValueError(f"{variant} unexpectedly reused a candidate corpus")

    expected_kinds = sorted(VIEW_KINDS[variant])
    version = value.get("version")
    if not isinstance(version, dict):
        raise TypeError(f"missing served version for {variant}")
    if version.get("variant") != variant:
        raise ValueError(f"served variant drift for {variant}")
    if version.get("compiled_kinds") != expected_kinds:
        raise ValueError(f"compiled kind policy drift for {variant}")
    expected_drop_fallback = variant != "M0_multiview_raw"
    if version.get("drop_compiler_fallback") is not expected_drop_fallback:
        raise ValueError(f"fallback storage policy drift for {variant}")

    status = value.get("corpus_status")
    if not isinstance(status, dict) or status.get("status") != "ready":
        raise ValueError(f"missing ready corpus status for {variant}")
    raw_count = _count(status.get("raw_chunk_count"), f"raw chunk count for {variant}")
    compiled_count = _count(
        status.get("compiled_chunk_count"), f"compiled chunk count for {variant}"
    )
    chunk_count = _count(status.get("chunk_count"), f"chunk count for {variant}")
    if raw_count <= 0 or chunk_count != raw_count + compiled_count:
        raise ValueError(f"stored corpus counters drifted for {variant}")
    kind_counts = status.get("compiled_kind_counts")
    profile_counts = status.get("compiler_profile_counts")
    if not isinstance(kind_counts, dict) or not isinstance(profile_counts, dict):
        raise TypeError(f"missing compiler corpus counters for {variant}")
    if sum(_count(count, f"kind count for {variant}") for count in kind_counts.values()) != (
        compiled_count
    ):
        raise ValueError(f"compiled kind counters drifted for {variant}")
    if (
        sum(
            _count(count, f"compiler profile count for {variant}")
            for count in profile_counts.values()
        )
        != compiled_count
    ):
        raise ValueError(f"compiler profile counters drifted for {variant}")
    if variant == "M0_multiview_raw":
        if compiled_count != 0 or kind_counts or profile_counts:
            raise ValueError("M0 contains compiled records")
    else:
        if compiled_count <= 0:
            raise ValueError(f"{variant} contains no compiled records")
        if not set(kind_counts) <= VIEW_KINDS[variant]:
            raise ValueError(f"cross-view compiled records found in {variant}")
        if set(profile_counts) != {"anchor-v2"}:
            raise ValueError(f"non-anchor compiler records found in {variant}")

    for row in _cells(value).values():
        items = row.get("items")
        if not isinstance(items, list):
            raise TypeError(f"missing returned items for {variant}")
        allowed = {"raw"} | VIEW_KINDS[variant]
        if any(not isinstance(item, dict) or item.get("kind") not in allowed for item in items):
            raise ValueError(f"cross-view Search item found in {variant}")


def _activated_tasks(value: dict[str, Any], variant: str) -> list[str]:
    allowed = VIEW_KINDS[variant]
    by_task: dict[str, list[dict[str, Any]]] = {}
    for (task_id, _), row in _cells(value).items():
        by_task.setdefault(task_id, []).append(row)
    return sorted(
        task_id
        for task_id, rows in by_task.items()
        if len(rows) == EXPECTED_CAPTURES
        and all(any(item.get("kind") in allowed for item in row["items"][:10]) for row in rows)
    )


def _retrieval_gates(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, bool]:
    base = baseline["aggregate"]
    view = candidate["aggregate"]
    return {
        "mrr_nondecline": view["mean_reciprocal_rank"] >= base["mean_reciprocal_rank"],
        "coverage_10_nondecline": (
            view["complete_coverage_at_10"] >= base["complete_coverage_at_10"]
        ),
        "coverage_100_nondecline": (
            view["complete_coverage_at_100"] >= base["complete_coverage_at_100"]
        ),
        "source_session_recall_nondecline": (
            view["mean_source_session_recall"] >= base["mean_source_session_recall"]
        ),
        "strict_rank_gain": (
            view["mean_reciprocal_rank"] > base["mean_reciprocal_rank"]
            or view["complete_coverage_at_10"] > base["complete_coverage_at_10"]
        ),
        "returned_characters_below_1_25x": (
            view["mean_character_count"] <= 1.25 * base["mean_character_count"]
        ),
        "search_p95_below_1000_ms": view["search_p95_ms"] < 1_000,
        "search_p95_below_2x_baseline": (view["search_p95_ms"] < 2 * base["search_p95_ms"]),
    }


def select_multiview(
    artifacts: dict[str, dict[str, Any]], admission: dict[str, Any]
) -> dict[str, Any]:
    """Select independent view candidates without authorizing executable cells."""
    _validate_admission(admission)
    if set(artifacts) != set(VARIANTS):
        raise ValueError("selection requires exactly the M0, M2, and M3 retrieval artifacts")
    for variant in VARIANTS:
        _validate_artifact(artifacts[variant], variant)

    baseline = artifacts["M0_multiview_raw"]
    stable_version = _stable_version(baseline.get("version"))
    invariant_keys = (
        "namespace",
        "corpus_manifest_sha256",
        "task_set_sha256",
        "sessions_offered",
        "messages_offered",
        "add_request_count",
        "task_count",
        "capture_count",
        "request_count",
        "http_timeout_seconds",
    )
    baseline_cells = _cells(baseline)
    raw_hash = baseline["corpus_status"].get("raw_corpus_sha256")
    if not isinstance(raw_hash, str) or len(raw_hash) != 64:
        raise ValueError("missing raw corpus identity")
    for variant in VARIANTS[1:]:
        candidate = artifacts[variant]
        if any(candidate.get(key) != baseline.get(key) for key in invariant_keys):
            raise ValueError(f"replay population drift for {variant}")
        if _stable_version(candidate.get("version")) != stable_version:
            raise ValueError(f"served product identity drift for {variant}")
        if candidate["corpus_status"].get("raw_corpus_sha256") != raw_hash:
            raise ValueError(f"raw corpus identity drift for {variant}")
        candidate_cells = _cells(candidate)
        if set(candidate_cells) != set(baseline_cells):
            raise ValueError(f"paired retrieval cells drifted for {variant}")
        for cell, row in candidate_cells.items():
            reference = baseline_cells[cell]
            if any(
                row.get(key) != reference.get(key)
                for key in ("kind", "query_sha256", "fact_terms_sha256")
            ):
                raise ValueError(f"retrieval identity drift for {variant} at {cell}")

    results: dict[str, Any] = {}
    preregistration_candidates: list[str] = []
    for variant in VARIANTS[1:]:
        candidate = artifacts[variant]
        activated = _activated_tasks(candidate, variant)
        fallback_count = _count(
            candidate["aggregate"].get("compiler_fallbacks"),
            f"compiler fallback count for {variant}",
        )
        mechanism = {
            "compiler_admission_dependency": True,
            "raw_projection_identical": (
                candidate["corpus_status"]["raw_corpus_sha256"] == raw_hash
            ),
            "anchor_v2_records_only": (
                set(candidate["corpus_status"]["compiler_profile_counts"]) == {"anchor-v2"}
            ),
            "view_kinds_isolated": (
                set(candidate["corpus_status"]["compiled_kind_counts"]) <= VIEW_KINDS[variant]
            ),
            "fallback_below_10_percent": (fallback_count / candidate["sessions_offered"] < 0.10),
            "activates_at_least_9_tasks": len(activated) >= MIN_ACTIVATED_TASKS,
        }
        retrieval = _retrieval_gates(baseline, candidate)
        passed = all(mechanism.values()) and all(retrieval.values())
        if passed:
            preregistration_candidates.append(variant)
        results[variant] = {
            "retrieval_pass": passed,
            "mechanism_gates": mechanism,
            "retrieval_gates": retrieval,
            "activated_tasks": activated,
            "activated_task_count": len(activated),
            "compiler_fallback_count": fallback_count,
            "aggregate": candidate["aggregate"],
        }

    return {
        "schema_version": 1,
        "baseline": "M0_multiview_raw",
        "retrieval_preregistration_candidates": preregistration_candidates,
        "authorize_executable_run": False,
        "dense_embedding_passes": 3,
        "lineage": {
            "namespace": baseline["namespace"],
            "raw_corpus_sha256": raw_hash,
            "compiler_admission_selected": admission["selected_compiler"],
        },
        "baseline_aggregate": baseline["aggregate"],
        "candidates": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--admission-selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    paths = {variant: args.artifacts_root / f"present-{variant}.json" for variant in VARIANTS}
    selected = select_multiview(
        {variant: _json(path) for variant, path in paths.items()},
        _json(args.admission_selection),
    )
    selected["input_sha256"] = {
        **{variant: _sha256(path) for variant, path in paths.items()},
        "admission_selection": _sha256(args.admission_selection),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
