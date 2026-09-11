"""Validate the seven hosted replay artifacts and select the registered A4 candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.recall_hosted_replay import REGISTERED_VARIANTS

A4_BUDGETS = {
    "A4_pack_5000": 5_000,
    "A4_pack_7000": 7_000,
    "A4_pack_9000": 9_000,
}
VERSION_VARIANT_KEY = "variant"


def _identity_without_variant(version: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in version.items() if key != VERSION_VARIANT_KEY}


def select_replay(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant = {str(artifact.get("variant")): artifact for artifact in artifacts}
    if set(by_variant) != set(REGISTERED_VARIANTS) or len(artifacts) != len(REGISTERED_VARIANTS):
        raise ValueError("selection requires exactly one artifact for every registered variant")

    ordered = [by_variant[name] for name in REGISTERED_VARIANTS]
    reference = ordered[0]
    invariant_keys = (
        "corpus_manifest_sha256",
        "task_set_sha256",
        "task_count",
        "sessions_offered",
        "messages_offered",
    )
    for artifact in ordered:
        if artifact.get("schema_version") != 1:
            raise ValueError(f"unsupported replay schema for {artifact.get('variant')}")
        if any(artifact.get(key) != reference.get(key) for key in invariant_keys):
            raise ValueError(f"replay population drift for {artifact.get('variant')}")
        version = artifact.get("version")
        if not isinstance(version, dict) or version.get("variant") != artifact.get("variant"):
            raise ValueError(f"served version mismatch for {artifact.get('variant')}")
        if _identity_without_variant(version) != _identity_without_variant(reference["version"]):
            raise ValueError(f"served product identity drift for {artifact.get('variant')}")
        aggregate = artifact.get("aggregate")
        if not isinstance(aggregate, dict):
            raise TypeError(f"missing aggregate for {artifact.get('variant')}")
        for key in ("compiler_fallbacks", "facet_fallbacks", "reranker_fallbacks"):
            if not isinstance(aggregate.get(key), int) or aggregate[key] < 0:
                raise ValueError(f"invalid {key} for {artifact.get('variant')}")

    coverage = {
        name: float(by_variant[name]["aggregate"]["complete_coverage"])
        for name in A4_BUDGETS
    }
    if any(value < 0 or value > 1 for value in coverage.values()):
        raise ValueError("complete coverage must be a proportion")
    threshold = max(coverage.values()) - 0.01
    candidate = min(
        (name for name, value in coverage.items() if value >= threshold),
        key=A4_BUDGETS.__getitem__,
    )
    summary = {
        name: {
            "complete_coverage": float(artifact["aggregate"]["complete_coverage"]),
            "hit_at_1": float(artifact["aggregate"]["hit_at_1"]),
            "mean_reciprocal_rank": float(artifact["aggregate"]["mean_reciprocal_rank"]),
            "mean_character_count": float(artifact["aggregate"]["mean_character_count"]),
            "add_p95_ms": artifact["aggregate"]["add_p95_ms"],
            "search_p95_ms": artifact["aggregate"]["search_p95_ms"],
            "compiler_fallbacks": artifact["aggregate"]["compiler_fallbacks"],
            "facet_fallbacks": artifact["aggregate"]["facet_fallbacks"],
            "reranker_fallbacks": artifact["aggregate"]["reranker_fallbacks"],
        }
        for name, artifact in zip(REGISTERED_VARIANTS, ordered, strict=True)
    }
    return {
        "schema_version": 1,
        "baseline": "A0_raw",
        "candidate": candidate,
        "candidate_context_chars": A4_BUDGETS[candidate],
        "a4_best_complete_coverage": max(coverage.values()),
        "a4_eligibility_threshold": threshold,
        "corpus_manifest_sha256": reference["corpus_manifest_sha256"],
        "task_set_sha256": reference["task_set_sha256"],
        "task_count": reference["task_count"],
        "served_product_identity": _identity_without_variant(reference["version"]),
        "variants": summary,
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
        for name in REGISTERED_VARIANTS
    ]
    selected = select_replay(artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
