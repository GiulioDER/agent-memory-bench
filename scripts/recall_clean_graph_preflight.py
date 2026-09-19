"""Freeze graph eligibility before preregistration 089 spends task cells."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from adapters.recall_hosted.adapter import HostedHttpClient
from harness.adapters.base import CorpusManifest, resolve_corpus_path

ELIGIBLE = frozenset({"supports", "references", "depends_on", "caused", "supersedes"})


def _relations(value: Any) -> tuple[int, int]:
    authored = 0
    eligible = 0
    if isinstance(value, dict):
        graph = value.get("recall_graph")
        if isinstance(graph, dict):
            declared = graph.get("relations", [])
            if isinstance(declared, list):
                for relation in declared:
                    if isinstance(relation, dict):
                        authored += 1
                        eligible += int(str(relation.get("relation", "")) in ELIGIBLE)
            dependencies = graph.get("depends_on", [])
            if isinstance(dependencies, list):
                authored += len(dependencies)
                eligible += len(dependencies)
        for nested in value.values():
            nested_authored, nested_eligible = _relations(nested)
            authored += nested_authored
            eligible += nested_eligible
    elif isinstance(value, list):
        for nested in value:
            nested_authored, nested_eligible = _relations(nested)
            authored += nested_authored
            eligible += nested_eligible
    return authored, eligible


def inspect_corpus(corpus: CorpusManifest) -> dict[str, Any]:
    corpus.verify()
    authored = 0
    eligible = 0
    for relative in sorted(corpus.sessions):
        for line in (
            resolve_corpus_path(corpus.root, relative).read_text(encoding="utf-8").splitlines()
        ):
            if not line.strip():
                continue
            found_authored, found_eligible = _relations(json.loads(line))
            authored += found_authored
            eligible += found_eligible
    return {
        "manifest_sha256": hashlib.sha256(
            (corpus.root / "manifest.json").read_bytes()
        ).hexdigest(),
        "session_count": len(corpus.sessions),
        "authored_relation_count": authored,
        "eligible_relation_count": eligible,
    }


def preflight(corpus: dict[str, Any], served: dict[str, Any]) -> dict[str, Any]:
    counts = (
        int(corpus["authored_relation_count"]),
        int(corpus["eligible_relation_count"]),
        int(served["authored_relation_count"]),
        int(served["eligible_relation_count"]),
        int(served["store_relation_count"]),
    )
    zero = any(count == 0 for count in counts)
    return {
        "schema_version": 1,
        "verdict": "ineligible_zero_relations" if zero else "pause_nonzero_relations",
        "graph_added_to_matrix": False,
        "corpus": corpus,
        "served": served,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite graph preflight: {args.output}")
    api_key = os.environ.get("AMB_RECALL_HOSTED_API_KEY", "")
    if not api_key:
        raise SystemExit("AMB_RECALL_HOSTED_API_KEY is required")
    client = HostedHttpClient(args.base_url, api_key, timeout=60)
    result = preflight(
        inspect_corpus(CorpusManifest.load(args.corpus)),
        client.request("/v1/corpus/status", {"user_id": args.namespace}),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["verdict"] != "ineligible_zero_relations":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
