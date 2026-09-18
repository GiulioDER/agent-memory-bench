"""Validate C0 through C4 replay artifacts and apply the preregistered retrieval gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.recall_hosted_replay import (
    CODING_MATRIX_VARIANTS,
    SPARSE_BACKFILL_HTTP_TIMEOUT_SECONDS,
)
from scripts.recall_hosted_select import _identity_without_variant


def _number(aggregate: dict[str, Any], key: str) -> float:
    value = aggregate.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"invalid {key}")
    return float(value)


def _rows_by_task(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = artifact.get("rows")
    if not isinstance(rows, list):
        raise TypeError(f"missing replay rows for {artifact.get('variant')}")
    by_task = {str(row.get("task_id")): row for row in rows if isinstance(row, dict)}
    if len(by_task) != len(rows):
        raise ValueError(f"duplicate or malformed replay rows for {artifact.get('variant')}")
    return by_task


def _identity_without_variant_or_commit(version: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in version.items()
        if key not in {"variant", "git_commit"}
    }


def select_coding_matrix(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant = {str(artifact.get("variant")): artifact for artifact in artifacts}
    if set(by_variant) != set(CODING_MATRIX_VARIANTS) or len(artifacts) != len(
        CODING_MATRIX_VARIANTS
    ):
        raise ValueError("selection requires exactly one C0 through C4 artifact")

    ordered = [by_variant[name] for name in CODING_MATRIX_VARIANTS]
    expected_cache = {
        "C0_raw_lexical": (False, True),
        "C1_splade": (True, False),
        "C2_procedure": (False, True),
        "C3_rerank": (True, False),
        "C4_task_pack": (True, False),
    }
    expected_backfill_timeout = {
        name: (
            SPARSE_BACKFILL_HTTP_TIMEOUT_SECONDS
            if expected_cache[name][0]
            else None
        )
        for name in CODING_MATRIX_VARIANTS
    }
    reference = ordered[0]
    repair_reference = by_variant["C2_procedure"]
    reference_rows = _rows_by_task(reference)
    invariant_keys = (
        "corpus_manifest_sha256",
        "task_set_sha256",
        "task_count",
        "sessions_offered",
        "messages_offered",
        "http_timeout_seconds",
    )
    reference_version = reference.get("version")
    repair_version = repair_reference.get("version")
    if not isinstance(reference_version, dict) or not isinstance(repair_version, dict):
        raise TypeError("missing served product identity")
    if reference_version.get("git_commit") == repair_version.get("git_commit"):
        raise ValueError("the amended retrieval requires a distinct repair commit identity")
    if _identity_without_variant_or_commit(
        reference_version
    ) != _identity_without_variant_or_commit(repair_version):
        raise ValueError("served product identity drift beyond the registered repair commit")
    for artifact in ordered:
        name = str(artifact["variant"])
        if artifact.get("schema_version") != 1:
            raise ValueError(f"unsupported replay schema for {name}")
        if (
            artifact.get("corpus_reused"),
            artifact.get("dense_embedding_pass"),
        ) != expected_cache[name]:
            raise ValueError(f"invalid corpus cache lineage for {name}")
        if artifact.get("sparse_backfill_timeout_seconds") != expected_backfill_timeout[name]:
            raise ValueError(f"invalid sparse backfill timeout identity for {name}")
        if bool(artifact.get("ingest_resumed", False)) != (name == "C2_procedure"):
            raise ValueError(f"invalid ingest resume lineage for {name}")
        if any(artifact.get(key) != reference.get(key) for key in invariant_keys):
            raise ValueError(f"replay population drift for {name}")
        version = artifact.get("version")
        if not isinstance(version, dict) or version.get("variant") != name:
            raise ValueError(f"served version mismatch for {name}")
        identity_reference = (
            reference_version
            if name in {"C0_raw_lexical", "C1_splade"}
            else repair_version
        )
        if _identity_without_variant(version) != _identity_without_variant(identity_reference):
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
            if row.get("task_type") not in {"feature", "bugfix", "unknown"}:
                raise ValueError(f"invalid task routing class for {name}:{task_id}")
        aggregate = artifact.get("aggregate")
        if not isinstance(aggregate, dict):
            raise TypeError(f"missing aggregate for {name}")
        for key in (
            "complete_coverage_at_10",
            "complete_coverage_at_100",
            "complete_coverage",
            "mean_reciprocal_rank",
            "mean_character_count",
            "search_p95_ms",
        ):
            _number(aggregate, key)
        if aggregate.get("sparse_failures") != 0:
            raise ValueError(f"learned sparse failure recorded for {name}")

    c0 = by_variant["C0_raw_lexical"]["aggregate"]
    c1 = by_variant["C1_splade"]["aggregate"]
    c2 = by_variant["C2_procedure"]["aggregate"]
    c3 = by_variant["C3_rerank"]["aggregate"]
    c4 = by_variant["C4_task_pack"]["aggregate"]
    deltas = {
        "c1_complete_at_10": _number(c1, "complete_coverage_at_10")
        - _number(c0, "complete_coverage_at_10"),
        "c2_mrr": _number(c2, "mean_reciprocal_rank")
        - _number(c1, "mean_reciprocal_rank"),
        "c3_mrr": _number(c3, "mean_reciprocal_rank")
        - _number(c2, "mean_reciprocal_rank"),
        "c3_complete_at_100_loss": _number(c2, "complete_coverage_at_100")
        - _number(c3, "complete_coverage_at_100"),
        "c4_complete_returned_loss": _number(c3, "complete_coverage")
        - _number(c4, "complete_coverage"),
        "c4_character_reduction": (
            0.0
            if _number(c3, "mean_character_count") == 0
            else 1.0
            - _number(c4, "mean_character_count") / _number(c3, "mean_character_count")
        ),
    }
    gates = {
        "C1_splade": (
            deltas["c1_complete_at_10"] >= 0.02
            and _number(c1, "search_p95_ms") < 3 * _number(c0, "search_p95_ms")
        ),
        "C2_procedure": deltas["c2_mrr"] >= 0.02,
        "C3_rerank": (
            deltas["c3_mrr"] >= 0.03
            and deltas["c3_complete_at_100_loss"] <= 0.01
        ),
        "C4_task_pack": (
            deltas["c4_complete_returned_loss"] <= 0.01
            and deltas["c4_character_reduction"] >= 0.30
        ),
    }
    deepest = "C0_raw_lexical"
    for name in CODING_MATRIX_VARIANTS[1:]:
        if not gates[name]:
            break
        deepest = name

    return {
        "schema_version": 1,
        "baseline": "C0_raw_lexical",
        "deepest_retrieval_eligible": deepest,
        "gates": gates,
        "deltas": deltas,
        "corpus_manifest_sha256": reference["corpus_manifest_sha256"],
        "task_set_sha256": reference["task_set_sha256"],
        "task_count": reference["task_count"],
        "served_product_identity": _identity_without_variant(reference["version"]),
        "served_product_repair_identity": _identity_without_variant(repair_version),
        "variants": {
            name: {
                key: by_variant[name]["aggregate"][key]
                for key in (
                    "complete_coverage_at_10",
                    "complete_coverage_at_100",
                    "complete_coverage",
                    "mean_reciprocal_rank",
                    "mean_character_count",
                    "search_p95_ms",
                )
            }
            for name in CODING_MATRIX_VARIANTS
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
        for name in CODING_MATRIX_VARIANTS
    ]
    selected = select_coding_matrix(artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
