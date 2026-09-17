"""Validate E0/E1/E2 replay artifacts and select the engineering experience representation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.recall_hosted_replay import EXPERIENCE_VARIANTS
from scripts.recall_hosted_select import _identity_without_variant


def _rows_by_task(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = artifact.get("rows")
    if not isinstance(rows, list):
        raise TypeError(f"missing replay rows for {artifact.get('variant')}")
    by_task = {str(row.get("task_id")): row for row in rows if isinstance(row, dict)}
    if len(by_task) != len(rows):
        raise ValueError(f"duplicate or malformed replay rows for {artifact.get('variant')}")
    return by_task


def _complete_at_10(row: dict[str, Any]) -> bool:
    metrics = row.get("metrics")
    if not isinstance(metrics, dict) or not isinstance(metrics.get("complete_coverage_at_10"), bool):
        raise TypeError("every replay row needs boolean complete_coverage_at_10")
    return metrics["complete_coverage_at_10"]


def select_experience(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the preregistered representation gates without inspecting task answers."""
    by_variant = {str(artifact.get("variant")): artifact for artifact in artifacts}
    if set(by_variant) != set(EXPERIENCE_VARIANTS) or len(artifacts) != len(EXPERIENCE_VARIANTS):
        raise ValueError("selection requires exactly one E0, E1, and E2 artifact")

    ordered = [by_variant[name] for name in EXPERIENCE_VARIANTS]
    reference = ordered[0]
    invariant_keys = (
        "corpus_manifest_sha256",
        "task_set_sha256",
        "task_count",
        "sessions_offered",
        "messages_offered",
    )
    reference_rows = _rows_by_task(reference)
    for artifact in ordered:
        name = str(artifact["variant"])
        if artifact.get("schema_version") != 1:
            raise ValueError(f"unsupported replay schema for {name}")
        if any(artifact.get(key) != reference.get(key) for key in invariant_keys):
            raise ValueError(f"replay population drift for {name}")
        version = artifact.get("version")
        if not isinstance(version, dict) or version.get("variant") != name:
            raise ValueError(f"served version mismatch for {name}")
        if _identity_without_variant(version) != _identity_without_variant(reference["version"]):
            raise ValueError(f"served product identity drift for {name}")
        rows = _rows_by_task(artifact)
        if set(rows) != set(reference_rows):
            raise ValueError(f"task row drift for {name}")
        for task_id, row in rows.items():
            baseline = reference_rows[task_id]
            if any(
                row.get(key) != baseline.get(key)
                for key in ("kind", "query_sha256", "fact_terms_sha256")
            ):
                raise ValueError(f"task identity drift for {name}:{task_id}")
            _complete_at_10(row)
        aggregate = artifact.get("aggregate")
        if not isinstance(aggregate, dict):
            raise TypeError(f"missing aggregate for {name}")
        for key in ("complete_coverage_at_10", "mean_reciprocal_rank"):
            value = aggregate.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"invalid {key} for {name}")

    e0 = by_variant["E0_raw"]
    e1 = by_variant["E1_compiled"]
    e2 = by_variant["E2_compiled_raw"]
    e0_aggregate = e0["aggregate"]
    e1_aggregate = e1["aggregate"]
    e2_aggregate = e2["aggregate"]
    e1_pass = (
        e1_aggregate["complete_coverage_at_10"]
        >= e0_aggregate["complete_coverage_at_10"] - 0.01
        and e1_aggregate["mean_reciprocal_rank"] > e0_aggregate["mean_reciprocal_rank"]
    )

    e0_rows = _rows_by_task(e0)
    e1_rows = _rows_by_task(e1)
    e2_rows = _rows_by_task(e2)
    lost_by_e1 = [
        task_id
        for task_id in e0_rows
        if _complete_at_10(e0_rows[task_id]) and not _complete_at_10(e1_rows[task_id])
    ]
    recovered_by_e2 = [task_id for task_id in lost_by_e1 if _complete_at_10(e2_rows[task_id])]
    recovery_rate = None if not lost_by_e1 else len(recovered_by_e2) / len(lost_by_e1)
    e2_coverage_improved = (
        e2_aggregate["complete_coverage_at_10"]
        > e0_aggregate["complete_coverage_at_10"]
    )
    e2_pass = (
        (e2_coverage_improved or (recovery_rate is not None and recovery_rate >= 0.5))
        and e2_aggregate["mean_reciprocal_rank"] >= e0_aggregate["mean_reciprocal_rank"]
    )
    candidate = "E2_compiled_raw" if e2_pass else "E1_compiled" if e1_pass else "E0_raw"

    return {
        "schema_version": 1,
        "baseline": "E0_raw",
        "candidate": candidate,
        "e1_pass": e1_pass,
        "e2_pass": e2_pass,
        "e1_lost_task_count": len(lost_by_e1),
        "e2_recovered_task_count": len(recovered_by_e2),
        "e2_recovery_rate": recovery_rate,
        "corpus_manifest_sha256": reference["corpus_manifest_sha256"],
        "task_set_sha256": reference["task_set_sha256"],
        "task_count": reference["task_count"],
        "served_product_identity": _identity_without_variant(reference["version"]),
        "variants": {
            name: {
                "complete_coverage_at_10": float(
                    by_variant[name]["aggregate"]["complete_coverage_at_10"]
                ),
                "mean_reciprocal_rank": float(
                    by_variant[name]["aggregate"]["mean_reciprocal_rank"]
                ),
                "mean_character_count": float(
                    by_variant[name]["aggregate"]["mean_character_count"]
                ),
                "add_p95_ms": by_variant[name]["aggregate"]["add_p95_ms"],
                "search_p95_ms": by_variant[name]["aggregate"]["search_p95_ms"],
                "compiler_fallbacks": by_variant[name]["aggregate"]["compiler_fallbacks"],
            }
            for name in EXPERIENCE_VARIANTS
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    artifacts = [
        json.loads((args.input_dir / f"{name}.json").read_text(encoding="utf-8"))
        for name in EXPERIENCE_VARIANTS
    ]
    selected = select_experience(artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
